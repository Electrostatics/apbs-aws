# coding: utf-8

from jobinterface import JobInterface
from json import dumps
from logging import getLogger, ERROR, INFO
from pathlib import Path
from typing import List
from utiljob import get_contents

_LOGGER = getLogger(__name__)

"""Pdb2PqrJob is used to hold information about an PDB2PQR job."""

"""
DESCRIPTION:
"""


class Pdb2PqrJob(JobInterface):
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

        self.job_type = "pdb2pqr"
        self._LOGGER = getLogger(__class__.__name__)
        super().__init__(jobid, file_path, file_list)

    def get_memory_usage(self):
        """Get the memory used which is a total guess

        Returns:
            int: Total memory used
        """
        # NOTE: This data is not being captured yet
        mem_used = 0
        return mem_used

    def get_pdb2pqr_flags(self, pqr_file):
        flags = {}
        # lines = get_contents(self.file_list[f"{self.job_type}_stdout.txt"])
        lines = get_contents(self.file_list[pqr_file])
        options = None
        for idx, line in enumerate(lines):
            if line.startswith(
                "REMARK   1 Command line used to generate this file:"
            ):
                # NOTE: The next line has the actual parameters
                #       passed to pdb2pqr
                next_line = idx + 1
                options = lines[next_line]
                break

        options = options.replace("REMARK   1 ", "")
        options = options.replace("--", "")
        for option in options.split():
            values = option.split("=")
            # Skip the data files file.pqr and file.pdb
            if ".pqr" not in values[0] and ".pdb" not in values[0]:
                flags[values[0]] = True if len(values) == 1 else values[1]
        return flags

    def build_job_file(self):
        """
        Create an pdb2pqr-job.json file to simulate what the Web/Gui/React
        application would create if a user submitted the job.
        """
        job = {
            "form": {
                "job_id": self.job_id,
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
        pdb_file = None
        pqr_file = None
        for filename in self.file_list:
            self._LOGGER.debug("PQR FILENAME: %s", filename)
            if filename.endswith(".pqr"):
                pqr_file = filename
            if filename.endswith(".pdb"):
                pdb_file = filename

        # TODO: Make sure pdb_file and pqr_file are not None

        job["form"]["flags"] = self.get_pdb2pqr_flags(pqr_file)
        job["form"]["pdb_name"] = pdb_file
        job["form"]["pqr_name"] = pqr_file

        with open(
            Path(self.file_path) / Path(f"{self.job_type}-job.json"), "w"
        ) as outfile:
            outfile.write(dumps(job, indent=4))
        _LOGGER.debug("JOB: %s", job)
