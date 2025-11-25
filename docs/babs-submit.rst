############################
``babs submit``: Submit jobs
############################

.. contents:: Table of Contents

**********************
Command-Line Arguments
**********************

.. argparse::
   :ref: babs.cli._parse_submit
   :prog: babs submit
   :nodefault:
   :nodefaultconst:

.. warning::
    Do NOT kill ``babs submit``
    while it's running! Otherwise, new job IDs may not be captured or saved into the ``job_status.csv``!


****************
Example commands
****************

Basic use
---------
If users only provide the required argument ``project_root``,
``babs submit`` will only submit one job:

.. code-block:: bash

    babs submit /path/to/my_BABS_project

Submitting a certain amount of jobs
-----------------------------------

.. code-block:: bash

    babs submit \
        /path/to/my_BABS_project \
        --count N

Change ``N`` to the number of jobs to be submitted.


Submit jobs for specific subjects (and sessions)
------------------------------------------------
For single-session datasets, select subjects with ``--select``. You can repeat the flag
or pass multiple values in one flag (argparse appends and supports nargs):

.. code-block:: bash

    babs submit \
        /path/to/my_BABS_project \
        --select sub-01 \
        --select sub-02

For multi-session datasets, include both ``sub-XX`` and ``ses-YY`` pairs:

.. code-block:: bash

    babs submit \
        /path/to/my_BABS_project \
        --select sub-01 ses-A \
        --select sub-02 ses-B

You may also pass multiple values per flag:

.. code-block:: bash

    babs submit \
        /path/to/my_BABS_project \
        --select sub-01 sub-02

.. note::
    If there are jobs currently running, ``babs submit`` will refuse to submit new jobs
    until the running jobs finish or are cancelled. Use ``babs status`` to check progress.


********
See also
********
:doc:`jobs`
