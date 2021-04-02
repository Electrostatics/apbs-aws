# coding: utf-8

from os import path as ospath
from typing import List

"""ApbsJob is used to hold information about an APBS job."""

"""
DESCRIPTION:
"""


class ApbsJob:
    def __init__(self, id: str, file_list: List = []):
        self.id = id
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
