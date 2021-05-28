"""Base class containing shared methods used in APBS/PDB2PQR setup classes."""

from urllib3.util import parse_url
from .utils import _LOGGER


class JobDirectoryExistsError(Exception):
    def __init__(self, expression):
        self.expression = expression


class MissingFilesError(FileNotFoundError):
    def __init__(self, message, file_list=[]):
        super().__init__(message)
        self.missing_files = file_list


class JobSetup:
    def __init__(self, job_id: str, job_date: str) -> None:
        self.job_id = job_id
        self.job_date = job_date
        self.job_tag = f"{job_date}/{job_id}"
        self.input_files = []
        self.output_files = []
        self._missing_files = []

    def is_url(self, file_string: str):
        url_obj = parse_url(file_string)
        return url_obj.scheme is not None

    def get_object_name(self, filename):
        if self.is_url(filename):
            raise ValueError(
                f"{self.job_tag} 'file_name' " f"value is a URL: {filename}"
            )
        return f"{self.job_tag}/{filename}"

    def add_input_file(self, file_name: str):
        if not self.is_url(file_name):
            file_name = f"{self.job_tag}/{file_name}"
        _LOGGER.debug("%s Adding an input file, %s", self.job_tag, file_name)
        self.input_files.append(file_name)

    def add_output_file(self, file_name: str):
        file_name = self.get_object_name(file_name)
        _LOGGER.debug("%s Adding an output file, %s", self.job_tag, file_name)
        self.output_files.append(file_name)

    def add_missing_file(self, file_name: str):
        file_name = self.get_object_name(file_name)
        _LOGGER.debug("%s Adding a missing file, %s", self.job_tag, file_name)
        self._missing_files.append(file_name)
