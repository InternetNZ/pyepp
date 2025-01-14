#!/bin/sh
command -v git>/dev/null && (cd "$(git rev-parse --show-toplevel)" || exit)
# exit when any command fails
set -e

# W0511 = TODO

# run pylint on app
pylint ./pyepp --disable=R0401,R0801 # disabled R0401 and R0801 because pylint complained without reason
