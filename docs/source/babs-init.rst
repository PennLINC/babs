##################################################
``babs-init``: Initialize a BABS project
##################################################

.. contents:: Table of Contents

**********************
Command-Line Arguments
**********************

.. argparse::
   :ref: babs.cli.babs_init_cli
   :prog: babs-init

    --input : @after
      Notes to add here: --------

**********************
Detailed Description
**********************

--------------------------------------------------------------------
How to prepare input dataset, container, and container's YAML file?
--------------------------------------------------------------------

Please see document :ref:`preparation` for how to prepare these inputs.

-----------------------------------------------------
How the list of subjects (and sessions) determined?
-----------------------------------------------------
A list of subjects (and sessions) will be determined when running ``babs-init``,
and will be saved in a CSV file called named ``sub_final_inclu.csv`` (for single-session dataset)
or ``sub_ses_final_inclu.csv`` (for multiple-session dataset),
located at ``/path/to/my_BABS_project/analysis/code``

See :ref:`list_included_subjects` for how this list is determined.


**********************
Example commands
**********************

TODO