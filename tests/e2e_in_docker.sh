#!/bin/bash
set -eu
E2E_DIR="${E2E_DIR:-$(mktemp -d /tmp/babs-e2e-XXXXXX)}"
mkdir -p "${E2E_DIR}"
echo "E2E_DIR=${E2E_DIR}"

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
    -v "$(pwd)":/tests \
    -v "${E2E_DIR}":/test-temp:rw \
    "${EXTRA_MOUNT[@]}" \
    -h slurmctl --cap-add sys_admin \
    --privileged \
    pennlinc/slurm-docker-ci:0.14 \
        /tests/tests/e2e-slurm/container/walkthrough-tests.sh
