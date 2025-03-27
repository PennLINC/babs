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

   --datasets : @after
      Examples: ``--datasets BIDS=/path/to/BIDS_datalad_dataset``;
      ``--datasets raw_BIDS=https://osf.io/t8urc/``.

      ``<name>`` is defined by yourself. Please see section
      :ref:`how-to-define-name-of-input-dataset` below for general guidelines
      and specific restrictions.

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

Please see document :ref:`preparation` for how to prepare these inputs.

.. _how-to-define-name-of-input-dataset:

--------------------------------------------------------------------------------
How do I define the input dataset's name ``<name>`` in ``babs init --datasets``?
--------------------------------------------------------------------------------

**General guideline**: a string you think that's informative.
Examples are ``BIDS``, ``freesurfer``.

**Specific restrictions**:

1. If you have **more than one** input BIDS dataset (i.e., more than one ``--datasets``),
   please make sure the ``<name>`` is different for each dataset;
2. If an input BIDS dataset is a **zipped dataset**, i.e., files are zipped files, such as BIDS data
   derivatives from another BABS project:

    #. You must name it with pattern in the zip filenames
       so that ``babs init`` knows which zip file you want to use for a subject or session.
       For example, one of your input dataset is BIDS derivates of fMRIPrep, which includes zip
       files of ``sub-xx*_freesurfer*.zip`` and ``sub-xx*_fmriprep*.zip``. If you'd like to feed
       ``freesurfer`` results zip files into current BABS project, then you should name this input
       dataset as ``freesurfer``. If you name it a random name like ``BIDS_derivatives``, as this
       is not a pattern found in these zip files, ``babs init`` will fail.
    #. In addition, the zip files named with such pattern (e.g., ``*freesurfer*.zip``)
       should include a folder named
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

------------------------------------------------------
How is the list of subjects (and sessions) determined?
------------------------------------------------------
A list of subjects (and sessions) will be determined when running ``babs init``,
and will be saved in a CSV file called named ``sub_final_inclu.csv`` (for single-session dataset)
or ``sub_ses_final_inclu.csv`` (for multiple-session dataset),
located at ``/path/to/my_BABS_project/analysis/code``.

**To filter subjects and sessions**, use ``babs init`` with ``--list-sub-file /path/to/subject/list/csv/file``. Examples: `Single-session example <https://github.com/PennLINC/babs/blob/ba32e8fd2d6473466d3c33a1b17dfffc4438d541/notebooks/initial_sub_list_single-ses.csv>`_, `Multi-session example <https://github.com/PennLINC/babs/blob/ba32e8fd2d6473466d3c33a1b17dfffc4438d541/notebooks/initial_sub_list_multi-ses.csv>`_.

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
        --datasets BIDS=/path/to/BIDS_datalad_dataset \
        --container_ds /path/to/toybidsapp-container \
        --container_name toybidsapp-0-0-7 \
        --container_config /path/to/container_toybidsapp.yaml \
        --processing_level session \
        --queue slurm \
        /path/to/a/folder/holding/BABS/project/my_BABS_project

Example command if you have more than one input datasets, e.g., raw BIDS data, and fMRIPrep
with FreeSurfer results ingressed. The 2nd dataset is also result from another BABS project -
a zipped dataset has filenames in patterns of 'sub-xx*_freesurfer*.zip'.
Therefore, the 2nd input dataset should be named as 'freesurfer', a keyword in filename:

.. code-block:: bash

    babs init \
        ... \
        --datasets \
        BIDS=/path/to/BIDS_datalad_dataset \
        freesurfer=/path/to/freesurfer_results_datalad_dataset \
        ...

*********
Debugging
*********

-----------------------------------
Error when cloning an input dataset
-----------------------------------
What happened: After ``babs init`` prints out a message like this:
``Cloning input dataset #x: '/path/to/input_dataset'``, there was an error message that includes this information:
``err: 'fatal: repository '/path/to/input_dataset' does not exist'``.

Diagnosis: This means that the specified path to this input dataset (i.e., in ``--datasets``) was not valid;
there is no DataLad dataset there.

How to solve the problem: Fix this path. To confirm the updated path is valid, you can try cloning
it to a temporary directory with ``datalad clone /updated/path/to/input_dataset``. If it is successful,
you can go ahead rerun ``babs init``.

********
See also
********

* :doc:`preparation`
* :doc:`create_babs_project`
