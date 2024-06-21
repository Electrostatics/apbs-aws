from typing import Optional
from boto3 import client
from dataclasses import dataclass
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
