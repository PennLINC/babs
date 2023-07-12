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


.. warning::
    Do NOT kill ``babs-status`` (especially with ``--resubmit*``)
    when it's running! Otherwise, new job IDs may not be captured or saved into the ``job_status.csv``!


**********************
Example commands
**********************

Basic use
-------------

When only providing the required argument ``--project-root``,
you'll only get job status summary (i.e., number of jobs finished/pending/running/failed):

.. code-block:: bash

    babs-status \
        --project-root /path/to/my_BABS_project

Failed job auditing
------------------------
Only use alert messages in log files for failed job auditing:

.. code-block:: bash

    babs-status \
        --project-root /path/to/my_BABS_project \
        --container-config-yaml-file /path/to/container_config.yaml

Use alert messages in log files + Perform job account for jobs
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

Job resubmission
------------------
By using commands like above, you might know there are some jobs pending or failed,
and you'd like to resubmit them.

Resubmit all the failed jobs:

.. code-block:: bash

    babs-status \
        --project-root /path/to/my_BABS_project \
        --resubmit failed

Resubmit specific jobs that failed or are pending:

For single-session dataset, assume jobs of ``sub-01`` and ``sub-02`` failed,
and you hope to resubmit them:

.. code-block:: bash

    babs-status \
        --project-root /path/to/my_BABS_project \
        --resubmit-job sub-01 \
        --resubmit-job sub-02

For multi-session dataset, assume jobs of ``sub-01, ses-A`` and ``sub-02, ses-B`` failed,
and you hope to resubmit them:

.. code-block:: bash

    babs-status \
        --project-root /path/to/my_BABS_project \
        --resubmit-job sub-01 ses-A \
        --resubmit-job sub-02 ses-B

**********************
Notes
**********************

For argument ``--resubmit-job``, please provide the subject ID (and session ID) whose job you'd like to resubmit.
You should not provide the job ID. See examples above.

**********************
See also
**********************
:doc:`jobs`
