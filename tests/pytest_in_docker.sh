#!/bin/bash
# Usage:
#   ./tests/pytest_in_docker.sh                  # run all tests
#   ./tests/pytest_in_docker.sh -sv tests/test_status.py  # run specific tests
set -eu
if [ $# -gt 0 ]; then
    ARGS=("$@")
else
    ARGS=(-svx --pdb /babs/tests/)
fi

# In a worktree, .git is a file pointing to the main repo's object store.
# Mount the real .git dir so setuptools-scm can resolve the version.
GIT_COMMON_DIR="$(git rev-parse --git-common-dir 2>/dev/null || true)"
EXTRA_MOUNT=()
if [ -n "${GIT_COMMON_DIR}" ] && [ "${GIT_COMMON_DIR}" != ".git" ]; then
    REAL_GIT_DIR="$(cd "${GIT_COMMON_DIR}" && pwd)"
    EXTRA_MOUNT=(-v "${REAL_GIT_DIR}:${REAL_GIT_DIR}")
fi

docker run -it \
    --platform linux/amd64 \
    -h slurmctl --cap-add sys_admin \
    --privileged \
    -v "$(pwd)":/babs \
    "${EXTRA_MOUNT[@]}" \
    -w /babs \
    pennlinc/slurm-docker-ci:0.14 \
        bash -c "pip install -e .[tests] && pytest \
        --cov-report=term-missing \
        --cov-report=xml:/tmp/coverage.xml \
        --cov=babs \
        ${ARGS[*]}"
