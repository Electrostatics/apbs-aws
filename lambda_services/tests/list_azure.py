# coding: utf-8

# NOTE: Based on code from https://github.com/Azure/azure-sdk-for-python/blob/
#       master/sdk/storage/azure-storage-blob/samples

# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------

"""
FILE: blob_samples_directory_interface.py
DESCRIPTION:
    This example shows how to perform common filesystem-like operations on a
    container. This includes uploading and downloading files to and from the
    container with an optional prefix, listing files in the container both at
    a single level and recursively, and deleting files in the container either
    individually or recursively.
    To run this sample, provide the name of the storage container to operate on
    as the script argument (e.g. `python3 directory_interface.py my-container`).
    This sample expects that the `AZURE_STORAGE_CONNECTION_STRING` environment
    variable is set. It SHOULD NOT be hardcoded in any code derived from this
    sample.
  USAGE: python blob_samples_directory_interface.py CONTAINER_NAME
    Set the environment variables with your own values before running the sample:
    1) AZURE_STORAGE_CONNECTION_STRING - the connection string to your storage account
"""

from collections import deque
import json
import os
import sys
import time
from azure.storage.blob import BlobServiceClient
import boto3
import requests

sys.path.append("../src/lambda_services/api_service")
from api_service import generate_id_and_tokens


class DirectoryClient:
    def __init__(self, connection_string, container_name, download_root=None):
        service_client = BlobServiceClient.from_connection_string(
            connection_string
        )
        self.client = service_client.get_container_client(container_name)
        self.download_root = download_root
        if download_root and not download_root.endswith("/"):
            self.download_root += "/"
            os.makedirs(self.download_root, exist_ok=True)

    def upload(self, source, dest):
        """
        Upload a file or directory to a path inside the container
        """
        if os.path.isdir(source):
            self.upload_dir(source, dest)
        else:
            self.upload_file(source, dest)

    def upload_file(self, source, dest):
        """
        Upload a single file to a path inside the container
        """
        print(f"Uploading {source} to {dest}")
        with open(source, "rb") as data:
            self.client.upload_blob(name=dest, data=data)

    def download(self, source, dest):
        """
        Download a file or directory to a path on the local filesystem
        """
        if not dest:
            raise Exception("A destination must be provided")

        blobs = self.ls_files(source, recursive=True)
        if blobs:
            # if source is a directory, dest must also be a directory
            if source != "" and not source.endswith("/"):
                source += "/"
            if not dest.endswith("/"):
                dest += "/"
            # append the directory name from source to the destination
            dest += os.path.basename(os.path.normpath(source)) + "/"

            blobs = [source + blob for blob in blobs]
            for blob in blobs:
                blob_dest = dest + os.path.relpath(blob, source)
                self.download_file(blob, blob_dest)
        else:
            self.download_file(source, dest)

    def walk(self, path="/"):
        # walk_blobs(name_starts_with=None, include=None, delimiter='/', **kwargs)
        return self.client.list_blobs(name_starts_with=path)
        # return self.client.walk_blobs(name_starts_with=path)

    def walk2(self, size, batch_size):
        blob_batch = deque()
        start_time = time.time()
        count = 0
        inc = 0
        page = None
        dirs = []
        continuation_token = ""
        while continuation_token is not None:
            print(f"1: {str(time.time() - start_time)}")
            blobs = self.client.walk_blobs(results_per_page=size).by_page(
                continuation_token=continuation_token
            )
            for idx, blob in enumerate(blobs):
                for jdx, dir in enumerate(blob):
                    # print(f"  DIR: {idx} {jdx} {dir.name}")
                    # NOTE: This is the slow part of the code
                    dirs.append(dir.name)
            print(f"2: {str(time.time() - start_time)}")
            try:
                page = next(blobs)
            except StopIteration as sie:
                pass
            print(f"3: {str(time.time() - start_time)}")
            blob_batch.append(page)
            continuation_token = blobs.continuation_token
            print(f"4: {str(time.time() - start_time)}")
            count += size
            inc += 1
            print(f"5: {str(time.time() - start_time)}")
            if not continuation_token or count > batch_size:
                end_time = time.time()
                print(
                    f"Inc = {size}, "
                    f"Total = {batch_size} : {end_time - start_time} "
                    f"seconds ({(end_time - start_time) / inc} second avg loop)"
                )
                break
            print(f"6: {str(time.time() - start_time)}, {str(count)}")
        return dirs

    def download_file(self, source, dest=None):
        """
        Download a single file to a path on the local filesystem
        """
        if dest is None or self.download_root not in dest:
            dest = self.download_root + source

        # dest is a directory if ending with '/' or '.', otherwise it's a file
        if dest.endswith("."):
            dest += "/"

        blob_dest = dest
        if dest.endswith("/"):
            blob_dest = dest + os.path.basename(source)

        print(f"    Downloading {source} to {blob_dest}")
        os.makedirs(os.path.dirname(blob_dest), exist_ok=True)
        bc = self.client.get_blob_client(blob=source)
        with open(blob_dest, "wb") as file:
            data = bc.download_blob()
            file.write(data.readall())
        return blob_dest

    def download_dir(self, path):
        files = []
        for file in self.ls_files(path, recursive=True):
            full_path = f"{path}{file}"
            files.append(self.download_file(full_path))
        return files

    def download_file_in_file(self, path, file_ext):
        files = []
        if not self.exists(path):
            return None

        file_path = self.download_file(path)
        with open(file_path, "r") as fh:
            for line in fh:
                full_path = line.strip("\n")
                if file_ext is None or full_path.endswith(file_ext):
                    # print(f"      DATAFILE: {full_path}")
                    if not self.exists(full_path):
                        full_path = full_path.replace("_", "-")
                        if not self.exists(full_path):
                            raise FileNotFoundError(full_path)
                    file_found = self.download_file(full_path)
                    files.append(file_found)
        return files

    def exists(self, path):
        # print(f"PATH {path}")
        blob_iter = self.client.list_blobs(name_starts_with=path)
        for blob in blob_iter:
            # print(f"BLOBNAME {blob.name}")
            if path in blob.name:
                return True
        return False

    def ls_files(self, path, recursive=False):
        """
        List files under a path, optionally recursively
        """
        if path != "" and not path.endswith("/"):
            path += "/"

        blob_iter = self.client.list_blobs(name_starts_with=path)
        files = []
        for blob in blob_iter:
            relative_path = os.path.relpath(blob.name, path)
            if recursive or "/" not in relative_path:
                files.append(relative_path)
        return files

    def ls_dirs(self, path, recursive=False):
        """
        List directories under a path, optionally recursively
        """
        if path != "" and not path.endswith("/"):
            path += "/"

        blob_iter = self.client.list_blobs(name_starts_with=path)
        dirs = []
        for blob in blob_iter:
            relative_dir = os.path.dirname(os.path.relpath(blob.name, path))
            if (
                relative_dir
                and (recursive or "/" not in relative_dir)
                and relative_dir not in dirs
            ):
                dirs.append(relative_dir)

        return dirs


def delete_job(dir):
    import shutil

    try:
        print(f"  WARNING: Deleting job, {dir}")
        shutil.rmtree(dir)
    except OSError as ose:
        print(f"ERROR: Can't delete job, {dir}, {ose.strerror}")


def get_file(job, client, file, ext):
    files = client.download_file_in_file(f"{job}{file}", ext)
    if files is None:
        print(f"  WARN: File not found: {job}{file}")
    return files


def get_pdb2pqr_flags(pqr_file):
    flags = {}
    try:
        with open(pqr_file, "r") as fh:
            for curline in fh:
                if curline.startswith(
                    "REMARK   1 Command line used to generate this file:"
                ):
                    options = fh.readline().strip("\n")
                    break
    except Exception as ose:
        print(f"ERROR: Can't read file: {pqr_file}")
        return None

    options = options.replace("REMARK   1 ", "")
    options = options.replace("--", "")
    for option in options.split():
        values = option.split("=")
        # Skip the data files file.pqr and file.pdb
        if ".pqr" not in values[0] and ".pdb" not in values[0]:
            flags[values[0]] = True if len(values) == 1 else values[1]
    return flags


def build_apbs_job(job, apbs_files):
    job_file = {
        "form": {
            "job_id": job.strip("/"),
            "invoke_method": "v2",
            "file_list": [],
        }
    }
    # Open up the apbs_input_files to find the files needed
    # to build a apbs-job.json that looks like the following:
    # {
    #   "job_id": "sampleID",
    #   "file_list": [
    #       "apbsinput.in",
    #       "file.pqr"
    #   ],
    # }

    for file in apbs_files:
        filename = file.replace(job, "")
        job_file["form"]["file_list"].append(filename)

    with open(f"{job}apbs-job.json", "w") as outfile:
        outfile.write(json.dumps(job_file, indent=4))


def build_pdb2pqr_job(job, pdb_file, pqr_file):
    job_file = {"form": {"job_id": job.strip("/"), "invoke_method": "v2"}}

    # Open up the pqr file to find the REMARK with command line options
    # to build a pdb2pqr-job.json that looks like the following:
    # {
    #   "form": {
    #      "flags": {
    #         "drop-water": true,
    #         "ff": "parse",
    #         "ph-calc-method": "propka",
    #         "verbose": true,
    #         "with-ph": 7
    #      },
    #      "invoke_method": "v2",
    #      "pdb_name": "1fas.pdb",
    #      "pqr_name": "1fas.pqr"
    #   }
    # }
    job_file["form"]["pdb_name"] = pdb_file[0].replace(job, "")
    job_file["form"]["pqr_name"] = pqr_file[0].replace(job, "")

    # print(f"PREFLAGS: {pqr_file[0]}")
    flags = get_pdb2pqr_flags(pqr_file[0])
    job_file["form"]["flags"] = flags

    with open(f"{job}pdb2pqr-job.json", "w") as outfile:
        outfile.write(json.dumps(job_file, indent=4))


def submit_aws_job(job, data_files):
    job_id = job.strip("/")
    upload_files = []
    job_type = "pdb2pqr"
    for file in data_files:
        data_file = data_files[0].replace(job, "")
        print(f"DATAFILE: {data_file}")
        upload_files.append(data_file)
        if data_file.startswith("apbs"):
            job_type = "apbs"

    # save current directory
    cwd = os.getcwd()
    work_dir = f"{cwd}/{job_id}/"
    os.environ["INPUT_BUCKET"] = "apbs-test-input"

    try:
        os.chdir(work_dir)
        job_request = {
            "job_id": f"{job_id}",
            "bucket_name": f"{job_id}",
            "file_list": [f"{job_type}-job.json"],
        }
        for file in upload_files:
            job_request["file_list"].append(file)
        print(f"REQUEST: {json.dumps(job_request)}")

        response = requests.post(API_TOKEN_URL, json=job_request)

        # NOTE: Must send *-job.json file last because that is what triggers the S3 event
        #       to start the job
        save_url = None
        save_file = None
        json_response = response.json()
        print(f"RESPONSE: {json_response}")
        for file in json_response["urls"]:
            url = json_response["urls"][file]
            # print(f"FILE: {file}, URL: {url}")
            if f"{job_type}-job.json" in file:
                save_url = url
                save_file = file
                continue
            upload = requests.put(url, data=open(file, "rb"))

        # NOTE: Send the "*-job.json" file to start the job
        if save_url is not None and save_file is not None:
            upload = requests.put(save_url, data=open(save_file, "rb"))
        else:
            print(f"ERROR: Can't find JOB file, {job}{job_type}-job.json")
    except:
        print(f"TYPE: {type(job_id)}")
        print(
            f"ERROR: Can't change from {cwd} directory to {work_dir} {sys.exc_info()}"
        )
    finally:
        # print("Restoring the path")
        os.chdir(cwd)


def get_jobs_from_cache(azure_client):
    jobs = []
    cache_file = "AZURE_CACHE.txt"
    if os.path.exists(cache_file) and os.path.isfile(cache_file):
        with open(cache_file, "r") as fh:
            for curline in fh:
                jobs.append(fh.readline().strip("\n"))
    else:
        jobs = azure_client.walk2(5000, 100000)
        with open(cache_file, "w") as outfile:
            for job in jobs:
                print(job, file=outfile)
    return jobs


# MAIN
# Get Azure environment to connect to Azure buckets

try:
    CONNECTION_STRING = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
except KeyError:
    print("AZURE_STORAGE_CONNECTION_STRING must be set")
    sys.exit(1)

try:
    CONTAINER_NAME = sys.argv[1]
except IndexError:
    print("USAGE: script.py CONTAINER_NAME")
    print("ERROR: the following arguments are required: CONTAINER_NAME")
    sys.exit(1)

try:
    API_TOKEN_URL = os.environ["API_TOKEN_URL"]
except KeyError:
    print("AZURE_STORAGE_CONNECTION_STRING must be set")
    sys.exit(1)

# Create a client that is connected to Azure storage container

try:
    azure_client = DirectoryClient(
        CONNECTION_STRING, CONTAINER_NAME, "azure_jobs"
    )

    # TODO: Make this a command line argument
    max_jobs = 100
    jobs = get_jobs_from_cache(azure_client)
    for idx, job in enumerate(jobs, start=1):
        # if idx % 5 != 0:
        #    continue
        # if "000buomdp2" not in job:
        #    continue
        if "00fuze47xm" not in job:
            continue
        print(f"JOB: {job}")
        print(f"STUFF: {azure_client.ls_files(job, recursive=True)}")
        break
        # TODO: Create function to find out if job is PDB2PQR or APBS
        # Should be able to determine job type from files in ls_files()
        # something like:
        # if job_type(job) == "APBS":
        # else:
        pdb_file = get_file(job, azure_client, "pdb2pqr_input_files", ".pdb")
        pqr_file = get_file(job, azure_client, "pdb2pqr_output_files", ".pqr")
        apbs_files = get_file(job, azure_client, "apbs_input_files", None)
        if pdb_file is not None and pqr_file is not None:
            build_pdb2pqr_job(job, pdb_file, pqr_file)
            submit_aws_job(job, pdb_file)
        else:
            if apbs_files is not None:
                build_apbs_job(job, apbs_files)
                submit_aws_job(job, apbs_files)
            else:
                print("============================================")
                print(f"========== TBD: INVALID JOB {job}")
                print("============================================")
                delete_job(job)
        if idx > max_jobs:
            break

except Exception as sysexc:
    print(f"ERROR: Exception, {sysexc}")
    sys.exit(1)