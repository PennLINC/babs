#!/bin/bash -i

SUBPROJECT_NAME=test_project

set -eu

echo "We are now running as user $(whoami)"
echo "DEBUG: MINICONDA_PATH=${MINICONDA_PATH}"
echo "DEBUG: TESTDATA=${TESTDATA}"

source  "$MINICONDA_PATH/etc/profile.d/conda.sh"
conda activate babs

# record the miniconda path so it can added to the test env (slurm jobs do not preserve env)
cat > /home/"$USER"/miniconda.env << EOF
. "$MINICONDA_PATH/etc/profile.d/conda.sh"
EOF



git config --global user.name "e2e testuser"
git config --global user.email "testuser@example.com"
echo "Git user: $(git config user.name)"
echo "Git email: $(git config user.email)"

# TODO switch back to osf project
# Populate input data (Divergent from tuturial, bc https://github.com/datalad/datalad-osf/issues/191
pushd ${TESTDATA}
echo "Installing Input Data"
datalad install ///dbic/QA

# Singularity image created by root, then chowned to this user, and datalad must be run as this user
datalad create -D "toy BIDS App" toybidsapp-container
pushd toybidsapp-container
datalad containers-add \
    --url ${PWD}/../toybidsapp-0.0.7.sif \
    toybidsapp-0-0-7
popd
rm -f toybidsapp-0.0.7.sif


# TODO File Issue: --where_project must be abspath file issue for relative path
babs-init \
    --where_project "${PWD}" \
    --project_name $SUBPROJECT_NAME \
    --input BIDS "${PWD}"/QA \
    --container_ds "${PWD}"/toybidsapp-container \
    --container_name toybidsapp-0-0-7 \
    --container_config_yaml_file "${PWD}"/config_toybidsapp.yaml \
    --type_session multi-ses \
    --type_system slurm

echo "PASSED: babs-init"
echo "Check setup, without job"
babs-check-setup --project_root "${PWD}"/test_project/
echo "PASSED: Check setup, without job"

babs-check-setup --project_root "${PWD}"/test_project/ --job-test
echo "Job submitted: Check setup, with job"

babs-status --project_root "${PWD}"/test_project/

# Wait for all running jobs to finish
while [[ -n $(squeue -u $USER -t RUNNING,PENDING --noheader) ]]; do
    echo "squeue -u $USER -t RUNNING,PENDING"
    squeue -u $USER -t RUNNING,PENDING
    echo "Waiting for running jobs to finish..."
    sleep 5 # Wait for 60 seconds before checking again
done

echo "No running jobs."

# TODO make sure this works
# Check for failed jobs TODO state filter doesnt seem to be working as expected
# if sacct -u $USER --state=FAILED --noheader | grep -q "FAILED"; then
if sacct -u $USER --noheader | grep -q "FAILED"; then
    sacct -u $USER
    echo "There are failed jobs."
    exit 1 # Exit with failure status
else
    sacct -u $USER
    echo "PASSED: No failed jobs."
fi

babs-submit --project-root "${PWD}/test_project/"

# # Wait for all running jobs to finish
while [[ -n $(squeue -u $USER -t RUNNING,PENDING --noheader) ]]; do
    echo "squeue -u $USER -t RUNNING,PENDING"
    squeue -u $USER -t RUNNING,PENDING
    echo "Waiting for running jobs to finish..."
    sleep 5 # Wait for 60 seconds before checking again
done

echo "========================================================================="
echo "babs-status:"
babs-status --project_root "${PWD}"/test_project/
echo "========================================================================="

# Check for failed jobs TODO state filter doesnt seem to be working as expected
# if sacct -u $USER --state=FAILED --noheader | grep -q "FAILED"; then
if sacct -u $USER --noheader | grep -q "FAILED"; then
    sacct -u $USER
    echo "========================================================================="
    echo "There are failed jobs."
    exit 1 # Exit with failure status
else
    sacct -u $USER
    echo "========================================================================="
    echo "PASSED: No failed jobs."
fi

babs-merge --project_root "${PWD}"/test_project/


# TODO: we need to fail if there is a failed job
# fi

# sleep 10
# babs-status --project_root "${PWD}"/test_project/
# sleep 10
# babs-status --project_root "${PWD}"/test_project/
# sleep 10
# babs-status --project_root "${PWD}"/test_project/
# sleep 10
# babs-status --project_root "${PWD}"/test_project/
#
# babs-submit --project_root "${PWD}"/test_project/
#
# babs-status --project_root "${PWD}"/test_project/
# sleep 30s
# babs-status --project_root "${PWD}"/test_project/
#
# echo "Print job logs--------------------------------------------"
# find "${PWD}"/test_project/analysis/logs/* -type f -print -exec cat {} \;
# echo "end job logs--------------------------------------------"
# # TODO: babs-check-status-job
#
# # TODO babs-merge
#
# popd
# # /tests/e2e-slurm/babs-tests.sh
# # podman exec  \
# # 	-e MINICONDA_PATH=${MINICONDA_PATH} \
# # 	slurm \
# # 	${PWD}/tests/e2e-slurm/babs-tests.sh
# #
#
#
# echo "--------------------------"
# echo "     HUZZZZZZAHHHHHH!!!!!!"
# echo "--------------------------"
#
