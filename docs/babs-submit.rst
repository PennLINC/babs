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


Submit all remaining jobs
-------------------------
To submit jobs for remaining subjects (and sessions) whose jobs haven't been submitted yet:

.. code-block:: bash

    babs submit \
        /path/to/my_BABS_project \
        --all


Submit jobs for specific subjects (and sessions)
------------------------------------------------
For single-session dataset, say you'd like to submit jobs for ``sub-01`` and ``sub-02``:

.. code-block:: bash

    babs submit \
        /path/to/my_BABS_project \
        --job sub-01 \
        --job sub-02

For multi-session dataset, say you'd like to submit jobs for ``sub-01, ses-A`` and ``sub-02, ses-B``:

.. code-block:: bash

    babs submit \
        /path/to/my_BABS_project \
        --job sub-01 ses-A \
        --job sub-02 ses-B


********
See also
********
:doc:`jobs`
