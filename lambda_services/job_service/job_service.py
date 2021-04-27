"""Interpret APBS/PDBP2QR job configurations and submit to SQS."""
import os
import time
import json
import logging
import boto3
from .launcher import pdb2pqr_runner, apbs_runner

OUTPUT_BUCKET = os.getenv("OUTPUT_BUCKET")
FARGATE_CLUSTER = os.getenv("FARGATE_CLUSTER")
FARGATE_SERVICE = os.getenv("FARGATE_SERVICE")
# Could use SQS URL below instead of a queue name; whichever is easier
SQS_QUEUE_NAME = os.getenv("JOB_QUEUE_NAME")
JOB_MAX_RUNTIME = int(os.getenv("JOB_MAX_RUNTIME",2000))

# Initialize logger
LOGGER = logging.getLogger()
LOGGER.setLevel(os.getenv("LOG_LEVEL", "INFO"))


def get_job_info(bucket_name: str, info_object_name: str) -> dict:
    """Retrieve job configuraiton JSON object from S3, and return as dict.

    :param bucket_name str: AWS S3 bucket to retrieve file from
    :param info_object_name str: The name of the file to download
    :return: A dictionary of the JSON object representing a job configuration
    :rtype: dict
    """

    # Download job info object from S3
    s3_client = boto3.client("s3")
    object_response: dict = s3_client.get_object(
        Bucket=bucket_name,
        Key=info_object_name,
    )

    # Convert content of JSON file to dict
    try:
        job_info: dict = json.loads(
            object_response["Body"].read().decode("utf-8")
        )
        return job_info
    except Exception:
        raise


def build_status_dict(
    job_id: str,
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

    job_start_time = time.time()
    initial_status_dict = {
        "jobid": job_id,
        "jobtype": job_type,
        job_type: {
            "status": status,
            "startTime": job_start_time,
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

    s3_client = boto3.client("s3")
    s3_client.put_object(
        Body=json.dumps(initial_status_dict),
        Bucket=OUTPUT_BUCKET,
        Key=object_filename,
    )


def interpret_job_submission(event: dict, context=None):
    """Interpret contents of job configuration, triggered from S3 event.

    :param event dict: Amazon S3 event, containing info to retrieve contents
    :param context: *fill in later*
    """

    # Get basic job information from S3 event
    #   TODO: will need to modify to correctly retrieve info
    jobinfo_object_name: str = event["Records"][0]["s3"]["object"]["key"]
    bucket_name: str = event["Records"][0]["s3"]["bucket"]["name"]
    job_id, jobinfo_filename = jobinfo_object_name.split("/")[-2:]
    job_date: str = jobinfo_object_name.split("/")[0]
    # Assumes 'pdb2pqr-job.json', or similar format
    job_type = jobinfo_filename.split('-')[0]

    # If PDB2PQR:
    #   - Obtain job configuration from config file
    #   - Use weboptions if from web
    #   - Interpret as is if using only command line args
    input_files = None
    output_files = None
    message = None
    status = "pending"
    timeout_seconds = None
    if job_type == "pdb2pqr":
        job_info_form = get_job_info(bucket_name, jobinfo_object_name)["form"]
        job_runner = pdb2pqr_runner.Runner(job_info_form, job_id)
        job_command_line_args = job_runner.prepare_job()
        input_files = job_runner.input_files
        output_files = job_runner.output_files
        timeout_seconds = job_runner.estimated_max_runtime

    # If APBS:
    #   - Obtain job configuration from config file
    #   - Use form data to interpret job
    elif job_type == "apbs":
        job_info_form = get_job_info(bucket_name, jobinfo_object_name)["form"]
        job_runner = apbs_runner.Runner(job_info_form, job_id)
        job_command_line_args = job_runner.prepare_job(
            OUTPUT_BUCKET, bucket_name
        )
        input_files = job_runner.input_files
        output_files = job_runner.output_files
        timeout_seconds = job_runner.estimated_max_runtime

    # If no valid job type
    #   - Construct "invalid" status
    #   - Log and (maybe) raise exception
    else:
        status = "invalid"
        message = "Invalid job type. No job executed"
        LOGGER.error(
            "Invalid job type - Job ID: %s, Job Type: %s", job_id, job_type
        )

    # Create and upload status file to S3
    status_filename = f"{job_type}-status.json"
    status_object_name = f"{job_id}/{status_filename}"
    initial_status: dict = build_status_dict(
        job_id, job_type, status, input_files, output_files, message
    )
    upload_status_file(status_object_name, initial_status)

    # Submit run info to SQS
    if status != "invalid":
        if timeout_seconds is None:
            timeout_seconds = JOB_MAX_RUNTIME

        sqs_json = {
            "job_id": job_id,
            "job_type": job_type,
            "bucket_name": bucket_name,
            "input_files": job_runner.input_files,
            "command_line_args": job_command_line_args,
            "max_run_time": timeout_seconds,
        }
        sqs_client = boto3.resource("sqs")
        queue = sqs_client.get_queue_by_name(QueueName=SQS_QUEUE_NAME)
        queue.send_message(MessageBody=json.dumps(sqs_json))
