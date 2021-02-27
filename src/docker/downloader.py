from typing import List
import os, argparse
import boto3

# Environment vars:
# - OUTPUT_BUCKET
# - QUEUE_NAME
# - REGION

QUEUE_NAME = os.getenv('QUEUE_NAME')

def get_jobinfo_from_sqs():
    pass

def extract_input_files() -> List[str]:
    pass

def main():

    if QUEUE_NAME is None:
        raise EnvironmentError('Environment variable QUEUE_NAME is not set')

if __name__ == '__main__':
    main()