#!/bin/bash -i


set -eu

export USER=root
export RUNNING_PYTEST=1

echo "Git user: $(git config user.name)"
echo "Git email: $(git config user.email)"

# use BABS from the mounted repo/local development copy
pip install -e /tests

if [ ! -f "/singularity_images/simbids_0.0.3.sif" ]; then
    mkdir -p /singularity_images
    apptainer build /singularity_images/simbids_0.0.3.sif docker://pennlinc/simbids:0.0.3
fi

# This will be mounted in the container to hold the test artifacts
pushd /test-temp

# Clean leftover dirs from a previous run so datalad create does not see a non-empty directory
rm -rf \
    simbids-container \
    simbids \
    test_project \
    multiinput_test

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
babs init \
    --container_ds "${PWD}"/simbids-container \
    --container_name simbids-0-0-3 \
    --container_config "/tests/tests/e2e-slurm/container/config_simbids.yaml" \
    --processing_level subject \
    --queue slurm \
    --keep-if-failed \
    "${PWD}/test_project"

echo "PASSED: babs init"

pushd "test_project/analysis"
datalad get "containers/.datalad/environments/simbids-0-0-3/image"
popd

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
    LOGS_DIR="analysis/logs"
    if [ -d "$LOGS_DIR" ]; then
        echo "========================================================================="
        echo "Failed job / task logs from $LOGS_DIR:"
        for f in "$LOGS_DIR"/*; do
            if [ -f "$f" ]; then
                echo "---------- $f ----------"
                cat "$f"
                echo ""
            fi
        done
    fi
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

pushd "${PWD}/${TEST2_NAME}/analysis"
datalad get "containers/.datalad/environments/simbids-0-0-3/image"
popd

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

popd
# Create a third BABS project with no zipping (loose output files)
TEST3_NAME=no_zip_test
babs init \
    --container_ds "${PWD}"/simbids-container \
    --container_name simbids-0-0-3 \
    --container_config "/tests/tests/e2e-slurm/container/config_simbids_no_zip.yaml" \
    --processing_level subject \
    --queue slurm \
    --keep-if-failed \
    "${PWD}/${TEST3_NAME}"

echo "PASSED: babs init (no zip)"

pushd "${PWD}/${TEST3_NAME}/analysis"
datalad get "containers/.datalad/environments/simbids-0-0-3/image"
popd

pushd "${PWD}/${TEST3_NAME}"

babs check-setup

babs submit
while [[ -n $(squeue -u "$USER" -t RUNNING,PENDING --noheader) ]]; do
    squeue -u "$USER" -t RUNNING,PENDING
    echo "Waiting for running jobs to finish..."
    sleep 5
done

babs status

sacct -u "$USER"
if sacct -u "$USER" --noheader | grep -q "FAILED"; then
    echo "========================================================================="
    echo "There are failed jobs in no-zip test."
    LOGS_DIR="analysis/logs"
    if [ -d "$LOGS_DIR" ]; then
        for f in "$LOGS_DIR"/*; do
            [ -f "$f" ] && echo "---------- $f ----------" && cat "$f"
        done
    fi
    exit 1
fi
echo "PASSED: No failed jobs (no-zip)"

babs merge

# After merge, verify outputs in the output RIA are loose files, not zips
RIA_PATH=$(find "${PWD}/output_ria" -mindepth 2 -maxdepth 2 -type d | head -1)
echo "========================================================================="
echo "Top-level entries in output RIA after merge:"
git -C "$RIA_PATH" ls-tree --name-only HEAD
echo "========================================================================="

if git -C "$RIA_PATH" ls-tree --name-only HEAD | grep -q '\.zip'; then
    echo "FAILED: found .zip files in no-zip project"
    exit 1
fi
echo "PASSED: no .zip files in output RIA (as expected)"

if ! git -C "$RIA_PATH" ls-tree --name-only HEAD | grep -q 'outputs'; then
    echo "FAILED: no outputs directory found in output RIA"
    exit 1
fi
echo "PASSED: outputs/ directory found in output RIA"

if ! git -C "$RIA_PATH" ls-tree -r --name-only HEAD -- outputs | grep -q 'dataset_description.json'; then
    echo "FAILED: missing dataset_description.json in outputs"
    exit 1
fi

if ! git -C "$RIA_PATH" ls-tree -r --name-only HEAD -- outputs | grep -q 'sub-0001'; then
    echo "FAILED: missing sub-0001 results in outputs"
    exit 1
fi

if ! git -C "$RIA_PATH" ls-tree -r --name-only HEAD -- outputs | grep -q 'sub-0002'; then
    echo "FAILED: missing sub-0002 results in outputs"
    exit 1
fi
echo "PASSED: output files present for both subjects"

echo "PASSED: e2e no-zip walkthrough successful!"
