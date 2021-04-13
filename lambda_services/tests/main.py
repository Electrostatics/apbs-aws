"""Main program to process jobs on AWS."""

from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import datetime
from logging import basicConfig, getLogger
import logging
from io import TextIOWrapper
from os import listdir

from apbsjob import ApbsJob
from pdb2pqrjob import Pdb2PqrJob
from rclone import Rclone
from utiljob import get_job_ids_from_cache, get_job_type, submit_aws_job

_LOGGER = getLogger(__name__)


@dataclass
class JobGroup:
    """
    A struct to hold information about a collection of related jobs

    filename: The path and filename containing data
    fptr: The file pointer to the filename
    jobs: A list of jobs in the filename
    count: The number of jobs in the filename
    """

    # NOTE: https://docs.python.org/3/library/dataclasses.html
    filename: str
    fptr: TextIOWrapper = None
    jobs: list = field(default_factory=list)
    count: int = 0

    def append(self, element):
        """This is needed to allow jobs to be mutable."""
        self.jobs.append(element)


def build_parser():
    """Create an argument parser for processing command line arguments.

    Returns:
        rtype: ArgumentParser
    """

    desc = "\n\tProcess jobs on AWS"
    url = "https://pcycrb4wrf.execute-api.us-west-2.amazonaws.com/test/jobid"

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
        "--apitoken",
        type=str,
        default=url,
        help=("AWS API Endpoint to get S3 tokens"),
    )
    parser.add_argument(
        "--jobids",
        type=str,
        nargs="+",
        default=[],
        help=("Jobid"),
    )
    parser.add_argument(
        "--rcloneconfig",
        type=str,
        default="S3",
        help=("rclone config to use (rclone listremotes)"),
    )
    parser.add_argument(
        "--rcloneremotepath",
        type=str,
        default="apbs-azure-migration",
        help=("rclone remote path for config"),
    )
    parser.add_argument(
        "--rclonemountpath",
        type=str,
        default=None,
        required=True,
        help=("The directory for rclone to mount remote path"),
    )
    parser.add_argument(
        "--maxjobs",
        default=None,
        type=int,
        help=("The maximum number of jobs to process"),
    )
    parser.add_argument(
        "--loglevel",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help=("Set verbosity of output"),
    )
    # Add CACHE FILENAME
    return parser.parse_args()


def create_job(rclone, args, job_id, job_types) -> None:
    """Create all the parts of the job and submit it.

    Args:
        rclone (Rclone): A class to mount/unmount job directories
        args (ArgumentParser): The command line arguments
        job_id (str): A unique job id
        job_types (Dict): A dictionary to count the types of jobs
    """
    start_time = datetime.now()
    _LOGGER.debug("MOUNTPATH: %s", args.rclonemountpath)
    rclone.mount(args.rcloneremotepath + f"/{job_id}", args.rclonemountpath)
    file_list = listdir(args.rclonemountpath)
    _LOGGER.debug("FILES: %s", file_list)
    job_type = get_job_type(file_list)
    _LOGGER.debug("JOBTYPE: %s = %s", job_id, job_type)
    job_types[job_type] += 1
    new_job = None
    if job_type in "apbs":
        new_job = ApbsJob(job_id, args.rclonemountpath, file_list)
    if job_type in "pdb2pqr":
        new_job = Pdb2PqrJob(job_id, args.rclonemountpath, file_list)
    _LOGGER.info("=" * 60)
    _LOGGER.info("JOB: %s", new_job)
    new_job.build_job_file()
    _LOGGER.info("RUNTIME: %s", new_job.get_execution_time())
    _LOGGER.info("MEMORY: %s", new_job.get_memory_usage())
    _LOGGER.info("STORAGE: %s", new_job.get_storage_usage())
    submit_aws_job(args.apitoken, new_job)
    _LOGGER.info("TIME TO CREATE JOB: %s", str(datetime.now() - start_time))


def main() -> None:
    """
    The algorithm is pretty simple:
      - Create Rclone that can be used to mount remote directories (e.g. S3)
      - Read in job ids from a cache
      - Parse existing job information and create a new job to submit

    :return:  None
    """

    args = build_parser()
    rclone = Rclone(args.rcloneconfig)
    basicConfig(
        format="%(levelname)s:%(message)s",
        level=getattr(logging, args.loglevel),
    )

    job_types = {"apbs": 0, "pdb2pqr": 0, "combined": 0, "unknown": 0}
    job_caches = {
        "apbs": JobGroup(filename="cache_meta/cache_apbs.txt"),
        "pdb2pqr": JobGroup(filename="cache_meta/cache_pdb2pqr.txt"),
        "combined": JobGroup(filename="cache_meta/cache_combined.txt"),
    }

    # NOTE: This is so you can use multiple context handlers
    #       so you can open multiple files at the same time safely.
    with ExitStack() as stack:
        for key, target in job_caches.items():
            fname = target.filename
            file_handle = stack.enter_context(open(fname))
            job_list = get_job_ids_from_cache(fname)
            target.fptr = file_handle
            target.jobs = job_list
            target.count = len(job_list)
            _LOGGER.debug("STACK: %s %s", key, target.count)

    firsttime = datetime.now()
    lasttime = firsttime
    if args.jobids:
        _LOGGER.debug("Looking for jobs: %s", args.jobids)
    for key in ["apbs", "pdb2pqr"]:
        for idx, job_id in enumerate(job_caches[key].jobs, start=1):
            if args.maxjobs is not None and idx > args.maxjobs:
                break
            if args.jobids is not None and job_id not in args.jobids:
                continue
            if idx % 50 == 0:
                interval_time = datetime.now()
                _LOGGER.debug(
                    "IDX: %s %s %s",
                    idx,
                    str(interval_time - lasttime),
                    str(interval_time - firsttime),
                )
                lasttime = interval_time
            create_job(rclone, args, job_id, job_types)

    _LOGGER.info("TIME TO RUN: %s", str(datetime.now() - lasttime))
    _LOGGER.info("JOBTYPES = %s", job_types)


if __name__ == "__main__":
    main()
