#!/bin/bash
docker build --platform linux/amd64 -t pennlinc/slurm-docker-ci:unstable -f Dockerfile_testing .
docker run -it \
    --platform linux/amd64 \
    -h slurmctl --cap-add sys_admin \
    --privileged \
    pennlinc/slurm-docker-ci:unstable \
        pytest -svx \
        --cov-report=term-missing \
        --cov-report=xml \
        --cov=babs \
        --pdb /babs/tests/test_template_job.py
    