# coding: utf-8

from json import dumps
from logging import getLogger, ERROR, INFO
from pathlib import Path
from os.path import isdir, isfile
from typing import List
import re

_LOGGER = getLogger(__name__)

"""ApbsJob is used to hold information about an APBS job."""

"""
DESCRIPTION:
"""


def get_contents(filename):
    lines = []
    _LOGGER.info("GET_CONTENTS: %s", filename)
    if isfile(filename):
        with open(filename, "r") as fh:
            for curline in fh:
                curline = curline.strip("\n")
                if curline:
                    lines.append(curline)
    return lines


class ApbsJob:
    def __init__(self, jobid: str, file_path: str, file_list: List = []):
        """The job consists of input and output files from an APBS job

        Args:
            jobid (str): The unique string for an Azure blog or AWS bucket
            file_path (str): The absolute path to the mounted directory
            file_list (List, optional): The list of files for the job

        Raises:
            TypeError: The file_path is not a directory
        """
        # NOTE: The file list should be something like:
        # apbs_end_time
        # apbs_exec_exit_code.txt
        # apbs_input_files
        # apbs_output_files
        # apbs_start_time
        # apbs_status
        # apbs_stderr.txt
        # apbs_stdout.txt
        # apbsinput.in
        # *.in
        # *.prq

        self._LOGGER = getLogger(__class__.__name__)
        self.jobid = jobid
        self.file_path = None
        self.file_list = {}
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

    def get_execution_time(self):
        """
        Subtract apbs_start_time from apbs_end_time to get number of seconds
        """
        starttime = get_contents(self.file_list["apbs_start_time"])[0]
        endtime = get_contents(self.file_list["apbs_end_time"])[0]
        return int(float(endtime) - float(starttime))

    def get_memory_usage(self):
        """Get the memory used and high water memory that could have been used

        Returns:
            Dict: Total & high memory usage found in apbs_stdout.txt file
        """
        # NOTE: This could be done by looking at the dime values in
        #       the apbsinput.in file and taking the x, y, and z values
        #       and multiplying them times 0.00019073486 and then if
        #       the elec type is mg-auto you could multiply that by 2.
        #
        #       Otherwise, you can parse the "Final memory usage" from
        #       the apbs_stdout.txt file. The line looks like:
        # Final memory usage:  0.001 MB total, 2666.345 MB high water
        mem_used = {"total": None, "high": None}
        lines = get_contents(self.file_list["apbs_stdout.txt"])
        for line in lines:
            if line.startswith("Final memory usage"):
                self._LOGGER.info("MEM LINE: %s", line)
                values = re.findall("\d+\.?\d+", line)
                self._LOGGER.info("VALUES: %s", values)
                mem_used["total"] = values[0]
                mem_used["high"] = values[1]
        return mem_used

    def get_storage_usage(self):
        return sum(
            f.stat().st_size
            for f in self.file_path.glob("**/*")
            if f.is_file()
        )

    def build_apbs_job(self):
        """
        Create an apbs-job.json file to simulate what the Web/Gui/React
        application would create if a user submitted the job.
        """
        job_file = {
            "form": {
                "job_id": self.jobid,
                "invoke_method": "v2",
                "file_list": [],
            }
        }
        # Open up the apbs_input_files to find the files needed
        # to build a apbs-job.json that looks like the following:
        # {
        #   "job_id": "000buomdp2",
        #   "file_list": [
        #       "apbsinput.in",
        #       "000buomdp2.pqr"
        #   ],
        # }

        for filename in self.file_list:
            if filename.endswith(".pqr") or filename in "apbsinput.in":
                job_file["form"]["file_list"].append(filename)

        with open(
            Path(self.file_path) / Path("apbs-job.json"), "w"
        ) as outfile:
            outfile.write(dumps(job_file, indent=4))
