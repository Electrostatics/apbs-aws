# coding: utf-8

from logging import getLogger
from os.path import isfile

_LOGGER = getLogger(__name__)

"""Utilities for APBS and PDB2PQR jobs."""

"""
DESCRIPTION:
"""


def get_contents(filename):
    lines = []
    _LOGGER.info("GET_CONTENTS: %s", filename)
    if isfile(filename):
        with open(filename, "r") as fh:
            for curline in fh:
                curline = curline.strip("\n")
                if curline:
                    lines.append(curline)
    return lines