#!/bin/sh
command -v git>/dev/null && (cd "$(git rev-parse --show-toplevel)" || exit)

bandit -r ./pyepp
