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

def generate_id_and_tokens(file_list: List[str], job_id:str=None):

    # Generate new job ID if not provided
    if job_id is None:
        job_id = ''.join( choices(ascii_lowercase+digits, k=10) ) # Random 10-character alphanumeric string

    # Create URLs with S3 tokens
    url_dict = {}
    for file_name in file_list:
        token_url = create_s3_url(file_name, job_id)
        url_dict[file_name] = token_url

    # Generate JSON response
    response = {
        'job_id': job_id,
        'urls': url_dict,
    }
    
    return response