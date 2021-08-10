"""Tests for interpreting and handling job configuration submissions."""
# NOTE: importing entire job_service us to modify module's global variables
from datetime import date
from json import dumps, load, loads
from pathlib import Path
from time import time
from typing import Union
from moto import mock_s3, mock_sqs
from boto3 import client
from lambda_services.job_service import job_service
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


def upload_data(s3_client, bucket_name: str, object_name: str, data):
    """
    Use S3 PUT to upload object data.
    """
    s3_client.put_object(
        Bucket=bucket_name,
        Key=object_name,
        Body=data,
    )


def download_data(
    s3_client, bucket_name: str, object_name: str
) -> Union[str, bytes]:
    """
    Use S3 GET to download object data.
    Returns the data in string or bytes.
    """
    s3_resp: dict = s3_client.get_object(Bucket=bucket_name, Key=object_name)
    return s3_resp["Body"].read()


def create_version_bucket_and_file(
    bucket_name: str, region_name: str, version_key: str
):
    s3_client = client("s3")
    s3_client.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={
            "LocationConstraint": region_name,
        },
    )
    with open("tests/input_data/versions.json") as fin:
        upload_data(s3_client, bucket_name, version_key, fin.read())


@pytest.fixture
def initialize_version_environment():
    version_bucket = "pytest_version_bucket"
    version_key = "info/versions.json"
    region_name = "us-west-2"

    with mock_s3():
        create_version_bucket_and_file(
            version_bucket, region_name, version_key
        )

        original_VERSION_BUCKET = job_service.VERSION_BUCKET
        original_VERSION_KEY = job_service.VERSION_KEY
        job_service.VERSION_BUCKET = version_bucket
        job_service.VERSION_KEY = version_key

        yield

        # Reset state of environment variables
        job_service.VERSION_BUCKET = original_VERSION_BUCKET
        job_service.VERSION_KEY = original_VERSION_KEY


def test_get_job_info(initialize_input_bucket):
    # Retrieve initialized AWS client and bucket name
    s3_client, bucket_name = initialize_input_bucket

    # Read sample input JSON file into dict
    input_name = Path.cwd() / Path(
        "tests/input_data/sample_web-pdb2pqr-job.json"
    )
    expected_pdb2pqr_job_info: dict
    with open(input_name) as fin:
        expected_pdb2pqr_job_info = load(fin)

    # Upload json for job config file
    object_name = "pytest/sample_web-pdb2pqr-job.json"
    upload_data(
        s3_client, bucket_name, object_name, dumps(expected_pdb2pqr_job_info)
    )

    # Download using get_job_info()
    job_info: dict = job_service.get_job_info(
        "2021-05-21/sampleId", bucket_name, object_name
    )

    # Verify output is dictionary and contents match input
    # TODO: Eo300 - check if '==' comparison is sufficient
    assert job_info == expected_pdb2pqr_job_info


def test_build_status_dict_valid_job(initialize_version_environment):
    """Test funciton for initial status creation for valid jobtypes"""

    # Valid job
    job_id = "sampleId"
    job_tag = f"2021-05-21/{job_id}"
    job_type = "apbs"
    input_files = ["sampleId.in", "1fas.pqr"]
    output_files = []
    job_status = "pending"
    status_dict: dict = job_service.build_status_dict(
        job_id,
        job_tag,
        job_type,
        job_status,
        input_files,
        output_files,
        message=None,
    )
    assert "jobid" in status_dict
    # assert "jobtag" in status_dict
    assert "jobtype" in status_dict
    assert job_type in status_dict
    assert "status" in status_dict[job_type]
    assert status_dict[job_type]["status"] == "pending"
    assert status_dict[job_type]["endTime"] is None
    assert isinstance(status_dict[job_type]["startTime"], float)
    assert isinstance(status_dict[job_type]["inputFiles"], list)
    assert isinstance(status_dict[job_type]["outputFiles"], list)


def test_build_status_dict_invalid_job(initialize_version_environment):
    """Test funciton for initial status creation for invalid jobtypes"""

    # Invalid job
    job_id = "sampleId"
    job_tag = f"2021-05-21/{job_id}"
    job_type = "nonsenseJobType"
    input_files = None
    output_files = None
    job_status = "invalid"
    invalid_message = "Invalid job type"
    status_dict: dict = job_service.build_status_dict(
        job_id,
        job_tag,
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
    downloaded_object_data: str = loads(
        download_data(s3_client, bucket_name, status_objectname)
    )

    # Compare downloaded dict with expected (sample dict)
    assert downloaded_object_data == sample_status

    # Reset module global variables to original state
    job_service.OUTPUT_BUCKET = original_OUTPUT_BUCKET


def test_interpret_job_submission_invalid(
    initialize_input_and_output_bucket, initialize_job_queue
):
    # Retrieve initialized AWS client and bucket name
    (
        s3_client,
        input_bucket_name,
        output_bucket_name,
    ) = initialize_input_and_output_bucket
    sqs_client, queue_name, region_name = initialize_job_queue

    # Initialize version-related variables
    version_bucket = "pytest_version_bucket"
    version_key = "info/versions.json"
    create_version_bucket_and_file(version_bucket, region_name, version_key)
    original_VERSION_BUCKET = job_service.VERSION_BUCKET
    original_VERSION_KEY = job_service.VERSION_KEY

    # Retrieve original global variable names from module
    original_OUTPUT_BUCKET = job_service.OUTPUT_BUCKET
    original_SQS_QUEUE_NAME = job_service.SQS_QUEUE_NAME
    original_JOB_QUEUE_REGION = job_service.JOB_QUEUE_REGION

    # Initialize job variables
    job_id = "sampleId"
    job_type = "invalidJobType"
    job_date = "2021-05-16"

    # Upload JSON for invalid jobtype
    input_name = Path.cwd() / Path("tests/input_data/invalid-job.json")
    invalid_job_info: dict
    with open(input_name) as fin:
        invalid_job_info = load(fin)
    job_object_name = f"{job_date}/{job_id}/{job_type}-sample-job.json"
    upload_data(
        s3_client, input_bucket_name, job_object_name, dumps(invalid_job_info)
    )

    # Setup dict with expected S3 trigger content
    s3_event: dict
    s3_event_filepath = Path.cwd() / Path(
        "tests/input_data/invalid_job-s3_trigger.json"
    )
    with open(s3_event_filepath) as fin:
        s3_event = load(fin)

    # Set module globals and inTerpret invalid job trigger
    job_service.SQS_QUEUE_NAME = queue_name
    job_service.OUTPUT_BUCKET = output_bucket_name
    job_service.JOB_QUEUE_REGION = region_name
    job_service.VERSION_BUCKET = version_bucket
    job_service.VERSION_KEY = version_key
    job_service.interpret_job_submission(s3_event, None)

    # Obtain SQS message
    queue_url: str = sqs_client.get_queue_url(QueueName=queue_name)["QueueUrl"]
    queue_message_response = sqs_client.receive_message(
        QueueUrl=queue_url, MaxNumberOfMessages=1
    )

    """Job type invalid: there should be no messages in queue"""
    assert "Messages" not in queue_message_response

    # Get status from output bucket
    status_object_name = f"{job_date}/{job_id}/{job_type}-status.json"
    status_object_data: dict = loads(
        download_data(s3_client, output_bucket_name, status_object_name)
    )

    """Check for expected values if invalid jobtype"""
    assert status_object_data["jobid"] == "sampleId"
    assert status_object_data["jobtype"] == job_type
    assert job_type in status_object_data
    assert "message" in status_object_data[job_type]
    assert status_object_data[job_type]["status"] == "invalid"
    assert status_object_data[job_type]["inputFiles"] is None
    assert status_object_data[job_type]["outputFiles"] is None
    assert status_object_data[job_type]["startTime"] is None
    assert status_object_data[job_type]["endTime"] is None

    # Reset module global variables to original state
    job_service.SQS_QUEUE_NAME = original_SQS_QUEUE_NAME
    job_service.OUTPUT_BUCKET = original_OUTPUT_BUCKET
    job_service.JOB_QUEUE_REGION = original_JOB_QUEUE_REGION
    job_service.VERSION_BUCKET = original_VERSION_BUCKET
    job_service.VERSION_KEY = original_VERSION_KEY


def initialize_s3_and_sqs_clients(
    input_bucket_name: str,
    output_bucket_name: str,
    queue_name: str,
    region_name: str,
):

    sqs_client = client("sqs", region_name=region_name)
    sqs_client.create_queue(QueueName=queue_name)

    s3_client = client("s3")
    s3_client.create_bucket(
        Bucket=input_bucket_name,
        CreateBucketConfiguration={
            "LocationConstraint": region_name,
        },
    )
    s3_client.create_bucket(
        Bucket=output_bucket_name,
        CreateBucketConfiguration={
            "LocationConstraint": region_name,
        },
    )

    return s3_client, sqs_client


INPUT_JOB_LIST: list = []
EXPECTED_OUTPUT_LIST: list = []
with open(
    Path.cwd() / Path("tests/input_data/test-job_service-input.json")
) as fin:
    INPUT_JOB_LIST = load(fin)
with open(
    Path.cwd() / Path("tests/expected_data/test-job_service-output.json")
) as fin:
    EXPECTED_OUTPUT_LIST = load(fin)


@mock_s3
@mock_sqs
@pytest.mark.parametrize(
    "apbs_test_job,expected_output",
    list(zip(INPUT_JOB_LIST, EXPECTED_OUTPUT_LIST)),
)
def test_interpret_job_submission_success(
    apbs_test_job: dict, expected_output: dict
):
    s3_event: dict = apbs_test_job["trigger"]
    job_info: dict = apbs_test_job["job"]
    expected_sqs_message: dict = expected_output["sqs_message"]
    expected_status: dict = expected_output["initial_status"]

    input_bucket_name = "pytest_input_bucket"
    output_bucket_name = "pytest_output_bucket"
    version_bucket_name = "pytest_version_bucket"
    version_object_key = "info/versions.json"
    queue_name = "pytest_sqs_job_queue"
    region_name = "us-west-2"

    job_tag: str = expected_sqs_message["job_tag"]
    job_type: str = expected_sqs_message["job_type"]

    s3_client, sqs_client = initialize_s3_and_sqs_clients(
        input_bucket_name, output_bucket_name, queue_name, region_name
    )

    create_version_bucket_and_file(
        version_bucket_name, region_name, version_object_key
    )

    # Retrieve original global variable names from module
    original_OUTPUT_BUCKET = job_service.OUTPUT_BUCKET
    original_SQS_QUEUE_NAME = job_service.SQS_QUEUE_NAME
    original_JOB_QUEUE_REGION = job_service.JOB_QUEUE_REGION
    original_VERSION_BUCKET = job_service.VERSION_BUCKET
    original_VERSION_KEY = job_service.VERSION_KEY

    # Upload job JSON to input bucket
    job_object_name: str = s3_event["Records"][0]["s3"]["object"]["key"]
    upload_data(
        s3_client,
        input_bucket_name,
        job_object_name,
        dumps(job_info),
    )

    # Upload additional input data to input bucket
    if "upload" in apbs_test_job:
        for file_name in apbs_test_job["upload"]["input"]:
            file_contents: str = open(
                Path.cwd() / Path(f"tests/input_data/{file_name}")
            ).read()
            upload_data(
                s3_client,
                input_bucket_name,
                f"{job_tag}/{file_name}",
                file_contents,
            )
        for file_name in apbs_test_job["upload"]["output"]:
            file_contents: str = open(
                Path.cwd() / Path(f"tests/input_data/{file_name}")
            ).read()
            upload_data(
                s3_client,
                output_bucket_name,
                f"{job_tag}/{file_name}",
                file_contents,
            )

    # Set module globals and interpret PDB2PQR job trigger
    job_service.SQS_QUEUE_NAME = queue_name
    job_service.OUTPUT_BUCKET = output_bucket_name
    job_service.JOB_QUEUE_REGION = region_name
    job_service.VERSION_BUCKET = version_bucket_name
    job_service.VERSION_KEY = version_object_key
    job_service.interpret_job_submission(s3_event, None)

    # Obtain message from SQS and status from S3
    queue_url: str = sqs_client.get_queue_url(QueueName=queue_name)["QueueUrl"]
    queue_message_response = sqs_client.receive_message(
        QueueUrl=queue_url, MaxNumberOfMessages=1
    )

    # TODO: adjust assertion to handle invalid cases
    assert "Messages" in queue_message_response
    queue_message = queue_message_response["Messages"][0]
    message_contents: dict = loads(queue_message["Body"])
    message_receipt_handle = queue_message["ReceiptHandle"]

    """Compare queue contents with expected"""
    assert message_contents == expected_sqs_message

    # job_id: str = expected_sqs_message["job_id"]
    # job_date: str = expected_sqs_message["job_date"]
    status_object_name: str = f"{job_tag}/{job_type}-status.json"
    status_object_data: dict = loads(
        download_data(s3_client, output_bucket_name, status_object_name)
    )

    """Check that status contains expected values"""
    assert status_object_data["jobid"] == expected_status["jobid"]
    assert status_object_data["jobtype"] == expected_status["jobtype"]
    assert status_object_data["metadata"] == expected_status["metadata"]
    assert job_type in status_object_data
    assert status_object_data[job_type]["status"] == "pending"
    assert (
        status_object_data[job_type]["inputFiles"]
        == expected_status[job_type]["inputFiles"]
    )
    assert (
        status_object_data[job_type]["outputFiles"]
        == expected_status[job_type]["outputFiles"]
    )
    # Checking type here since startTime is determined at runtime
    assert isinstance(status_object_data[job_type]["startTime"], float)
    assert status_object_data[job_type]["endTime"] is None

    # Delete message from SQS queue
    sqs_client.delete_message(
        QueueUrl=queue_url, ReceiptHandle=message_receipt_handle
    )

    # Reset module global variables to original state
    job_service.SQS_QUEUE_NAME = original_SQS_QUEUE_NAME
    job_service.OUTPUT_BUCKET = original_OUTPUT_BUCKET
    job_service.JOB_QUEUE_REGION = original_JOB_QUEUE_REGION
    job_service.VERSION_BUCKET = original_VERSION_BUCKET
    job_service.VERSION_KEY = original_VERSION_KEY
