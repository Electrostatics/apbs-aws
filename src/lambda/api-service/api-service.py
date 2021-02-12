from string import ascii_lowercase, digits
from random import choices

def create_s3_url(file_name, prefix_name):
    # TODO: 2021/02/11, Elvis - Use boto3 to create and return presigned URL for return
    return 'This is an S3 token'    

def generate_id_and_token(file_name, job_id=None):

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