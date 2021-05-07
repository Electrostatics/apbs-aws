"""Tests for the generating unique IDs and S3 tokens."""
from copy import copy
from lambda_services.api_service.api_service import generate_id_and_tokens


def test_generate_id_and_tokens():
    """Test token request with no existing Job ID."""
    test_api_gateway_event_without_jobid = {
        "bucket_name": "sample-bucket",
        "file_list": ["file1.txt", "file2.pdb", "file3.csv"],
    }
    response = generate_id_and_tokens(
        test_api_gateway_event_without_jobid, None
    )

    assert "job_id" in response, "Service did not generate new Job ID"
    assert "urls" in response, "Service did not generate the presigned URLs"
    assert len(response["urls"]) == len(
        test_api_gateway_event_without_jobid["file_list"]
    ), (
        "Number of URLs returned do not match number of files requested. "
        f"Expected: {len(test_api_gateway_event_without_jobid['file_list'])}"
    )

    # Test token request with existing Job ID
    test_api_gateway_event_with_jobid = copy(
        test_api_gateway_event_without_jobid
    )
    test_api_gateway_event_with_jobid["job_id"] = "sampleJobID"
    response = generate_id_and_tokens(test_api_gateway_event_with_jobid, None)

    assert response["job_id"] == test_api_gateway_event_with_jobid["job_id"], (
        f"Job ID ({response['job_id']}) used in response does "
        "not match Job ID in request"
    )
