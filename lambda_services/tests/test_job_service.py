"""Tests for interpreting and handling job configuration submissions."""
# NOTE: importing entire job_service us to modify module's global variables
from lambda_services.job_service import job_service
from time import time
from datetime import date
from json import dumps, load, loads
from moto import mock_s3, mock_sqs
from boto3 import client
import pytest


@pytest.fixture
def initialize_input_bucket():
    """Create an input bucket to perform test. Returns name of bucket"""
    bucket_name = "pytest_input_bucket"
    with mock_s3():
        s3_client = client("s3")
        s3_client.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={
                "LocationConstraint": "us-west-2",
            },
        )
        yield s3_client, bucket_name


@pytest.fixture
def initialize_output_bucket():
    """Create an output bucket to perform test. Returns name of bucket"""
    bucket_name = "pytest_output_bucket"
    with mock_s3():
        s3_client = client("s3")
        s3_client.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={
                "LocationConstraint": "us-west-2",
            },
        )
        yield s3_client, bucket_name


@pytest.fixture
def initialize_input_and_output_bucket():
    """
    Create S3 input/output buckets to perform test.
    Returns client and bucket names
    """
    input_bucket_name = "pytest_input_bucket"
    output_bucket_name = "pytest_output_bucket"
    with mock_s3():
        s3_client = client("s3")
        s3_client.create_bucket(
            Bucket=input_bucket_name,
            CreateBucketConfiguration={
                "LocationConstraint": "us-west-2",
            },
        )
        s3_client.create_bucket(
            Bucket=output_bucket_name,
            CreateBucketConfiguration={
                "LocationConstraint": "us-west-2",
            },
        )
        yield s3_client, input_bucket_name, output_bucket_name


@pytest.fixture
def initialize_job_queue():
    """
    Create an job queue queue to perform test.
    Returns client and name of bucket
    """
    queue_name = "pytest_sqs_job_queue"
    region_name = "us-west-2"
    with mock_sqs():
        sqs_client = client("sqs", region_name=region_name)
        sqs_client.create_queue(QueueName=queue_name)
        yield sqs_client, queue_name, region_name


def test_get_job_info(initialize_input_bucket):
    # Retrieve initialized AWS client and bucket name
    s3_client, bucket_name = initialize_input_bucket

    # Read sample input JSON file into dict
    input_name = "lambda_services/tests/input_data/sample_web-pdb2pqr-job.json"
    expected_pdb2pqr_job_info: dict
    with open(input_name) as fin:
        expected_pdb2pqr_job_info = load(fin)

    # Upload json for job config file
    object_name = "pytest/sample_web-pdb2pqr-job.json"
    s3_client.put_object(
        Bucket=bucket_name,
        Key=object_name,
        Body=dumps(expected_pdb2pqr_job_info),
    )

    # Download using get_job_info()
    job_info: dict = job_service.get_job_info(bucket_name, object_name)

    # Verify output is dictionary and contents match input
    # TODO: Eo300 - check if '==' comparison is sufficient
    assert job_info == expected_pdb2pqr_job_info


def test_build_status_dict_valid_job():
    """Test funciton for initial status creation for valid jobtypes"""

    # Valid job
    job_id = "sampleId"
    job_type = "apbs"
    input_files = ["sampleId.in", "1fas.pqr"]
    output_files = []
    job_status = "pending"
    status_dict: dict = job_service.build_status_dict(
        job_id, job_type, job_status, input_files, output_files, message=None
    )
    assert "jobid" in status_dict
    assert "jobtype" in status_dict
    assert job_type in status_dict
    assert "status" in status_dict[job_type]
    assert status_dict[job_type]["status"] == "pending"
    assert status_dict[job_type]["endTime"] is None
    assert isinstance(status_dict[job_type]["startTime"], float)
    assert isinstance(status_dict[job_type]["inputFiles"], list)
    assert isinstance(status_dict[job_type]["outputFiles"], list)


def test_build_status_dict_invalid_job():
    """Test funciton for initial status creation for invalid jobtypes"""

    # Invalid job
    job_id = "sampleId"
    job_type = "nonsenseJobType"
    input_files = None
    output_files = None
    job_status = "invalid"
    invalid_message = "Invalid job type"
    status_dict: dict = job_service.build_status_dict(
        job_id,
        job_type,
        job_status,
        input_files,
        output_files,
        message=invalid_message,
    )
    assert "status" in status_dict[job_type]
    assert "message" in status_dict[job_type]
    assert status_dict[job_type]["status"] == "invalid"
    assert status_dict[job_type]["startTime"] is None
    assert status_dict[job_type]["inputFiles"] is None
    assert status_dict[job_type]["outputFiles"] is None
    # assert status_dict[job_type]["subtasks"] == None


def test_upload_status_file(initialize_output_bucket):
    # Retrieve initialized AWS client and bucket name
    s3_client, bucket_name = initialize_output_bucket

    # Retrieve original global variable names from module
    original_OUTPUT_BUCKET = job_service.OUTPUT_BUCKET

    # Create sample status dict
    job_id = "sampleId"
    job_type = "pdb2pqr"
    current_date = date.today().isoformat()
    sample_status: dict = {
        "jobid": job_id,
        "jobtype": job_type,
        job_type: {
            "status": "pending",
            "startTime": time(),
            "endTime": None,
            "subtasks": [],
            "inputFiles": [f"{current_date}/{job_id}/1fas.pdb"],
            "outputFiles": [],
        },
    }

    # Upload dict to S3 as JSON
    status_objectname: str = f"{current_date}/{job_id}/{job_type}-status.json"
    job_service.OUTPUT_BUCKET = bucket_name
    job_service.upload_status_file(status_objectname, sample_status)

    # Download JSON from S3, parse into dict
    s3_resp: dict = s3_client.get_object(
        Bucket=bucket_name, Key=status_objectname
    )
    downloaded_object_data: dict = loads(s3_resp["Body"].read())

    # Compare downloaded dict with expected (sample dict)
    assert downloaded_object_data == sample_status

    # Reset module global variables to original state
    job_service.OUTPUT_BUCKET = original_OUTPUT_BUCKET


def test_interpret_job_submission_pdb2pqr(
    initialize_input_and_output_bucket, initialize_job_queue
):
    # Retrieve initialized AWS client and bucket name
    (
        s3_client,
        input_bucket_name,
        output_bucket_name,
    ) = initialize_input_and_output_bucket
    sqs_client, queue_name, region_name = initialize_job_queue

    # Retrieve original global variable names from module
    original_OUTPUT_BUCKET = job_service.OUTPUT_BUCKET
    original_SQS_QUEUE_NAME = job_service.SQS_QUEUE_NAME
    original_JOB_QUEUE_REGION = job_service.JOB_QUEUE_REGION

    # Initialize job variables
    job_id = "sampleId"
    job_date = "2021-05-16"

    # Upload PDB2PQR job JSON to input bucket
    input_name = "lambda_services/tests/input_data/sample_web-pdb2pqr-job.json"
    expected_pdb2pqr_job_info: dict
    with open(input_name) as fin:
        expected_pdb2pqr_job_info = load(fin)

    object_name = f"{job_date}/{job_id}/pdb2pqr-sample-job.json"
    s3_client.put_object(
        Bucket=input_bucket_name,
        Key=object_name,
        Body=dumps(expected_pdb2pqr_job_info),
    )

    # Setup dict with expected S3 trigger content
    s3_event: dict
    s3_event_filepath = (
        "lambda_services/tests/input_data/sample_web-pdb2pqr-s3_trigger.json"
    )
    with open(s3_event_filepath) as fin:
        s3_event = load(fin)

    # Set module globals and interpret PDB2PQR job trigger
    job_service.SQS_QUEUE_NAME = queue_name
    job_service.OUTPUT_BUCKET = output_bucket_name
    job_service.JOB_QUEUE_REGION = region_name
    job_service.interpret_job_submission(s3_event, None)

    # Obtain SQS message
    queue_url: str = sqs_client.get_queue_url(QueueName=queue_name)["QueueUrl"]
    queue_message_response = sqs_client.receive_message(
        QueueUrl=queue_url, MaxNumberOfMessages=1
    )
    queue_message = queue_message_response["Messages"][0]
    message_contents: dict = loads(queue_message["Body"])
    message_receipt_handle = queue_message["ReceiptHandle"]
    # print(f"message_contents: {dumps(message_contents, indent=2)}")

    # Declare expected output of SQS message
    expected_output: dict = {
        "job_id": "sampleId",
        "job_type": "pdb2pqr",
        "job_date": "2021-05-16",
        "bucket_name": "pytest_input_bucket",
        "input_files": ["https://files.rcsb.org/download/1fas.pdb"],
        "command_line_args": "--with-ph=7.0 --ph-calc-method=propka --drop-water --apbs-input --ff=parse --verbose  1fas.pdb sampleId.pqr",  # noqa: E501
        "max_run_time": 2700,
    }

    # Compare queue contents with expected
    assert expected_output == message_contents

    # Delete message from SQS queue
    sqs_client.delete_message(
        QueueUrl=queue_url, ReceiptHandle=message_receipt_handle
    )

    # Reset module global variables to original state
    job_service.SQS_QUEUE_NAME = original_SQS_QUEUE_NAME
    job_service.OUTPUT_BUCKET = original_OUTPUT_BUCKET
    job_service.JOB_QUEUE_REGION = original_JOB_QUEUE_REGION


def test_interpret_job_submission_apbs(
    initialize_input_and_output_bucket, initialize_job_queue
):
    # Retrieve initialized AWS client and bucket name
    # Retrieve original global variable names from module

    # Upload APBS job JSON to input bucket
    # Setup dict with expected S3 trigger content
    # Set module globals and interpret APBS job trigger

    # Obtain SQS message

    # Declare expected output of SQS message
    # Compare queue contents with expected

    # Delete message from SQS queue
    # Reset module global variables to original state
    pass


def test_interpret_job_submission_invalid(
    initialize_input_and_output_bucket, initialize_job_queue
):
    # Retrieve initialized AWS client and bucket name
    # Retrieve original global variable names from module

    # Upload JSON for invalid jobtype
    # Setup dict with expected S3 trigger content
    # Set module globals and inTerpret invalid job trigger

    # Obtain SQS message

    # Declare expected output of SQS message
    # Compare queue contents with expected

    # Reset module global variables to original state
    pass
