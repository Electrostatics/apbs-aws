#!/usr/bin/env python3

from os import listdir
import os
import sys
import shutil
from os import path
import datetime, time, json, urllib
import boto3

qtimeout=300
AWS_REGION='us-west-2'
max_tries=6
retry_time=15

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
  ups3=boto3.resource('s3')
  objectfile=jobid+'/'+jobtype+'-status.json'
  s3obj = ups3.Object(bucket, objectfile)
  statobj:dict = json.loads(s3obj.get()['Body'].read().decode('utf-8')) 
  
  statobj[jobtype]['status']=status
  statobj[jobtype]['endTime']=time.time()
  ## FIX
  statobj[jobtype]['outputFiles']=jobid+"output-fix"
  
  object_response:dict = s3.put_object(
                              Body=json.dumps(statobj),
                              Bucket=bucket,
                              Key=objectfile
  )

def run_code(job,s3):
  out=1
  try:
    job_info:dict = json.loads(job) 
    if 'job_id' not in job_info:
      return 1
  except:
    print ("Not a json q item")
    return 1
  rundir=path+job_info['job_id']
  inbucket=job_info['bucket_name']
  os.makedirs(rundir,exist_ok=True)
  os.chdir(rundir)

  for index,file in enumerate(job_info['input_files']):
    if 'https' in file:
      name=job_info['job_id']+'/'+file.split('/')[-1]
      try:
        urllib.request.urlretrieve(file,path+name)
      except:
        print('download failed '+file)
        os.chdir(path)
        shutil.rmtree(rundir)
        return 0
      job_info['input_files'][index]=name
    else  
      try:
        s3.download_file(inbucket, file, path+file )
      except:
        print('download failed '+file)
        os.chdir(path)
        shutil.rmtree(rundir)
        return 0

  update_state(s3, job_info['job_id'], job_info['job_type'],"running")
  
  if "apbs" in job_info['job_type']:
    command='LD_LIBRARY_PATH=/apps/APBS-3.0.0.Linux/lib /app/APBS-3.0.0.Linux/bin/apbs '+job_info['command_line_args']+' > apbs.stdout.txt 2> apbs.stderr.txt'    
  elif "pdb2pqr" in job_info['job_type']:
    command='/app/builds/pdb2pqr/pdb2pqr.py '+job_info['command_line_args']+' > pdb2pqr.stdout.txt 2> pdb2pqr.stderr.txt'
  try:
    os.system('command')
    for file in os.listdir('.'): s3.upload_file(path+job_info['job_id']+'/'+file, bucket, job_info['job_id']+'/'+file ) 
  except:
    print('upload failed out')
    out=0
  
  #output_files=[if file in infile for infile in job_info['input_files'] for file in os.listdir(.)]
  os.chdir(path)
  shutil.rmtree(rundir)
  update_state(s3, job_info['job_id'], job_info['job_type'],"complete")

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
