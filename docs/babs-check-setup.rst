###############################################
``babs check-setup``: Validate the BABS project
###############################################

.. contents:: Table of Contents

**********************
Command-Line Arguments
**********************

.. argparse::
   :ref: babs.cli._parse_check_setup
   :prog: babs check-setup
   :nodefault:
   :nodefaultconst:

********************
Detailed description
********************

----------------------------------
What does ``babs check-setup`` do?
----------------------------------

``babs check-setup`` will perform these steps:

1. Print out configurations of the BABS project;
2. Perform sanity checks in this BABS project;
3. Submit a test job to make sure necessary packages (e.g., `DataLad`)
   are installed in the designated environment. This happen when ``--job-test``
   is requested. We highly recommend doing so.

------------------------------------------------------------------------------------
What if ``babs check-setup`` fails or the BABS project's setup is not what I desire?
------------------------------------------------------------------------------------

If running ``babs check-setup`` (e.g., with test jobs) fails,
or the summarized information from ``babs check-setup`` is not what you desire,
please remove the current BABS project, fix the problems, and generate a new BABS project.
In details,

#. Before removing the current BABS project, make sure you know what went wrong and what to fix.
   Please carefully read the printed messages from failed ``babs check-setup``.

#. Remove the current BABS project
   with following commands::

    cd <project_root>/analysis    # replace `<project_root>` with the path to your BABS project

    # Remove input dataset(s) one by one:
    datalad remove -d inputs/data/<input_ds_name>   # replace `<input_ds_name>` with each input dataset's name
    # repeat above step until all input datasets have been removed.
    # if above command leads to "drop impossible" due to modified content, add `--reckless modification` at the end

    git annex dead here
    datalad push --to input
    datalad push --to output

    cd ..
    pwd   # this prints `<project_root>`; you can copy it in case you forgot
    cd ..   # outside of `<project_root>`
    rm -rf <project_root>

   If you don't remove the current BABS project, you cannot overwrite it by running ``babs init`` again.

   .. developer's note: above step: copied from `babs-init.rst` (CLI for ``babs init``)

#. Fix the problems, e.g., in the ``babs init`` command,
   or in the container configuration YAML file.

#. Generate a new BABS project by running ``babs init``.

****************
Example commands
****************

We highly recommend running ``babs check-setup`` with a test job::

    babs check-setup /path/to/my_BABS_project --job-test

Otherwise, you could run without a test job::

    babs check-setup /path/to/my_BABS_project

********
See also
********

* :doc:`create_babs_project`
