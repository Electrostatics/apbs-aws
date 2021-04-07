# coding: utf-8

from json import dumps
from logging import getLogger, ERROR, INFO
from pathlib import Path
from os.path import isdir, isfile
from typing import List
from utiljob import get_contents
import re

_LOGGER = getLogger(__name__)

"""Pdb2PqrJob is used to hold information about an PDB2PQR job."""

"""
DESCRIPTION:
"""


class Pdb2PqrJob:
    def __init__(self, jobid: str, file_path: str, file_list: List = []):
        """The job consists of input and output files from an PDB2PQR job

        Args:
            jobid (str): The unique string for an Azure blog or AWS bucket
            file_path (str): The absolute path to the mounted directory
            file_list (List, optional): The list of files for the job

        Raises:
            TypeError: The file_path is not a directory
        """
        # NOTE: The file list should be something like:
        # pdb2pqr_end_time
        # pdb2pqr_exec_exit_code.txt
        # pdb2pqr_input_files
        # pdb2pqr_output_files
        # pdb2pqr_start_time
        # pdb2pqr_status
        # pdb2pqr_stderr.txt
        # pdb2pqr_stdout.txt
        # pdb2pqrinput.in
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
        Subtract pdb2pqr_start_time from pdb2pqr_end_time to get number of seconds
        """
        starttime = get_contents(self.file_list["pdb2pqr_start_time"])[0]
        endtime = get_contents(self.file_list["pdb2pqr_end_time"])[0]
        return int(float(endtime) - float(starttime))

    def get_memory_usage(self):
        """Get the memory used and high water memory that could have been used

        Returns:
            Dict: Total & high memory usage found in pdb2pqr_stdout.txt file
        """
        # NOTE: This could be done by looking at the dime values in
        #       the pdb2pqrinput.in file and taking the x, y, and z values
        #       and multiplying them times 0.00019073486 and then if
        #       the elec type is mg-auto you could multiply that by 2.
        #
        #       Otherwise, you can parse the "Final memory usage" from
        #       the pdb2pqr_stdout.txt file. The line looks like:
        # Final memory usage:  0.001 MB total, 2666.345 MB high water
        mem_used = {"total": None, "high": None}
        lines = get_contents(self.file_list["pdb2pqr_stdout.txt"])
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

    def get_pdb2pqr_flags(self, pqr_file):
        flags = {}
        try:
            # TODO: use get_contents to get lines
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

    def build_pdb2pqr_job(self, pdb_file, pqr_file):
        """
        Create an pdb2pqr-job.json file to simulate what the Web/Gui/React
        application would create if a user submitted the job.
        """
        job_file = {
            "form": {
                "job_id": self.jobid,
                "invoke_method": "v2",
                "file_list": [],
            }
        }

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
        job_file["form"]["pdb_name"] = pdb_file[0].replace(self.jobid, "")
        job_file["form"]["pqr_name"] = pqr_file[0].replace(self.jobid, "")

        # print(f"PREFLAGS: {pqr_file[0]}")
        flags = self.get_pdb2pqr_flags(pqr_file[0])
        job_file["form"]["flags"] = flags

        with open(
            Path(self.file_path) / Path("pdb2pqr-job.json"), "w"
        ) as outfile:
            outfile.write(dumps(job_file, indent=4))
