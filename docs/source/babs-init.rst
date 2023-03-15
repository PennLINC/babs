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
      Notes to add here.

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

--------------------------------------------------------------------
What should I do for error message "input dataset is not matched"?
--------------------------------------------------------------------
This is probably because you've changed the path to an input dataset, and rerun ``babs-init``.
To solve the issue, you need to remove the original input dataset (following commands below),
then rerun ``babs-init``::

    conda activate <my_env>    # replace `<my_env>` with the conda environment where DataLad is installed
    cd /path/to/my_BABS_project/analysis   # change the path to yours
    datalad remove -d inputs/data/<input_ds_name>   # replace `<input_ds_name>` with the name that has error

**********************
Example commands
**********************

TODO: to add some example commands