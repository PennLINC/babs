##################################################
``babs init``: Initialize a BABS project
##################################################

.. contents:: Table of Contents

**********************
Command-Line Arguments
**********************

.. argparse::
   :ref: babs.cli._parse_init
   :prog: babs init

   --keep_if_failed, --keep-if-failed : @after
      These words below somehow refuse to appear in the built docs...
      Please refer to below section
      here: :ref:`what-if-babs-init-fails` for details.


********************
Detailed description
********************

-------------------------------------------------------------------------
How do I prepare the input dataset, container, and container's YAML file?
-------------------------------------------------------------------------

Please see document :doc:`preparation` for how to prepare these inputs.

.. _how-to-define-name-of-input-dataset:

-----------------------------------------------------------
How do I define the input datasets in the YAML config file?
-----------------------------------------------------------

Please see document :doc:`preparation_config_yaml_file` for how to define the input datasets in the YAML config file.

------------------------------------------------------
How is the list of subjects (and sessions) determined?
------------------------------------------------------
A list of subjects (and sessions) will be determined when running ``babs init``,
and will be saved in a CSV file called named ``processing_inclusion.csv`` 
located at ``/path/to/my_BABS_project/analysis/code``.

**To filter subjects and sessions**, use ``babs init`` with ``-- /path/to/subject/list/csv/file``. 
Examples: `Single-session example <https://github.com/PennLINC/babs/blob/ba32e8fd2d6473466d3c33a1b17dfffc4438d541/notebooks/initial_sub_list_single-ses.csv>`_, `Multi-session example <https://github.com/PennLINC/babs/blob/ba32e8fd2d6473466d3c33a1b17dfffc4438d541/notebooks/initial_sub_list_multi-ses.csv>`_.

See :ref:`list_included_subjects` for how this list is determined.

.. _what-if-babs-init-fails:

----------------------------
What if ``babs init`` fails?
----------------------------

If ``babs init`` fails, by default it will remove ("clean up") the created, failed BABS project.

When this happens, if you hope to use ``babs check-setup`` to debug what's wrong, you'll notice that
the failed BABS project has been cleaned and it's not ready to run ``babs check-setup`` yet. What you need
to do are as follows:

#. Run ``babs init`` with ``--keep-if-failed`` turned on.

    * In this way, the failed BABS project will be kept.

#. Then you can run ``babs check-setup`` for diagnosis.
#. After you know what's wrong, please remove the failed BABS project
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

   If you don't remove the failed BABS project, you cannot overwrite it by running ``babs init`` again.


****************
Example commands
****************

Example ``babs init`` command for toy BIDS App + multi-session data on
a SLURM cluster:

.. code-block:: bash

    babs init \
        --container_ds /path/to/toybidsapp-container \
        --container_name toybidsapp-0-0-7 \
        --container_config /path/to/container_toybidsapp.yaml \
        --processing_level session \
        --queue slurm \
        /path/to/a/folder/holding/BABS/project/my_BABS_project


*********
Debugging
*********

-----------------------------------
Error when cloning an input dataset
-----------------------------------
What happened: After ``babs init`` prints out a message like this:
``Cloning input dataset #x: '/path/to/input_dataset'``, there was an error message that includes this information:
``err: 'fatal: repository '/path/to/input_dataset' does not exist'``.

Diagnosis: This means that the specified path to this input dataset (i.e., in ``origin_url``) was not valid;
there is no DataLad dataset there.

How to solve the problem: Fix this path. To confirm the updated path is valid, you can try cloning
it to a temporary directory with ``datalad clone /updated/path/to/input_dataset``. If it is successful,
you can go ahead rerun ``babs init``.

********
See also
********

* :doc:`preparation`
* :doc:`create_babs_project`
