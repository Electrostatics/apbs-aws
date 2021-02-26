import os, sys, time
# import glob
# import requests
import logging
# from multiprocessing import Process
from pprint import pprint
from json import dumps
# from flask import request

# import kubernetes.client
# from kubernetes import config
# from kubernetes.client.rest import ApiException

# from service import tesk_proxy_utils
# from service.legacy.pdb2pqr_old_utils import redirector, setID
from .weboptions import WebOptions, WebOptionsError


class JobDirectoryExistsError(Exception):
    def __init__(self, expression):
        self.expression = expression

class Runner:
    def __init__(self, form, job_id):
        # self.starttime = None
        # self.job_id = None
        self.weboptions = None
        self.invoke_method = None
        self.cli_params = None
        self.command_line_args:str = None
        self.job_id = job_id
        self.input_files = []

        try:
            # if 'invoke_method' in form and isinstance(form['invoke_method'], str):
            if 'invoke_method' in form :
                logging.info('invoke_method found, value: %s' % str(form['invoke_method']) )
                if form['invoke_method'].lower() == 'v2' or form['invoke_method'].lower() == 'cli':
                    self.invoke_method = 'cli'
                    self.cli_params = {
                        'pdb_name' : form['pdb_name'],
                        'pqr_name' : form['pqr_name'],
                        'flags' : form['flags']
                    }
                    
                elif form['invoke_method'].lower() == 'v1' or form['invoke_method'].lower() == 'gui':
                    self.invoke_method = 'gui'
                    self.weboptions = WebOptions(form)
            else:
                logging.warning('invoke_method not found: %s' % str('invoke_method' in form))
                if 'invoke_method' in form:
                    logging.debug("form['invoke_method']: "+str(form['invoke_method']))
                    logging.debug(type(form['invoke_method']))
                self.invoke_method = 'gui'
                self.weboptions = WebOptions(form)

        except WebOptionsError:
            raise

    # def prepare_job(self, job_id):
    #     pass
    #     # statusfile = open('%s%s%s/pdb2pqr_status' % (INSTALLDIR, TMPDIR, job_id), 'w')
    #     # statusfile.write('running')
    #     # statusfile.close()


    def prepare_job(self):
        job_id = self.job_id
        pqr_name = None
        # print(self.weboptions.pdbfilestring)
        # pdblist, errlist = readPDB(self.weboptions.pdbfile)

        # currentdir = os.getcwd()
        # os.chdir("/")
        # # os.setsid()
        # # os.umask(0)
        # os.chdir(currentdir)

        # os.close(1) # not sure if these
        # os.close(2) # two lines are necessary


        # pqrpath = '%s%s%s/%s.pqr' % (INSTALLDIR, TMPDIR, job_id, job_id)

        # orig_stdout = sys.stdout
        # orig_stderr = sys.stderr
        # sys.stdout = open('%s%s%s/pdb2pqr_stdout.txt' % (INSTALLDIR, TMPDIR, job_id), 'w')
        # sys.stderr = open('%s%s%s/pdb2pqr_stderr.txt' % (INSTALLDIR, TMPDIR, job_id), 'w')
        
        if self.invoke_method == 'gui' or self.invoke_method == 'v1':

            # Retrieve information about the PDB file and command line arguments
            if self.weboptions.user_did_upload:
                # upload_list = ['pdb2pqr_status', 'pdb2pqr_start_time']
                pass
            else:
                if os.path.splitext(self.weboptions.pdbfilename)[1] != '.pdb':
                    self.weboptions.pdbfilename = self.weboptions.pdbfilename+'.pdb' # add pdb extension to pdbfilename
                    # # Write the PDB file contents to disk
                    # with open(os.path.join(INSTALLDIR, TMPDIR, job_id, self.weboptions.pdbfilename), 'w') as fout:
                    #     fout.write(self.weboptions.pdbfilestring)
                    #     upload_list = [self.weboptions.pdbfilename, 'pdb2pqr_status', 'pdb2pqr_start_time']

            self.weboptions.pqrfilename = job_id+'.pqr' # make pqr name prefix the job_id

            # Retrieve PDB2PQR command line arguments
            command_line_args = self.weboptions.getCommandLine()
            if '--summary' in command_line_args:
                command_line_args = command_line_args.replace('--summary', '')

            logging.debug(command_line_args)
            logging.debug(self.weboptions.pdbfilename)
            
        elif self.invoke_method == 'cli' or self.invoke_method == 'v2':
            # construct command line argument string for when CLI is invoked
            command_line_list = []
            # get list of args from self.cli_params['flags']
            for name in self.cli_params['flags']:
                command_line_list.append( (name, self.cli_params['flags'][name]) )
            
            command_line_args = ''

            # append to command_line_str
            for pair in command_line_list:
                if isinstance(pair[1], bool):
                    cli_arg = '--%s' % (pair[0]) #add conditionals later to distinguish between data types
                else:
                    cli_arg = '--%s=%s' % (pair[0], str(pair[1])) #add conditionals later to distinguish between data types
                command_line_args = '%s %s' % (command_line_args, cli_arg)

            # append self.cli_params['pdb_name'] and self.cli_params['pqr_name'] to command_line_str
            # pprint(self.cli_params)
            command_line_args = '%s %s %s' % (command_line_args, self.cli_params['pdb_name'], self.cli_params['pqr_name'])
            upload_list = ['pdb2pqr_status', 'pdb2pqr_start_time']

            # pqr_name = self.cli_params['pqr_name']
            # logging.info('pqr filename: %s', pqr_name)
        
        self.command_line_args = command_line_args
        return command_line_args

        # """
        # # TESK request headers
        # headers = {}
        # headers['Content-Type'] = 'application/json'
        # headers['Accept'] = 'application/json'
        # pdb2pqr_json_dict = tesk_proxy_utils.pdb2pqr_json_config(job_id, command_line_args, storage_host, os.path.join(INSTALLDIR, TMPDIR), pqr_name=pqr_name)

        # url = tesk_host + '/v1/tasks/'
        # print(url)
        # # print( dumps(pdb2pqr_json_dict, indent=2) )
        # """        

        # # Set up job to send to Volcano.sh
        # volcano_namespace = os.environ.get('VOLCANO_NAMESPACE')
        # pdb2pqr_kube_dict = tesk_proxy_utils.pdb2pqr_yaml_config(job_id, volcano_namespace, image_pull_policy, command_line_args, storage_host, os.path.join(INSTALLDIR, TMPDIR), pqr_name=pqr_name)
        # # print( dumps(pdb2pqr_kube_dict, indent=2) )

        # # create an instance of the API class
        # configuration = kubernetes.client.Configuration()
        # api_instance = kubernetes.client.CustomObjectsApi(kubernetes.client.ApiClient(configuration))
        # group = 'batch.volcano.sh' # str | The custom resource's group name
        # version = 'v1alpha1' # str | The custom resource's version
        # namespace = volcano_namespace # str | The custom resource's namespace
        # plural = 'jobs' # str | The custom resource's plural name. For TPRs this would be lowercase plural kind.
        # # body = kubernetes.client.UNKNOWN_BASE_TYPE() # UNKNOWN_BASE_TYPE | The JSON schema of the Resource to create.
        # pretty = 'true' # str | If 'true', then the output is pretty printed. (optional)
        
        # body = pdb2pqr_kube_dict

        # try:
        #     api_response = api_instance.create_namespaced_custom_object(group, version, namespace, plural, body, pretty=pretty)

        #     # print('\n\n\n')
        #     logging.debug( 'Response from Kube API server: %s', dumps(api_response, indent=2) )
        #     # print(type(api_response))
        # except ApiException as e:
        #     logging.error("Exception when calling CustomObjectsApi->create_namespaced_custom_object: %s\n",  e)
        #     raise

                
        # # #TODO: create handler in case of non-200 response
        # # response = requests.post(url, headers=headers, json=pdb2pqr_json_dict)
        
        # # print(response.content)
        # return

    """
    def start(self, storage_host, tesk_host, image_pull_policy, analytics_id, analytics_dim_index=None):
        # Acquire job ID
        job_id = self.job_id
        # job_id = requests.get()

        # Prepare job
        self.prepare_job(job_id)

        # Run PDB2PQR in separate process
        # p = Process(target=self.run_job, args=(job_id, storage_host))
        # p.start()

        self.run_job(job_id, storage_host, tesk_host, image_pull_policy)

        if 'X-Forwarded-For' in request.headers:
            source_ip = request.headers['X-Forwarded-For']
        else:
            logging.warning("Unable to find 'X-Forwarded-For' header in request")
            source_ip = None

        if 'X-APBS-Client-ID' in request.headers:
            client_id = request.headers['X-APBS-Client-ID']
        else:
            logging.warning("Unable to find 'X-APBS-Client-ID' header in request")
            client_id = job_id

        redirect = redirector(job_id, self.weboptions, 'pdb2pqr', source_ip, analytics_id, analytics_dim_index, client_id)
        # Upload initial files to storage service
        # file_list = [
        #     'typemap',
        #     'pdb2pqr_status',
        #     'pdb2pqr_start_time',
        # ]
        # if isinstance(file_list, list):
        #     try:
        #         tesk_proxy_utils.send_to_storage_service(storage_host, job_id, file_list, os.path.join(INSTALLDIR, TMPDIR))
        #     except Exception as err:
        #         with open('storage_err', 'a+') as fin:
        #             fin.write(err)
                    
        return redirect
    
    """