from string import ascii_lowercase, digits
from random import choices
from typing import List
import os
import boto3

INPUT_BUCKET_NAME = os.getenv('INPUT_BUCKET_NAME', 'sample_bucket')

def create_s3_url(file_name, prefix_name):
    # TODO: 2021/02/11, Elvis - Use boto3 to create and return presigned URL for return
    object_name = f'{prefix_name}/{file_name}'
    s3_client = boto3.client('s3')

    url = s3_client.generate_presigned_url( 'put_object',
                                            Params={
                                                'Bucket': INPUT_BUCKET_NAME,
                                                'Key': object_name
                                            },
                                            ExpiresIn=3600,
                                          )
    
    return url

# TODO 2021/02/15 - Add support for asking for multiple tokens at once
def generate_id_and_token(file_name: str, job_id:str=None):

    # Generate new job ID if not provided
    if job_id is None:
        job_id = ''.join( choices(ascii_lowercase+digits, k=10) ) # Random 10-character alphanumeric string

    # Create S3 token URL
    token_url = create_s3_url(file_name, job_id)

    # Generate JSON response
    response = {
        'job_id': job_id,
        's3_url': token_url,
    }
    
    return response