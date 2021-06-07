# coding: utf-8

"""Pdb2PqrJob is used to hold information about an PDB2PQR job."""

from json import dumps
from logging import basicConfig, getLogger, INFO, StreamHandler
from pathlib import Path
from os import getenv
from typing import List
from sys import stdout

from jobinterface import JobInterface
from utiljob import get_contents, JOBTYPE


class Pdb2PqrJob(JobInterface):
    """The concrete implementation of an APBS job."""

    def __init__(self, jobid: str, file_path: str, file_list: List):
        """The job consists of input and output files from an PDB2PQR job

        Args:
            jobid (str): The unique string for an Azure blog or AWS bucket
            file_path (str): The absolute path to the mounted directory
            file_list (List): The list of files for the job

        Raises:
            TypeError: The file_path is not a directory
        """
        # NOTE: The file list should be something like:
        # pdb2pqr_exec_exit_code.txt
        # pdb2pqr_input_files
        # pdb2pqr_output_files
        # pdb2pqr_status
        # pdb2pqr_stderr.txt
        # pdb2pqr_stdout.txt
        # pdb2pqrinput.in
        # *.in
        # *.prq

        self.job_type = JOBTYPE.PDB2PQR.name.lower()
        self._logger = getLogger(__class__.__name__)
        basicConfig(
            format="[%(levelname)s] [%(filename)s:%(lineno)s:%(funcName)s()] %(message)s",
            level=int(getenv("LOG_LEVEL", str(INFO))),
            handlers=[StreamHandler(stdout)],
        )
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
        """Extract the command line arguments thhat were used to run pdb2pqr.

        Args:
            pqr_file (str): The name of the pqr filename where the command
                            line argument are stored

        Returns:
            Dict: A dictionary of command line parameters for a PDB2PQR job
        """
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
            self._logger.debug("%s PQR FILENAME: %s", self.job_id, filename)
            if filename.endswith(".pqr"):
                pqr_file = filename
            if filename.endswith(".pdb"):
                pdb_file = filename

        # Make sure pdb_file and pqr_file are not None
        if not pdb_file or not pqr_file:
            if not pdb_file:
                self._logger.warning("%s Missing pdb input file", self.job_id)
            if not pqr_file:
                self._logger.warning("%s Missing PQR input file", self.job_id)
            return None

        job["form"]["flags"] = self.get_pdb2pqr_flags(pqr_file)
        job["form"]["pdb_name"] = pdb_file
        job["form"]["pqr_name"] = pqr_file

        json_job_file = Path(self.file_path) / Path(
            f"{self.job_type}-job.json"
        )
        json_job_file.unlink(missing_ok=True)

        with open(json_job_file, "w") as outfile:
            outfile.write(dumps(job, indent=4))

        return json_job_file
