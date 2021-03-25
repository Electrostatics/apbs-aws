import os
import time
import json
import boto3
from launcher import pdb2pqr_runner, apbs_runner

OUTPUT_BUCKET = os.getenv('OUTPUT_BUCKET')
FARGATE_CLUSTER = os.getenv('FARGATE_CLUSTER')
FARGATE_SERVICE = os.getenv('FARGATE_SERVICE')
# Could use SQS URL below instead of a queue name; whichever is easier
SQS_QUEUE_NAME = os.getenv('JOB_QUEUE_NAME')


def get_job_info(bucket_name: str, info_object_name: str) -> dict:
    """Retrieve job configuraiton JSON object from S3, and return as dict.

    :param bucket_name str: AWS S3 bucket to retrieve file from
    :param info_object_name str: The name of the file to download
    :return: A dictionary of the JSON object representing a job configuration
    :rtype: dict
    """

    # Download job info object from S3
    s3_client = boto3.client('s3')
    object_response: dict = s3_client.get_object(
                            Bucket=bucket_name,
                            Key=info_object_name,
                        )

    # Convert content of JSON file to dict
    try:
        job_info: dict = json.loads(object_response['Body'].read().decode('utf-8'))
        return job_info
    except Exception:
        raise


def upload_status_file(job_id: str, object_filename: str, job_type: str, inputfile_list: list, outputfile_list: list):
    """Upload a generated initial status object to S3

    :param bucket_name str: AWS S3 bucket to upload file to
    :param object_filename str: the name of the file to download
    :param job_type str: name of job type (e.g. 'apbs', 'pdb2pqr')
    :param inputfile_list list: List of current input files
    :param outputfile_list list: List of current output files

    """
    # TODO: 2021/03/02, Elvis - add submission time to initial status

    job_start_time = time.time()
    initial_status_dict = {
        'jobid': job_id,
        'jobtype': job_type,
        job_type: {
            'status': 'pending',
            'startTime': job_start_time,
            'endTime': None,
            'subtasks': [],
            'inputFiles': inputfile_list,
            'outputFiles': outputfile_list
            # 'inputFiles': [f'{job_id}/{filename}' for filename in inputfile_list],
            # 'inputFiles': [filename for filename in inputfile_list],
            # 'outputFiles': [filename for filename in outputfile_list]
        }
    }

    s3_client = boto3.client('s3')
    object_response: dict = s3_client.put_object(
                            Body=json.dumps(initial_status_dict),
                            Bucket=OUTPUT_BUCKET,
                            Key=object_filename
    )


def interpret_job_submission(event: dict, context=None):
    """Interpret contents of job configuration, triggered from S3 event.

    :param event dict: Amazon S3 event, containing info to retrieve contents
    :param context: *fill in later*
    """

    # Get basic job information from S3 event
    #   TODO: will need to modify to correctly retrieve info
    jobinfo_object_name: str = event['Records'][0]['s3']['object']['key']
    bucket_name: str = event['Records'][0]['s3']['bucket']['name']
    job_id = jobinfo_object_name.split('/')[0]

    # Obtain job configuration from config file
    job_info_form = get_job_info(bucket_name, jobinfo_object_name)['form']
    job_type = jobinfo_object_name.split('-')[0].split('/')[1]  # Assumes 'pdb2pqr-job.json', or similar format

    # If PDB2PQR:
    #   - Use weboptions if from web
    #   - Interpret as is if using only command line args
    if job_type == 'pdb2pqr':
        job_runner = pdb2pqr_runner.Runner(job_info_form, job_id)
        job_command_line_args = job_runner.prepare_job()

    # If APBS:
    #   - Use form data to interpret job
    elif job_type == 'apbs':
        job_runner = apbs_runner.Runner(job_info_form, job_id)
        job_command_line_args = job_runner.prepare_job(OUTPUT_BUCKET, bucket_name)

    # Create and upload status file to S3
    status_filename = f'{job_type}-status.json'
    status_object_name = f'{job_id}/{status_filename}'
    upload_status_file(job_id, status_object_name, job_type, job_runner.input_files, job_runner.output_files)

    # Submit run info to SQS
    sqs_json = {
        "job_id": job_id,
        "job_type": job_type,
        "bucket_name": bucket_name,
        "input_files": job_runner.input_files,
        "command_line_args": job_command_line_args,
    }
    sqs_client = boto3.resource('sqs')
    queue = sqs_client.get_queue_by_name(QueueName=SQS_QUEUE_NAME)
    queue.send_message(MessageBody=json.dumps(sqs_json))
