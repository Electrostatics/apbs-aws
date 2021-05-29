"""Generate unique job id and S3 tokens for each job."""

from datetime import datetime
from logging import getLevelName, getLogger, Formatter, INFO
from os import getenv
from random import choices
from string import ascii_lowercase, digits
from typing import List
from boto3 import client
from botocore.exceptions import ClientError
from dateutil.tz import UTC


def apbs_logger():
    """Get a singleton logger for all code.

    Returns:
        Logger: An all encompassing logger.
    """
    _apbs_logger = getLogger()
    _apbs_logger.handlers.clear()
    for handler in _apbs_logger.handlers:
        handler.setFormatter(
            Formatter(
                "[%(aws_request_id)s] [%(levelname)s] "
                "[%(filename)s:%(lineno)s:%(funcName)s()] %(message)s"
            )
        )
    _apbs_logger.setLevel(getenv("LOG_LEVEL", getLevelName(INFO)))
    return _apbs_logger


_LOGGER = apbs_logger()


def create_s3_url(bucket_name: str, job_tag: str, file_name: str) -> str:
    """Create an URL that will allow a file to be stored on an S3 bucket.

    Args:
        bucket_name str: AWS S3 bucket to store file in
        job_tag str: the directory in the bucket_name
        file_name str: the filename to put under the job_tag directory
    Returns:
        url (str): A URL that can be used to upload a file to the S3 bucket
    """

    object_name = f"{job_tag}/{file_name}"
    url = ""
    try:
        # Generate presigned URL for file
        url = client("s3").generate_presigned_url(
            "put_object",
            Params={
                "Bucket": bucket_name,
                "Key": object_name,
            },
            ExpiresIn=3600,
            HttpMethod="PUT",
        )
    except (ClientError) as err:
        _LOGGER.exception(
            "%s Unable to create presigned URL for %s/%s: %s",
            job_tag,
            bucket_name,
            object_name,
            err,
        )
    return url


def generate_id_and_tokens(event: dict, context) -> dict:
    # pylint: disable=unused-argument
    """Generate an unique job id and S3 auth tokens.

    Args:
        event (dict): A dictionary of terms.
        context: Required by AWS Lambda
    Returns:
        URLs (dict): A dictionary of URLs and filenames
    """

    # Assign object variables from Lambda event
    bucket_name: str = getenv("INPUT_BUCKET", "TEST_BUCKET")
    file_list: List[str] = event["file_list"]
    job_id: str

    # Generate new job ID if not provided
    if "job_id" in event:
        job_id = event["job_id"]
    else:
        # Random 10-character alphanumeric string
        job_id = "".join(choices(ascii_lowercase + digits, k=10))

    # Create URLs with S3 tokens
    url_dict = {}
    current_date = datetime.now(UTC).strftime("%Y-%m-%d")
    job_tag = f"{current_date}/{job_id}"
    for file_name in file_list:
        # Generate presigned URL for file
        url_dict[file_name] = create_s3_url(bucket_name, job_tag, file_name)

    _LOGGER.info(
        "%s Created URL for %s/%s: %s",
        job_tag,
        bucket_name,
        job_tag,
        file_list,
    )

    # Generate JSON response
    return {
        "date": current_date,
        "job_id": job_id,
        "job_tag": job_tag,
        "urls": url_dict,
    }
