#!/usr/bin/env python3
"""Software to run apbs and pdb2pqr jobs."""

from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from datetime import datetime
from enum import Enum
from json import dumps, loads, JSONDecodeError
from logging import getLogger, DEBUG, ERROR, INFO
from os import chdir, getenv, listdir, makedirs
from pathlib import Path
from resource import getrusage, RUSAGE_CHILDREN
from shutil import rmtree
from subprocess import run, CalledProcessError, PIPE
from time import sleep, time
from typing import Any, Dict, List
from urllib import request
from boto3 import client, resource
from botocore.exceptions import ClientError, ParamValidationError

_LOGGER = getLogger(__name__)
_LOGGER.setLevel(ERROR)
_LOGGER.setLevel(INFO)
# TODO: This may need to be increased or calculated based
#       on complexity of the job (dimension of molecule?)
#       The job could get launched multiple times if the
#       job takes longer than Q_TIMEOUT
Q_TIMEOUT = int(getenv("SQS_QUEUE_TIMEOUT", "300"))
AWS_REGION = getenv("SQS_AWS_REGION", "us-west-2")
MAX_TRIES = int(getenv("SQS_MAX_TRIES", "60"))
RETRY_TIME = int(getenv("SQS_RETRY_TIME", "15"))

MEM_PATH = "/dev/shm/test/"
S3_BUCKET = getenv("OUTPUT_BUCKET")
QUEUE = getenv("JOB_QUEUE_NAME")

if S3_BUCKET is None:
    raise ValueError("Environment variable 'OUTPUT_BUCKET' is not set")
if QUEUE is None:
    raise ValueError("Environment variable 'JOB_QUEUE_NAME' is not set")


class JOBTYPE(Enum):
    """The valid values for a job's type."""

    APBS = 1
    PDB2PQR = 2
    UNKNOWN = 3


class JOBSTATUS(Enum):
    """The valid values for a job's status."""

    COMPLETE = 1
    RUNNING = 2
    UNKNOWN = 3


class JobMetrics:
    """
    A way to collect metrics from a subprocess.

    To get memory, we use resource.getrusage(RUSAGE_CHILDREN).
    To avoid accumulating the memory usage from all subprocesses
    we subtract the previous rusage values to get a delta for
    just the current subprocess.

    To get the time to run metrics we subtract the start time from
    the end time (e.g., {jobtype}_end_time - {jobtype}_start_time)

    To get the disk usage we sum up the stats of all the files in
    the output directory.

    The result for each job will to to output a file named:
        {jobtype}-metrics.json
    Where {jobtype} will be apbs or pdb2pqr.
    The contents of the file will be JSON and look like:
    {
        "metrics": {
            "rusage": {
                "ru_utime": 0.004102999999999999,
                "ru_stime": 0.062483999999999984,
                "ru_maxrss": 1003520,
                "ru_ixrss": 0,
                "ru_idrss": 0,
                "ru_isrss": 0,
                "ru_minflt": 823,
                "ru_majflt": 0,
                "ru_nswap": 0,
                "ru_inblock": 0,
                "ru_oublock": 0,
                "ru_msgsnd": 0,
                "ru_msgrcv": 0,
                "ru_nsignals": 0,
                "ru_nvcsw": 903,
                "ru_nivcsw": 4
            },
            "runtime_in_seconds": 262,
            "disk_storage_in_bytes": 4003345,
        },
    }
    """

    def __init__(self):
        """Capture the initial state of the resource usage."""
        metrics = getrusage(RUSAGE_CHILDREN)
        self.job_type = None
        self.output_dir = None
        self.start_time = 0
        self.end_time = 0
        self.values: Dict = {}
        self.values["ru_utime"] = metrics.ru_utime
        self.values["ru_stime"] = metrics.ru_stime
        self.values["ru_maxrss"] = metrics.ru_maxrss
        self.values["ru_ixrss"] = metrics.ru_ixrss
        self.values["ru_idrss"] = metrics.ru_idrss
        self.values["ru_isrss"] = metrics.ru_isrss
        self.values["ru_minflt"] = metrics.ru_minflt
        self.values["ru_majflt"] = metrics.ru_majflt
        self.values["ru_nswap"] = metrics.ru_nswap
        self.values["ru_inblock"] = metrics.ru_inblock
        self.values["ru_oublock"] = metrics.ru_oublock
        self.values["ru_msgsnd"] = metrics.ru_msgsnd
        self.values["ru_msgrcv"] = metrics.ru_msgrcv
        self.values["ru_nsignals"] = metrics.ru_nsignals
        self.values["ru_nvcsw"] = metrics.ru_nvcsw
        self.values["ru_nivcsw"] = metrics.ru_nivcsw

    def get_rusage_delta(self, memory_disk_usage):
        """
        Caluculate the difference between the last time getrusage
        was called and now.

        :param memory_disk_usage: Need to subtract out the files in memory.
        :return:  The rusage values as a dictionary
        :rtype:  Dict
        """
        metrics = getrusage(RUSAGE_CHILDREN)
        self.values["ru_utime"] = metrics.ru_utime - self.values["ru_utime"]
        self.values["ru_stime"] = metrics.ru_stime - self.values["ru_stime"]
        self.values["ru_maxrss"] = (
            metrics.ru_maxrss - self.values["ru_maxrss"] - memory_disk_usage
        )
        self.values["ru_ixrss"] = metrics.ru_ixrss - self.values["ru_ixrss"]
        self.values["ru_idrss"] = metrics.ru_idrss - self.values["ru_idrss"]
        self.values["ru_isrss"] = metrics.ru_isrss - self.values["ru_isrss"]
        self.values["ru_minflt"] = metrics.ru_minflt - self.values["ru_minflt"]
        self.values["ru_majflt"] = metrics.ru_majflt - self.values["ru_majflt"]
        self.values["ru_nswap"] = metrics.ru_nswap - self.values["ru_nswap"]
        self.values["ru_inblock"] = (
            metrics.ru_inblock - self.values["ru_inblock"]
        )
        self.values["ru_oublock"] = (
            metrics.ru_oublock - self.values["ru_oublock"]
        )
        self.values["ru_msgsnd"] = metrics.ru_msgsnd - self.values["ru_msgsnd"]
        self.values["ru_msgrcv"] = metrics.ru_msgrcv - self.values["ru_msgrcv"]
        self.values["ru_nsignals"] = (
            metrics.ru_nsignals - self.values["ru_nsignals"]
        )
        self.values["ru_nvcsw"] = metrics.ru_nvcsw - self.values["ru_nvcsw"]
        self.values["ru_nivcsw"] = metrics.ru_nivcsw - self.values["ru_nivcsw"]
        return self.values

    def get_storage_usage(self):
        """Get the total number of bytes of the output files.

        Returns:
            int: The total bytes in all the files in the job directory
        """
        return sum(
            f.stat().st_size
            for f in self.output_dir.glob("**/*")
            if f.is_file()
        )

    # TODO: intendo: 2021/04/15
    #       The creation of the start time and end time files
    #       is not necesssary and should be removed in the future.
    def set_start_time(self):
        """
        Set the current time to denote that the job started.
        """
        self.start_time = time()

    def set_end_time(self):
        """
        Set the current time to denote that the job ended.
        """
        self.end_time = time()

    def get_metrics(self):
        """
        Create a dictionary of memory usage, execution time, and amount of
        disk storage used.

        Returns:
            Dict: A dictionary of (memory), execution time, and disk storage.
        """
        metrics = {
            "metrics": {"rusage": {}},
        }
        memory_disk_usage = self.get_storage_usage()
        metrics["metrics"]["rusage"] = self.get_rusage_delta(memory_disk_usage)
        metrics["metrics"]["runtime_in_seconds"] = int(
            self.end_time - self.start_time
        )
        metrics["metrics"]["disk_storage_in_bytes"] = memory_disk_usage
        _LOGGER.debug("METRICS: %s", metrics)
        return metrics

    def write_metrics(self, job_type, output_dir: str):
        """Get the metrics of the latest subprocess and create the output file.

        Args:
            job_type (str): Either "apbs" or "pdb2pqr".
            output_dir (str): The directory to find the output files.
        """
        self.job_type = job_type
        self.output_dir = Path(output_dir)
        _LOGGER.debug("JOBTYPE: %s", self.job_type)
        _LOGGER.debug("OUTPUTDIR: %s", self.output_dir)
        with open(f"{job_type}-metrics.json", "w") as fout:
            fout.write(dumps(self.get_metrics(), indent=4))


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
    jobtype: str,
    jobdate: str,
    status: JOBSTATUS,
    output_files: List,
) -> Dict:
    """Update the status file in the S3 bucket for the current job.

    :param s3:  S3 output bucket for the job being updated
    :param jobid:  Unique ID for this job
    :param jobtype:  The job type (apbs, pdb2pqr, etc.)
    :param jobdate:  The date for the job in ISO-8601 format (YYYY-MM-DD)
    :param status:  The job status
    :param output_files:  List of output files
    :return:  Response from storing status file in S3 bucket
    :rtype:  Dict
    """
    ups3 = resource("s3")
    objectfile = f"{jobdate}/{jobid}/{jobtype}-status.json"
    s3obj = ups3.Object(S3_BUCKET, objectfile)
    statobj: dict = loads(s3obj.get()["Body"].read().decode("utf-8"))

    statobj[jobtype]["status"] = status.name.lower()
    if status == JOBSTATUS.COMPLETE:
        statobj[jobtype]["endTime"] = time()
    statobj[jobtype]["outputFiles"] = output_files

    object_response = {}
    try:
        object_response: dict = s3client.put_object(
            Body=dumps(statobj), Bucket=S3_BUCKET, Key=objectfile
        )
    except ClientError as cerr:
        _LOGGER.exception(
            "%s ERROR: Unknown ClientError exception from s3.put_object, %s",
            jobid,
            cerr,
        )
    except ParamValidationError as perr:
        _LOGGER.exception(
            "%s ERROR: Unknown ParamValidation exception from s3.put_object, %s",
            jobid,
            perr,
        )

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


def execute_command(
    job_id: str,
    command_line_str: str,
    stdout_filename: str,
    stderr_filename: str,
):
    """Spawn a subprocess and collect all the information about it.

    Args:
        job_id (str): The unique job id.
        command_line_str (str): The command and arguments.
        stdout_filename (str): The name of the output file for stdout.
        stderr_filename (str): The name of the output file for stderr.
    """
    command_split = command_line_str.split()
    try:
        proc = run(command_split, stdout=PIPE, stderr=PIPE, check=True)
    except CalledProcessError as cpe:
        # TODO: intendo 2021/05/05
        #       we need the jobid here
        _LOGGER.exception(
            "%s failed to run command, %s: %s",
            job_id,
            command_line_str,
            cpe,
        )

    # Write stdout to file
    with open(stdout_filename, "w") as fout:
        fout.write(proc.stdout.decode("utf-8"))

    # Write stderr to file
    with open(stderr_filename, "w") as fout:
        fout.write(proc.stderr.decode("utf-8"))


def run_job(
    job: str,
    s3client: client,
    metrics: JobMetrics,
    queue_url: str,
    receipt_handle: str,
) -> int:
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
    except JSONDecodeError as error:
        _LOGGER.error(
            "ERROR: Unable to load json information for job, %s \n\t%s",
            job,
            error,
        )
        return ret_val
    job_type = job_info["job_type"]
    job_id = job_info["job_id"]
    job_date = job_info["job_date"]
    rundir = f"{MEM_PATH}{job_date}/{job_id}"
    inbucket = job_info["bucket_name"]

    # Prepare job directory and download input files
    makedirs(rundir, exist_ok=True)
    chdir(rundir)

    for file in job_info["input_files"]:
        if "https" in file:
            name = f"{job_date}/{job_id}/{file.split('/')[-1]}"
            try:
                request.urlretrieve(file, f"{MEM_PATH}{name}")
            except Exception as error:
                # TODO: intendo 2021/05/05 - Find more specific exception
                _LOGGER.exception(
                    "%s ERROR: Download failed for file, %s \n\t%s",
                    job_id,
                    name,
                    error,
                )
                return cleanup_job(rundir)
        else:
            try:
                s3client.download_file(inbucket, file, f"{MEM_PATH}{file}")
            except Exception as error:
                # TODO: intendo 2021/05/05 - Find more specific exception
                _LOGGER.exception(
                    "%s ERROR: Download failed for file, %s \n\t%s",
                    job_id,
                    file,
                    error,
                )
                return cleanup_job(rundir)

    # Run job and record associated metrics
    update_status(
        s3client,
        job_id,
        job_type,
        job_date,
        JOBSTATUS.RUNNING,
        [],
    )

    if JOBTYPE.APBS.name.lower() in job_type:
        command = f"apbs {job_info['command_line_args']}"
    elif JOBTYPE.PDB2PQR.name.lower() in job_type:
        command = f"pdb2pqr.py {job_info['command_line_args']}"
    else:
        raise KeyError(f"Invalid job type, {job_type}")

    if "max_run_time" in job_info:
        sqs = client("sqs", region_name=AWS_REGION)
        sqs.change_message_visibility(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle,
            VisibilityTimeout=int(job_info["max_run_time"]),
        )

    file = "MISSING"
    try:
        metrics.set_start_time()
        execute_command(
            job_id, command, f"{job_type}.stdout.txt", f"{job_type}.stderr.txt"
        )
        metrics.set_end_time()

        # We need to create the {job_type}-metrics.json before we upload
        # the files to the S3_BUCKET.
        metrics.write_metrics(job_type, ".")

        for file in listdir("."):
            file_path = f"{job_date}/{job_id}/{file}"
            s3client.upload_file(
                f"{MEM_PATH}{file_path}",
                S3_BUCKET,
                f"{file_path}",
            )
    except Exception as error:
        # TODO: intendo 2021/05/05 - Find more specific exception
        _LOGGER.exception(
            "%s ERROR: Failed to upload file, %s \n\t%s",
            job_id,
            f"{job_date}/{job_id}/{file}",
            error,
        )
        # TODO: Should this return 1 because noone else will succeed?
        ret_val = 1

    # TODO: 2021/03/30, Elvis - Will need to address how we bundle output
    #       subdirectory for PDB2PKA when used; I previous bundled it as
    #       a compressed tarball (i.e. "{job_id}-pdb2pka_output.tar.gz")

    # Create list of output files
    input_files_no_id = [  # Remove job_id prefix from input file list
        "".join(name.split("/")[-1]) for name in job_info["input_files"]
    ]
    output_files = [
        f"{job_date}/{job_id}/{filename}"
        for filename in listdir(".")
        if filename not in input_files_no_id
    ]

    # Cleanup job directory and update status
    cleanup_job(rundir)
    update_status(
        s3client,
        job_id,
        job_type,
        job_date,
        JOBSTATUS.COMPLETE,
        output_files,
    )

    return ret_val


def build_parser():
    """Build argument parser.

    :return:  argument parser
    :rtype:  ArgumentParser
    """
    desc = "\n\tRun the APBS or PDB2PQR process"

    parser = ArgumentParser(
        description=desc,
        formatter_class=ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print out verbose output",
    )
    return parser


def main() -> None:
    """Loop over the SQS Queue and run any jobs in the queue.
    :return:  None
    """

    parser = build_parser()
    args = parser.parse_args()

    _LOGGER.setLevel(INFO)
    if args.verbose:
        _LOGGER.setLevel(DEBUG)

    s3client = client("s3")
    sqs = client("sqs", region_name=AWS_REGION)
    queue_url = sqs.get_queue_url(QueueName=QUEUE)
    qurl = queue_url["QueueUrl"]
    lasttime = datetime.now()

    metrics = JobMetrics()

    # The structure of the SQS messages is documented at:
    # https://docs.aws.amazon.com/AWSSimpleQueueService/
    # latest/APIReference/API_ReceiveMessage.html
    mess = get_messages(sqs, qurl)
    while mess:
        for idx in mess["Messages"]:
            run_job(idx["Body"], s3client, metrics, qurl, idx["ReceiptHandle"])
            sqs.delete_message(
                QueueUrl=qurl, ReceiptHandle=idx["ReceiptHandle"]
            )
        mess = get_messages(sqs, qurl)
    _LOGGER.info("DONE: %s", str(datetime.now() - lasttime))


if __name__ == "__main__":
    main()
