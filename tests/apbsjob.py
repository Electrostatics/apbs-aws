# coding: utf-8
"""ApbsJob is used to hold information about an APBS job."""


from json import dumps
from logging import basicConfig, getLogger, INFO, StreamHandler
from os import getenv
from pathlib import Path
from re import findall
from sys import stdout
from typing import List

from jobinterface import JobInterface
from utiljob import get_contents, LOGGER_FORMAT, JOBTYPE


class ApbsJob(JobInterface):
    """The concrete implementation of an APBS job."""

    def __init__(self, jobid: str, file_path: str, file_list: List):
        """The job consists of input and output files from an APBS job

        Args:
            jobid (str): The unique string for an Azure blog or AWS bucket
            file_path (str): The absolute path to the mounted directory
            file_list (List): The list of files for the job

        Raises:
            TypeError: The file_path is not a directory
        """
        # NOTE: The file list should be something like:
        # apbs_exec_exit_code.txt
        # apbs_input_files
        # apbs_output_files
        # apbs_status
        # apbs_stderr.txt
        # apbs_stdout.txt
        # apbsinput.in
        # *.in
        # *.prq

        self.job_type = JOBTYPE.APBS.name.lower()
        self._logger = getLogger(__class__.__name__)
        basicConfig(
            format=LOGGER_FORMAT,
            level=int(getenv("LOG_LEVEL", str(INFO))),
            handlers=[StreamHandler(stdout)],
        )
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
        if f"{self.job_type}_stdout.txt" in self.file_list:
            lines = get_contents(self.file_list[f"{self.job_type}_stdout.txt"])
            for line in lines:
                if line.startswith("Final memory usage"):
                    self._logger.debug("MEM LINE: %s", line)
                    values = findall(r"\d+\.?\d+", line)  # noqa W605
                    self._logger.debug("VALUES: %s", values)
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
        #   "form" : {
        #     "job_id": "000buomdp2",
        #     "file_list": [
        #         "apbsinput.in",
        #         "000buomdp2.pqr"
        #     ],
        #     "filename": "apbsinput.in"
        #   }
        # }

        self._logger.debug("FILE_LIST: %s", self.job_input_files)

        if len(self.job_input_files) < 2:
            self._logger.warning(
                "%s WARNING: Missing input files, only found: %s",
                self.job_id,
                self.job_input_files,
            )
            return None

        use_hardcoded_apbsinput = False
        if "apbsinput.in" in self.job_input_files:
            use_hardcoded_apbsinput = True
            job["form"]["filename"] = "apbsinput.in"

        for filename in self.job_input_files:
            self._logger.debug("%s JOB INPUT_FILE: %s", self.job_id, filename)
            if filename.endswith(".pqr"):
                job["form"]["file_list"].append(filename)
            if filename.endswith(".in") and not use_hardcoded_apbsinput:
                job["form"]["filename"] = filename

        json_job_file = Path(self.file_path) / Path(
            f"{self.job_type}-job.json"
        )
        json_job_file.unlink(missing_ok=True)

        with open(json_job_file, "w") as outfile:
            outfile.write(dumps(job, indent=4))

        return json_job_file
