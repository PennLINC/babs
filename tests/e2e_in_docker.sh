#!/bin/bash
E2E_DIR="${E2E_DIR:-$(mktemp -d /tmp/babs-e2e-XXXXXX)}"
mkdir -p "${E2E_DIR}"
echo "E2E_DIR=${E2E_DIR}"
docker run -it \
    --platform linux/amd64 \
    -v "$(pwd)":/tests \
    -v "${E2E_DIR}":/test-temp:rw \
    -h slurmctl --cap-add sys_admin \
    --privileged \
    pennlinc/slurm-docker-ci:0.14 \
        /tests/tests/e2e-slurm/container/walkthrough-tests.sh
