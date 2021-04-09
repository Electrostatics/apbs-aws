# coding: utf-8

from jobinterface import JobInterface
from json import dumps
from logging import getLogger, ERROR, INFO
from pathlib import Path
from typing import List
from utiljob import get_contents
import re

"""ApbsJob is used to hold information about an APBS job."""

"""
DESCRIPTION:
"""


class ApbsJob(JobInterface):
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

        self.job_type = "apbs"
        self._LOGGER = getLogger(__class__.__name__)
        super().__init__(jobid, file_path, file_list)

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
        lines = get_contents(self.file_list[f"{self.job_type}_stdout.txt"])
        for line in lines:
            if line.startswith("Final memory usage"):
                self._LOGGER.debug("MEM LINE: %s", line)
                values = re.findall("\d+\.?\d+", line)
                self._LOGGER.debug("VALUES: %s", values)
                mem_used["total"] = values[0]
                mem_used["high"] = values[1]
        return mem_used

    def build_job_file(self):
        """
        Create an apbs-job.json file to simulate what the Web/Gui/React
        application would create if a user submitted the job.
        """
        job = {
            "form": {
                "job_id": self.job_id,
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
                job["form"]["file_list"].append(filename)

        with open(
            Path(self.file_path) / Path(f"{self.job_type}-job.json"), "w"
        ) as outfile:
            outfile.write(dumps(job, indent=4))
