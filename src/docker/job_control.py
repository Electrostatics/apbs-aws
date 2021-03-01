#!/usr/bin/env python3

from os import listdir
import os
import sys
import shutil
from os import path
import datetime, time, json
import boto3

qtimeout=3600
AWS_REGION='us-west-2'
max_tries=5
retry_time=30

path = '/dev/shm/test/'
bucket=os.getenv("OUTPUT_BUCKET")
bucket='apbs-test-output'
queue=os.getenv("JOB_QUEUE_NAME")
queue='apbs-test-job-q'


def get_items(sqs,qurl):
  loop=0

  items = sqs.receive_message( QueueUrl=qurl, MaxNumberOfMessages=1, VisibilityTimeout=qtimeout)
  
  while 'Messages' not in items:
    loop+=1
    if loop==max_tries:
      return 0
    print "Waiting ...."
    time.sleep(retry_time)
    items = sqs.receive_message( QueueUrl=qurl, MaxNumberOfMessages=1, VisibilityTimeout=qtimeout)
  
  return items

def update_state(s3,jobid,jobtype,status):
  objectfile=jobid+'/'+jobtype+'-status.json'
  obj = s3.Object(bucket, objectfile)
  statobj:dict = json.loads(obj.get()['Body'].read().decode('utf-8')) 
  
  statobj[jobtype]['status']=status
  statobj[jobtype]['endTime']=time.time()
  ## FIX
  statobj[jobtype]['outputFiles']=jobid+"output-fix"
  
  object_response:dict = s3_client.put_object(
                              Body=json.dumps(statobj),
                              Bucket=OUTPUT_BUCKET,
                              Key=object_filename
  )

def run_code(job,s3):
  out=1
  try:
    job_info:dict = json.loads(job) 
    if 'jobid' not in job_info:
      return 1
  except:
    print ("Not a json q item")
    return 1
  rundir=path+job_info['jobid']
  inbucket=job_info['bucket_name']
  os.makedirs(rundir,exist_ok=True)
  os.chdir(rundir)

  for file in job_info['input_files']:
    try:
      s3.download_file(inbucket, file, path+file )
    except:
      print('download failed '+file)
      os.chdir(path)
      shutil.rmtree(rundir)
      return 0

  update_state(s3, job_info['jobid'], job_info['job_type'],"Starting")
  
  if "apbs" in job_info['job_type']:
     pass
  elif "pdb2pqr" in job_info['job_type']:
    try:
      os.system('pdb2pqr '+job_info['command_line_args'])
      s3.upload_file(path+job_info['jobid']+'/pdb2pqr.out', bucket, job_info['jobid']+'/' )
    except:
      print('upload failed pdb out')
      out=0
  os.chdir(path)
  shutil.rmtree(rundir)
  update_state(s3, job_info['jobid'], job_info['job_type'],"Finished")

  return out



def worker():
  # master loop to manage queue
  s3 = boto3.client('s3')
  sqs = boto3.client('sqs',region_name=AWS_REGION)
  queue_url = sqs.get_queue_url(QueueName=queue)
  qurl=queue_url['QueueUrl']
  lasttime=datetime.datetime.now()

  mess = get_items(sqs,qurl)
  while (mess):
    for i in mess['Messages']:
        if (run_code (i['Body'],s3)):
          sqs.delete_message( QueueUrl=qurl, ReceiptHandle=i['ReceiptHandle'])
    mess=get_items(sqs,qurl)
  print (str(datetime.datetime.now()-lasttime))
  print ("done")
  return


worker()

exit()
