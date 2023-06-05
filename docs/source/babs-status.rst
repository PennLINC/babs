##################################################
``babs-status``: Check job status
##################################################

.. contents:: Table of Contents

**********************
Command-Line Arguments
**********************

.. argparse::
   :ref: babs.cli.babs_status_cli
   :prog: babs-status
   :nodefault:
   :nodefaultconst:


**********************
Example commands
**********************

Basic use: you'll only get job summary (number of jobs finished/pending/running/failed):

.. code-block:: bash

    babs-status \
        --project-root /path/to/my_BABS_project

Failed job auditing: only using alert messages in log files:

.. code-block:: bash

    babs-status \
        --project-root /path/to/my_BABS_project \
        --container-config-yaml-file /path/to/container_config.yaml

Failed job auditing: using alert messages in log files + performing job account for jobs
without alert messages in log files:

.. code-block:: bash

    babs-status \
        --project-root /path/to/my_BABS_project \
        --container-config-yaml-file /path/to/container_config.yaml \
        --job-account

When using ``--job-account``, you should also use ``--container-config-yaml-file``.

.. developer's note: seems like if only using `--job-account` without `--container-config-yaml-file`,
..  although job account commands will be called (taking more time),
..  it won't report the message e.g., "Among job(s) that are failed and don't have alert message in log files:"
..  This is probably because the "alert_message" was cleared up, so no job has "BABS: No alert message found in log files."

.. TODO: add example commands for `babs-status --resubmit` or `--resubmit-job`
..  including multi-ses and single-ses cases
