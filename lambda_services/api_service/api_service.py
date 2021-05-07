"""Generate unique job id and S3 tokens for each job."""

from datetime import date
from os import getenv
from random import choices
from string import ascii_lowercase, digits
from typing import List
from boto3 import client

# TODO 2020/02/17, Elvis - Establish specific logging format to be used in
#                  Lambda functions


def create_s3_url(bucket_name: str, file_name: str, prefix_name: str) -> str:
    """Create an URL that will allow a file to be stored on an S3 bucket.

    :param bucket_name str: AWS S3 bucket to store file in
    :param file_name str: the filename to put under the prefix_name directory
    :param prefix_name str: the directory in the bucket_name
    :return: a URL that can be used to upload a file to the S3 bucket
    :rtype: str
    """

    object_name = f"{prefix_name}/{file_name}"
    s3_client = client("s3")

    # Generate presigned URL for file
    url = s3_client.generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket_name, "Key": object_name},
        ExpiresIn=3600,
        HttpMethod="PUT",
    )
    return url


def generate_id_and_tokens(event: dict, context) -> dict:
    # pylint: disable=unused-argument
    """Generate an unique job id and S3 auth tokens"""

    # Assign object variables from Lambda event
    bucket_name: str = getenv("INPUT_BUCKET", "TEST_BUCKET")

    file_list: List[str] = event["file_list"]
    job_id: str

    # Generate new job ID if not provided
    if "job_id" in event:
        job_id = event["job_id"]
    else:
        job_id = "".join(
            choices(ascii_lowercase + digits, k=10)
        )  # Random 10-character alphanumeric string

    # Create URLs with S3 tokens
    url_dict = {}
    current_date = date.today().isoformat()
    date_jobid_prefix = f"{current_date}/{job_id}"  # UTC or local?
    for file_name in file_list:
        token_url = create_s3_url(bucket_name, file_name, date_jobid_prefix)
        url_dict[file_name] = token_url

    # Generate JSON response
    response = {
        "date": current_date,
        "job_id": job_id,
        "urls": url_dict,
    }

    return response
