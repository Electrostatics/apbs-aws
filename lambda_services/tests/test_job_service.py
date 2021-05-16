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
                'LocationConstraint': 'us-west-2',
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
                'LocationConstraint': 'us-west-2',
            },
        )
        yield s3_client, bucket_name


@pytest.fixture
def initialize_job_queue():
    """
        Create an job queue queue to perform test.
        Returns client and name of bucket
    """
    queue_name = "pytest_sqs_job_queue"
    with mock_sqs():
        sqs_client = client("sqs")
        sqs_client.create_queue(QueueName=queue_name)
        yield sqs_client, queue_name


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
        Body=dumps(expected_pdb2pqr_job_info)
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
            "inputFiles": [
                f"{current_date}/{job_id}/1fas.pdb"
            ],
            "outputFiles": []
        }
    }

    # Upload dict to S3 as JSON
    status_objectname: str = f"{current_date}/{job_id}/{job_type}-status.json"
    job_service.OUTPUT_BUCKET = bucket_name
    job_service.upload_status_file(status_objectname, sample_status)

    # Download JSON from S3, parse into dict
    s3_resp: dict = s3_client.get_object(
        Bucket=bucket_name,
        Key=status_objectname
    )
    downloaded_object_data: dict = loads(s3_resp["Body"].read())

    # Compare downloaded dict with expected (sample dict)
    assert downloaded_object_data == sample_status

    # Reset module global variables to original state
    job_service.OUTPUT_BUCKET = original_OUTPUT_BUCKET


@mock_s3
@mock_sqs
def test_interpret_job_submission_pdb2pqr():
    # Retrieve initialized AWS client and bucket name
    # Retrieve original global variable names from module

    # Upload PDB2PQR job JSON
    # Setup dict with expected S3 trigger content
    # Interpret PDB2PQR job trigger

    # Declare expected output of SQS message
    # Obtain SQS message and compare contents

    # Reset module global variables to original state
    pass


@mock_s3
@mock_sqs
def test_interpret_job_submission_apbs():
    # Retrieve initialized AWS client and bucket name
    # Retrieve original global variable names from module

    # Upload APBS job JSON
    # Setup dict with expected S3 trigger content
    # Interpret APBS job trigger

    # Declare expected output of SQS message
    # Obtain SQS message and compare contents

    # Reset module global variables to original state
    pass


@mock_s3
@mock_sqs
def test_interpret_job_submission_invalid():
    # Retrieve initialized AWS client and bucket name
    # Retrieve original global variable names from module

    # Upload JSON for invalid jobtype
    # Setup dict with expected S3 trigger content
    # Interpret invalid job trigger

    # Declare expected output of SQS message
    # Obtain SQS message and compare contents

    # Reset module global variables to original state
    pass
