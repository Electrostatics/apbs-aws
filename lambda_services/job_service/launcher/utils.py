from io import StringIO
import logging
import boto3
from botocore.exceptions import ClientError


def s3_download_file_str(bucket_name: str, object_name: str) -> str:
    try:
        s3_client = boto3.client('s3')
        s3_response: dict = s3_client.get_object(
                                Bucket=bucket_name,
                                Key=object_name,
                            )
        object_str = s3_response['Body'].read().decode('utf-8')
        return object_str

    except Exception as err:
        logging.error('ERROR: %s', err)
        raise


def s3_put_object(bucket_name: str, object_name: str, body):
    s3_client = boto3.client('s3')
    s3_response = s3_client.put_object(
                        Bucket=bucket_name,
                        Key=object_name,
                        Body=body,
                    )


def s3_object_exists(bucket_name: str, object_name: str) -> bool:
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
    read_start = False
    read_end = False
    file_list = []
    for whole_line in StringIO(u'%s' % infile_text):
        line = whole_line.strip()

        if read_start and read_end:
            break

        elif not read_start and not read_end:
            if line.startswith('#'):
                pass
            else:
                split_line = line.split()
                if len(split_line) > 0:
                    if split_line[0].upper() == 'READ':
                        # print('ENTERING READ SECTION')
                        read_start = True
                    elif split_line[0].upper() == 'END':
                        # print('LEAVING READ SECTION')
                        read_end = True

        elif read_start and not read_end:
            if line.startswith('#'):
                pass
            else:
                split_line = line.split()
                if len(split_line) > 0:
                    if split_line[0].upper() == 'END':
                        # print('LEAVING READ SECTION')
                        read_end = True
                    else:
                        for arg in line.split()[2:]:
                            if arg.startswith('#'):
                                break
                            file_list.append(arg)

    return file_list


def apbs_infile_creator(apbsOptions: dict) -> str:
    """
        Creates a new APBS input file, using the data from the form
    """

    # apbsOptions['tempFile'] = "apbsinput.in"
    apbsOptions['tab'] = "    "  # 4 spaces - used for writing to file
    # input = open('%s/tmp/%s/%s' % (INSTALLDIR, apbsOptions['writeStem'], apbsOptions['tempFile']), 'w')
    apbsinput_io = StringIO()

    # print("apbsOptions['tmpDirName'] = " + apbsOptions['tmpDirName'])
    # print("apbsOptions['tempFile'] = " + apbsOptions['tempFile'])
    # print("apbsOptions['pqrPath'] = " + apbsOptions['pqrPath'])
    # print("apbsOptions['pqrFileName'] = " + apbsOptions['pqrFileName'])

    # writing READ section to file
    apbsinput_io.write('read\n')
    apbsinput_io.write('%s%s %s %s%s' % (apbsOptions['tab'], apbsOptions['readType'], apbsOptions['readFormat'], apbsOptions['pqrPath'], apbsOptions['pqrFileName']))
    apbsinput_io.write('\nend\n')

    # writing ELEC section to file
    apbsinput_io.write('elec\n')
    apbsinput_io.write('%s%s\n' % (apbsOptions['tab'], apbsOptions['calcType']))
    if apbsOptions['calcType'] != "fe-manual":
        apbsinput_io.write('%sdime %d %d %d\n' % (apbsOptions['tab'], apbsOptions['dimeNX'], apbsOptions['dimeNY'], apbsOptions['dimeNZ']))
    if apbsOptions['calcType'] == "mg-para":
        apbsinput_io.write('%spdime %d %d %d\n' % (apbsOptions['tab'], apbsOptions['pdimeNX'], apbsOptions['pdimeNY'], apbsOptions['pdimeNZ']))
        apbsinput_io.write('%sofrac %g\n' % (apbsOptions['tab'], apbsOptions['ofrac']))
        if apbsOptions['asyncflag']:
            apbsinput_io.write('%sasync %d\n' % (apbsOptions['tab'], apbsOptions['async']))

    if apbsOptions['calcType'] == "mg-manual":
        apbsinput_io.write('%sglen %g %g %g\n' % (apbsOptions['tab'], apbsOptions['glenX'], apbsOptions['glenY'], apbsOptions['glenZ']))
    if apbsOptions['calcType'] in ['mg-auto', 'mg-para', 'mg-dummy']:
        apbsinput_io.write('%scglen %g %g %g\n' % (apbsOptions['tab'], apbsOptions['cglenX'], apbsOptions['cglenY'], apbsOptions['cglenZ']))
    if apbsOptions['calcType'] in ['mg-auto', 'mg-para']:
        apbsinput_io.write('%sfglen %g %g %g\n' % (apbsOptions['tab'], apbsOptions['fglenX'], apbsOptions['fglenY'], apbsOptions['fglenZ']))

        if apbsOptions['coarseGridCenterMethod'] == 'molecule':
            apbsinput_io.write('%scgcent mol %d\n' % (apbsOptions['tab'], apbsOptions['coarseGridCenterMoleculeID']))
        elif apbsOptions['coarseGridCenterMethod'] == 'coordinate':
            apbsinput_io.write('%scgcent %d %d %d\n' % (apbsOptions['tab'], apbsOptions['cgxCent'], apbsOptions['cgyCent'], apbsOptions['cgzCent']))

        if apbsOptions['fineGridCenterMethod'] == 'molecule':
            apbsinput_io.write('%sfgcent mol %d\n' % (apbsOptions['tab'], apbsOptions['fineGridCenterMoleculeID']))
        elif apbsOptions['fineGridCenterMethod'] == 'coordinate':
            apbsinput_io.write('%sfgcent %d %d %d\n' % (apbsOptions['tab'], apbsOptions['fgxCent'], apbsOptions['fgyCent'], apbsOptions['fgzCent']))

    if apbsOptions['calcType'] in ['mg-manual', 'mg-dummy']:
        if apbsOptions['gridCenterMethod'] == 'molecule':
            apbsinput_io.write('%sgcent mol %d\n' % (apbsOptions['tab'], apbsOptions['gridCenterMoleculeID']))
        elif apbsOptions['gridCenterMethod'] == 'coordinate':
            apbsinput_io.write('%sgcent %d %d %d\n' % (apbsOptions['tab'], apbsOptions['gxCent'], apbsOptions['gyCent'], apbsOptions['gzCent']))

    apbsinput_io.write('%smol %d\n' % (apbsOptions['tab'], apbsOptions['mol']))
    apbsinput_io.write('%s%s\n' % (apbsOptions['tab'], apbsOptions['solveType']))
    apbsinput_io.write('%sbcfl %s\n' % (apbsOptions['tab'], apbsOptions['boundaryConditions']))
    apbsinput_io.write('%spdie %g\n' % (apbsOptions['tab'], apbsOptions['biomolecularDielectricConstant']))
    apbsinput_io.write('%ssdie %g\n' % (apbsOptions['tab'], apbsOptions['dielectricSolventConstant']))
    apbsinput_io.write('%ssrfm %s\n' % (apbsOptions['tab'], apbsOptions['dielectricIonAccessibilityModel']))
    apbsinput_io.write('%schgm %s\n' % (apbsOptions['tab'], apbsOptions['biomolecularPointChargeMapMethod']))
    apbsinput_io.write('%ssdens %g\n' % (apbsOptions['tab'], apbsOptions['surfaceConstructionResolution']))
    apbsinput_io.write('%ssrad %g\n' % (apbsOptions['tab'], apbsOptions['solventRadius']))
    apbsinput_io.write('%sswin %g\n' % (apbsOptions['tab'], apbsOptions['surfaceDefSupportSize']))
    apbsinput_io.write('%stemp %g\n' % (apbsOptions['tab'], apbsOptions['temperature']))
    apbsinput_io.write('%scalcenergy %s\n' % (apbsOptions['tab'], apbsOptions['calcEnergy']))
    apbsinput_io.write('%scalcforce %s\n' % (apbsOptions['tab'], apbsOptions['calcForce']))
    for i in range(0, 3):
        ch_str = 'charge%i' % i
        conc_str = 'conc%i' % i
        rad_str = 'radius%i' % i
        # if apbsOptions.has_key(chStr) and apbsOptions.has_key(concStr) and apbsOptions.has_key(radStr):
        if ('chStr' in apbsOptions) and ('concStr' in apbsOptions) and ('radStr' in apbsOptions):
            # ion charge {charge} conc {conc} radius {radius}
            apbsinput_io.write('%sion charge %d conc %g radius %g\n' % (apbsOptions['tab'],
                                                                        apbsOptions[ch_str],
                                                                        apbsOptions[conc_str],
                                                                        apbsOptions[rad_str]))

    if apbsOptions['writeCharge']:
        apbsinput_io.write('%swrite charge %s %s-charge\n' % (apbsOptions['tab'], apbsOptions['writeFormat'], apbsOptions['writeStem']))

    if apbsOptions['writePot']:
        apbsinput_io.write('%swrite pot %s %s-pot\n' % (apbsOptions['tab'], apbsOptions['writeFormat'], apbsOptions['writeStem']))

    if apbsOptions['writeSmol']:
        apbsinput_io.write('%swrite smol %s %s-smol\n' % (apbsOptions['tab'], apbsOptions['writeFormat'], apbsOptions['writeStem']))

    if apbsOptions['writeSspl']:
        apbsinput_io.write('%swrite sspl %s %s-sspl\n' % (apbsOptions['tab'], apbsOptions['writeFormat'],  apbsOptions['writeStem']))

    if apbsOptions['writeVdw']:
        apbsinput_io.write('%swrite vdw %s %s-vdw\n' % (apbsOptions['tab'], apbsOptions['writeFormat'], apbsOptions['writeStem']))

    if apbsOptions['writeIvdw']:
        apbsinput_io.write('%swrite ivdw %s %s-ivdw\n' % (apbsOptions['tab'], apbsOptions['writeFormat'], apbsOptions['writeStem']))

    if apbsOptions['writeLap']:
        apbsinput_io.write('%swrite lap %s %s-lap\n' % (apbsOptions['tab'], apbsOptions['writeFormat'], apbsOptions['writeStem']))

    if apbsOptions['writeEdens']:
        apbsinput_io.write('%swrite edens %s %s-edens\n' % (apbsOptions['tab'], apbsOptions['writeFormat'], apbsOptions['writeStem']))

    if apbsOptions['writeNdens']:
        apbsinput_io.write('%swrite ndens %s %s-ndens\n' % (apbsOptions['tab'], apbsOptions['writeFormat'], apbsOptions['writeStem']))

    if apbsOptions['writeQdens']:
        apbsinput_io.write('%swrite qdens %s %s-qdens\n' % (apbsOptions['tab'], apbsOptions['writeFormat'], apbsOptions['writeStem']))

    if apbsOptions['writeDielx']:
        apbsinput_io.write('%swrite dielx %s %s-dielx\n' % (apbsOptions['tab'], apbsOptions['writeFormat'], apbsOptions['writeStem']))

    if apbsOptions['writeDiely']:
        apbsinput_io.write('%swrite diely %s %s-diely\n' % (apbsOptions['tab'], apbsOptions['writeFormat'], apbsOptions['writeStem']))

    if apbsOptions['writeDielz']:
        apbsinput_io.write('%swrite dielz %s %s-dielz\n' % (apbsOptions['tab'], apbsOptions['writeFormat'], apbsOptions['writeStem']))

    if apbsOptions['writeKappa']:
        apbsinput_io.write('%swrite kappa %s %s-kappa\n' % (apbsOptions['tab'], apbsOptions['writeFormat'], apbsOptions['writeStem']))

    apbsinput_io.write('end\n')
    apbsinput_io.write('quit')

    # input.close()
    apbsinput_io.seek(0)

    # Return contents of updated input file
    return apbsinput_io.read()
