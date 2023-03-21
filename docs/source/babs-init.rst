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
      Examples: ``--input BIDS /path/to/BIDS_datalad_dataset``;
      ``--input raw_BIDS https://osf.io/t8urc/``.
      
      Note for ``<name>``: ``<name>`` is defined by yourself. As long as it is not repeated
      across different ``--input``, you can use whatever string you'd like or you think 
      that's informative.


**********************
Detailed description
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
What will happen if ``babs-init`` fails?
--------------------------------------------------------------------

If ``babs-init`` fails, by default it will remove ("clean up") the created, failed BABS project;
if ``--keep-if-failed`` is specified, then this failed BABS project will be kept - in this case, however,
if you want to create the BABS project in the same folder, you will have to remove the existing failed
BABS project manually. Therefore, we do NOT recommend using ``--keep-if-failed`` unless you are familiar with DataLad
and know how to remove a BABS project.


**********************
Example commands
**********************

Example ``babs-init`` command for toy BIDS App + multi-session data on 
an SGE cluster::

    babs-init \
        --where_project /path/to/a/folder/holding/BABS/project \
        --project_name my_BABS_project \
        --input BIDS /path/to/BIDS_datalad_dataset \
        --container_ds /path/to/toybidsapp-container \
        --container_name toybidsapp-0-0-5 \
        --container_config_yaml_file /path/to/container_toybidsapp.yaml \
        --type_session multi-ses \
        --type_system sge

Example command if you have more than one input datasets, e.g., fMRIPrep
with FreeSurfer results ingressed::

    babs-init \
        ... \
        --input BIDS /path/to/BIDS_datalad_dataset \
        --input freesurfer /path/to/freesurfer_results_datalad_dataset \
        ...

***************
Debugging
***************

----------------------------------------
Error when cloning an input dataset
----------------------------------------
What happened: After ``babs-init`` prints out a message like this:
``Cloning input dataset #x: '/path/to/input_dataset'``, there was an error message that includes this information:
``err: 'fatal: repository '/path/to/input_dataset' does not exist'``.

Diagnosis: This means that the specified path to this input dataset (i.e., in ``--input``) was not valid;
there is no DataLad dataset there.

How to solve the problem: Fix this path. To confirm the updated path is valid, you can try cloning
it to a temporary directory with ``datalad clone /updated/path/to/input_dataset``. If it is successful,
you can go ahead rerun ``babs-init``.
