"""A class to interpret/prepare a PDB2PQR job submission for job queue."""

from os.path import splitext

from .jobsetup import JobSetup
from .utils import _LOGGER
from .weboptions import WebOptions, WebOptionsError


class Runner(JobSetup):
    """Class to setup a PDB2PQR job."""

    def __init__(self, form: dict, job_id: str, job_date: str):
        super().__init__(job_id, job_date)
        self.weboptions = None
        self.invoke_method = "gui" # Assumes web submission unless specified
        self.cli_params = None
        self.command_line_args: str = None
        self.job_id = job_id
        self.estimated_max_runtime = 2700

        try:
            # Reassign self.invoke_method if found in form
            if "invoke_method" in form:
                _LOGGER.info(
                    "%s Submission method specified: %s",
                    self.job_tag,
                    str(form["invoke_method"]),
                )
                submission_method = form["invoke_method"].lower()
                if submission_method in ["v2", "cli"]:
                    self.invoke_method = "cli"
                    self.cli_params = {
                        "pdb_name": form["pdb_name"],
                        "pqr_name": form["pqr_name"],
                        "flags": form["flags"],
                    }
                elif submission_method in ["v1", "gui"]:
                    self.invoke_method = submission_method

            # Instantiate self.weboptions if job is web submission
            if self.invoke_method in ("v1", "gui"):
                self.weboptions = WebOptions(self.job_tag, form)

        except WebOptionsError:
            raise

    def prepare_job(self):
        """Setup the job to run from the GUI or the command line."""
        job_id = self.job_id

        if self.invoke_method in ["gui", "v1"]:
            command_line_args = self.version_1_job(job_id)
        elif self.invoke_method in ["cli", "v2"]:
            command_line_args = self.version_2_job()
        self.command_line_args = command_line_args
        _LOGGER.debug(
            "%s Using command line arguments: %s",
            self.job_tag,
            command_line_args,
        )
        return command_line_args

    def version_2_job(self):
        """Setup the job to run from the command line."""
        # construct command line argument string for when CLI is invoked
        command_line_list = []

        # Add PDB filename to input file list
        self.add_input_file(self.cli_params["pdb_name"])

        # get list of args from self.cli_params['flags']
        for name in self.cli_params["flags"]:
            command_line_list.append((name, self.cli_params["flags"][name]))

            # Add to input file list if userff, names,
            #  or ligand flags are defined
            if (
                name in ["userff", "usernames", "ligand"]
                and self.cli_params[name]
            ):
                self.add_input_file(self.cli_params[name])

        result = ""

        # append to command_line_str
        for pair in command_line_list:
            # TODO: add conditionals later to
            #       distinguish between data types
            if isinstance(pair[1], bool):
                cli_arg = f"--{pair[0]}"
            else:
                cli_arg = f"--{pair[0]}={str(pair[1])}"
            result = f"{result} {cli_arg}"

        # Add PDB and PQR file names to command line string
        result = (
            f"{result} {self.cli_params['pdb_name']} "
            f"{self.cli_params['pqr_name']}"
        )

        return result

    def version_1_job(self, job_id):
        """Setup the job to run from the Web GUI."""
        # Retrieve information about the
        #   PDB fileand command line arguments
        if self.weboptions.user_did_upload:
            # Update input files
            self.add_input_file(self.weboptions.pdbfilename)
        else:
            if splitext(self.weboptions.pdbfilename)[1] != ".pdb":
                self.weboptions.pdbfilename = (
                    self.weboptions.pdbfilename + ".pdb"
                )  # add pdb extension to pdbfilename

                # Add url to RCSB PDB file to input file list
                self.add_input_file(
                    f"https://files.rcsb.org/download/"
                    f"{self.weboptions.pdbfilename}"
                )

        # Check for userff, names, ligand files to add to input_file list
        if hasattr(self.weboptions, "ligandfilename"):
            self.add_input_file(self.weboptions.ligandfilename)
        if hasattr(self.weboptions, "userfffilename"):
            self.add_input_file(self.weboptions.userfffilename)
        if hasattr(self.weboptions, "usernamesfilename"):
            self.add_input_file(self.weboptions.usernamesfilename)

        # Make the pqr name prefix the job_id
        self.weboptions.pqrfilename = job_id + ".pqr"

        # Retrieve PDB2PQR command line arguments
        result = self.weboptions.get_command_line()
        if "--summary" in result:
            result = result.replace("--summary", "")

        _LOGGER.debug("%s Generated CLI args: %s", self.job_tag, result)
        _LOGGER.debug(
            "%s PDB Filename: %s", self.job_tag, self.weboptions.pdbfilename
        )

        return result
