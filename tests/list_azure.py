# coding: utf-8

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

import os
from collections import deque
import sys
import time
from azure.storage.blob import BlobServiceClient


class DirectoryClient:
    def __init__(self, connection_string, container_name):
        service_client = BlobServiceClient.from_connection_string(
            connection_string
        )
        self.client = service_client.get_container_client(container_name)

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
                    print(f"DIR: {idx} {jdx} {dir.name}")
                    dirs.append(dir.name)
                    # TODO: Remove early exit
                    if idx > 1:
                        return dirs
            print("2: %s" % str(time.time() - start_time))
            try:
                page = next(blobs)
            except StopIteration as sie:
                pass
            print("3: %s" % str(time.time() - start_time))
            blob_batch.append(page)
            continuation_token = blobs.continuation_token
            print("4: %s" % str(time.time() - start_time))
            count += size
            inc += 1
            print("5: %s" % str(time.time() - start_time))
            if not continuation_token or count == batch_size:
                End = time.time()
                print(
                    "Inc = %s, Total = %s : %s seconds ( %s second avg loop) "
                    % (
                        size,
                        batch_size,
                        End - start_time,
                        (End - start_time) / inc,
                    )
                )
                break
            print("6: %s - %s" % (str(time.time() - start_time), str(count)))
        return dirs

    def download_file(self, source, dest):
        """
        Download a single file to a path on the local filesystem
        """
        # dest is a directory if ending with '/' or '.', otherwise it's a file
        if dest.endswith("."):
            dest += "/"
        blob_dest = (
            dest + os.path.basename(source) if dest.endswith("/") else dest
        )

        print(f"Downloading {source} to {blob_dest}")
        os.makedirs(os.path.dirname(blob_dest), exist_ok=True)
        bc = self.client.get_blob_client(blob=source)
        with open(blob_dest, "wb") as file:
            data = bc.download_blob()
            file.write(data.readall())

    def download_dir(self, path):
        for file in self.ls_files(path, recursive=True):
            print(f"FILE: {path}{file}")
            if ".cube" in file or ".gz" in file or ".dx" in file:
                continue
            full_path = f"{path}{file}"
            self.download_file(full_path, full_path)

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


# Sample setup


try:
    CONNECTION_STRING = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
except KeyError:
    print("AZURE_STORAGE_CONNECTION_STRING must be set")
    sys.exit(1)

try:
    CONTAINER_NAME = sys.argv[1]
except IndexError:
    print("usage: directory_interface.py CONTAINER_NAME")
    print("error: the following arguments are required: CONTAINER_NAME")
    sys.exit(1)

# Sample body

client = DirectoryClient(CONNECTION_STRING, CONTAINER_NAME)

# List files in a single directory
# Returns:
# files = client.ls_files("000")
# print(f"FILE: {files}")

# for idx, dir in enumerate(client.walk("01")):
# print(f"DIR: {idx} {dir.name}")
# files = client.ls_files(dir.name, recursive=True)
# for idx2, file in enumerate(files):
#    print(f"    FILE: {idx2} {file}")

# asyncio.run(client.walk2())

dirs = client.walk2(50000, 100000)
for dir in dirs:
    print(f"DIR: {dir}")
    client.download_dir(dir)


# Download a single file to a location on disk, specifying the destination file
# name. When the destination does not end with a slash '/' and is not a relative
# path specifier (e.g. '.', '..', '../..', etc), the destination will be
# interpreted as a full path including the file name. If intermediate
# directories in the destination do not exist they will be created.
#
# After this call, your working directory will look like:
#   downloads/
#     cat-info.txt
# client.download('cat-herding/readme.txt', 'downloads/cat-info.txt')
# import glob
# print(glob.glob('downloads/**', recursive=True))

# Download a single file to a folder on disk, preserving the original file name.
# When the destination ends with a slash '/' or is a relative path specifier
# (e.g. '.', '..', '../..', etc), the destination will be interpreted as a
# directory name and the specified file will be saved within the destination
# directory. If intermediate directories in the destination do not exist they
# will be created.
#
# After this call, your working directory will look like:
#   downloads/
#     cat-info.txt
#     herd-info/
#       herds.txt
# client.download('cat-herding/cats/herds.txt', 'downloads/herd-info/')
# print(glob.glob('downloads/**', recursive=True))

# Download a directory to a folder on disk. The destination is always
# interpreted as a directory name. The directory structure will be preserved
# inside destination folder. If intermediate directories in the destination do
# not exist they will be created.
#
# After this call, your working directory will look like:
#   downloads/
#     cat-data/
#       cats/
#         herds.txt
#         calico/
#          anna.txt
#          felix.txt
#         siamese/
#           mocha.txt
#         tabby/
#           bojangles.txt
#     cat-info.txt
#     herd-info/
#       herds.txt
# client.download('cat-herding/cats', 'downloads/cat-data')
# print(glob.glob('downloads/**', recursive=True))
