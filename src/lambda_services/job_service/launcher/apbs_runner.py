from io import StringIO
from os import path
import locale
import logging
# import requests
import urllib3

from . import utils

class JobDirectoryExistsError(Exception):
    def __init__(self, expression):
        self.expression = expression

class MissingFilesError(FileNotFoundError):
    def __init__(self, message, file_list=[]):
        # super(FileNotFoundError, self).__init__(message)
        super().__init__(message) #TODO: use this line on Python3 upgrade
        self.missing_files = file_list

class Runner:
    def __init__(self, form, job_id=None):
        self.job_id = None
        self.form = None
        self.infile_name = None
        # self.read_file_list = []
        # self.read_file_list = None
        self.command_line_args = None
        self.input_files = []
        self.output_files = []
        # Load kubeconfig
        # config.load_incluster_config()
        # config.load_kube_config()

        # if infile_name is not None:
        #     self.infile_name = infile_name
        form = form['form']
        if 'filename' in form:
            self.infile_name = form['filename']
        elif form is not None:

            for key in form:
                # Unravels output parameters from form
                if key == 'output_scalar':
                    for option in form[key]:
                        form[option] = option
                    form.pop('output_scalar')
                elif not isinstance(form[key], str):
                    # TODO: 2021/03/03, Elvis - Eliminate need to cast all items as string (see 'self.fieldStorageToDict()')
                    form[key] = str(form[key])

            self.form = form
            self.apbsOptions = self.fieldStorageToDict(form)
            # TODO: catch error if something wrong happes in fieldStorageToDict;
            #   handle in tesk_proxy_service

        if job_id is not None:
            self.job_id = job_id
        else:
            self.job_id = form['pdb2pqrid']


        # TODO: 2021/03/02, Elvis - remove below; no need to create directories
        # self.job_dir = '%s%s%s' % (INSTALLDIR, TMPDIR, self.job_id)
        # logging.debug(self.job_dir)
        # if not os.path.isdir(self.job_dir):
        #     os.mkdir(self.job_dir)

    def prepare_job(self, output_bucket_name:str, input_bucket_name:str):
        # taken from mainInput()
        logging.info(f'preparing job execution: {self.job_id} (apbs)')
        infile_name = self.infile_name
        form = self.form
        job_id = self.job_id

        # downloading necessary files
        if infile_name is not None:
            # If APBS directly run, verify necessary files exist in S3

            # Check S3 for file existence; raise exception if not
            if not utils.s3_object_exists(input_bucket_name, f'{job_id}/{infile_name}'):
                raise MissingFilesError(f'Missing APBS input file. Please upload: {infile_name}')

            # Get text for infile string
            infile_str = utils.s3_download_file_str(input_bucket_name, job_id, infile_name)

            # Get list of expected supporting files
            expected_files_list = utils.apbs_extract_input_files( infile_str )

            # Check if additional READ files exist in S3
            missing_files = []
            for name in expected_files_list:
                object_name = f"{job_id}/{name}"
                if utils.s3_object_exists(input_bucket_name, object_name):
                    self.input_files.append( str(name) )
                else:
                    missing_files.append( str(name) )

            if len(missing_files) > 0:
                raise MissingFilesError(f'Please upload missing file(s) from READ section storage: {missing_files}')


            # Set input files and return command line args
            self.command_line_args = infile_name
            self.input_files.append( infile_name )

            return self.command_line_args

        elif form is not None:
            # Using APBS input file name from PDB2PQR run
            infile_name = f'{job_id}.in'

            apbsOptions = self.apbsOptions

            # Get text for infile string
            infile_str = utils.s3_download_file_str(output_bucket_name, job_id, infile_name)

            # Extracts PQR file name from the '*.in' file within storage bucket
            # pqrFileName = tesk_proxy_utils.apbs_extract_input_files(self.job_id, self.job_id+'.in', storage_host)[0]
            pqrFileName = utils.apbs_extract_input_files(infile_str)[0]
            apbsOptions['pqrFileName'] = pqrFileName

            # Get contents of updated APBS input file, based on form
            apbsOptions['tempFile'] = "apbsinput.in"
            new_infile_contents = utils.apbs_infile_creator(apbsOptions)

            # Get contents of PQR file from PDB2PQR run
            pqrfile_text = utils.s3_download_file_str(output_bucket_name, job_id, pqrFileName)

            # Remove waters from molecule (PQR file) if requested by the user
            try:
                if "removewater" in form and form["removewater"] == "on":
                    pqr_filename_root, pqr_filename_ext = path.splitext(pqrFileName)
                    
                    no_water_pqrname = f"{pqr_filename_root}-nowater{pqr_filename_ext}"
                    water_pqrname    = f"{pqr_filename_root}-water{pqr_filename_ext}"

                    # pqrfile_text = utils.s3_download_file_str(output_bucket_name, job_id, pqrFileName)

                    # Add lines to new PQR text, skipping lines with water
                    nowater_pqrfile_text = ''
                    for line in StringIO(pqrfile_text):
                        # if line == '':
                        #     break
                        # (2020/03/03) Commented out above because we not using while-loop; didn't seem necessary
                        if "WAT" in line:
                            pass
                        elif "HOH" in line:
                            pass
                        else:
                            nowater_pqrfile_text += line
                            # nowater_pqrfile_text.write(line)
                    # nowater_pqrfile_text.seek(0)

                    # Send original PQR file (with water) to S3 output bucket
                    utils.s3_put_object(output_bucket_name, f"{job_id}/{water_pqrname}", pqrfile_text.encode('utf-8') )
                    self.output_files.append( f"{job_id}/{water_pqrname}" )

                    # Replace PQR file text with version with water removed
                    pqrfile_text = nowater_pqrfile_text

            except:
                # TODO: May wanna do more here (logging?)
                raise

            # Upload *.pqr and *.in file to input bucket
            utils.s3_put_object(input_bucket_name, f"{job_id}/{apbsOptions['tempFile']}", new_infile_contents.encode('utf-8') )
            utils.s3_put_object(input_bucket_name, f"{job_id}/{pqrFileName}", pqrfile_text.encode('utf-8') )

            # Set input files for status reporting
            self.input_files.append(f"{job_id}/{pqrFileName}")
            self.input_files.append(f"{job_id}/{apbsOptions['tempFile']}")

            # Return command line args
            self.command_line_args = apbsOptions['tempFile'] # 'apbsinput.in'
            return self.command_line_args


    # TODO: 2021/03/03, Elvis - Find a way to retrieve the headers we need here
    def report_to_ga(self, analytics_id:str, headers:dict, analytics_dim_index=None):
        # Log event to Analytics
        if 'X-Forwarded-For' in headers:
            source_ip = headers['X-Forwarded-For']
        else:
            logging.warning("Unable to find 'X-Forwarded-For' header in request")
            source_ip = ''

        if 'X-APBS-Client-ID' in headers:
            client_id = headers['X-APBS-Client-ID']
        else:
            logging.warning("Unable to find 'X-APBS-Client-ID' header in request")
            client_id = self.job_id
            
        # Configure values to construct request body 
        e_category = 'apbs'
        e_action = 'submission'
        e_label = source_ip
        custom_dim = ''

        if analytics_dim_index is not None:
            custom_dim = '&cd%s=%s' % ( str(analytics_dim_index), self.job_id )

        # Set headers and body
        ga_user_agent_header = {'User-Agent': headers['User-Agent']}
        ga_request_body = 'v=1&tid=%s&cid=%s&t=event&ec=%s&ea=%s&el=%s%s\n' % (analytics_id, client_id, e_category, e_action, e_label, custom_dim)

        logging.info('Submitting analytics request - category: %s, action: %s', e_category, e_action)

        # # Send Analytics event
        # resp = requests.post('https://www.google-analytics.com/collect', data=ga_request_body, headers=ga_user_agent_header)
        # if not resp.ok:
        #     resp.raise_for_status

        # Send Analytics event
        http = urllib3.PoolManager()
        resp:urllib3.HTTPResponse = http.request('POST', 
                            'https://www.google-analytics.com/collect',
                            headers=ga_user_agent_header,
                            body=bytes( ga_request_body )
                        )
        if resp.status >= 400:
            raise ValueError(f'No successful response. Response Status: {resp.status}')

    def fieldStorageToDict(self, form: dict):
        """ Converts the CGI input from the web interface to a dictionary """
        apbsOptions = {'writeCheck':0}

        if "writecharge" in form and form["writecharge"] != "":
            apbsOptions['writeCheck'] += 1
            apbsOptions['writeCharge'] = True
        else:
            apbsOptions['writeCharge'] = False
        
        if "writepot" in form and form["writepot"] != "":
            apbsOptions['writeCheck'] += 1
            apbsOptions['writePot'] = True
        else:
            apbsOptions['writePot'] = False

        if "writesmol" in form and form["writesmol"] == "on":
            apbsOptions['writeCheck'] += 1
            apbsOptions['writeSmol'] = True
        else:
            apbsOptions['writeSmol'] = False
            
        if "asyncflag" in form and form["asyncflag"] == "on":
            apbsOptions['async'] = locale.atoi(form["async"])
            apbsOptions['asyncflag'] = True
        else:
            apbsOptions['asyncflag'] = False

        if "writesspl" in form and form["writesspl"] == "on":
            apbsOptions['writeCheck'] += 1
            apbsOptions['writeSspl'] = True
        else:
            apbsOptions['writeSspl'] = False

        if "writevdw" in form and form["writevdw"] == "on":
            apbsOptions['writeCheck'] += 1
            apbsOptions['writeVdw'] = True
        else:
            apbsOptions['writeVdw'] = False

        if "writeivdw" in form and form["writeivdw"] == "on":
            apbsOptions['writeCheck'] += 1
            apbsOptions['writeIvdw'] = True
        else:
            apbsOptions['writeIvdw'] = False

        if "writelap" in form and form["writelap"] == "on":
            apbsOptions['writeCheck'] += 1
            apbsOptions['writeLap'] = True
        else:
            apbsOptions['writeLap'] = False

        if "writeedens" in form and form["writeedens"] == "on":
            apbsOptions['writeCheck'] += 1
            apbsOptions['writeEdens'] = True
        else:
            apbsOptions['writeEdens'] = False

        if "writendens" in form and form["writendens"] == "on":
            apbsOptions['writeCheck'] += 1
            apbsOptions['writeNdens'] = True
        else:
            apbsOptions['writeNdens'] = False

        if "writeqdens" in form and form["writeqdens"] == "on":
            apbsOptions['writeCheck'] += 1
            apbsOptions['writeQdens'] = True
        else:
            apbsOptions['writeQdens'] = False

        if "writedielx" in form and form["writedielx"] == "on":
            apbsOptions['writeCheck'] += 1
            apbsOptions['writeDielx'] = True
        else:
            apbsOptions['writeDielx'] = False

        if "writediely" in form and form["writediely"] == "on":
            apbsOptions['writeCheck'] += 1
            apbsOptions['writeDiely'] = True
        else:
            apbsOptions['writeDiely'] = False

        if "writedielz" in form and form["writedielz"] == "on":
            apbsOptions['writeCheck'] += 1
            apbsOptions['writeDielz'] = True
        else:
            apbsOptions['writeDielz'] = False

        if "writekappa" in form and form["writekappa"] == "on":
            apbsOptions['writeCheck'] += 1
            apbsOptions['writeKappa'] = True
        else:
            apbsOptions['writeKappa'] = False
        
        if apbsOptions['writeCheck'] > 4:
            # TODO: 2021/03/02, Elvis - validation error; please raise exception here
            print( "Please select a maximum of four write statements." )
            # os._exit(99)

        # READ section variables
        apbsOptions['readType'] = "mol"
        apbsOptions['readFormat'] = "pqr"
        apbsOptions['pqrPath'] = ""
        # apbsOptions['pqrFileName'] = form['pdb2pqrid']+'.pqr'

        #ELEC section variables
        apbsOptions['calcType'] = form["type"] 
        
        apbsOptions['ofrac'] = locale.atof(form["ofrac"])

        apbsOptions['dimeNX'] = locale.atoi(form["dimenx"])
        apbsOptions['dimeNY'] = locale.atoi(form["dimeny"])
        apbsOptions['dimeNZ'] = locale.atoi(form["dimenz"])

        apbsOptions['cglenX'] = locale.atof(form["cglenx"])
        apbsOptions['cglenY'] = locale.atof(form["cgleny"])
        apbsOptions['cglenZ'] = locale.atof(form["cglenz"])

        apbsOptions['fglenX'] = locale.atof(form["fglenx"])
        apbsOptions['fglenY'] = locale.atof(form["fgleny"])
        apbsOptions['fglenZ'] = locale.atof(form["fglenz"])

        apbsOptions['glenX'] = locale.atof(form["glenx"])
        apbsOptions['glenY'] = locale.atof(form["gleny"])
        apbsOptions['glenZ'] = locale.atof(form["glenz"])
        
        apbsOptions['pdimeNX'] = locale.atof(form["pdimex"])
        apbsOptions['pdimeNY'] = locale.atof(form["pdimey"])
        apbsOptions['pdimeNZ'] = locale.atof(form["pdimez"])

        if form["cgcent"] == "mol":
            apbsOptions['coarseGridCenterMethod'] = "molecule"
            apbsOptions['coarseGridCenterMoleculeID'] = locale.atoi(form["cgcentid"])

        elif form["cgcent"] == "coord":
            apbsOptions['coarseGridCenterMethod'] = "coordinate"
            apbsOptions['cgxCent'] = locale.atoi(form["cgxcent"])
            apbsOptions['cgyCent'] = locale.atoi(form["cgycent"])
            apbsOptions['cgzCent'] = locale.atoi(form["cgzcent"])

        if form["fgcent"] == "mol":
            apbsOptions['fineGridCenterMethod'] = "molecule"
            apbsOptions['fineGridCenterMoleculeID'] = locale.atoi(form["fgcentid"])
        elif form["fgcent"] == "coord":
            apbsOptions['fineGridCenterMethod'] = "coordinate"
            apbsOptions['fgxCent'] = locale.atoi(form["fgxcent"])
            apbsOptions['fgyCent'] = locale.atoi(form["fgycent"])
            apbsOptions['fgzCent'] = locale.atoi(form["fgzcent"])

        # added conditional to avoid checking 'gcent' for incompatible methods
        if apbsOptions['calcType'] in ['mg-manual','mg-dummy']:
            if form["gcent"] == "mol":
                apbsOptions['gridCenterMethod'] = "molecule"
                apbsOptions['gridCenterMoleculeID'] = locale.atoi(form["gcentid"])
            elif form["gcent"] == "coord":
                apbsOptions['gridCenterMethod'] = "coordinate"
                apbsOptions['gxCent'] = locale.atoi(form["gxcent"])
                apbsOptions['gyCent'] = locale.atoi(form["gycent"])
                apbsOptions['gzCent'] = locale.atoi(form["gzcent"])


        apbsOptions['mol'] = locale.atoi(form["mol"])
        apbsOptions['solveType'] = form["solvetype"]
        apbsOptions['boundaryConditions'] = form["bcfl"]
        apbsOptions['biomolecularDielectricConstant'] = locale.atof(form["pdie"])
        apbsOptions['dielectricSolventConstant'] = locale.atof(form["sdie"])
        apbsOptions['dielectricIonAccessibilityModel'] = form["srfm"]
        apbsOptions['biomolecularPointChargeMapMethod'] = form["chgm"]
        apbsOptions['surfaceConstructionResolution'] = locale.atof(form["sdens"])
        apbsOptions['solventRadius'] = locale.atof(form["srad"])    
        apbsOptions['surfaceDefSupportSize'] = locale.atof(form["swin"])
        apbsOptions['temperature'] = locale.atof(form["temp"])
        apbsOptions['calcEnergy'] = form["calcenergy"]
        apbsOptions['calcForce'] = form["calcforce"]

        for i in range(0,3):
            chStr = 'charge%i' % i
            concStr = 'conc%i' % i
            radStr = 'radius%i' % i
            if form[chStr] != "":
                apbsOptions[chStr] = locale.atoi(form[chStr])
            if form[concStr] != "":
                apbsOptions[concStr] = locale.atof(form[concStr])
            if form[radStr] != "":
                apbsOptions[radStr] = locale.atof(form[radStr])
        apbsOptions['writeFormat'] = form["writeformat"]
        #apbsOptions['writeStem'] = apbsOptions['pqrFileName'][:-4]
        apbsOptions['writeStem'] = form["pdb2pqrid"]


        return apbsOptions

