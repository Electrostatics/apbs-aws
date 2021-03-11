import os, time, json
import boto3
from .launcher import pdb2pqr_runner, apbs_runner

OUTPUT_BUCKET = os.getenv('OUTPUT_BUCKET')
# Could use SQS URL below instead of a queue name; whichever is easier
SQS_QUEUE_NAME = os.getenv('JOB_QUEUE_NAME')

# Analytics variables
GA_TRACKING_ID = os.environ.get('GA_TRACKING_ID', None)
GA_JOBID_INDEX = os.environ.get('GA_JOBID_INDEX', None)
if GA_TRACKING_ID == '': GA_TRACKING_ID = None
if GA_JOBID_INDEX == '': GA_JOBID_INDEX = None

def get_job_info(bucket_name: str, info_object_name: str) -> dict:
    # Download job info object from S3
    s3_client = boto3.client('s3')
    object_response:dict = s3_client.get_object(
                            Bucket=bucket_name,
                            Key=info_object_name,
                        )

    # Convert content of JSON file to dict
    try:
        job_info:dict = json.loads( object_response['Body'].read().decode('utf-8') )
        return job_info
    except:
        raise


def upload_status_file(job_id:str, object_filename: str, job_type: str, inputfile_list: list, outputfile_list: list):
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
            # 'inputFiles': [f'{job_id}/{filename}' for filename in inputfile_list],
            'inputFiles': [ filename for filename in inputfile_list ],
            'outputFiles': [ filename for filename in outputfile_list ]
        }
    }


    s3_client = boto3.client('s3')
    object_response:dict = s3_client.get_object(
                            Body=json.dump(initial_status_dict),
                            Bucket=OUTPUT_BUCKET,
                            Key=object_filename
    )
    
def submit_ga_event_pdb2pqr(job_id, weboptions, jobtype=None, client_ip=None, analytics_id=None, analytics_dim_index=None, ga_client_id=None):
    pass

def submit_ga_event_apbs(job_id, analytics_id=None, analytics_dim_index=None):
    pass

def interpret_job_submission(event: dict, context=None):
    # Get basic job information from S3 event
    #   TODO: may need to modify to correctly retrieve info
    jobinfo_object_name:str = event['s3']['object']['key']
    bucket_name:str = event['s3']['bucket']['name']
    job_id = jobinfo_object_name.split('/')[0]

    # Obtain job configuration from config file
    job_info = get_job_info(bucket_name, jobinfo_object_name )
    job_info_form = job_info['form']
    job_type = jobinfo_object_name.split('-')[0] # Assumes 'pdb2pqr-job.json', or similar format

    """ Interpret contents of job configuration """
    # If PDB2PQR
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
        "input_files": job_runner.input_files,
        "command_line_args": job_command_line_args,
    }
    sqs_client = boto3.resource('sqs')
    queue = sqs_client.get_queue_by_name(QueueName=SQS_QUEUE_NAME)
    queue.send_message( MessageBody=json.dumps(sqs_json) )

    # Send reporting data to GA
    if GA_TRACKING_ID is not None:
        ga_job_metadata = job_info['metadata']['ga']
        source_ip = event['Records']['requestParameters']['sourceIPAddress']
        job_runner.report_to_ga(GA_TRACKING_ID, ga_job_metadata, source_ip, analytics_dim_index=GA_JOBID_INDEX)