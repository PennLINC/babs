#!/bin/bash
docker build -t pennlinc/slurm-docker-ci:unstable -f Dockerfile_testing .
docker run -it \
    -v /Users/mcieslak/projects/babs:/babs \
    -h slurmctl --cap-add sys_admin \
    --privileged \
    pennlinc/slurm-docker-ci:unstable


    #pytest -svx --pdb \
    #/babs/tests