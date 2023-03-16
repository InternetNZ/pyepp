#!/bin/sh
command -v git>/dev/null && (cd "$(git rev-parse --show-toplevel)" || exit)

# exit when any command fails
set -e

# run unit tests and collect data for coverage
coverage run -m pytest tests/

# coverage report
coverage report -m
