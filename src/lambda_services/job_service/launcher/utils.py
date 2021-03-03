from io import StringIO
import logging, json
import boto3
from botocore import exceptions
from botocore.exceptions import ClientError

def s3_download_file_str(bucket_name:str, job_id:str, file_name:str) -> str:
    try:
        object_name = '%s/%s' % (job_id, file_name)

        s3_client = boto3.client('s3')
        s3_response:dict = s3_client.get_object(
                                Bucket=bucket_name,
                                Key=object_name,
                            )
        object_str = s3_response['Body'].read().decode('utf-8')
        return object_str

    except Exception as e:
        logging.error('ERROR: %s', e)
        raise

def s3_put_object(bucket_name:str, object_name:str, body):
    s3_client = boto3.client('s3')
    s3_response = s3_client.put_object(
                        Bucket=bucket_name,
                        Key=object_name,
                        Body=body,
                    )

def s3_object_exists(bucket_name:str, object_name:str) -> bool:
    s3_client = boto3.client('s3')
    try:
        s3_response = s3_client.head_object(
                            Bucket=bucket_name,
                            Key=object_name,
                        )
        return True

    except ClientError as err:
        if err.response["Error"]["Code"] == "NoSuchKey":
            return False
        else:
            raise

def apbs_extract_input_files(infile_text):
    # Read only the READ section of infile, 
    # extracting out the files needed for APBS
    READ_start = False
    READ_end = False
    file_list = []
    for whole_line in StringIO(u'%s' % infile_text):
        line = whole_line.strip()

        if READ_start and READ_end:
            break
        
        elif not READ_start and not READ_end:
            if line.startswith('#'):
                pass
            else:
                split_line = line.split()
                if len(split_line) > 0:
                    if split_line[0].upper() == 'READ':
                        # print('ENTERING READ SECTION')
                        READ_start = True
                    elif split_line[0].upper() == 'END':
                        # print('LEAVING READ SECTION')
                        READ_end = True

        elif READ_start and not READ_end:
            if line.startswith('#'):
                pass
            else:
                split_line = line.split()
                if len(split_line) > 0:
                    if split_line[0].upper() == 'END':
                        # print('LEAVING READ SECTION')
                        READ_end = True
                    else:
                        for arg in line.split()[2:]:
                            file_list.append(arg)

    return file_list

def apbs_infile_creator(apbsOptions:dict) -> str:
    """
        Creates a new APBS input file, using the data from the form
    """
    print('in apbs_infile_creator')
    # print('in pqrFileCreator')
    # apbsOptions['tmpDirName'] = "%s%s%s/" % (INSTALLDIR, TMPDIR, apbsOptions['writeStem'])
    # print('making directory %s\n' % apbsOptions['tmpDirName'])
    
    # try:
    #     os.makedirs(apbsOptions['tmpDirName'])
    # except OSError, err:
    #     if err.errno == errno.EEXIST:
    #         if os.path.isdir(apbsOptions['tmpDirName']):
    #             # print "Error (tmp directory already exists) - please try again"
    #             pass
    #         else:
    #             print "Error (file exists where tmp dir should be) - please try again"
    #             raise
    #     else:
    #         raise

    # apbsOptions['tempFile'] = "apbsinput.in"
    apbsOptions['tab'] = "    " # 4 spaces - used for writing to file
    # input = open('%s/tmp/%s/%s' % (INSTALLDIR, apbsOptions['writeStem'], apbsOptions['tempFile']), 'w')
    input = StringIO()

    
    print("apbsOptions['tmpDirName'] = " + apbsOptions['tmpDirName'])
    print("apbsOptions['tempFile'] = " + apbsOptions['tempFile'])
    print("apbsOptions['pqrPath'] = " + apbsOptions['pqrPath'])
    print("apbsOptions['pqrFileName'] = " + apbsOptions['pqrFileName'])

    # writing READ section to file
    input.write('read\n')
    input.write('%s%s %s %s%s' % (apbsOptions['tab'], apbsOptions['readType'], apbsOptions['readFormat'], apbsOptions['pqrPath'], apbsOptions['pqrFileName']))
    input.write('\nend\n')

    # writing ELEC section to file
    input.write('elec\n')
    input.write('%s%s\n' % (apbsOptions['tab'], apbsOptions['calcType']))
    if apbsOptions['calcType']!="fe-manual":
        input.write('%sdime %d %d %d\n' % (apbsOptions['tab'], apbsOptions['dimeNX'], apbsOptions['dimeNY'], apbsOptions['dimeNZ']))
    if apbsOptions['calcType'] == "mg-para":
        input.write('%spdime %d %d %d\n' % (apbsOptions['tab'], apbsOptions['pdimeNX'], apbsOptions['pdimeNY'], apbsOptions['pdimeNZ']))
        input.write('%sofrac %g\n' % (apbsOptions['tab'], apbsOptions['ofrac']))
        if apbsOptions['asyncflag']:
            input.write('%sasync %d\n' % (apbsOptions['tab'], apbsOptions['async']))

    if apbsOptions['calcType'] == "mg-manual":
        input.write('%sglen %g %g %g\n' % (apbsOptions['tab'], apbsOptions['glenX'], apbsOptions['glenY'], apbsOptions['glenZ']))
    if apbsOptions['calcType'] in ['mg-auto','mg-para','mg-dummy']:
        input.write('%scglen %g %g %g\n' % (apbsOptions['tab'], apbsOptions['cglenX'], apbsOptions['cglenY'], apbsOptions['cglenZ']))
    if apbsOptions['calcType'] in ['mg-auto','mg-para']:
        input.write('%sfglen %g %g %g\n' % (apbsOptions['tab'], apbsOptions['fglenX'], apbsOptions['fglenY'], apbsOptions['fglenZ']))

        if apbsOptions['coarseGridCenterMethod']=='molecule':
            input.write('%scgcent mol %d\n' % (apbsOptions['tab'], apbsOptions['coarseGridCenterMoleculeID'] ))
        elif apbsOptions['coarseGridCenterMethod']=='coordinate':
            input.write('%scgcent %d %d %d\n' % (apbsOptions['tab'], apbsOptions['cgxCent'], apbsOptions['cgyCent'], apbsOptions['cgzCent']))

        if apbsOptions['fineGridCenterMethod']=='molecule':
            input.write('%sfgcent mol %d\n' % (apbsOptions['tab'], apbsOptions['fineGridCenterMoleculeID']))
        elif apbsOptions['fineGridCenterMethod']=='coordinate':
            input.write('%sfgcent %d %d %d\n' % (apbsOptions['tab'], apbsOptions['fgxCent'], apbsOptions['fgyCent'], apbsOptions['fgzCent']))

    if apbsOptions['calcType'] in ['mg-manual','mg-dummy']:
        if apbsOptions['gridCenterMethod']=='molecule':
            input.write('%sgcent mol %d\n' % (apbsOptions['tab'], apbsOptions['gridCenterMoleculeID'] ))
        elif apbsOptions['gridCenterMethod']=='coordinate':
            input.write('%sgcent %d %d %d\n' % (apbsOptions['tab'], apbsOptions['gxCent'], apbsOptions['gyCent'], apbsOptions['gzCent']))

    input.write('%smol %d\n' % (apbsOptions['tab'], apbsOptions['mol']))
    input.write('%s%s\n' % (apbsOptions['tab'], apbsOptions['solveType']))
    input.write('%sbcfl %s\n' % (apbsOptions['tab'], apbsOptions['boundaryConditions']))
    input.write('%spdie %g\n' % (apbsOptions['tab'], apbsOptions['biomolecularDielectricConstant']))
    input.write('%ssdie %g\n' % (apbsOptions['tab'], apbsOptions['dielectricSolventConstant']))
    input.write('%ssrfm %s\n' % (apbsOptions['tab'], apbsOptions['dielectricIonAccessibilityModel']))
    input.write('%schgm %s\n' % (apbsOptions['tab'], apbsOptions['biomolecularPointChargeMapMethod']))
    input.write('%ssdens %g\n' % (apbsOptions['tab'], apbsOptions['surfaceConstructionResolution']))
    input.write('%ssrad %g\n' % (apbsOptions['tab'], apbsOptions['solventRadius']))
    input.write('%sswin %g\n' % (apbsOptions['tab'], apbsOptions['surfaceDefSupportSize']))
    input.write('%stemp %g\n' % (apbsOptions['tab'], apbsOptions['temperature']))
    input.write('%scalcenergy %s\n' % (apbsOptions['tab'], apbsOptions['calcEnergy']))
    input.write('%scalcforce %s\n' % (apbsOptions['tab'], apbsOptions['calcForce']))
    for i in range(0,3):
        chStr = 'charge%i' % i
        concStr = 'conc%i' % i
        radStr = 'radius%i' % i
        # if apbsOptions.has_key(chStr) and apbsOptions.has_key(concStr) and apbsOptions.has_key(radStr):
        if ('chStr' in apbsOptions) and ('concStr' in apbsOptions) and ('radStr' in apbsOptions):
            #ion charge {charge} conc {conc} radius {radius}
            input.write('%sion charge %d conc %g radius %g\n' % (apbsOptions['tab'], 
                                                                 apbsOptions[chStr], 
                                                                 apbsOptions[concStr], 
                                                                 apbsOptions[radStr]))

    if apbsOptions['writeCharge']:
        input.write('%swrite charge %s %s-charge\n' % (apbsOptions['tab'], apbsOptions['writeFormat'], apbsOptions['writeStem']))
    
    if apbsOptions['writePot']:
        input.write('%swrite pot %s %s-pot\n' % (apbsOptions['tab'], apbsOptions['writeFormat'], apbsOptions['writeStem']))

    if apbsOptions['writeSmol']:
        input.write('%swrite smol %s %s-smol\n' % (apbsOptions['tab'], apbsOptions['writeFormat'], apbsOptions['writeStem']))

    if apbsOptions['writeSspl']:
        input.write('%swrite sspl %s %s-sspl\n' % (apbsOptions['tab'], apbsOptions['writeFormat'],  apbsOptions['writeStem']))

    if apbsOptions['writeVdw']:
        input.write('%swrite vdw %s %s-vdw\n' % (apbsOptions['tab'], apbsOptions['writeFormat'], apbsOptions['writeStem']))

    if apbsOptions['writeIvdw']:
        input.write('%swrite ivdw %s %s-ivdw\n' % (apbsOptions['tab'], apbsOptions['writeFormat'], apbsOptions['writeStem']))

    if apbsOptions['writeLap']:
        input.write('%swrite lap %s %s-lap\n' % (apbsOptions['tab'], apbsOptions['writeFormat'], apbsOptions['writeStem']))

    if apbsOptions['writeEdens']:
        input.write('%swrite edens %s %s-edens\n' % (apbsOptions['tab'], apbsOptions['writeFormat'], apbsOptions['writeStem']))

    if apbsOptions['writeNdens']:
        input.write('%swrite ndens %s %s-ndens\n' % (apbsOptions['tab'], apbsOptions['writeFormat'], apbsOptions['writeStem']))

    if apbsOptions['writeQdens']:
        input.write('%swrite qdens %s %s-qdens\n' % (apbsOptions['tab'], apbsOptions['writeFormat'], apbsOptions['writeStem']))

    if apbsOptions['writeDielx']:
        input.write('%swrite dielx %s %s-dielx\n' % (apbsOptions['tab'], apbsOptions['writeFormat'], apbsOptions['writeStem']))

    if apbsOptions['writeDiely']:
        input.write('%swrite diely %s %s-diely\n' % (apbsOptions['tab'], apbsOptions['writeFormat'], apbsOptions['writeStem']))

    if apbsOptions['writeDielz']:
        input.write('%swrite dielz %s %s-dielz\n' % (apbsOptions['tab'], apbsOptions['writeFormat'], apbsOptions['writeStem']))

    if apbsOptions['writeKappa']:
        input.write('%swrite kappa %s %s-kappa\n' % (apbsOptions['tab'], apbsOptions['writeFormat'], apbsOptions['writeStem']))

    input.write('end\n')
    input.write('quit')
    
    # input.close()
    input.seek(0)
    
    # Return contents of updated input file
    return input.read()

