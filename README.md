[![Python package](https://github.com/Electrostatics/apbs-aws/actions/workflows/python-package.yml/badge.svg)](https://github.com/Electrostatics/apbs-aws/actions/workflows/python-package.yml)
[![codecov](https://codecov.io/gh/Electrostatics/apbs-aws/branch/main/graph/badge.svg)](https://codecov.io/gh/Electrostatics/apbs-aws)
[![Documentation Status](https://readthedocs.org/projects/apbs-aws/badge/?version=latest)](https://apbs-aws.readthedocs.io/en/latest/?badge=latest)

APBS-AWS
============

This package contains the software to automate the workflow of APBS and PDB2PQR using Amazon Web Services. For more information, please see

* Home page:  http://www.poissonboltzmann.org/
* Documentation: http://apbs-aws.readthedocs.io


## Setting up Development Environment
Python 3.10 or newer is required, including for Ansible dependencies.
The patched urllib3 dependency no longer supports Python 3.8 or 3.9.
To setup a development environment, enter your Python3 environment of choice (e.g. virtualenv, conda, etc.). From the top of the repository in your terminal, enter the following:
```bash
pip install -e .[dev,test]
```
This will install all the necessary packages to develop and test the APBS-AWS software.  Check [`setup.py`](./setup.py) to view the list of packages.

The legacy Ansible Lambda configuration still specifies Python 3.6.
It must be migrated to a supported runtime and validated before deployment with these dependencies.
