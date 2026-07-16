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
    Do NOT kill ``babs status``
    while it's running! Otherwise, new job IDs may not be captured or saved into the ``job_status.csv``!


**********************
Example commands
**********************

Basic use
-------------

When only providing the required argument ``project_root``,
you'll only get job status summary (i.e., number of jobs finished/pending/running/failed):

.. code-block:: bash

    cd /path/to/my_BABS_project
    babs status

Machine-readable output
------------------------

Pass ``--json`` to print **only** a JSON summary of the job counts to stdout
(no human-readable table), so tooling can parse it directly:

.. code-block:: bash

    babs status --json /path/to/my_BABS_project

.. code-block:: json

    {"total": 5, "submitted": 5, "unsubmitted": 0, "pending": 0, "running": 0, "completing": 0, "configuring": 0, "done": 5, "failed": 0}

``pending``, ``running``, ``completing``, and ``configuring`` are the live scheduler
states (queued / executing / finishing / preparing); ``done`` finished with results
and ``failed`` ended without. ``total == submitted + unsubmitted`` always holds.
``--json`` cannot be combined with ``--wait``.

Job resubmission
------------------
After running ``babs status``, you might see that some jobs are pending or failed,
and you'd like to resubmit them.

Run this (in BABS project root) to resubmit all the failed jobs:

.. code-block:: bash

    babs submit

**********************
See also
**********************
:doc:`jobs`
