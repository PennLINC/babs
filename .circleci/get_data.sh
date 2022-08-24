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
        datalad clone osf://j854e/ ${DS}  
        # tested: if osf project does not exist, there will be datalad install error, and the circle ci test will stop immediately with error
    fi

    # check the dataset has been cloned:
    cd ${DS}
    datalad status
    tree

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