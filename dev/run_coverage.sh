#!/bin/bash

coverage run --source=lambda_services -m pytest
coverage report -m | tee coverage.txt
coverage html
coverage xml
