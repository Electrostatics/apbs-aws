# coding: utf-8

from sys import exc_info, exit
from enum import Enum
from json import dumps
from logging import getLogger
from os.path import isfile
from os import chdir, getcwd
from os import path as ospath
from pathlib import Path
from requests import post, put

_LOGGER = getLogger(__name__)

"""Utilities for APBS and PDB2PQR jobs."""


class JOBTYPE(Enum):
    """The valid values for a job's type."""

    APBS = 1
    PDB2PQR = 2
    COMBINED = 3
    UNKNOWN = 4


def get_contents(filename):
    """[summary]

    Args:
        filename (str): The full path of the file to read from.

    Returns:
        List: The lines of the file with the newlines stripped.
    """
    lines = []
    _LOGGER.debug("GET_CONTENTS: %s", filename)
    if isfile(filename):
        with open(filename, "r") as fptr:
            for curline in fptr:
                curline = curline.strip("\n")
                if curline:
                    lines.append(curline)
    return lines


def submit_aws_job(api_token_url, job):
    """Upload all the files to submit a job.

    Args:
        API_TOKEN_URL (str): The AWS REST endpoint to submit a job.
        job (JobInterface): The job that holds the data to be submitted.
    """
    job_id = job.job_id
    job_type = job.job_type
    job_file = f"{job_type}-job.json"
    upload_files = job.job_input_files
    job_work_dir = job.file_path
    # job_type is "apbs" or "pdb2pqr"
    # data_files are the list of files inside the job_file that came from
    _LOGGER.debug("JOB: %s", job)
    _LOGGER.debug("DATAFILES: %s: ", upload_files)

    cwd = getcwd()

    try:
        chdir(job_work_dir)
    except OSError as oerr:
        _LOGGER.error("ERROR: JOB: %s", job)
        _LOGGER.error(
            "ERROR: Can't change from directory, %s, to %s because %s: %s}",
            cwd,
            job_work_dir,
            exc_info(),
            oerr,
        )
        exit(1)
    finally:
        _LOGGER.debug("Restoring the path to %s", cwd)
        chdir(cwd)

    # Build the JSON to send to the API_TOKEN_URL to get a list
    # of S3 Auth tokens for each file
    job_request = {
        "job_id": f"{job_id}",
        "bucket_name": f"{job_id}",
        "file_list": [f"{job_file}"],
    }
    for file in upload_files:
        job_request["file_list"].append(file)
    _LOGGER.debug("REQUEST: %s", dumps(job_request))

    response = post(api_token_url, json=job_request)

    # NOTE: Must send *-job.json file last because that is what triggers
    #       the S3 event to start the job
    save_url = None
    save_file = None
    json_response = response.json()
    _LOGGER.debug("POST RESPONSE: %s", json_response)
    for file in json_response["urls"]:
        url = json_response["urls"][file]
        _LOGGER.debug("FILE: %s, URL: %s", file, url)
        if f"{job_type}-job.json" in file:
            save_url = url
            save_file = file
            continue
        full_filepath = Path(job_work_dir) / file
        _ = put(url, data=open(full_filepath, "rb"))

    # NOTE: Send the "*-job.json" file to start the job
    if save_url is not None and save_file is not None:
        full_filepath = Path(job_work_dir) / save_file
        _ = put(save_url, data=open(full_filepath, "rb"))
    else:
        _LOGGER.error(
            "ERROR: Can't find JOB file, %s",
            job_id + job_type + "-job.json",
        )


def get_job_type(file_list):
    """Determine if the job is APBS, PDB2PQR, COMBINED, or Unknown

    Args:
        file_list List: a list of filenames from a job directory

    Returns:
        str: A keyword of one of the names in the JOBTYPE Enum
    """
    apbs_job_type = False
    pdb2pqr_job_type = False
    for filename in file_list:
        if filename.endswith(".dx") or filename in "apbs_end_time":
            apbs_job_type = True
        if filename.endswith(".propka") or filename in "pdb2pqr_end_time":
            pdb2pqr_job_type = True
    if apbs_job_type and pdb2pqr_job_type:
        return JOBTYPE.COMBINED.name.lower()
    if apbs_job_type:
        return JOBTYPE.APBS.name.lower()
    if pdb2pqr_job_type:
        return JOBTYPE.PDB2PQR.name.lower()
    return JOBTYPE.UNKNOWN.name.lower()


def get_job_ids_from_cache(cache_file):
    """Read in all the job ids from a file.

    Args:
        cache_file (str): The full filename of the file holding jobs ids.

    Returns:
        List: The list of job ids in th cache_file.
    """

    # TODO: This should do more error handling.
    jobs = []
    if ospath.exists(cache_file) and ospath.isfile(cache_file):
        with open(cache_file, "r") as fptr:
            for curline in fptr:
                job_id = curline.strip("\n").split(" ")[0].strip("/")
                if job_id is not None:
                    jobs.append(job_id)
    return jobs
