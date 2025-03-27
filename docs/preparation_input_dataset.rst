###################################################
Prepare input BIDS dataset(s) as DataLad dataset(s)
###################################################

.. contents:: Table of Contents

You can provide one or more BIDS dataset(s) as input. Each input can either be raw BIDS dataset(s),
or zipped BIDS derivatives datasets (e.g., zipped results from another BABS' project).
BABS is compatible to both single-session datasets and multi-session datasets (more than one session per subject).

Regardless, each BIDS dataset should be presented as a *DataLad dataset*,
which is version tracked by DataLad and can be cloned to another directory.
A DataLad dataset can be created with DataLad command ``datalad create``.
For more details, please refer to
`its documentation <http://docs.datalad.org/en/stable/generated/man/datalad-create.html>`_,
and `DataLad Handbook <https://handbook.datalad.org/en/latest/basics/101-101-create.html>`__.

====================================================
Raw (unzipped) BIDS dataset, or zipped BIDS dataset?
====================================================

* If there are zip files, like ``sub-*.zip``,
  it would be considered as a zipped BIDS derivatives dataset.
* If there are only unzipped folders in the BIDS file/directory structure format, like folder ``sub-*/``,
  then it is considered as a raw (unzipped) BIDS dataset.
* If both zipped file ``sub-*.zip`` and unzipped folders ``sub-*`` present,
  then it is considered as a zipped BIDS derivatives dataset.

    * Therefore, if you have a raw BIDS dataset, please do not include zipped files
      called ``sub-*.zip`` in this dataset.

When running ``babs init``, you will see printed messages describing each input BIDS dataset
was categorized as a raw (unzipped) dataset or a zipped dataset.

.. _requirements_for_zipped_BIDS_derivatives_dataset:

========================================================
Requirements for a zipped BIDS derivatives input dataset
========================================================
There are several requirements for zipped BIDS derivatives dataset:

Note: an input dataset's name is defined when ``babs init --name``.

----------------
Naming zip files
----------------

* For single-session dataset, the zip filename should follow the pattern of
  ``sub-*_<name>*.zip``, where ``<name>`` is the name of this input dataset.

    * Here, ``*ses-*`` is allowed in the zip filenames.

* Similarly, for multi-session dataset, the zip filename should follow the pattern of
  ``sub-*_ses-*_<name>*.zip``
* In this dataset, for each subject/session pair,
  there should only be one zip file whose filename contains input dataset's name.

    * For example, say we have ``sub-01_ses-A_freesurfer-20-2-3.zip``,
      where ``freesurfer`` will be the input dataset's name.
      There should not be another zip file with ``freesurfer`` for this session,
      e.g., ``sub-01_ses-A_freesurfer-xxx.zip``

------------------------
Content of the zip files
------------------------
Within the zip file of a specific subject (or session), there should be a folder
named by this input dataset's name, e.g., folder ``freesurfer``
inside ``sub-01_ses-A_freesurfer-20-2-3.zip`` in the input dataset ``freesurfer``.

.. developer's note: The name of the folder within the zip file must be the input dataset's name, and this applies to all the subjects in this input dataset

For more explanations and examples, please refer to "See also" below.

--------
See also
--------

Notes in ``babs init`` CLI: :ref:`how-to-define-name-of-input-dataset`


================================================================
Using results from another BABS project as an input BIDS dataset
================================================================
If you hope to use zipped results from another BABS project ("BABS project A")
as input dataset for a new BABS project ("BABS project B"), you may follow these steps:

#. Test out the path you'll to use.
   This step is optional but highly recommended.
   This is to make sure that the input dataset's path you'll provide is correct.
   To do so, please try cloning the results from the output RIA of BABS project A:

    * If BABS project A is on the local file system that current directory has access to,
      you may clone the results from its output RIA by::

        datalad clone ria+file:///absolute/path/to/my_BABS_project_A/output_ria#~data

    * For more details and/or other RIA scenarios,
      please refer to `datalad clone's documentation <https://docs.datalad.org/en/stable/generated/man/datalad-clone.html>`_
      and `DataLad Handbook about cloning from RIA stores <https://handbook.datalad.org/en/latest/beyond_basics/101-147-riastores.html#cloning-and-updating-from-ria-stores>`_

#. If you successfully cloned the results, then this means the path you used is correct.
   You can go ahead and use this path
   as the input dataset path for generating BABS project B.

    * Please make sure you use the *entire* string after ``datalad clone`` as the input dataset path.
      For above example, this path is::

        ria+file:///absolute/path/to/my_BABS_project_A/output_ria#~data

#. You may remove the cloned results
   of the BABS project A (from the first step)::

    datalad remove -d <cloned_results_of_BABS_project_A>

#. :octicon:`alert-fill` :bdg-warning:`warning`
   Please refer to docs listed below for detailed requirements before you run ``babs init``:

    * :ref:`how-to-define-name-of-input-dataset`:
      for restrictions in naming a zipped dataset as input.
    * :ref:`requirements_for_zipped_BIDS_derivatives_dataset`:
      for requirements in zip files naming and their contents.

.. Developer's Notes: In theory the user could directly provide ``ria+file://xxx/output_ria#~data`` as the path to the input dataset in ``babs init``,
..      but we hope they could test if this string is correct by letting them clone once.

.. _example_input_BIDS_datasets_for_BABS:

====================================
Example input BIDS datasets for BABS
====================================

.. list-table:: Example input datasets available on OSF
   :widths: 25 25 25
   :header-rows: 1

   * -
     - single-session data
     - multi-session data
   * - raw BIDS data
     - https://osf.io/t8urc/
     - https://osf.io/w2nu3/
   * - zipped BIDS derivatives from fMRIPrep
     - https://osf.io/2jvub/
     - https://osf.io/k9zw2/
   * - zipped BIDS derivatives from QSIPrep
     - https://osf.io/8t9sf/
     - https://osf.io/d3js6/


Notes:

* All images have been zero-ed out.
* To clone a dataset::

    conda activate <datalad_env>
    # Here, `<datalad_env>`: the conda environment where DataLad is installed

    datalad clone https://osf.io/<id>/ <local_foldername>
    # Please replace `<id>` and `<local_foldername>` accordingly
    # e.g., `datalad clone https://osf.io/t8urc/ raw_BIDS_single-ses`
