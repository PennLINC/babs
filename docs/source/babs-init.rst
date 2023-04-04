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
      
      ``<name>`` is defined by yourself. Please see section
      :ref:`how-to-define-name-of-input-dataset` below for general guidelines
      and specific restrictions.


**********************
Detailed description
**********************

--------------------------------------------------------------------
How to prepare input dataset, container, and container's YAML file?
--------------------------------------------------------------------

Please see document :ref:`preparation` for how to prepare these inputs.

.. _how-to-define-name-of-input-dataset:

----------------------------------------------------------------
How to define input dataset's name ``<name>`` in ``--input``?
----------------------------------------------------------------

**General guideline**: a string you think that's informative, and you don't need to choose
from a predefined pool by BABS. Examples are ``BIDS``, ``freesurfer``.

**Specific restrictions**:

1. If you have **more than one** input BIDS dataset (i.e., more than one ``--input``),
   please make sure the ``<name>`` are different for each dataset;
2. If an input BIDS dataset is a **zipped dataset**, i.e., files are zipped files, such as BIDS data
   derivatives from another BABS project:
   
    #. You must name it with pattern in the zip filenames
       so that ``babs-init`` knows which zip file you want to use for a subject or session.
       For example, one of your input dataset is BIDS derivates of fMRIPrep, which includes zip
       files of ``sub-xx*_freesurfer*.zip`` and ``sub-xx*_fmriprep*.zip``. If you'd like to feed
       ``freesurfer`` results zip files into current BABS project, then you should name this input
       dataset as ``freesurfer``. If you name it a random name like ``BIDS_derivatives``, as this
       is not a pattern found in these zip files, ``babs-init`` will fail.
    #. In addition, the zip files that have such pattern (e.g., ``*freesurfer*``) should include a folder named
       as the same name too (e.g., a folder called ``freesurfer``).
    #. For example,
       in multi-session, zipped fMRIPrep derivatives data (e.g., https://osf.io/k9zw2/)::

            sub-01_ses-A_freesurfer-20.2.3.zip
            ├── freesurfer
            │   ├── fsaverage
            │   └── sub-01
            sub-01_ses-B_freesurfer-20.2.3.zip
            ├── freesurfer
            │   ├── fsaverage
            │   └── sub-02
            etc

--------------------------------------------------------
How is the list of subjects (and sessions) determined?
--------------------------------------------------------
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
        --container_name toybidsapp-0-0-6 \
        --container_config_yaml_file /path/to/container_toybidsapp.yaml \
        --type_session multi-ses \
        --type_system sge

Example command if you have more than one input datasets, e.g., raw BIDS data, and fMRIPrep
with FreeSurfer results ingressed. The 2nd dataset is also result from another BABS project -
a zipped dataset has filenames in patterns of 'sub-xx*_freesurfer*.zip'.
Therefore, the 2nd input dataset should be named as 'freesurfer', a keyword in filename::

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
