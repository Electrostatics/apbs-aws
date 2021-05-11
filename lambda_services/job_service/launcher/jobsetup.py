from urllib3.util import parse_url


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
        self.input_files = []
        self.output_files = []
        self._missing_files = []

    def add_input_file(self, file_name: str):
        if self.is_url(file_name):
            self.input_files.append(file_name)
        else:
            self.input_files.append(
                f"{self.job_date}/{self.job_id}/{file_name}"
            )

    def add_output_file(self, file_name: str):
        if self.is_url(file_name):
            raise ValueError(
                f"{self.job_id} {self.job_date} 'file_name' "
                f"value is a URL: {file_name}"
            )
        self.output_files.append(f"{self.job_date}/{self.job_id}/{file_name}")

    def add_missing_file(self, file_name: str):
        if self.is_url(file_name):
            raise ValueError(
                f"{self.job_id} {self.job_date} 'file_name' "
                f"value is a URL: {file_name}"
            )
        self._missing_files.append(f"{self.job_date}/{self.job_id}/{file_name}")

    def is_url(self, file_string: str):
        url_obj = parse_url(file_string)
        return url_obj.scheme is not None
