# coding: utf-8
"""Utilities for APBS and PDB2PQR jobs."""

from enum import Enum
from logging import basicConfig, getLogger, INFO, StreamHandler
from os.path import isfile
from os import getenv
from sys import stdout

_LOGGER = getLogger(__name__)
LOGGER_FORMAT = (
    "[%(levelname)s] "
    "[%(filename)s:%(lineno)s:%(funcName)s()] "
    "%(message)s"
)
basicConfig(
    format=LOGGER_FORMAT,
    level=int(getenv("LOG_LEVEL", str(INFO))),
    handlers=[StreamHandler(stdout)],
)


class JOBTYPE(Enum):
    """The valid values for a job's type."""

    APBS = 1
    PDB2PQR = 2
    COMBINED = 3
    UNKNOWN = 4


def get_contents(filename):
    """[summary]

    Args:
        filename (str): The full path of the file to read from.

    Returns:
        List: The lines of the file with the newlines stripped.
    """
    lines = []
    _LOGGER.debug("GET_CONTENTS: %s", filename)
    if isfile(filename):
        with open(filename, "r") as fptr:
            for curline in fptr:
                curline = curline.strip("\n")
                if curline:
                    lines.append(curline)
    return lines
