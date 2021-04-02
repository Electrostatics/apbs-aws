"""Main program to process jobs from Azure to AWS."""

from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from datetime import datetime
from logging import getLogger, ERROR, INFO
from os import path as ospath
from sys import exit

from azureapbs import AzureClient

_LOGGER = getLogger(__name__)


def get_job_type(file_list):
    apbs_job_type = False
    pdb2pqr_job_type = False
    for filename in file_list:
        if filename.endswith(".dx") or filename in "apbs_end_time":
            apbs_job_type = True
        if filename.endswith(".propka") or filename in "pdb2pqr_end_time":
            pdb2pqr_job_type = True
    if apbs_job_type and pdb2pqr_job_type:
        return "combined"
    if apbs_job_type:
        return "apbs"
    if pdb2pqr_job_type:
        return "pdb2pqr"
    return "unknown"


def get_jobs_from_cache(jobid_cache, job_filelist_cache, azure_client):
    jobs = []
    jobs_done = []
    if ospath.exists(job_filelist_cache) and ospath.isfile(job_filelist_cache):
        with open(job_filelist_cache, "r") as fh:
            for curline in fh:
                jobs_done.append(curline.strip("\n"))
    if ospath.exists(jobid_cache) and ospath.isfile(jobid_cache):
        with open(jobid_cache, "r") as fh:
            for curline in fh:
                curline = curline.strip("\n")
                if curline not in jobs_done:
                    jobs.append(curline)
    else:
        jobs = azure_client.walk2(5000, 100000)
        with open(jobid_cache, "w") as outfile:
            for job in jobs:
                print(job, file=outfile)
    # print(f"JOBS: {len(jobs)} {jobs}")
    # exit(1)
    return jobs


def build_parser():
    """Build argument parser.

    :return:  argument parser
    :rtype:  ArgumentParser
    """
    desc = f"\n\tCopy jobs from Azure to AWS"

    parser = ArgumentParser(
        description=desc,
        formatter_class=ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print out verbose output",
    )
    parser.add_argument(
        "--azconnection",
        type=str,
        default="MISSING",
        required=True,
        help=(
            "Azure connection string that looks something like"
            "'DefaultEndpointsProtocol=https;AccountName=apbsminio;"
            "AccountKey=ReallyLongSequenceOfCharactersThatMakeUpTheHashedKeyForYour"
            "AccountThatWouldBeHardToMemorizeOrUnderstand;"
            "EndpointSuffix=core.windows.net'"
        ),
    )
    parser.add_argument(
        "--azcontainer",
        type=str,
        default="MISSING",
        required=True,
        help=("Azure storage container name"),
    )
    parser.add_argument(
        "--cachedir",
        type=str,
        default="MISSING",
        required=True,
        help=("Local download directory to cache jobs from Azure"),
    )
    parser.add_argument(
        "--cachejoblist",
        type=str,
        default="cache_meta/AZURE_CACHE.txt",
        help=("Local download file to cache job ids from Azure"),
    )
    parser.add_argument(
        "--cachejobfilelist",
        type=str,
        default="cache_meta/AZURE_FILELIST_CACHE.txt",
        help=(
            "Local download file to cache list of files for job ids from Azure"
        ),
    )
    parser.add_argument(
        "--apitoken",
        type=str,
        default="https://pcycrb4wrf.execute-api.us-west-2.amazonaws.com/test/jobid",
        help=("AWS API Endpoint to get S3 tokens"),
    )
    parser.add_argument(
        "--jobid",
        type=str,
        default=None,
        help=("Azure Jobid"),
    )
    parser.add_argument(
        "--maxjobs",
        type=int,
        default=None,
        help=("The maximum number of jobs to process"),
    )
    # Add CACHE FILLENAME
    return parser.parse_args()


def main() -> None:
    """
    :return:  None
    """

    args = build_parser()

    _LOGGER.setLevel(ERROR)
    if args.verbose:
        _LOGGER.setLevel(INFO)

    # Create a client that is connected to Azure storage container

    try:
        azure_client = AzureClient(
            args.azconnection, args.azcontainer, args.cachedir
        )
    except Exception as sysexc:
        print(f"ERROR: Exception, {sysexc}")
        exit(1)

    # TODO: Make this a command line argument
    jobs = get_jobs_from_cache(
        args.cachejoblist, args.cachejobfilelist, azure_client
    )
    job_types = {"apbs": 0, "pdb2pqr": 0, "combined": 0, "unknown": 0}
    firsttime = datetime.now()
    lasttime = firsttime
    apbs_fh = open("cache_apbs.txt", "a")
    pdb2pqr_fh = open("cache_pdb2pqr.txt", "a")
    combined_fh = open("cache_combined.txt", "a")
    unknown_fh = open("cache_unknown.txt", "a")
    job_caches = {
        "apbs": apbs_fh,
        "pdb2pqr": pdb2pqr_fh,
        "combined": combined_fh,
        "unknown": unknown_fh,
    }
    for idx, job in enumerate(jobs, start=1):
        if idx % 50 == 0:
            interval_time = datetime.now()
            print(
                f"IDX: {idx} {str(interval_time - lasttime)} {str(interval_time - firsttime)}"
            )
            lasttime = interval_time
        if args.maxjobs is not None and idx > args.maxjobs:
            break
        if args.jobid is not None and args.jobid not in job:
            continue
        # print(f"JOB: {job}")
        file_list = azure_client.ls_files(job, recursive=True)
        job_type = get_job_type(file_list)
        job_types[job_type] += 1
        print(f"{job} {file_list}", file=job_caches[job_type])

    _LOGGER.info("DONE: %s", str(datetime.now() - lasttime))
    apbs_fh.close()
    pdb2pqr_fh.close()
    combined_fh.close()
    unknown_fh.close()
    print(f"{job_types}")


if __name__ == "__main__":
    main()