#!/bin/bash -i


set -eu

export USER=root
export SUBPROJECT_NAME=test_project
echo "Git user: $(git config user.name)"
echo "Git email: $(git config user.email)"

# Create a file that will be imported into the BABS project
export IMPORTED_DATA_FILE=/imported_file.txt
echo "FAKE DATA" > "$IMPORTED_DATA_FILE"
DATA_DIR=/data
mkdir -p "$DATA_DIR"

# ds005237 is a single-ses bold dataset
apptainer exec -B "$DATA_DIR" \
    /singularity_images/simbids_0.0.3.sif \
    simbids-raw-mri \
    "$DATA_DIR" \
    ds005237_configs.yaml

# This will be mounted in the container to hold the test artifacts
pushd "$DATA_DIR"

# Singularity image created by root, then chowned to this user, and datalad must be run as this user
datalad create -D "Simbids" simbids-container
pushd simbids-container
datalad containers-add \
    --url "/singularity_images/simbids_0.0.3.sif" \
    simbids-0-0-3
popd

babs init \
    --datasets BIDS="${DATA_DIR}/simbids" \
    --container_ds "${PWD}"/simbids-container \
    --container_name simbids-0-0-2 \
    --container_config "/babs/tests/e2e-slurm/container/simbids_fmriprep-24-1-1_anatonly.yaml" \
    --processing_level subject \
    --queue slurm \
    --keep-if-failed \
    "${PWD}/${SUBPROJECT_NAME}"

# apptainer run -B "$DATA_DIR" \
#     /singularity_images/simbids_0.0.3.sif \
#     "${DATA_DIR}/simbids" \
#     "${DATA_DIR}/fmriprep_anat" \
#     participant \
#     --bids-app fmriprep \
#     --participant-label NDARINVAZ218MB7 \
#     --anat-only \
#     -v -v

echo "PASSED: babs init"

pushd "${PWD}/${SUBPROJECT_NAME}"

echo "Check setup, without job"
babs check-setup
echo "PASSED: Check setup, without job"

# Check that the imported file is present
if [ ! -f "${PWD}/analysis/code/imported_file.txt" ]; then
    echo "Imported file ${PWD}/analysis/code/imported_file.txt does not exist"
    exit 1
fi

babs check-setup --job-test
echo "Job submitted: Check setup, with job"

babs status

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

babs submit --all

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

babs merge
echo "PASSED: e2e walkthrough successful!"
