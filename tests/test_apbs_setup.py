"""This file tests functions for setting up APBS jobs."""
from json import load
from pathlib import Path
import pytest

from .constants import INPUT_DIR, REF_DIR
from lambda_services.job_service.launcher.apbs_runner import Runner
from lambda_services.job_service.launcher.utils import apbs_infile_creator


@pytest.mark.parametrize(
    "pqr_file_name, form_input_filename, expected_infile_name,",
    [
        pytest.param("1fas.pqr", "test_apbs_setup-1fas-default.json", "1fas-default.in", id="1fas-default"),
        pytest.param("1fas.pqr", "test_apbs_setup-1fas-ion.json", "1fas-ion.in", id="1fas-ion"),
    ],
)
def test_apbs_infile_creator(pqr_file_name: str, form_input_filename: str, expected_infile_name: str):

    # Get path information
    expected_path: Path = REF_DIR / Path(expected_infile_name)
    form_path: Path = INPUT_DIR / Path(form_input_filename)

    # Set sample job information
    job_id: str = "sampleId"
    job_date: str = "2021-05-16"
    job_tag: str = f"{job_date}/{job_id}"

    # Load input data
    form_data: dict = load(open(form_path))
    apbs_options: Runner = Runner(form_data, job_id, job_date).apbs_options
    apbs_options["pqrFileName"] = pqr_file_name

    # Generate input file contents
    new_infile_contents: str = apbs_infile_creator(job_tag, apbs_options)

    # Compare contents with reference file
    assert new_infile_contents == open(expected_path, 'r').read()
