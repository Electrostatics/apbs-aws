
from pathlib import Path
import pytest

from lambda_services.job_service.launcher.utils import apbs_infile_creator
from .constants import REF_DIR


@pytest.mark.parametrize(
    "expected_infile_path,",
    [
        pytest.param("1fas-default.in", id="1fas-default"),
        pytest.param("1fas-ion.in", id="1fas-ion"),
    ],
)
def test_apbs_infile_creator(tmp_path, expected_infile_name: str):

    job_tag: str
    apbs_options: dict
    expected_path: Path = REF_DIR / Path(expected_infile_name)

    # TODO: create dummy job_tag
    job_tag = ""
    # TODO: create dummy apbs_options
    apbs_options = {}

    # create input file from options
    new_infile_contents = apbs_infile_creator(job_tag, apbs_options)

    # Get contents of expected file and compare
    assert new_infile_contents == open(expected_path, 'r').read()
