#!/bin/bash

# This script is to run toy BIDS App upon the raw BIDS data (multi-ses)

set -e -x -u     # -u: raise error if any variable you haven't defined yet | -x: print the msg in terminal | -e: exist bash if any command has non-zero exit

# Step 1. get the data
source ./get_data.sh
TESTDIR=${PWD}
TESTNAME="rawBIDS_multises"
# set -ex
get_bids_data ${TESTDIR} rawBIDS_multises

# Step 2. call `babs-init`
# TODO

# Step 3. (if run `babs-submit` and get results) compare with the prior answer
# TODO

# Step 4. datalad drop
remove_datalad_dataset ${TESTDIR} rawBIDS_multises