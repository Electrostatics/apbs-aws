# coding: utf-8

from os import path as ospath
from typing import List
from json import dumps

"""ApbsJob is used to hold information about an APBS job."""

"""
DESCRIPTION:
"""


class ApbsJob:
    def __init__(self, jobid: str, file_list: List = []):
        self.jobid = jobid
        self.file_list = file_list
        # apbs_end_time
        # apbs_exec_exit_code.txt
        # apbs_input_files
        # apbs_output_files
        # apbs_start_time
        # apbs_status
        # apbs_stderr.txt
        # apbs_stdout.txt
        # apbsinput.in

    def execution_time(self):
        # TODO: Subtract apbs_start_time from apbs_end_time
        #       to get number of seconds
        pass

    def build_apbs_job(self, apbs_files):
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

        for filename in apbs_files:
            job_file["form"]["file_list"].append(filename)

        with open(f"apbs-job.json", "w") as outfile:
            outfile.write(dumps(job_file, indent=4))
