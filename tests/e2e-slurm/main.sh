#!/bin/bash
#
set -eux

# Expects: Conda env to be activated
# Expects: Babs to be installed
#
# WIP-NOT-WORKING
# Reminder :Z for selinux

# TODO switch back to upstream after build
# Currently using asmacdo, OpenSSL bump upstream, but no new docker build
# https://github.com/giovtorres/docker-centos7-slurm/pull/49
REGISTRY=docker.io
HUBUSER=asmacdo
# HUBUSER=giovtorres
REPO=centos7-slurm
# REPO=docker-centos7-slurm
TAG=23.11.07 # TODO

FQDN_IMAGE=${REGISTRY}/${HUBUSER}/${REPO}:${TAG}
THIS_DIR="$(readlink -f "$0" | xargs dirname )"

# Sets MINICONDA_PATH
. tests/e2e-slurm/container/ensure-env.sh

if [ "$MINICONDA_PATH/envs/$CONDA_DEFAULT_ENV/bin/babs-init" != "$(which babs-init)" ]; then
    echo "Error: This script expects to be run inside a conda env with 'babs-init'!" >&2
    echo "       We have not found it in conda env '$CONDA_DEFAULT_ENV' under '$MINICONDA_PATH'" >&2
    exit 1
fi

echo "Success, we are in the conda env with babs-init!"

# PWD shared so babs can be optionally be installed with develop install
podman run -it --rm \
	--name slurm \
	--hostname slurmctl  \
	-e "MINICONDA_PATH=${MINICONDA_PATH}" \
	--privileged \
	-v "${PWD}:${PWD}:ro,Z" \
	-v "${MINICONDA_PATH}:${MINICONDA_PATH}:Z" \
	-v "${THIS_DIR}/container:/opt/outer:ro,Z" \
	"${FQDN_IMAGE}" \
	/bin/bash -c ". /opt/outer/walkthrough-tests.sh"
