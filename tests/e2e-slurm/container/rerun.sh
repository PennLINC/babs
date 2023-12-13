#!/bin/bash

su "testuser" "rm -rf ${TESTDATA}"
cp /opt/outer/* "${TESTDATA}"

su "${BABS_USER}" "${TESTDATA}/babs-user-script.sh"
