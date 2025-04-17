#!/bin/bash -i


set -eu

export USER=root
export RUNNING_PYTEST=1

echo "Git user: $(git config user.name)"
echo "Git email: $(git config user.email)"

if [ ! -f "/singularity_images/simbids_0.0.3.sif" ]; then
    mkdir -p /singularity_images
    apptainer build /singularity_images/simbids_0.0.3.sif docker://pennlinc/simbids:0.0.3
fi

# This will be mounted in the container to hold the test artifacts
pushd /test-temp

# Singularity image created by root, then chowned to this user, and datalad must be run as this user
datalad create -D "simbids" simbids-container
pushd simbids-container
datalad containers-add \
    --url "/singularity_images/simbids_0.0.3.sif" \
    simbids-0-0-3
popd

# Create some test data 
apptainer exec \
    /singularity_images/simbids_0.0.3.sif \
    simbids-raw-mri \
        "$PWD" \
        ds004146_configs.yaml

# Save it as a datalad dataset
datalad create -D "empty BIDS dataset" --force /test-temp/simbids
datalad save -m "add empty files" -d /test-temp/simbids

cd /test-temp
if [ -d "test_project" ]; then
    rm -rf test_project
fi
babs init \
    --container_ds "${PWD}"/simbids-container \
    --container_name simbids-0-0-3 \
    --container_config "/tests/tests/e2e-slurm/container/config_simbids.yaml" \
    --processing_level subject \
    --queue slurm \
    --keep-if-failed \
    "${PWD}/test_project"

echo "PASSED: babs init"

pushd "${PWD}/test_project"

echo "Check setup, without job"
babs check-setup
echo "PASSED: Check setup, without job"

babs check-setup --job-test
echo "Job submitted: Check setup, with job"

babs submit

# # Wait for all running jobs to finish
while [[ -n $(squeue -u "$USER" -t RUNNING,PENDING --noheader) ]]; do
    echo "squeue -u \"$USER\" -t RUNNING,PENDING"
    squeue -u "$USER" -t RUNNING,PENDING
    echo "Waiting for running jobs to finish..."
    sleep 5 # Wait for 60 seconds before checking again
done

echo "========================================================================="
echo "babs status:"
babs status
echo "========================================================================="

# Check for failed jobs TODO see above
# if sacct -u $USER --state=FAILED --noheader | grep -q "FAILED"; then
sacct -u "$USER"
if sacct -u "$USER" --noheader | grep -q "FAILED"; then
    echo "========================================================================="
    echo "There are failed jobs."
    exit 1 # Exit with failure status
else
    echo "========================================================================="
    echo "PASSED: No failed jobs."
fi

babs merge
echo "PASSED: e2e walkthrough successful!"

popd
# Create a second BABS project with raw and zipped inputs
TEST2_NAME=multiinput_test
babs init \
    --container_ds "${PWD}"/simbids-container \
    --container_name simbids-0-0-3 \
    --container_config "/tests/tests/e2e-slurm/container/config_simbids_multiinput.yaml" \
    --processing_level subject \
    --queue slurm \
    --keep-if-failed \
    "${PWD}/${TEST2_NAME}"

pushd "${PWD}/${TEST2_NAME}"

babs check-setup

babs submit
# # Wait for all running jobs to finish
while [[ -n $(squeue -u "$USER" -t RUNNING,PENDING --noheader) ]]; do
    echo "squeue -u \"$USER\" -t RUNNING,PENDING"
    squeue -u "$USER" -t RUNNING,PENDING
    echo "Waiting for running jobs to finish..."
    sleep 5 # Wait for 60 seconds before checking again
done

babs status

babs merge
