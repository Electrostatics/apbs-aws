"""A collection of utility functions."""

from boto3 import client
from botocore.exceptions import ClientError
from io import StringIO
from logging import getLogger, ERROR, INFO

_LOGGER = getLogger(__name__)
_LOGGER.setLevel(ERROR)
_LOGGER.setLevel(INFO)


def s3_download_file_str(bucket_name: str, object_name: str) -> str:
    try:
        s3_client = client("s3")
        s3_response: dict = s3_client.get_object(
            Bucket=bucket_name,
            Key=object_name,
        )
        return s3_response["Body"].read().decode("utf-8")

    except Exception as err:
        _LOGGER.exception("%s ERROR: %s", bucket_name, err)
        raise


def s3_put_object(bucket_name: str, object_name: str, body):
    s3_client = client("s3")
    _ = s3_client.put_object(
        Bucket=bucket_name,
        Key=object_name,
        Body=body,
    )


def s3_object_exists(bucket_name: str, object_name: str) -> bool:
    s3_client = client("s3")
    try:
        _ = s3_client.head_object(
            Bucket=bucket_name,
            Key=object_name,
        )
        return True

    except ClientError as err:
        if err.response["Error"]["Code"] == "404":  # "NoSuchKey" error
            return False
        elif err.response["Error"]["Code"] == "403":  # "Forbidden" error
            objectname_split: list = object_name.split("/")
            job_id: str = objectname_split[-2]
            job_date: str = objectname_split[-3]
            _LOGGER.warn(
                "%s %s Received '%s' (%d) message on object HEAD: %s",
                job_id,
                job_date,
                err.response["Error"]["Message"],
                err.response["ResponseMetadata"]["HTTPStatusCode"],
                object_name,
            )
            return False
        else:
            raise


def apbs_extract_input_files(infile_text):
    # Read only the READ section of infile,
    # extracting out the files needed for APBS
    read_start = False
    read_end = False
    file_list = []
    for whole_line in StringIO(f"{infile_text}"):
        line = whole_line.strip()

        if read_start and read_end:
            break

        elif not read_start and not read_end:
            if not line.startswith("#"):
                split_line = line.split()
                if len(split_line) > 0:
                    if split_line[0].upper() == "READ":
                        # print('ENTERING READ SECTION')
                        read_start = True
                    elif split_line[0].upper() == "END":
                        # print('LEAVING READ SECTION')
                        read_end = True

        elif read_start:
            if not line.startswith("#"):
                split_line = line.split()
                if len(split_line) > 0:
                    if split_line[0].upper() == "END":
                        # print('LEAVING READ SECTION')
                        read_end = True
                    else:
                        for arg in line.split()[2:]:
                            file_list.append(arg)

    return file_list


def apbs_infile_creator(apbsOptions: dict) -> str:
    """
    Creates a new APBS input file, using the data from the form
    """

    # apbsOptions['tempFile'] = "apbsinput.in"
    apbsinput_io = StringIO()

    # writing READ section to file
    apbsinput_io.write("read\n")
    apbsinput_io.write(
        f"\t{apbsOptions['readType']} "
        f"{apbsOptions['readFormat']} "
        f"{apbsOptions['pqrPath']}{apbsOptions['pqrFileName']}\n"
    )
    apbsinput_io.write("end\n")

    # writing ELEC section to file
    apbsinput_io.write("elec\n")
    apbsinput_io.write(f"\t{apbsOptions['calcType']}\n")
    if apbsOptions["calcType"] != "fe-manual":
        apbsinput_io.write(
            f"\tdime {apbsOptions['dimeNX']} "
            f"{apbsOptions['dimeNY']} {apbsOptions['dimeNZ']}\n"
        )
    if apbsOptions["calcType"] == "mg-para":
        apbsinput_io.write(
            f"\tpdime {apbsOptions['pdimeNX']} "
            f"{apbsOptions['pdimeNY']} {apbsOptions['pdimeNZ']}\n"
        )
        apbsinput_io.write(f"\tofrac {apbsOptions['ofrac']}\n")
        if apbsOptions["asyncflag"]:
            apbsinput_io.write(f"\tasync {apbsOptions['async']}\n")

    if apbsOptions["calcType"] == "mg-manual":
        apbsinput_io.write(
            f"\tglen {apbsOptions['glenX']} "
            f"{apbsOptions['glenY']} {apbsOptions['glenZ']}\n"
        )
    if apbsOptions["calcType"] in ["mg-auto", "mg-para", "mg-dummy"]:
        apbsinput_io.write(
            f"\tcglen {apbsOptions['cglenX']} "
            f"{apbsOptions['cglenY']} {apbsOptions['cglenZ']}\n"
        )
    if apbsOptions["calcType"] in ["mg-auto", "mg-para"]:
        apbsinput_io.write(
            f"\tfglen {apbsOptions['fglenX']} "
            f"{apbsOptions['fglenY']} {apbsOptions['fglenZ']}\n"
        )

        if apbsOptions["coarseGridCenterMethod"] == "molecule":
            apbsinput_io.write(
                f"\tcgcent mol {apbsOptions['coarseGridCenterMoleculeID']}\n"
            )
        elif apbsOptions["coarseGridCenterMethod"] == "coordinate":
            apbsinput_io.write(
                f"\tcgcent {apbsOptions['cgxCent']} "
                f"{apbsOptions['cgyCent']} {apbsOptions['cgzCent']}\n"
            )

        if apbsOptions["fineGridCenterMethod"] == "molecule":
            apbsinput_io.write(
                f"\tfgcent mol {apbsOptions['fineGridCenterMoleculeID']}\n"
            )
        elif apbsOptions["fineGridCenterMethod"] == "coordinate":
            apbsinput_io.write(
                f"\tfgcent {apbsOptions['fgxCent']} "
                f"{apbsOptions['fgyCent']} {apbsOptions['fgzCent']}\n"
            )

    if apbsOptions["calcType"] in ["mg-manual", "mg-dummy"]:
        if apbsOptions["gridCenterMethod"] == "molecule":
            apbsinput_io.write(
                f"\tgcent mol {apbsOptions['gridCenterMoleculeID']}\n"
            )
        elif apbsOptions["gridCenterMethod"] == "coordinate":
            apbsinput_io.write(
                f"\tgcent {apbsOptions['gxCent']} "
                f"{apbsOptions['gyCent']} {apbsOptions['gzCent']}\n"
            )

    apbsinput_io.write(f"\tmol {apbsOptions['mol']}\n")
    apbsinput_io.write(f"\t{apbsOptions['solveType']}\n")
    apbsinput_io.write(f"\tbcfl {apbsOptions['boundaryConditions']}\n")
    apbsinput_io.write(
        f"\tpdie {apbsOptions['biomolecularDielectricConstant']}\n"
    )
    apbsinput_io.write(f"\tsdie {apbsOptions['dielectricSolventConstant']}\n")
    apbsinput_io.write(
        f"\tsrfm {apbsOptions['dielectricIonAccessibilityModel']}\n"
    )
    apbsinput_io.write(
        f"\tchgm {apbsOptions['biomolecularPointChargeMapMethod']}\n"
    )
    apbsinput_io.write(
        f"\tsdens {apbsOptions['surfaceConstructionResolution']}\n"
    )
    apbsinput_io.write(f"\tsrad {apbsOptions['solventRadius']}\n")
    apbsinput_io.write(f"\tswin {apbsOptions['surfaceDefSupportSize']}\n")
    apbsinput_io.write(f"\ttemp {apbsOptions['temperature']}\n")
    apbsinput_io.write(f"\tcalcenergy {apbsOptions['calcEnergy']}\n")
    apbsinput_io.write(f"\tcalcforce {apbsOptions['calcForce']}\n")
    for idx in range(3):
        ch_str = f"charge{idx}"
        conc_str = f"conc{idx}"
        rad_str = f"radius{idx}"
        if (
            ("chStr" in apbsOptions)
            and ("concStr" in apbsOptions)
            and ("radStr" in apbsOptions)
        ):
            # ion charge {charge} conc {conc} radius {radius}
            apbsinput_io.write(
                f"\tion charge {apbsOptions[ch_str]} "
                f"conc {apbsOptions[conc_str]} radius {apbsOptions[rad_str]}\n"
            )

    if apbsOptions["writeCharge"]:
        apbsinput_io.write(
            f"\twrite charge {apbsOptions['writeFormat']} "
            f"{apbsOptions['writeStem']}-charge\n"
        )

    if apbsOptions["writePot"]:
        apbsinput_io.write(
            f"\twrite pot {apbsOptions['writeFormat']} "
            f"{apbsOptions['writeStem']}-pot\n"
        )

    if apbsOptions["writeSmol"]:
        apbsinput_io.write(
            f"\twrite smol {apbsOptions['writeFormat']} "
            f"{apbsOptions['writeStem']}-smol\n"
        )

    if apbsOptions["writeSspl"]:
        apbsinput_io.write(
            f"\twrite sspl {apbsOptions['writeFormat']} "
            f"{apbsOptions['writeStem']}-sspl\n"
        )

    if apbsOptions["writeVdw"]:
        apbsinput_io.write(
            f"\twrite vdw {apbsOptions['writeFormat']} "
            f"{apbsOptions['writeStem']}-vdw\n"
        )

    if apbsOptions["writeIvdw"]:
        apbsinput_io.write(
            f"\twrite ivdw {apbsOptions['writeFormat']} "
            f"{apbsOptions['writeStem']}-ivdw\n"
        )

    if apbsOptions["writeLap"]:
        apbsinput_io.write(
            f"\twrite lap {apbsOptions['writeFormat']} "
            f"{apbsOptions['writeStem']}-lap\n"
        )

    if apbsOptions["writeEdens"]:
        apbsinput_io.write(
            f"\twrite edens {apbsOptions['writeFormat']} "
            f"{apbsOptions['writeStem']}-edens\n"
        )

    if apbsOptions["writeNdens"]:
        apbsinput_io.write(
            f"\twrite ndens {apbsOptions['writeFormat']} "
            f"{apbsOptions['writeStem']}-ndens\n"
        )

    if apbsOptions["writeQdens"]:
        apbsinput_io.write(
            f"\twrite qdens {apbsOptions['writeFormat']} "
            f"{apbsOptions['writeStem']}-qdens\n"
        )

    if apbsOptions["writeDielx"]:
        apbsinput_io.write(
            f"\twrite dielx {apbsOptions['writeFormat']} "
            f"{apbsOptions['writeStem']}-dielx\n"
        )

    if apbsOptions["writeDiely"]:
        apbsinput_io.write(
            f"\twrite diely {apbsOptions['writeFormat']} "
            f"{apbsOptions['writeStem']}-diely\n"
        )

    if apbsOptions["writeDielz"]:
        apbsinput_io.write(
            f"\twrite dielz {apbsOptions['writeFormat']} "
            f"{apbsOptions['writeStem']}-dielz\n"
        )

    if apbsOptions["writeKappa"]:
        apbsinput_io.write(
            f"\twrite kappa {apbsOptions['writeFormat']} "
            f"{apbsOptions['writeStem']}-kappa\n"
        )

    apbsinput_io.write("end\n")
    apbsinput_io.write("quit")

    # input.close()
    apbsinput_io.seek(0)

    # Return contents of updated input file
    return apbsinput_io.read()
