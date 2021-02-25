from string import ascii_lowercase, digits
from random import choices
from typing import List
import os
import boto3

# TODO 2020/17/20, Elvis - Establish specific logging format to be used in Lambda functions

def create_s3_url(bucket_name: str, file_name: str, prefix_name: str) -> str:
    object_name = f'{prefix_name}/{file_name}'
    s3_client = boto3.client('s3')

    # Generate presigned URL for file
    url = s3_client.generate_presigned_url( 'put_object',
                                            Params={
                                                'Bucket': bucket_name,
                                                'Key': object_name
                                            },
                                            ExpiresIn=3600,
                                            HttpMethod='PUT',
                                          )
    return url

def generate_id_and_tokens(event: dict, context=None) -> dict:
    
    # Assign object variables from Lambda event 
    bucket_name : str     = os.getenv('INPUT_BUCKET')
    file_list : List[str] = event['file_list']
    job_id : str

    # Generate new job ID if not provided
    if 'job_id' in event:
        job_id = event['job_id']
    else:
        job_id = ''.join( choices(ascii_lowercase+digits, k=10) ) # Random 10-character alphanumeric string

    # Create URLs with S3 tokens
    url_dict = {}
    for file_name in file_list:
        token_url = create_s3_url(bucket_name, file_name, job_id)
        url_dict[file_name] = token_url

    # Generate JSON response
    response = {
        'job_id': job_id,
        'urls': url_dict,
    }
    
    return response