#!/usr/bin/env python3
"""Software to run apbs and pdb2pqr jobs."""

from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from datetime import datetime
from enum import Enum
from json import dumps, loads, JSONDecodeError
from logging import basicConfig, getLogger, DEBUG, INFO, StreamHandler
from os import chdir, getenv, getpid, listdir, makedirs
from pathlib import Path
from resource import getrusage, RUSAGE_CHILDREN
from shutil import rmtree
import signal
from subprocess import run, CalledProcessError, PIPE
from time import sleep, time
from typing import Any, Dict, List, Optional
from urllib import request
from sys import stderr
import sys
from boto3 import client, resource
from botocore.exceptions import ClientError, ParamValidationError


# Global Environment Variables
GLOBAL_VARS = {
    "Q_TIMEOUT": None,
    "AWS_REGION": None,
    "MAX_TRIES": None,
    "RETRY_TIME": None,
    "LOG_LEVEL": INFO,
    "JOB_PATH": None,
    "S3_TOPLEVEL_BUCKET": None,
    "QUEUE": None,
}
_LOGGER = getLogger(__name__)
basicConfig(
    format=(
        "[%(levelname)s] "
        "[%(filename)s:%(lineno)s:%(funcName)s()] %(message)s"
    ),
    level=GLOBAL_VARS["LOG_LEVEL"],
    handlers=[StreamHandler(stderr)],
)


# Default to start processing immediately
PROCESSING = True


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
    FAILED = 4


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
        self.output_dir = None
        self._start_time = 0
        self._end_time = 0
        self.exit_code = None
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

    def get_rusage_delta(self):
        """
        Caluculate the difference between the last time getrusage
        was called and now.

        :param memory_disk_usage: Need to subtract out the files in memory.
        :return:  The rusage values as a dictionary
        :rtype:  Dict
        """
        metrics = getrusage(RUSAGE_CHILDREN)
        self.values["ru_utime"] = round(
            metrics.ru_utime - self.values["ru_utime"], 2
        )
        self.values["ru_stime"] = round(
            metrics.ru_stime - self.values["ru_stime"], 2
        )
        self.values["ru_maxrss"] = metrics.ru_maxrss - self.values["ru_maxrss"]
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

    @property
    def start_time(self):
        """The time the job started."""
        return self._start_time

    @start_time.setter
    def start_time(self, value):
        """Set the current time to denote that the job started."""
        self._start_time = value

    @property
    def end_time(self):
        """The time the job ended."""
        return self._end_time

    @end_time.setter
    def end_time(self, value):
        """Set the current time to denote that the job ended."""
        self._end_time = value

    @property
    def exit_code(self):
        """The exit code of the process."""
        return self._exit_code

    @exit_code.setter
    def exit_code(self, exit_code: int):
        """
        Set the exit code of the job executed.
        """
        self._exit_code = exit_code

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
        disk_usage = self.get_storage_usage()
        metrics["metrics"]["rusage"] = self.get_rusage_delta()
        metrics["metrics"]["runtime_in_seconds"] = round(
            self.end_time - self.start_time, 2
        )
        metrics["metrics"]["disk_storage_in_bytes"] = disk_usage
        metrics["metrics"]["exit_code"] = self.exit_code
        return metrics

    def write_metrics(self, job_tag: str, job_type: str, output_dir: str):
        """Get the metrics of the latest subprocess and create the output file.

        Args:
            job_type (str): Either "apbs" or "pdb2pqr".
            output_dir (str): The directory to find the output files.
        Returns:
            N/A
        """
        self.output_dir = Path(output_dir)
        metrics = self.get_metrics()
        _LOGGER.info(
            "%s %s METRICS: exit_code %s %s",
            job_tag,
            job_type.upper(),
            metrics["metrics"]["exit_code"],
            metrics,
        )
        with open(f"{job_type}-metrics.json", "w") as fout:
            fout.write(dumps(metrics, indent=4))


def print_current_state():
    for idx in sorted(GLOBAL_VARS):
        _LOGGER.info("VAR: %s, VALUE: %s", idx, GLOBAL_VARS[idx])
        print(f"VAR: {idx}, VALUE: set to: {GLOBAL_VARS[idx]}", file=stderr)
    _LOGGER.info("PROCESSING state: %s", PROCESSING)
    print(f"PROCESSING state: {PROCESSING}\n", file=stderr)


def receive_signal(signal_number, frame):
    _LOGGER.info("Received signal: %s, %s", signal_number, frame)
    print(f"Received signal: {signal_number}, {frame}", file=stderr)
    signal_help(signal_number, frame)


def signal_help(signal_number, frame):
    # pylint: disable=unused-argument
    print("\n", file=stderr)
    print(f"RECEIVED SIGNAL: {signal_number}\n\n", file=stderr)
    print("\tYou have asked for help:\n\n", file=stderr)
    print(
        f"\tTo update environment variables, type: kill -USR1 {getpid()}\n\n",
        file=stderr,
    )
    print(
        f"\tTo toggle processing, type: kill -USR2 {getpid()}\n\n", file=stderr
    )
    print_current_state()


def terminate_process(signal_number, frame):
    # pylint: disable=unused-argument
    print("Caught (SIGTERM) terminating the process\n", file=stderr)
    sys.exit()


def toggle_processing(signal_number, frame):
    # pylint: disable=unused-argument
    global PROCESSING
    PROCESSING = not PROCESSING
    _LOGGER.info("PROCESSING set to: %s", PROCESSING)
    print(f"PROCESSING set to:{PROCESSING}\n", file=stderr)


def update_environment(signal_number, frame):
    # pylint: disable=unused-argument
    # TODO: This may need to be increased or calculated based
    #       on complexity of the job (dimension of molecule?)
    #       The job could get launched multiple times if the
    #       job takes longer than Q_TIMEOUT
    global GLOBAL_VARS
    GLOBAL_VARS["Q_TIMEOUT"] = int(getenv("SQS_QUEUE_TIMEOUT", "300"))
    GLOBAL_VARS["AWS_REGION"] = getenv("SQS_AWS_REGION", "us-west-2")
    GLOBAL_VARS["MAX_TRIES"] = int(getenv("SQS_MAX_TRIES", "60"))
    GLOBAL_VARS["RETRY_TIME"] = int(getenv("SQS_RETRY_TIME", "15"))
    GLOBAL_VARS["LOG_LEVEL"] = int(getenv("LOG_LEVEL", str(INFO)))
    GLOBAL_VARS["JOB_PATH"] = getenv("JOB_PATH", "/var/tmp/")
    GLOBAL_VARS["S3_TOPLEVEL_BUCKET"] = getenv("OUTPUT_BUCKET")
    GLOBAL_VARS["QUEUE"] = getenv("JOB_QUEUE_NAME")
    _LOGGER.setLevel(GLOBAL_VARS["LOG_LEVEL"])

    if GLOBAL_VARS["S3_TOPLEVEL_BUCKET"] is None:
        raise ValueError("Environment variable 'OUTPUT_BUCKET' is not set")
    if GLOBAL_VARS["QUEUE"] is None:
        raise ValueError("Environment variable 'JOB_QUEUE_NAME' is not set")


def get_messages(sqs: client, qurl: str) -> Any:
    """Get SQS Messages from the queue.

    :param sqs:  S3 output bucket for the job being updated
    :type sqs:  boto3.client connection
    :param qurl:  URL for the SNS Queue to listen for new messages
    :return:  List of messages from the queue
    :rtype:  Any
    """
    loop = 0

    messages = sqs.receive_message(
        QueueUrl=qurl,
        MaxNumberOfMessages=1,
        VisibilityTimeout=GLOBAL_VARS["Q_TIMEOUT"],
    )

    while "Messages" not in messages:
        loop += 1
        if loop == GLOBAL_VARS["MAX_TRIES"]:
            return None
        _LOGGER.debug("Waiting ....")
        sleep(GLOBAL_VARS["RETRY_TIME"])
        messages = sqs.receive_message(
            QueueUrl=qurl,
            MaxNumberOfMessages=1,
            VisibilityTimeout=GLOBAL_VARS["Q_TIMEOUT"],
        )
    return messages


def update_status(
    s3client: client,
    job_tag: str,
    jobtype: str,
    status: JOBSTATUS,
    output_files: List,
    message: Optional[str] = None,
) -> Dict:
    """Update the status file in the S3 bucket for the current job.

    :param s3:  S3 output bucket for the job being updated
    :param job_tag:  Unique ID for this job
    :param jobtype:  The job type (apbs, pdb2pqr, etc.)
    :param status:  The job status
    :param output_files:  List of output files
    :return:  Response from storing status file in S3 bucket
    :rtype:  Dict
    """
    ups3 = resource("s3")
    objectfile = f"{job_tag}/{jobtype}-status.json"
    s3obj = ups3.Object(GLOBAL_VARS["S3_TOPLEVEL_BUCKET"], objectfile)
    statobj: dict = loads(s3obj.get()["Body"].read().decode("utf-8"))

    # Update status and timestamps
    statobj[jobtype]["status"] = status.name.lower()
    if status == JOBSTATUS.COMPLETE or status == JOBSTATUS.FAILED:
        statobj[jobtype]["endTime"] = time()

    if status == JOBSTATUS.FAILED and message is not None:
        statobj[jobtype]["message"] = message

    statobj[jobtype]["outputFiles"] = output_files

    object_response = {}
    try:
        object_response: dict = s3client.put_object(
            Body=dumps(statobj),
            Bucket=GLOBAL_VARS["S3_TOPLEVEL_BUCKET"],
            Key=objectfile,
        )
    except ClientError as cerr:
        _LOGGER.exception(
            "%s ERROR: ClientError exception from s3.put_object, %s",
            job_tag,
            cerr,
        )
    except ParamValidationError as perr:
        _LOGGER.exception(
            "%s ERROR: ParamValidation exception from s3.put_object, %s",
            job_tag,
            perr,
        )

    return object_response


def cleanup_job(job_tag: str, rundir: str) -> int:
    """Remove the directory for the job.

    :param rundir:  The local directory where the job is being executed.
    :return:  int
    """
    _LOGGER.info("%s Deleting run directory, %s", job_tag, rundir)
    chdir(GLOBAL_VARS["JOB_PATH"])
    rmtree(rundir)
    return 1


def execute_command(
    job_tag: str,
    command_line_str: str,
    stdout_filename: str,
    stderr_filename: str,
) -> int:
    """Spawn a subprocess and collect all the information about it.
    Returns the exit code the of the executed command.

    Args:
        job_tag (str): The unique job id.
        command_line_str (str): The command and arguments.
        stdout_filename (str): The name of the output file for stdout.
        stderr_filename (str): The name of the output file for stderr.
    Return:
        exit_code (int): The exit code of the executed command
    """
    command_split = command_line_str.split()
    stdout_text: str
    stderr_text: str
    exit_code: int
    try:
        proc = run(command_split, stdout=PIPE, stderr=PIPE, check=True)
        stdout_text = proc.stdout.decode("utf-8")
        stderr_text = proc.stderr.decode("utf-8")
        exit_code = proc.returncode
    except CalledProcessError as cpe:
        _LOGGER.exception(
            "%s failed to run command, %s: %s",
            job_tag,
            command_line_str,
            cpe,
        )
        stdout_text = cpe.stdout.decode("utf-8")
        stderr_text = cpe.stderr.decode("utf-8")
        exit_code = cpe.returncode

    # Write stdout to file
    with open(stdout_filename, "w") as fout:
        fout.write(stdout_text)

    # Write stderr to file
    with open(stderr_filename, "w") as fout:
        fout.write(stderr_text)

    return exit_code


# TODO: intendo - 2021/05/10 - Break run_job into multiple functions
#                              to reduce complexity.
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
        if "job_date" not in job_info:
            _LOGGER.error("ERROR: Missing job date for job, %s", job)
            return ret_val
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
    job_tag = f"{job_info['job_date']}/{job_info['job_id']}"
    rundir = f"{GLOBAL_VARS['JOB_PATH']}{job_tag}"
    inbucket = job_info["bucket_name"]

    # Prepare job directory and download input files
    makedirs(rundir, exist_ok=True)
    chdir(rundir)

    for file in job_info["input_files"]:
        if "https" in file:
            name = f"{job_tag}/{file.split('/')[-1]}"
            try:
                request.urlretrieve(file, f"{GLOBAL_VARS['JOB_PATH']}{name}")
            except Exception as error:
                # TODO: intendo 2021/05/05 - Find more specific exception
                _LOGGER.exception(
                    "%s ERROR: Download failed for file, %s \n\t%s",
                    job_tag,
                    name,
                    error,
                )
                update_status(
                    s3client,
                    job_tag,
                    job_type,
                    JOBSTATUS.FAILED,
                    [],
                    "Failed to download input file. Job did not run.",
                )
                return cleanup_job(job_tag, rundir)

        else:
            try:
                s3client.download_file(
                    inbucket, file, f"{GLOBAL_VARS['JOB_PATH']}{file}"
                )
            except Exception as error:
                # TODO: intendo 2021/05/05 - Find more specific exception
                _LOGGER.exception(
                    "%s ERROR: Download failed for file, %s \n\t%s",
                    job_tag,
                    file,
                    error,
                )
                update_status(
                    s3client,
                    job_tag,
                    job_type,
                    JOBSTATUS.FAILED,
                    [],
                    "Failed to download input file. Job did not run.",
                )
                return cleanup_job(job_tag, rundir)

    # Run job and record associated metrics
    update_status(
        s3client,
        job_tag,
        job_type,
        JOBSTATUS.RUNNING,
        [],
    )

    # TODO: (Eo300) consider moving binary
    #       command (e.g. 'apbs', 'pdb2pqr30') into SQS message
    if JOBTYPE.APBS.name.lower() in job_type:
        command = f"apbs {job_info['command_line_args']}"
    elif JOBTYPE.PDB2PQR.name.lower() in job_type:
        command = f"pdb2pqr30 {job_info['command_line_args']}"
    else:
        raise KeyError(f"Invalid job type, {job_type}")

    if "max_run_time" in job_info:
        sqs = client("sqs", region_name=GLOBAL_VARS["AWS_REGION"])
        sqs.change_message_visibility(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle,
            VisibilityTimeout=int(job_info["max_run_time"]),
        )

    # Execute job binary with appropriate arguments and record metrics
    try:
        metrics.start_time = time()
        metrics.exit_code = execute_command(
            job_tag,
            command,
            f"{job_type}.stdout.txt",
            f"{job_type}.stderr.txt",
        )
        metrics.end_time = time()

        # We need to create the {job_type}-metrics.json before we upload
        # the files to the S3_TOPLEVEL_BUCKET.
        metrics.write_metrics(job_tag, job_type, ".")
    except Exception as error:
        # TODO: intendo 2021/05/05 - Find more specific exception
        _LOGGER.exception(
            "%s ERROR: Failed to execute job: %s",
            job_tag,
            error,
        )
        # TODO: Should this return 1 because noone else will succeed?
        ret_val = 1

    # Upload directory contents to S3
    for file in listdir("."):
        try:
            file_path = f"{job_tag}/{file}"
            _LOGGER.info(
                "%s Uploading file to output bucket, %s", job_tag, file
            )
            s3client.upload_file(
                f"{GLOBAL_VARS['JOB_PATH']}{file_path}",
                GLOBAL_VARS["S3_TOPLEVEL_BUCKET"],
                f"{file_path}",
            )
        except ClientError as error:
            _LOGGER.exception(
                "%s ERROR: Failed to upload file, %s \n\t%s",
                job_tag,
                f"{job_tag}/{file}",
                error,
            )
        # ret_val = 1

    # TODO: 2021/03/30, Elvis - Will need to address how we bundle output
    #       subdirectory for PDB2PKA when used; I previous bundled it as
    #       a compressed tarball (i.e. "{job_id}-pdb2pka_output.tar.gz")

    # Create list of output files
    input_files_no_id = [  # Remove job_id prefix from input file list
        "".join(name.split("/")[-1]) for name in job_info["input_files"]
    ]
    output_files = [
        f"{job_tag}/{filename}"
        for filename in listdir(".")
        if filename not in input_files_no_id
    ]

    # Cleanup job directory and update status
    cleanup_job(job_tag, rundir)
    update_status(
        s3client,
        job_tag,
        job_type,
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

    s3client = client("s3")
    sqs = client("sqs", region_name=GLOBAL_VARS["AWS_REGION"])
    queue_url = sqs.get_queue_url(QueueName=GLOBAL_VARS["QUEUE"])
    qurl = queue_url["QueueUrl"]
    lasttime = datetime.now()

    metrics = JobMetrics()

    # The structure of the SQS messages is documented at:
    # https://docs.aws.amazon.com/AWSSimpleQueueService/
    # latest/APIReference/API_ReceiveMessage.html
    messages = get_messages(sqs, qurl)
    while messages:
        for idx in messages["Messages"]:
            run_job(idx["Body"], s3client, metrics, qurl, idx["ReceiptHandle"])
            sqs.delete_message(
                QueueUrl=qurl, ReceiptHandle=idx["ReceiptHandle"]
            )
        while not PROCESSING:
            sleep(10)
        messages = get_messages(sqs, qurl)
    _LOGGER.info("DONE: %s", str(datetime.now() - lasttime))


if __name__ == "__main__":
    update_environment(None, None)

    signal.signal(signal.SIGHUP, signal_help)
    signal.signal(signal.SIGINT, receive_signal)
    signal.signal(signal.SIGQUIT, receive_signal)
    signal.signal(signal.SIGILL, receive_signal)
    signal.signal(signal.SIGTRAP, receive_signal)
    signal.signal(signal.SIGABRT, receive_signal)
    signal.signal(signal.SIGBUS, receive_signal)
    signal.signal(signal.SIGFPE, receive_signal)
    # signal.signal(signal.SIGKILL, receiveSignal)
    signal.signal(signal.SIGUSR1, update_environment)
    signal.signal(signal.SIGSEGV, receive_signal)
    signal.signal(signal.SIGUSR2, toggle_processing)
    signal.signal(signal.SIGPIPE, receive_signal)
    signal.signal(signal.SIGALRM, receive_signal)
    signal.signal(signal.SIGTERM, terminate_process)

    parser = build_parser()
    args = parser.parse_args()

    if args.verbose:
        GLOBAL_VARS["LOG_LEVEL"] = DEBUG
        _LOGGER.setLevel(GLOBAL_VARS["LOG_LEVEL"])

    main()
