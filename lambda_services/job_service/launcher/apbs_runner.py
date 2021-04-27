from io import StringIO
from os import path
from sys import stderr
import locale
import logging
# import requests

from .jobsetup import JobSetup
from . import utils


class JobDirectoryExistsError(Exception):
    def __init__(self, expression):
        self.expression = expression


class MissingFilesError(FileNotFoundError):
    def __init__(self, message, file_list=[]):
        super().__init__(message)
        self.missing_files = file_list


class Runner(JobSetup):
    def __init__(self, form, job_id, job_date):
        super().__init__(job_id, job_date)
        self.job_id = None
        self.form = None
        self.infile_name = None
        self.command_line_args = None
        self.input_files = []
        self.output_files = []
        self.estimated_max_runtime = 7200

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
            self.apbs_options = self.field_storage_to_dict(form)
            # TODO: catch error if something wrong happes in fieldStorageToDict;
            #   handle in tesk_proxy_service

        if job_id is not None:
            self.job_id = job_id
        else:
            self.job_id = form['pdb2pqrid']


    def prepare_job(self, output_bucket_name: str, input_bucket_name: str) -> str:
        # taken from mainInput()
        logging.info('preparing job execution: %s (apbs)', self.job_id)
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
            expected_files_list = utils.apbs_extract_input_files(infile_str)

            # Check if additional READ files exist in S3
            missing_files = []
            for name in expected_files_list:
                object_name = f"{job_id}/{name}"
                if utils.s3_object_exists(input_bucket_name, object_name):
                    # TODO: 2021/03/04, Elvis - Update input files via a common function
                    self.add_input_file(f"{job_id}/{str(name)}")
                else:
                    missing_files.append(str(name))

            if len(missing_files) > 0:
                raise MissingFilesError(f'Please upload missing file(s) from READ section storage: {missing_files}')

            # Set input files and return command line args
            self.command_line_args = infile_name
            self.add_input_file(f"{job_id}/{infile_name}")

            return self.command_line_args

        elif form is not None:
            # Using APBS input file name from PDB2PQR run
            infile_name = f'{job_id}.in'

            apbs_options = self.apbs_options

            # Get text for infile string
            infile_str = utils.s3_download_file_str(output_bucket_name, job_id, infile_name)

            # Extracts PQR file name from the '*.in' file within storage bucket
            # pqrFileName = tesk_proxy_utils.apbs_extract_input_files(self.job_id, self.job_id+'.in', storage_host)[0]
            pqr_file_name = utils.apbs_extract_input_files(infile_str)[0]
            apbs_options['pqrFileName'] = pqr_file_name

            # Get contents of updated APBS input file, based on form
            apbs_options['tempFile'] = "apbsinput.in"
            new_infile_contents = utils.apbs_infile_creator(apbs_options)

            # Get contents of PQR file from PDB2PQR run
            pqrfile_text = utils.s3_download_file_str(output_bucket_name, job_id, pqr_file_name)

            # Remove waters from molecule (PQR file) if requested by the user
            try:
                if "removewater" in form and form["removewater"] == "on":
                    pqr_filename_root, pqr_filename_ext = path.splitext(pqr_file_name)

                    # no_water_pqrname = f"{pqr_filename_root}-nowater{pqr_filename_ext}"
                    water_pqrname = f"{pqr_filename_root}-water{pqr_filename_ext}"

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
                    utils.s3_put_object(output_bucket_name, f"{job_id}/{water_pqrname}", pqrfile_text.encode('utf-8'))
                    self.output_files.append(f"{job_id}/{water_pqrname}")

                    # Replace PQR file text with version with water removed
                    pqrfile_text = nowater_pqrfile_text

            except Exception:
                # TODO: May wanna do more here (logging?)
                raise

            # Upload *.pqr and *.in file to input bucket
            utils.s3_put_object(input_bucket_name, f"{job_id}/{apbs_options['tempFile']}", new_infile_contents.encode('utf-8'))
            utils.s3_put_object(input_bucket_name, f"{job_id}/{pqr_file_name}", pqrfile_text.encode('utf-8'))

            # Set input files for status reporting
            self.add_input_file(f"{job_id}/{pqr_file_name}")
            self.add_input_file(f"{job_id}/{apbs_options['tempFile']}")

            # Return command line args
            self.command_line_args = apbs_options['tempFile']  # 'apbsinput.in'
            return self.command_line_args

    def field_storage_to_dict(self, form: dict) -> dict:
        """ Converts the CGI input from the web interface to a dictionary """
        apbs_options = {'writeCheck': 0}

        if "writecharge" in form and form["writecharge"] != "":
            apbs_options['writeCheck'] += 1
            apbs_options['writeCharge'] = True
        else:
            apbs_options['writeCharge'] = False

        if "writepot" in form and form["writepot"] != "":
            apbs_options['writeCheck'] += 1
            apbs_options['writePot'] = True
        else:
            apbs_options['writePot'] = False

        if "writesmol" in form and form["writesmol"] == "on":
            apbs_options['writeCheck'] += 1
            apbs_options['writeSmol'] = True
        else:
            apbs_options['writeSmol'] = False

        if "asyncflag" in form and form["asyncflag"] == "on":
            apbs_options['async'] = locale.atoi(form["async"])
            apbs_options['asyncflag'] = True
        else:
            apbs_options['asyncflag'] = False

        if "writesspl" in form and form["writesspl"] == "on":
            apbs_options['writeCheck'] += 1
            apbs_options['writeSspl'] = True
        else:
            apbs_options['writeSspl'] = False

        if "writevdw" in form and form["writevdw"] == "on":
            apbs_options['writeCheck'] += 1
            apbs_options['writeVdw'] = True
        else:
            apbs_options['writeVdw'] = False

        if "writeivdw" in form and form["writeivdw"] == "on":
            apbs_options['writeCheck'] += 1
            apbs_options['writeIvdw'] = True
        else:
            apbs_options['writeIvdw'] = False

        if "writelap" in form and form["writelap"] == "on":
            apbs_options['writeCheck'] += 1
            apbs_options['writeLap'] = True
        else:
            apbs_options['writeLap'] = False

        if "writeedens" in form and form["writeedens"] == "on":
            apbs_options['writeCheck'] += 1
            apbs_options['writeEdens'] = True
        else:
            apbs_options['writeEdens'] = False

        if "writendens" in form and form["writendens"] == "on":
            apbs_options['writeCheck'] += 1
            apbs_options['writeNdens'] = True
        else:
            apbs_options['writeNdens'] = False

        if "writeqdens" in form and form["writeqdens"] == "on":
            apbs_options['writeCheck'] += 1
            apbs_options['writeQdens'] = True
        else:
            apbs_options['writeQdens'] = False

        if "writedielx" in form and form["writedielx"] == "on":
            apbs_options['writeCheck'] += 1
            apbs_options['writeDielx'] = True
        else:
            apbs_options['writeDielx'] = False

        if "writediely" in form and form["writediely"] == "on":
            apbs_options['writeCheck'] += 1
            apbs_options['writeDiely'] = True
        else:
            apbs_options['writeDiely'] = False

        if "writedielz" in form and form["writedielz"] == "on":
            apbs_options['writeCheck'] += 1
            apbs_options['writeDielz'] = True
        else:
            apbs_options['writeDielz'] = False

        if "writekappa" in form and form["writekappa"] == "on":
            apbs_options['writeCheck'] += 1
            apbs_options['writeKappa'] = True
        else:
            apbs_options['writeKappa'] = False

        if apbs_options['writeCheck'] > 4:
            # TODO: 2021/03/02, Elvis - validation error; please raise exception here
            print("Please select a maximum of four write statements.", file=stderr)
            # os._exit(99)

        # READ section variables
        apbs_options['readType'] = "mol"
        apbs_options['readFormat'] = "pqr"
        apbs_options['pqrPath'] = ""
        # apbsOptions['pqrFileName'] = form['pdb2pqrid']+'.pqr'

        # ELEC section variables
        apbs_options['calcType'] = form["type"]

        apbs_options['ofrac'] = locale.atof(form["ofrac"])

        apbs_options['dimeNX'] = locale.atoi(form["dimenx"])
        apbs_options['dimeNY'] = locale.atoi(form["dimeny"])
        apbs_options['dimeNZ'] = locale.atoi(form["dimenz"])

        apbs_options['cglenX'] = locale.atof(form["cglenx"])
        apbs_options['cglenY'] = locale.atof(form["cgleny"])
        apbs_options['cglenZ'] = locale.atof(form["cglenz"])

        apbs_options['fglenX'] = locale.atof(form["fglenx"])
        apbs_options['fglenY'] = locale.atof(form["fgleny"])
        apbs_options['fglenZ'] = locale.atof(form["fglenz"])

        apbs_options['glenX'] = locale.atof(form["glenx"])
        apbs_options['glenY'] = locale.atof(form["gleny"])
        apbs_options['glenZ'] = locale.atof(form["glenz"])

        apbs_options['pdimeNX'] = locale.atof(form["pdimex"])
        apbs_options['pdimeNY'] = locale.atof(form["pdimey"])
        apbs_options['pdimeNZ'] = locale.atof(form["pdimez"])

        if form["cgcent"] == "mol":
            apbs_options['coarseGridCenterMethod'] = "molecule"
            apbs_options['coarseGridCenterMoleculeID'] = locale.atoi(form["cgcentid"])

        elif form["cgcent"] == "coord":
            apbs_options['coarseGridCenterMethod'] = "coordinate"
            apbs_options['cgxCent'] = locale.atoi(form["cgxcent"])
            apbs_options['cgyCent'] = locale.atoi(form["cgycent"])
            apbs_options['cgzCent'] = locale.atoi(form["cgzcent"])

        if form["fgcent"] == "mol":
            apbs_options['fineGridCenterMethod'] = "molecule"
            apbs_options['fineGridCenterMoleculeID'] = locale.atoi(form["fgcentid"])
        elif form["fgcent"] == "coord":
            apbs_options['fineGridCenterMethod'] = "coordinate"
            apbs_options['fgxCent'] = locale.atoi(form["fgxcent"])
            apbs_options['fgyCent'] = locale.atoi(form["fgycent"])
            apbs_options['fgzCent'] = locale.atoi(form["fgzcent"])

        # added conditional to avoid checking 'gcent' for incompatible methods
        if apbs_options['calcType'] in ['mg-manual', 'mg-dummy']:
            if form["gcent"] == "mol":
                apbs_options['gridCenterMethod'] = "molecule"
                apbs_options['gridCenterMoleculeID'] = locale.atoi(form["gcentid"])
            elif form["gcent"] == "coord":
                apbs_options['gridCenterMethod'] = "coordinate"
                apbs_options['gxCent'] = locale.atoi(form["gxcent"])
                apbs_options['gyCent'] = locale.atoi(form["gycent"])
                apbs_options['gzCent'] = locale.atoi(form["gzcent"])

        apbs_options['mol'] = locale.atoi(form["mol"])
        apbs_options['solveType'] = form["solvetype"]
        apbs_options['boundaryConditions'] = form["bcfl"]
        apbs_options['biomolecularDielectricConstant'] = locale.atof(form["pdie"])
        apbs_options['dielectricSolventConstant'] = locale.atof(form["sdie"])
        apbs_options['dielectricIonAccessibilityModel'] = form["srfm"]
        apbs_options['biomolecularPointChargeMapMethod'] = form["chgm"]
        apbs_options['surfaceConstructionResolution'] = locale.atof(form["sdens"])
        apbs_options['solventRadius'] = locale.atof(form["srad"])
        apbs_options['surfaceDefSupportSize'] = locale.atof(form["swin"])
        apbs_options['temperature'] = locale.atof(form["temp"])
        apbs_options['calcEnergy'] = form["calcenergy"]
        apbs_options['calcForce'] = form["calcforce"]

        for i in range(0, 3):
            ch_str = 'charge%i' % i
            conc_str = 'conc%i' % i
            rad_str = 'radius%i' % i
            if form[ch_str] != "":
                apbs_options[ch_str] = locale.atoi(form[ch_str])
            if form[conc_str] != "":
                apbs_options[conc_str] = locale.atof(form[conc_str])
            if form[rad_str] != "":
                apbs_options[rad_str] = locale.atof(form[rad_str])
        apbs_options['writeFormat'] = form["writeformat"]
        # apbsOptions['writeStem'] = apbsOptions['pqrFileName'][:-4]
        apbs_options['writeStem'] = form["pdb2pqrid"]

        return apbs_options
