##################################################
``babs-check-setup``: Validate the BABS project
##################################################

.. contents:: Table of Contents

**********************
Command-Line Arguments
**********************

.. argparse::
   :ref: babs.cli.babs_check_setup_cli
   :prog: babs-check-setup
   :nodefault:
   :nodefaultconst:

**********************
Detailed description
**********************

`babs-check-setup` will perform these steps:

1. Print out configurations of the BABS project;
2. Perform sanity checks in this BABS project;
3. Submit a test job to make sure necessary packages (e.g., `DataLad`)
   are installed in the designated environment. This happen when ``--job-test``
   is requested. We highly recommend doing so.

**********************
Example commands
**********************

We highly recommend running ``babs-check-setup`` with a test job::

    babs-check-setup --project-root /path/to/my_BABS_project --job-test

Otherwise, you could run without a test job::

    babs-check-setup --project-root /path/to/my_BABS_project

**********************
See also
**********************

* :doc:`create_babs_project`
