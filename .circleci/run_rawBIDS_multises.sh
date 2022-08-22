#!/bin/bash

# This script is to run toy BIDS App upon the raw BIDS data (multi-ses)

# Step 1. get the data
source ./get_data.sh
TESTDIR=${PWD}
TESTNAME="rawBIDS_multises"
get_bids_data ${TESTDIR} rawBIDS_multises

# Step 2. call `babs-init`
# TODO

# Step 3. (if run `babs-submit` and get results) compare with the prior answer
# TODO

# Step 4. datalad drop
remove_datalad_dataset ${TESTDIR} rawBIDS_multises