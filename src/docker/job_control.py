#!/usr/bin/env python3
"""Software to run apbs and pdb2pqr jobs."""

from os import chdir, getenv, listdir, makedirs, system
from datetime import datetime
from enum import Enum
from json import dumps, loads
from logging import getLogger
from time import sleep, time
from shutil import rmtree
from typing import Any, Dict, List
from urllib import request
from boto3 import client, resource

_LOGGER = getLogger(__name__)
Q_TIMEOUT = 300
AWS_REGION = "us-west-2"
MAX_TRIES = 60
RETRY_TIME = 15

MEM_PATH = "/dev/shm/test/"
S3_BUCKET = getenv("OUTPUT_BUCKET")
QUEUE = getenv("JOB_QUEUE_NAME")


class JOBTYPE(Enum):
    """The valid values for a job's type."""

    APBS = 1
    PDB2PQR = 2


class JOBSTATUS(Enum):
    """The valid values for a job's status."""

    COMPLETE = 1
    RUNNING = 2


def get_messages(sqs: client, qurl: str) -> Any:
    """Get SQS Messages from the queue.

    :param sqs:  S3 output bucket for the job being updated
    :type sqs:  boto3.client connection
    :param qurl:  URL for the SNS Queue to listen for new messages
    :return:  List of messages from the queue
    :rtype:  Any
    """
    loop = 0

    items = sqs.receive_message(
        QueueUrl=qurl, MaxNumberOfMessages=1, VisibilityTimeout=Q_TIMEOUT
    )

    while "Messages" not in items:
        loop += 1
        if loop == MAX_TRIES:
            return None
        _LOGGER.info("Waiting ....")
        sleep(RETRY_TIME)
        items = sqs.receive_message(
            QueueUrl=qurl, MaxNumberOfMessages=1, VisibilityTimeout=Q_TIMEOUT
        )

    return items


def update_status(
    s3client: client,
    jobid: str,
    jobtype: JOBTYPE,
    status: JOBSTATUS,
    output_files: List,
) -> Dict:
    """Update the status file in the S3 bucket for the current job.

    :param s3:  S3 output bucket for the job being updated
    :param jobid:  Unique ID for this job
    :param jobtype:  The job type (apbs, pdb2pqr, etc.)
    :param status:  The job status
    :param output_files:  List of output files
    :return:  Response from storing status file in S3 bucket
    :rtype:  Dict
    """
    ups3 = resource("s3")
    objectfile = f"{jobid}/{jobtype.name}-status.json"
    s3obj = ups3.Object(S3_BUCKET, objectfile)
    statobj: dict = loads(s3obj.get()["Body"].read().decode("utf-8"))

    statobj[jobtype]["status"] = status.name
    statobj[jobtype]["endTime"] = time()
    # FIX TODO: What does FIX mean?
    statobj[jobtype]["outputFiles"] = output_files

    object_response = {}
    try:
        object_response: dict = s3client.put_object(
            Body=dumps(statobj), Bucket=S3_BUCKET, Key=objectfile
        )
    except Exception as error:
        _LOGGER.error("ERROR: Unknown exception from s3.put_object, %s", error)

    return object_response


def cleanup_job(rundir: str) -> int:
    """Remove the directory for the job.

    :param rundir:  The local directory where the job is being executed.
    :return:  int
    """
    _LOGGER.info("Deleting run directory, %s", rundir)
    chdir(MEM_PATH)
    rmtree(rundir)
    return 1


def run_job(job: str, s3client: client) -> int:
    """Remove the directory for the job.

    :param job:  The job file describing what needs to be run.
    :param s3client:  S3 input bucket with input files.
    :return:  int
    """
    ret_val = 1
    try:
        job_info: dict = loads(job)
        if "job_id" not in job_info:
            _LOGGER.error("ERROR: Missing job id for job, %s", job)
            return ret_val
    except Exception as error:
        _LOGGER.error(
            "ERROR: Unable to load json information for job, %s \n\t%s",
            job,
            error,
        )
        return ret_val
    rundir = f"{MEM_PATH}{job_info['job_id']}"
    inbucket = job_info["bucket_name"]
    makedirs(rundir, exist_ok=True)
    chdir(rundir)

    for file in job_info["input_files"]:
        if "https" in file:
            name = f"{job_info['job_id']}/{file.split('/')[-1]}"
            try:
                request.urlretrieve(file, f"{MEM_PATH}{name}")
            except Exception as error:
                _LOGGER.error(
                    "ERROR: Download failed for file, %s \n\t%s", name, error
                )
                return cleanup_job(rundir)
        else:
            try:
                s3client.download_file(inbucket, file, f"{MEM_PATH}{file}")
            except Exception as error:
                _LOGGER.error(
                    "ERROR: Download failed for file, %s \n\t%s", file, error
                )
                return cleanup_job(rundir)
    update_status(
        s3client,
        job_info["job_id"],
        job_info["job_type"],
        JOBSTATUS.RUNNING,
        [],
    )

    if JOBTYPE.APBS.name in job_info["job_type"]:
        command = (
            "LD_LIBRARY_PATH=/app/APBS-3.0.0.Linux/lib "
            "/app/APBS-3.0.0.Linux/bin/apbs "
            f"{job_info['command_line_args']} "
            "> apbs.stdout.txt 2> apbs.stderr.txt"
        )
    elif JOBTYPE.PDB2PQR.name in job_info["job_type"]:
        command = (
            "/app/builds/pdb2pqr/pdb2pqr.py "
            f"{job_info['command_line_args']} "
            "> pdb2pqr.stdout.txt 2> pdb2pqr.stderr.txt"
        )
    else:
        raise KeyError(f"Invalid job type, {job_info['job_type']}")

    file = ""
    try:
        system(command)
        for file in listdir("."):
            s3client.upload_file(
                f"{MEM_PATH}{job_info['job_id']}/{file}",
                S3_BUCKET,
                f"{job_info['job_id']}/{file}",
            )
    except Exception as error:
        _LOGGER.error(
            "ERROR: Failed to upload file, %s \n\t%s",
            f"{job_info['job_id']}/{file}",
            error,
        )
        ret_val = 0

    output_files = [
        f"{job_info['job_id']}/{file}"
        for file in listdir(".")
        for infile in job_info["input_files"]
        if file not in infile
    ]
    chdir(MEM_PATH)
    rmtree(rundir)
    update_status(
        s3client,
        job_info["job_id"],
        job_info["job_type"],
        JOBSTATUS.COMPLETE,
        output_files,
    )

    return ret_val


def main() -> None:
    """Loop over the SQS Queue and run any jobs in the queue.
    :return:  None
    """

    s3client = client("s3")
    sqs = client("sqs", region_name=AWS_REGION)
    queue_url = sqs.get_queue_url(QueueName=QUEUE)
    qurl = queue_url["QueueUrl"]
    lasttime = datetime.now()

    # TODO: Document what a mess structure looks like
    mess = get_messages(sqs, qurl)
    while mess:
        for idx in mess["Messages"]:
            if run_job(idx["Body"], s3client):
                sqs.delete_message(
                    QueueUrl=qurl, ReceiptHandle=idx["ReceiptHandle"]
                )
        mess = get_messages(sqs, qurl)
    _LOGGER.info("DONE: %s", str(datetime.now() - lasttime))


if __name__ == "__main__":
    main()
