##############################################
``babs sync-code``: Save and push code changes
##############################################

.. contents:: Table of Contents

**********************
Command-Line Arguments
**********************

.. argparse::
   :ref: babs.cli._parse_sync_code
   :prog: babs sync-code
   :nodefault:
   :nodefaultconst:

Examples
--------

1. Basic usage with default options:

   .. code-block:: bash

       babs sync-code

2. Specify a custom project root and commit message:

   .. code-block:: bash

       babs sync-code /path/to/my_babs_project -m "Updated singularity run command"

Notes
-----

- This command must be run from within a valid BABS project
- Changes are saved and pushed from the `analysis/code` directory only
- The command will fail if the `analysis/code` directory does not exist
- Job status and submission files are automatically excluded from being saved

See Also
--------

- :doc:`babs-init`
- :doc:`babs-submit`
- :doc:`babs-status`