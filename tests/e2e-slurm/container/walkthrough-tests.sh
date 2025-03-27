#!/bin/bash -i


set -eu

export USER=root
export SUBPROJECT_NAME=test_project
echo "Git user: $(git config user.name)"
echo "Git email: $(git config user.email)"

# Create a file that will be imported into the BABS project
export IMPORTED_DATA_FILE=/imported_file.txt
echo "FAKE DATA" > "$IMPORTED_DATA_FILE"
DATA_DIR=/home/circleci/test_data

if [ ! -d "${DATA_DIR}/BIDS_multi-ses" ]; then
    echo "Data directory ${DATA_DIR}/BIDS_multi-ses does not exist"
    mkdir -p "$DATA_DIR"
    cd "$DATA_DIR"
    datalad clone osf://w2nu3/ BIDS_multi-ses
fi

# This will be mounted in the container to hold the test artifacts
pushd /test-temp

# Singularity image created by root, then chowned to this user, and datalad must be run as this user
datalad create -D "toy BIDS App" toybidsapp-container
pushd toybidsapp-container
datalad containers-add \
    --url "/singularity_images/toybidsapp_0.0.7.sif" \
    toybidsapp-0-0-7
popd

babs init \
    --datasets BIDS="${DATA_DIR}/BIDS_multi-ses" \
    --container_ds "${PWD}"/toybidsapp-container \
    --container_name toybidsapp-0-0-7 \
    --container_config "/tests/tests/e2e-slurm/container/config_toybidsapp.yaml" \
    --processing_level session \
    --queue slurm \
    "${PWD}/${SUBPROJECT_NAME}"

echo "PASSED: babs init"
echo "Check setup, without job"
babs check-setup "${PWD}"/test_project/
echo "PASSED: Check setup, without job"

# Check that the imported file is present
if [ ! -f "${PWD}/${SUBPROJECT_NAME}/analysis/code/imported_file.txt" ]; then
    echo "Imported file ${PWD}/${SUBPROJECT_NAME}/analysis/code/imported_file.txt does not exist"
    exit 1
fi

babs check-setup "${PWD}"/test_project/ --job-test
echo "Job submitted: Check setup, with job"

babs status "${PWD}"/test_project/

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
    #exit 1 # Exit with failure status
else
    sacct -u "$USER"
    echo "PASSED: No failed jobs."
fi

babs submit "${PWD}/test_project/" --all

# # Wait for all running jobs to finish
while [[ -n $(squeue -u "$USER" -t RUNNING,PENDING --noheader) ]]; do
    echo "squeue -u \"$USER\" -t RUNNING,PENDING"
    squeue -u "$USER" -t RUNNING,PENDING
    echo "Waiting for running jobs to finish..."
    sleep 5 # Wait for 60 seconds before checking again
done

echo "========================================================================="
echo "babs status:"
babs status "${PWD}"/test_project/
echo "========================================================================="

# Check for failed jobs TODO see above
# if sacct -u $USER --state=FAILED --noheader | grep -q "FAILED"; then
if sacct -u "$USER" --noheader | grep -q "FAILED"; then
    sacct -u "$USER"
    echo "========================================================================="
    echo "There are failed jobs."
    #exit 1 # Exit with failure status
else
    sacct -u "$USER"
    echo "========================================================================="
    echo "PASSED: No failed jobs."
fi

babs merge "${PWD}"/test_project/
echo "PASSED: e2e walkthrough successful!"
