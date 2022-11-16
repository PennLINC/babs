#!/bin/bash


get_bids_data() {
    set -e -x -u
    # set -o errexit

    WORKDIR=$1
    DS=$2
    ENTRYDIR=`pwd`
    mkdir -p ${WORKDIR}/data
    cd ${WORKDIR}/data

    # raw BIDS data, multi-ses:
    if [[ "${DS}" == "rawBIDS_multises" ]]; then
        datalad clone osf://w2nu3/ ${DS}  
        # tested: if osf project does not exist, there will be datalad install error, and the circle ci test will stop immediately with error
    elif [[ "${DS}" == "rawBIDS_singleses" ]]; then
        datalad clone osf://t8urc/ ${DS}
    fi

    # check the dataset has been cloned:
    cd ${DS}
    datalad status
    #ls sub-01/ses-A/dwi

    # go back to the dir before running this current function:
    cd ${ENTRYDIR}

    echo SUCCESS
}


remove_datalad_dataset() {
    WORKDIR=$1
    DS=$2
    ENTRYDIR=`pwd`

    # TODO: sanity check: ${WORKDIR}/data exists

    cd ${WORKDIR}/data
    echo "datalad remove ${DS}"
    datalad remove -d ${DS}

    # go back to the dir before running this current function:
    cd ${ENTRYDIR}
}