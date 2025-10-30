##################################################
``babs status``: Check job status
##################################################

.. contents:: Table of Contents

**********************
Command-Line Arguments
**********************

.. argparse::
   :ref: babs.cli._parse_status
   :prog: babs status
   :nodefault:
   :nodefaultconst:


.. warning::
    Do NOT kill ``babs status`` (especially with ``--resubmit*``)
    while it's running! Otherwise, new job IDs may not be captured or saved into the ``job_status.csv``!


**********************
Example commands
**********************

Basic use
-------------

When only providing the required argument ``project_root``,
you'll only get job status summary (i.e., number of jobs finished/pending/running/failed):

.. code-block:: bash

    babs status /path/to/my_BABS_project

Failed job auditing
------------------------
Only use alert messages in log files for failed job auditing:

.. code-block:: bash

    babs status \
        /path/to/my_BABS_project \
        --container-config /path/to/container_config.yaml

Use alert messages in log files + Perform job account for jobs
without alert messages in log files:

.. code-block:: bash

    babs status \
        /path/to/my_BABS_project \
        --container-config-yaml-file /path/to/container_config.yaml

Job resubmission
------------------
By running ``babs status``, you might see that some jobs are pending or failed,
and you'd like to resubmit them.

Run this (in BABS project root) to resubmit all the failed jobs:

.. code-block:: bash

    babs submit

**********************
See also
**********************
:doc:`jobs`
