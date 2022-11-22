#!/bin/bash
# This is to prepare containers and data prior to running tests of `babs-init`.

# Make sure you're in the correct conda env:
conda activate mydatalad

# Container dataset
## Inputs:
# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++
folder_root="/cbica/projects/BABS/data"

fmriprep_version_dot="20.2.3"   # RBC used (8/10/22)
fmriprep_version_dash="20-2-3"
fmriprep_docker_path="nipreps/fmriprep:${fmriprep_version_dot}"

qsiprep_version_dot="0.16.0RC3"
qsiprep_version_dash="0-16-0RC3"
qsiprep_docker_path="pennbbl/qsiprep:${qsiprep_version_dot}"
# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++

## Pull:
# +++++++++ change below ++++++++++++++++++++++++++++++++++++++
bidsapp="qsiprep"    # e.g., qsiprep, fmriprep, xcp (without d!!), toybidsapp
bidsapp_version_dot=${qsiprep_version_dot}    # e.g., x.x.x
bidsapp_version_dash=${qsiprep_version_dash}     # e.g., x-x-x
docker_path=${qsiprep_docker_path}   # e.g., pennbbl/qsiprep:x.x.x

docker_link="docker://${docker_path}"  # e.g., docker://pennbbl/qsiprep:x.x.x
# +++++++++++++++++++++++++++++++++++++++++++++++
# 
folder_sif="${folder_root}"    # where the container's .sif file is. Sif file in this folder is temporary and will be deleted once the container dataset is created.
msg_container="this is ${bidsapp} container"   # e.g., this is qsiprep container
folder_container="${folder_sif}/${bidsapp}-container"    # the datalad dataset of the container

cd ${folder_sif}

# Step 2.1 Build singularity
cmd="singularity build ${bidsapp}-${bidsapp_version_dot}.sif ${docker_link}"
# ^^ took how long: ~10-25min; depending on what already exist on the cubic project user.

# Step 2.2 Create a container dataset:
datalad create -D "${msg_container}" ${bidsapp}-container  

cd ${bidsapp}-container
fn_sif_orig="${folder_sif}/${bidsapp}-${bidsapp_version_dot}.sif"
cmd="datalad containers-add --url ${fn_sif_orig} ${bidsapp}-${bidsapp_version_dash}"
# ^^ this sif file is copied as: `.datalad/environment/${bidsapp}-${bidsapp_version_dash}/image` 

# as the sif file has been copied into `${bidsapp}-container` folder, now we can delete the original sif file:
cmd="rm ${fn_sif_orig}"