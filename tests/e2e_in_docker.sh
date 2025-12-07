#!/bin/bash
mkdir -p "${HOME}"/projects/e2e-testing
docker build --platform linux/amd64 \
    -t pennlinc/slurm-docker-ci:unstable \
    -f Dockerfile_testing .
docker run -it \
    --platform linux/amd64 \
    -v "${HOME}"/projects/babs:/tests \
    -v "${HOME}"/projects/e2e-testing:/test-temp:rw \
    -h slurmctl --cap-add sys_admin \
    --privileged \
    pennlinc/slurm-docker-ci:unstable #\
        #/babs/tests/e2e-slurm/container/walkthrough-tests.sh


    #pytest -svx --pdb \
    #/babs/tests