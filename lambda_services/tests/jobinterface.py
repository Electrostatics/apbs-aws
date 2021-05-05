# coding: utf-8

"""
The JobInterface is the set of properties and functions that must
be implemented for an APBS, PDB2PQR, and a combined APBS/PDB2PQR job.
"""

from logging import getLogger
from os.path import isdir, isfile
from pathlib import Path
from typing import List

from utiljob import get_contents


class JobInterface:
    """The abstact interface of a job."""

    def __init__(self, jobid: str, file_path: str, file_list: List):
        """The job consists of input and output files from a job

        Args:
            jobid (str): The unique string for an Azure blog or AWS bucket
            file_path (str): The absolute path to the mounted directory
            file_list (List): The list of files for the job

        Raises:
            TypeError: The file_path is not a directory
        """
        self.job_id = jobid
        self.file_path = None
        self.file_list = {}
        self.job_input_files = []
        self._logger = getLogger(__class__.__name__)

        if not isdir(file_path):
            raise TypeError(
                f"Expected file path to be a directory: {type(file_path)}"
            )

        self.file_path = Path(file_path)
        for filename in file_list:
            self._logger.debug("FILENAME: %s", filename)
            full_filename = self.file_path / filename
            if isfile(full_filename):
                self.file_list[filename] = full_filename
                if filename.endswith("input_files"):
                    for check_file in get_contents(full_filename):
                        base_filename = check_file.split("/")[-1]
                        self.job_input_files.append(base_filename)

    def __str__(self):
        """Generate a human readable version of a job.

        Returns:
            [str]: A string for printing
        """
        return (
            f"Id: {self.job_id}, "
            f"Type: {self.job_type}, "
            f"Input Files: {self.job_input_files}"
        )

    @property
    def job_id(self):
        """The unique id for the job."""
        return self._job_id

    @job_id.setter
    def job_id(self, job_id):
        self._job_id = job_id

    @property
    def job_input_files(self):
        """The list of input files for the job."""
        return self._job_input_files

    @job_input_files.setter
    def job_input_files(self, job_input_files):
        self._job_input_files = job_input_files

    @property
    def job_type(self):
        """The concrete type for the job."""
        return self._job_type

    @job_type.setter
    def job_type(self, job_type):
        self._job_type = job_type

    @property
    def file_list(self):
        """The list of all files related to a job."""
        return self._file_list

    @file_list.setter
    def file_list(self, file_list):
        self._file_list = file_list

    def build_job_file(self):
        """Abstract interface to be overridden by concrete class."""

    def get_memory_usage(self):
        """Abstract interface to be overridden by concrete class."""

    def get_storage_usage(self):
        """Get the total number of bytes of the output files.

        Returns:
            int: The total bytes in all the files in the job directory
        """
        return sum(
            f.stat().st_size
            for f in self.file_path.glob("**/*")
            if f.is_file()
        )
