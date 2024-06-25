from typing import Optional
from boto3 import client
from dataclasses import dataclass

from botocore.exceptions import ClientError
from .utils import _LOGGER


class S3Utils:
    @staticmethod
    def copy_object(
        job_tag: str,
        source_bucket_name: str,
        source_object_name: str,
        dest_object_name: str,
        dest_bucket_name: Optional[str] = None,
    ):
        # Destination bucket is same as source if not defined
        if dest_bucket_name is None:
            dest_bucket_name = source_bucket_name

        # Initialize boto3 S3 client
        s3_client = client("s3")

        # Use S3 client to copy object
        _LOGGER.debug(
            "%s Copying file: '%s' (bucket: %s) - Destination: '%s' (bucket: %s)",
            job_tag,
            source_object_name,
            source_bucket_name,
            dest_object_name,
            dest_bucket_name,
        )
        s3_client.copy_object(
            CopySource=f"{source_bucket_name}/{source_object_name}",
            Bucket=source_bucket_name,
            Key=dest_object_name,
        )

    @staticmethod
    def download_file_str(bucket_name: str, object_name: str) -> str:
        job_tag = _extract_job_tag_from_objectname(object_name)
        try:
            s3_client = client("s3")
            s3_response: dict = s3_client.get_object(
                Bucket=bucket_name,
                Key=object_name,
            )
            return s3_response["Body"].read().decode("utf-8")
        except Exception as err:
            _LOGGER.exception(
                "%s ERROR downloading '%s' from bucket '%s': %s",
                job_tag,
                object_name,
                bucket_name,
                err,
            )
            raise

    @staticmethod
    def put_object(bucket_name: str, object_name: str, body):
        job_tag = _extract_job_tag_from_objectname(object_name)
        s3_client = client("s3")
        _ = s3_client.put_object(
            Bucket=bucket_name,
            Key=object_name,
            Body=body,
        )
        _LOGGER.debug(
            "%s Putting file: %s (bucket: %s)",
            job_tag,
            object_name,
            bucket_name,
        )

    @staticmethod
    def object_exists(bucket_name: str, object_name: str) -> bool:
        s3_client = client("s3")
        try:
            _ = s3_client.head_object(
                Bucket=bucket_name,
                Key=object_name,
            )
            return True
        except ClientError as err:
            if err.response["Error"]["Code"] == "404":  # "NoSuchKey" error
                return False
            elif err.response["Error"]["Code"] == "403":
                job_tag: str = _extract_job_tag_from_objectname(object_name)
                _LOGGER.warning(
                    "%s Received '%s' (%d) message on object HEAD: %s",
                    job_tag,
                    err.response["Error"]["Message"],
                    err.response["ResponseMetadata"]["HTTPStatusCode"],
                    object_name,
                )
                return False
            else:
                raise


@dataclass
class S3CopyPayload:
    source_object: str
    dest_object: str
    bucket_name: Optional[str] = None

    def __init__(
        self,
        source_object_name: str,
        dest_object_name: str,
        bucket_name: Optional[str] = None,
    ):
        self.source_object = source_object_name
        self.dest_object = dest_object_name
        self.bucket_name = bucket_name


def _extract_job_tag_from_objectname(s3_object_name: str) -> str:
    """Parse an S3 object key and return the job tag.

    Args:
        s3_object_name (str): An S3 object key, prefixed with date and job_id

    Returns:
        str: the job tag, extracted from the S3 object key
    """
    objectname_split: list = s3_object_name.split("/")
    job_tag: str
    if len(objectname_split) >= 3:
        job_tag = f"{objectname_split[-3]}/{objectname_split[-2]}"
    else:
        # NOTE: (Eo300) should we raise error here instead?
        job_tag = s3_object_name
        _LOGGER.warn(
            "%s Couldn't extract job tag from object name '%s'. "
            "Returning object name as job_tag.",
            job_tag,
            s3_object_name,
        )
    return job_tag
