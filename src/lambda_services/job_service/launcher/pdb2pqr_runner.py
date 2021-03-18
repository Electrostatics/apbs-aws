import os
# import glob
# import requests
import logging
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
        self.command_line_args: str = None
        self.job_id = job_id
        self.input_files = []
        self.output_files = []

        try:
            # if 'invoke_method' in form and isinstance(form['invoke_method'], str):
            if 'invoke_method' in form:
                logging.info('invoke_method found, value: %s' % str(form['invoke_method']))
                if form['invoke_method'].lower() == 'v2' or form['invoke_method'].lower() == 'cli':
                    self.invoke_method = 'cli'
                    self.cli_params = {
                        'pdb_name': form['pdb_name'],
                        'pqr_name': form['pqr_name'],
                        'flags': form['flags']
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
        # pqr_name = None
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
                # Update input files
                # TODO: 2021/03/04, Elvis - Update input files via a common function
                self.input_files.append(f'{job_id}/{self.weboptions.pdbfilename}')

            else:
                if os.path.splitext(self.weboptions.pdbfilename)[1] != '.pdb':
                    self.weboptions.pdbfilename = self.weboptions.pdbfilename+'.pdb'  # add pdb extension to pdbfilename

                    # Add url to RCSB PDB file to input file list
                    self.input_files.append(f'https://files.rcsb.org/download/{self.weboptions.pdbfilename}')

            # Check for userff, names, ligand files to add to input_file list
            if hasattr(self.weboptions, 'ligandfilename'):
                self.input_files.append(f'{job_id}/{self.weboptions.ligandfilename}')
            if hasattr(self.weboptions, 'userfffilename'):
                self.input_files.append(f'{job_id}/{self.weboptions.userfffilename}')
            if hasattr(self.weboptions, 'usernamesfilename'):
                self.input_files.append(f'{job_id}/{self.weboptions.usernamesfilename}')

            # Make the pqr name prefix the job_id
            self.weboptions.pqrfilename = job_id+'.pqr'

            # Retrieve PDB2PQR command line arguments
            command_line_args = self.weboptions.getCommandLine()
            if '--summary' in command_line_args:
                command_line_args = command_line_args.replace('--summary', '')

            logging.debug(command_line_args)
            logging.debug(self.weboptions.pdbfilename)

        elif self.invoke_method == 'cli' or self.invoke_method == 'v2':
            # construct command line argument string for when CLI is invoked
            command_line_list = []

            # Add PDB filename to input file list
            self.input_files.append(f"{job_id}/{self.cli_params['pdb_name']}")

            # get list of args from self.cli_params['flags']
            for name in self.cli_params['flags']:
                command_line_list.append((name, self.cli_params['flags'][name]))

                # Add to input file list if userff, names, or ligand flags are defined
                if name in ['userff', 'usernames', 'ligand'] and self.cli_params[name]:
                    self.input_files.append(f"{job_id}/{self.cli_params[name]}")

            command_line_args = ''

            # append to command_line_str
            for pair in command_line_list:
                if isinstance(pair[1], bool):
                    cli_arg = '--%s' % (pair[0])  # add conditionals later to distinguish between data types
                else:
                    cli_arg = '--%s=%s' % (pair[0], str(pair[1]))  # add conditionals later to distinguish between data types
                command_line_args = '%s %s' % (command_line_args, cli_arg)

            # append self.cli_params['pdb_name'] and self.cli_params['pqr_name'] to command_line_str
            # pprint(self.cli_params)
            command_line_args = '%s %s %s' % (command_line_args, self.cli_params['pdb_name'], self.cli_params['pqr_name'])
            # upload_list = ['pdb2pqr_status', 'pdb2pqr_start_time']

            # pqr_name = self.cli_params['pqr_name']
            # logging.info('pqr filename: %s', pqr_name)

        self.command_line_args = command_line_args
        return command_line_args
