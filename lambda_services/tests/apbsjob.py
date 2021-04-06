# coding: utf-8

from json import dumps
from logging import getLogger, ERROR, INFO
from pathlib import Path
from os.path import isdir, isfile
from typing import List

_LOGGER = getLogger()

"""ApbsJob is used to hold information about an APBS job."""

"""
DESCRIPTION:
"""


def get_contents(filename):
    lines = []
    _LOGGER.info("GET_CONTENTS: %s", filename)
    print("GET_CONTENTS: %s" % filename)
    if isfile(filename):
        with open(filename, "r") as fh:
            for curline in fh:
                curline = curline.strip("\n")
                if curline:
                    lines.append(curline)
    return lines


class ApbsJob:
    def __init__(self, jobid: str, file_path: str, file_list: List = []):
        self._LOGGER = getLogger(__class__.__name__)
        self.jobid = jobid
        self.file_path = None
        self.file_list = {}
        if not isdir(file_path):
            raise TypeError(
                "Expected file path to be a directory: %s", type(file_path)
            )

        # print("ABPS: filepath %s" % file_path)
        self.file_path = file_path
        for filename in file_list:
            self._LOGGER.info("FILENAME: %s", filename)
            full_filename = Path(file_path) / Path(filename)
            # print("ABPS: full filename %s" % full_filename)
            if isfile(full_filename):
                self.file_list[filename] = full_filename
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

    def execution_time(self):
        """
        Subtract apbs_start_time from apbs_end_time to get number of seconds
        """
        starttime = get_contents(self.file_list["apbs_start_time"])[0]
        endtime = get_contents(self.file_list["apbs_end_time"])[0]
        return int(float(endtime) - float(starttime))

    def build_apbs_job(self):
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
