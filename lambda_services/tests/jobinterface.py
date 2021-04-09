# coding: utf-8

"""
The JobInterface is the set of properties and functions that must
be implemented for an APBS, PDB2PQR, and a combined APBS/PDB2PQR job.
"""

from pathlib import Path
from os.path import isdir, isfile
from typing import List

from utiljob import get_contents


class JobInterface:
    def __init__(self, jobid: str, file_path: str, file_list: List = []):
        """The job consists of input and output files from an APBS job

        Args:
            jobid (str): The unique string for an Azure blog or AWS bucket
            file_path (str): The absolute path to the mounted directory
            file_list (List, optional): The list of files for the job

        Raises:
            TypeError: The file_path is not a directory
        """
        self.job_id = jobid
        self.file_path = None
        self.file_list = {}
        self.job_input_files = []

        if not isdir(file_path):
            raise TypeError(
                "Expected file path to be a directory: %s", type(file_path)
            )

        self.file_path = Path(file_path)
        for filename in file_list:
            self._LOGGER.info("FILENAME: %s", filename)
            full_filename = self.file_path / filename
            if isfile(full_filename):
                self.file_list[filename] = full_filename
                if filename.endswith("input_files"):
                    for check_file in get_contents(full_filename):
                        base_filename = check_file.split("/")[-1]
                        self.job_input_files.append(base_filename)

    def __str__(self):
        return (
            f"JOB:\n"
            f"  Id:          {self.job_id}\n"
            f"  Type:        {self.job_type}\n"
            f"  Input Files: {self.job_input_files}"
        )

    @property
    def job_id(self):
        return self._job_id

    @job_id.setter
    def job_id(self, job_id):
        self._job_id = job_id

    @property
    def job_input_files(self):
        return self._job_input_files

    @job_input_files.setter
    def job_input_files(self, job_input_files):
        self._job_input_files = job_input_files

    @property
    def job_type(self):
        return self._job_type

    @job_type.setter
    def job_type(self, job_type):
        self._job_type = job_type

    @property
    def file_list(self):
        return self._file_list

    @file_list.setter
    def file_list(self, file_list):
        self._file_list = file_list

    def build_job_file(self):
        pass

    def get_execution_time(self):
        """
        Subtract "{job_type}_start_time from "{job_type}_end_time to get
        number of seconds
        """
        starttime = get_contents(
            self.file_list[f"{self.job_type}_start_time"]
        )[0]
        endtime = get_contents(self.file_list[f"{self.job_type}_end_time"])[0]
        return int(float(endtime) - float(starttime))

    def get_memory_usage(self):
        pass

    def get_storage_usage(self):
        return sum(
            f.stat().st_size
            for f in self.file_path.glob("**/*")
            if f.is_file()
        )
