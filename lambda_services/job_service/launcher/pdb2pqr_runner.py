import os
import logging
from .jobsetup import JobSetup
from .weboptions import WebOptions, WebOptionsError


class JobDirectoryExistsError(Exception):
    def __init__(self, expression):
        self.expression = expression


class Runner(JobSetup):
    def __init__(self, form: dict, job_id: str, job_date: str):
        super().__init__(job_id, job_date)
        # self.starttime = None
        # self.job_id = None
        self.weboptions = None
        self.invoke_method = None
        self.cli_params = None
        self.command_line_args: str = None
        self.job_id = job_id
        self.input_files = []
        self.output_files = []
        self.estimated_max_runtime = 2700

        try:
            if "invoke_method" in form:
                logging.info(
                    "%s Invoke_method found, value: %s", self.job_id,
                    str(form["invoke_method"]),
                )
                if form["invoke_method"].lower() in ["v2", "cli"]:
                    self.invoke_method = "cli"
                    self.cli_params = {
                        "pdb_name": form["pdb_name"],
                        "pqr_name": form["pqr_name"],
                        "flags": form["flags"],
                    }

                elif form["invoke_method"].lower() in ["v1", "gui"]:
                    self.invoke_method = "gui"
                    self.weboptions = WebOptions(form)
            else:
                logging.warning(
                    "%s Invoke_method not found: %s", job_id, str("invoke_method" in form)
                )
                if "invoke_method" in form:
                    logging.debug(
                        "%s Form['invoke_method']: %s", job_id, str(form["invoke_method"])
                    )
                    logging.debug("%s Form type: %s", job_id, type(form["invoke_method"]))
                self.invoke_method = "gui"
                self.weboptions = WebOptions(form)

        except WebOptionsError:
            raise

    def prepare_job(self):
        job_id = self.job_id

        if self.invoke_method in ["gui", "v1"]:
            command_line_args = self.version_1_job(job_id)
        elif self.invoke_method in ["cli", "v2"]:
            command_line_args = self.version_2_job()
        self.command_line_args = command_line_args
        return command_line_args

    def version_2_job(self):
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
        result = f"{result} {self.cli_params['pdb_name']} {self.cli_params['pqr_name']}"

        return result

    def version_1_job(self, job_id):
        # Retrieve information about the
        #   PDB fileand command line arguments
        if self.weboptions.user_did_upload:
            # Update input files
            self.add_input_file(self.weboptions.pdbfilename)
        else:
            if os.path.splitext(self.weboptions.pdbfilename)[1] != ".pdb":
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

        logging.debug(result)
        logging.debug(self.weboptions.pdbfilename)

        return result
