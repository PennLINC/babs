#!/bin/bash
docker run -it \
    --platform linux/amd64 \
    -h slurmctl --cap-add sys_admin \
    --privileged \
    -v "$(pwd)":/babs \
    -w /babs \
    pennlinc/slurm-docker-ci:0.14 \
        bash -c "pip install -e .[tests] && pytest -svx \
        --cov-report=term-missing \
        --cov-report=xml:/tmp/coverage.xml \
        --cov=babs \
        --pdb \
        /babs/tests/"
