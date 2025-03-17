#!/bin/bash -i

SUBPROJECT_NAME=test_project

set -eu

echo "Git user: $(git config user.name)"
echo "Git email: $(git config user.email)"

mkdir /test-temp
pushd /test-temp
datalad clone osf://w2nu3/ multi-ses

# TODO switch back to osf project


# Singularity image created by root, then chowned to this user, and datalad must be run as this user
datalad create -D "toy BIDS App" toybidsapp-container
pushd toybidsapp-container
datalad containers-add \
    --url "/singularity_images/toybidsapp_0.0.7.sif" \
    toybidsapp-0-0-7
popd

# TODO File Issue: --where_project must be abspath file issue for relative path
babs-init \
    --where_project "${PWD}" \
    --project_name $SUBPROJECT_NAME \
    --input BIDS "${PWD}"/multi-ses \
    --container_ds "${PWD}"/toybidsapp-container \
    --container_name toybidsapp-0-0-7 \
    --container_config_yaml_file "/tests/tests/e2e-slurm/container/config_toybidsapp.yaml" \
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
while [[ -n $(squeue -u "$USER" -t RUNNING,PENDING --noheader) ]]; do
    echo "squeue -u \"$USER\" -t RUNNING,PENDING"
    squeue -u "$USER" -t RUNNING,PENDING
    echo "Waiting for running jobs to finish..."
    sleep 5 # Wait for 60 seconds before checking again
done

echo "No running jobs."

# TODO make sure this works
# Check for failed jobs TODO state filter doesn't seem to be working as expected
# if sacct -u $USER --state=FAILED --noheader | grep -q "FAILED"; then
if sacct -u "$USER" --noheader | grep -q "FAILED"; then
    sacct -u "$USER"
    echo "There are failed jobs."
    exit 1 # Exit with failure status
else
    sacct -u "$USER"
    echo "PASSED: No failed jobs."
fi

babs-submit --project-root "${PWD}/test_project/"

# # Wait for all running jobs to finish
while [[ -n $(squeue -u "$USER" -t RUNNING,PENDING --noheader) ]]; do
    echo "squeue -u \"$USER\" -t RUNNING,PENDING"
    squeue -u "$USER" -t RUNNING,PENDING
    echo "Waiting for running jobs to finish..."
    sleep 5 # Wait for 60 seconds before checking again
done

echo "========================================================================="
echo "babs-status:"
babs-status --project_root "${PWD}"/test_project/
echo "========================================================================="

# Check for failed jobs TODO see above
# if sacct -u $USER --state=FAILED --noheader | grep -q "FAILED"; then
if sacct -u "$USER" --noheader | grep -q "FAILED"; then
    sacct -u "$USER"
    echo "========================================================================="
    echo "There are failed jobs."
    exit 1 # Exit with failure status
else
    sacct -u "$USER"
    echo "========================================================================="
    echo "PASSED: No failed jobs."
fi

babs-merge --project_root "${PWD}"/test_project/
echo "PASSED: e2e walkthrough successful!"
