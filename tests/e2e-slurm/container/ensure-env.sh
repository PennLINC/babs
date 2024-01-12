#!/bin/bash
#
# exported for use in inner-slurm.sh
if [ -z "${MINICONDA_PATH:-}" ]; then
    if hash conda; then
        # We don't need the return value, we already catch the error
        # shellcheck disable=SC2155
        export MINICONDA_PATH=$(/bin/which conda | xargs dirname | xargs dirname)
    else
        echo "ERROR: must have MINICONDA_PATH set or have 'conda' available"
        exit 1
    fi
fi
