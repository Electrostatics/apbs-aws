from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from datetime import datetime
from logging import getLogger, ERROR, INFO
from os import path
from pathlib import Path
from sys import exit

from .AzureClient import AzureClient

# import AzureClient


_LOGGER = getLogger(__name__)


def get_jobs_from_cache(azure_client):
    jobs = []
    cache_file = "AZURE_CACHE.txt"
    if path.exists(cache_file) and path.isfile(cache_file):
        with open(cache_file, "r") as fh:
            for curline in fh:
                jobs.append(fh.readline().strip("\n"))
    else:
        jobs = azure_client.walk2(5000, 100000)
        with open(cache_file, "w") as outfile:
            for job in jobs:
                print(job, file=outfile)
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
        "--jobdir",
        type=str,
        default="MISSING",
        required=True,
        help=("Local download directory to copy from Azure"),
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
    return parser.parse_args()


def main() -> None:
    """
    :return:  None
    """

    args = build_parser()

    _LOGGER.setLevel(ERROR)
    if args.verbose:
        _LOGGER.setLevel(INFO)

    lasttime = datetime.now()

    # Create a client that is connected to Azure storage container

    try:
        azure_client = AzureClient.AzureClient(
            args.azconnection, args.azcontainer, args.jobdir
        )
    except Exception as sysexc:
        print(f"ERROR: Exception, {sysexc}")
        exit(1)

    # TODO: Make this a command line argument
    max_jobs = 10
    jobs = get_jobs_from_cache(azure_client)
    for idx, job in enumerate(jobs, start=1):
        # if idx % 5 != 0:
        #    continue
        if idx > max_jobs:
            break
        if args.jobid is not None and args.jobid not in job:
            continue
        # print(f"JOB: {job}")
        print(f"FILE LIST: {azure_client.ls_files(job, recursive=True)}")

    _LOGGER.info("DONE: %s", str(datetime.now() - lasttime))


if __name__ == "__main__":
    main()