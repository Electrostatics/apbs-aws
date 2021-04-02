# coding: utf-8

# NOTE: Based on code from https://github.com/Azure/azure-sdk-for-python/blob/
#       master/sdk/storage/azure-storage-blob/samples

"""AzureClient is used to connect to Azure BLOB storage."""

"""
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
from os import makedirs, path as ospath
import time
from azure.storage.blob import BlobServiceClient


class AzureClient:
    def __init__(self, connection_string, container_name, download_root=None):
        service_client = BlobServiceClient.from_connection_string(
            connection_string
        )
        self.client = service_client.get_container_client(container_name)
        self.download_root = download_root
        if download_root and not download_root.endswith("/"):
            self.download_root += "/"
            makedirs(self.download_root, exist_ok=True)

    def upload(self, source, dest):
        """
        Upload a file or directory to a path inside the container
        """
        if ospath.isdir(source):
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
            dest += ospath.basename(ospath.normpath(source)) + "/"

            blobs = [source + blob for blob in blobs]
            for blob in blobs:
                blob_dest = dest + ospath.relpath(blob, source)
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
            blob_dest = dest + ospath.basename(source)

        print(f"    Downloading {source} to {blob_dest}")
        makedirs(ospath.dirname(blob_dest), exist_ok=True)
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
            relative_path = ospath.relpath(blob.name, path)
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
            relative_dir = ospath.dirname(path.relpath(blob.name, path))
            if (
                relative_dir
                and (recursive or "/" not in relative_dir)
                and relative_dir not in dirs
            ):
                dirs.append(relative_dir)

        return dirs