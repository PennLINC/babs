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

babs status --wait --wait-interval 5
echo "PASSED: No failed jobs."

babs merge

echo "Checking job_status.csv after merge..."
cat analysis/code/job_status.csv
python -c "
import csv, sys
with open('analysis/code/job_status.csv') as f:
    for row in csv.DictReader(f):
        if row['submitted'].strip().lower() == 'true':
            if row['has_results'].strip().lower() != 'true':
                print(f'FAIL: {row[\"sub_id\"]} submitted but has_results={row[\"has_results\"]}')
                sys.exit(1)
            if row['is_failed'].strip().lower() == 'true':
                print(f'FAIL: {row[\"sub_id\"]} has_results=True but is_failed=True')
                sys.exit(1)
print('PASSED: job_status.csv is consistent')
"
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
babs status --wait --wait-interval 5

babs merge

echo "Checking job_status.csv after merge (multiinput)..."
cat analysis/code/job_status.csv
python -c "
import csv, sys
with open('analysis/code/job_status.csv') as f:
    for row in csv.DictReader(f):
        if row['submitted'].strip().lower() == 'true':
            if row['has_results'].strip().lower() != 'true':
                print(f'FAIL: {row[\"sub_id\"]} submitted but has_results={row[\"has_results\"]}')
                sys.exit(1)
            if row['is_failed'].strip().lower() == 'true':
                print(f'FAIL: {row[\"sub_id\"]} has_results=True but is_failed=True')
                sys.exit(1)
print('PASSED: job_status.csv is consistent (multiinput)')
"
