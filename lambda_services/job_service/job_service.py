"""Interpret APBS/PDBP2QR job configurations and submit to SQS."""
from json import dumps, loads, JSONDecodeError
from os import getenv
from time import time
from logging import basicConfig, getLogger, INFO, StreamHandler
from boto3 import client, resource
from botocore.exceptions import ClientError
from .launcher import pdb2pqr_runner, apbs_runner
from .launcher.jobsetup import MissingFilesError

OUTPUT_BUCKET = getenv("OUTPUT_BUCKET")
FARGATE_CLUSTER = getenv("FARGATE_CLUSTER")
FARGATE_SERVICE = getenv("FARGATE_SERVICE")
# Could use SQS URL below instead of a queue name; whichever is easier
SQS_QUEUE_NAME = getenv("JOB_QUEUE_NAME")
JOB_MAX_RUNTIME = int(getenv("JOB_MAX_RUNTIME", 2000))

# Initialize logger
_LOGGER = getLogger(__name__)
basicConfig(
    format="[%(filename)s:%(lineno)s:%(funcName)s()] %(message)s",
    level=getenv("LOG_LEVEL", str(INFO)),
    handlers=[StreamHandler],
)


def get_job_info(
    job_tag: str, bucket_name: str, info_object_name: str
) -> dict:
    """Retrieve job configuraiton JSON object from S3, and return as dict.

    :param job_tag str: Unique ID for this job
    :param bucket_name str: AWS S3 bucket to retrieve file from
    :param info_object_name str: The name of the file to download
    :return: A dictionary of the JSON object representing a job configuration
    :rtype: dict
    """

    # Download job info object from S3
    object_response = {}
    try:
        object_response = client("s3").get_object(
            Bucket=bucket_name,
            Key=info_object_name,
        )
    except (ClientError) as err:
        _LOGGER.exception(
            "%s Unable to get object for Bucket, %s, and Key, %s: %s",
            f"{bucket_name}/{info_object_name}",
            bucket_name,
            info_object_name,
            err,
        )
        raise

    # Convert content of JSON file to dict
    try:
        job_info: dict = loads(object_response["Body"].read().decode("utf-8"))
        _LOGGER.info("%s Found job_info: %s", job_tag, job_info)
        return job_info
    except JSONDecodeError as jerr:
        _LOGGER.exception(
            "%s Can't decode JSON: %s, (%s)",
            bucket_name,
            object_response,
            jerr,
        )
    except Exception as jerr:
        _LOGGER.exception(
            "%s Can't loads JSON: %s, (%s)",
            bucket_name,
            object_response,
            jerr,
        )
        raise


def build_status_dict(
    job_id: str,
    job_tag: str,
    job_type: str,
    status: str,
    inputfile_list: list,
    outputfile_list: list,
    message: str = None,
) -> dict:
    """Build a dictionary for the initial status

    :param job_id str: Identifier string for specific job
    :param job_type str: Name of job type (e.g. 'apbs', 'pdb2pqr')
    :param status str: A string indicating initial status of job
    :param inputfile_list list: List of current input files
    :param outputfile_list list: List of current output files
    :param message: Optional message to add to status
    :type message: optional

    :return: a JSON-compatible dictionary containing initial status
             info of the job
    :rtype: dict
    """

    # TODO: 2021/03/02, Elvis - add submission time to initial status
    # TODO: 2021/03/25, Elvis - Reconstruct format of status since
    #                           they're constructed on a per-job basis

    initial_status_dict = {
        "jobid": job_id,
        "jobtype": job_type,
        job_type: {
            "status": status,
            "startTime": time(),
            "endTime": None,
            "subtasks": [],
            "inputFiles": inputfile_list,
            "outputFiles": outputfile_list,
        },
    }

    # if message is not None:
    if status == "invalid":
        initial_status_dict[job_type]["message"] = message
        initial_status_dict[job_type]["startTime"] = None
        initial_status_dict[job_type]["subtasks"] = None
        initial_status_dict[job_type]["inputFiles"] = None
        initial_status_dict[job_type]["outputFiles"] = None

    _LOGGER.info("%s Initial Status: %s", job_tag, initial_status_dict)
    return initial_status_dict


def upload_status_file(object_filename: str, initial_status_dict: dict):
    """Upload the initial status object to S3

    :param object_filename str: the name of the file to download
    :param initial_status_dict dict: a JSON-compatible dictionary containing
                                     initial status info of the job
    """
    # TODO: 2021/03/02, Elvis - add submission time to initial status
    # TODO: 2021/03/25, Elvis - Reconstruct format of status since
    #                           they're constructed on a per-job basis

    s3_client = client("s3")
    s3_client.put_object(
        Body=dumps(initial_status_dict),
        Bucket=OUTPUT_BUCKET,
        Key=object_filename,
    )


def interpret_job_submission(event: dict, context):
    # pylint: disable=unused-argument
    """Interpret contents of job configuration, triggered from S3 event.

    :param event dict: Amazon S3 event, containing info to retrieve contents
    :param context: context object for AWS Lambda handler, containing info
                    about the invocation, function, and execution environment
    """

    # Get basic job information from S3 event
    #   TODO: will need to modify to correctly retrieve info
    jobinfo_object_name: str = event["Records"][0]["s3"]["object"]["key"]
    bucket_name: str = event["Records"][0]["s3"]["bucket"]["name"]
    job_id, jobinfo_filename = jobinfo_object_name.split("/")[-2:]
    job_date: str = jobinfo_object_name.split("/")[0]
    job_tag = f"{job_date}/{job_id}"
    # Assumes 'pdb2pqr-job.json', or similar format
    job_type = jobinfo_filename.split("-")[0]

    input_files = None
    output_files = None
    job_runner = None
    message = None
    status = "pending"
    timeout_seconds = None
    job_info_form = get_job_info(job_tag, bucket_name, jobinfo_object_name)[
        "form"
    ]
    if job_type in "pdb2pqr":
        # If PDB2PQR:
        #   - Obtain job configuration from config file
        #   - Use weboptions if from web
        #   - Interpret as is if using only command line args
        job_runner = pdb2pqr_runner.Runner(job_info_form, job_id, job_date)
        job_command_line_args = job_runner.prepare_job()

    elif job_type in "apbs":
        # If APBS:
        #   - Obtain job configuration from config file
        #   - Use form data to interpret job
        job_runner = apbs_runner.Runner(job_info_form, job_id, job_date)
        try:
            job_command_line_args = job_runner.prepare_job(
                OUTPUT_BUCKET, bucket_name
            )
        except MissingFilesError as err:
            status = "failed"
            message = (
                f"Files specified but not found: {err.missing_files}. "
                f"Please check that all files upload before resubmitting."
            )
    else:
        # If no valid job type
        #   - Construct "invalid" status
        #   - Log and (maybe) raise exception
        status = "invalid"
        message = "Invalid job type. No job executed"
        _LOGGER.error("%s Invalid job type - Job Type: %s", job_id, job_type)

    if job_type in ("apbs", "pdb2pqr"):
        input_files = job_runner.input_files
        output_files = job_runner.output_files
        timeout_seconds = job_runner.estimated_max_runtime

    # Create and upload status file to S3
    status_filename = f"{job_type}-status.json"
    status_object_name = f"{job_tag}/{status_filename}"
    initial_status: dict = build_status_dict(
        job_id, job_tag, job_type, status, input_files, output_files, message
    )
    _LOGGER.info(
        "%s Uploading status file, %s: %s",
        job_tag,
        status_object_name,
        initial_status,
    )
    upload_status_file(status_object_name, initial_status)

    # Submit run info to SQS
    if status not in ("invalid", "failed"):
        if timeout_seconds is None:
            timeout_seconds = JOB_MAX_RUNTIME

        sqs_json = {
            "job_date": job_date,
            "job_id": job_id,
            "job_tag": job_tag,
            "job_type": job_type,
            "bucket_name": bucket_name,
            "input_files": job_runner.input_files,
            "command_line_args": job_command_line_args,
            "max_run_time": timeout_seconds,
        }
        sqs_client = resource("sqs")
        queue = sqs_client.get_queue_by_name(QueueName=SQS_QUEUE_NAME)
        _LOGGER.info("%s Sending message to queue: %s", job_tag, sqs_json)
        queue.send_message(MessageBody=dumps(sqs_json))
