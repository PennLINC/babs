#!/bin/bash


get_bids_data() {
    WORKDIR=$1
    DS=$2
    ENTRYDIR=`pwd`
    mkdir -p ${WORKDIR}/data
    cd ${WORKDIR}/data

    # raw BIDS data, multi-ses:
    if [[ ${DS} == "rawBIDS_multises" ]]; then
        datalad clone osf://fhm8b/ ${DS}
    fi

    # go back to the dir before running this current function:
    cd ${ENTRYDIR}
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