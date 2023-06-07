#########################################################
Prepare input BIDS dataset(s) as DataLad dataset(s)
#########################################################

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

==============================================================================
Raw (unzipped) BIDS dataset, or zipped BIDS dataset?
==============================================================================

* If there are zip files, like ``sub-*.zip``,
  it would be considered as a zipped BIDS derivatives dataset.
* If there are only unzipped folders, like folder ``sub-*/``,
  then it is considered as a raw (unzipped) BIDS dataset.
* If both zipped file ``sub-*.zip`` and unzipped folders ``sub-*`` present,
  then it is considered as a zipped BIDS derivatives dataset.

    * Therefore, if you have a raw BIDS dataset, please do not include zipped files
      called ``sub-*.zip`` in this dataset.

When running ``babs-init``, you will see printed messages describing each input BIDS dataset
was categorized as a raw (unzipped) dataset or a zipped dataset.

=====================================================
Requirements for zipped BIDS derivatives dataset
=====================================================
There are several requirements for zipped BIDS derivatives dataset:

Note: an input dataset's name is defined when ``babs-init --name``.

-------------------------
Naming of the zip files
-------------------------

* For single-session dataset, the zip filename should follow the pattern of
  ``sub-*_<name>*.zip``, where ``<name>`` is the name of this input dataset.

    * Here, ``*ses-*`` is allowed in the zip filenames.

* Similarly, for multi-session dataset, the zip filename should follow the pattern of
  ``sub-*_ses-*_<name>*.zip``
* In this dataset, for each subject (for single-session data),
  or each session (in multi-session data),
  there should only be one zip file whose filename contains input dataset's name.

    * For example, say we have ``sub-01_ses-A_freesurfer-20-2-3.zip``,
      where ``freesurfer`` will be the input dataset's name.
      There should not be another zip file with ``freesurfer`` for this session,
      e.g., ``sub-01_ses-A_freesurfer-xxx.zip``

-------------------------
Content of the zip files
-------------------------
Within the zip file for a specific subject (or session), there should be a folder
named by this input dataset's name, e.g., folder ``freesurfer``
inside ``sub-01_ses-A_freesurfer-20-2-3.zip`` in the input dataset ``freesurfer``.

.. developer's note: The name of the folder within the zip file must be the input dataset's name, and this applies to all the subjects in this input dataset

For more explanations and examples, please refer to "See also" below.

-------------------
See also
-------------------

Notes in ``babs-init`` CLI: :ref:`how-to-define-name-of-input-dataset`


================================================================
Using results from another BABS project as input BIDS dataset
================================================================
If you hope to use zipped results from another BABS' project ("BABS project A")
as input dataset for your current BABS project ("BABS project B"), you may:

#. Clone the results out from the output RIA of BABS project A:

    * If BABS project A is on the local file system that current directory has access to,
      you may clone its output RIA by::
        
        datalad clone ria+file:///absolute/path/to/my_BABS_project_A/output_ria#~data

    * For more details and/or other RIA scenarios, please refer to `datalad clone's documentation <https://docs.datalad.org/en/stable/generated/man/datalad-clone.html>`_ and `DataLad Handbook about cloning from RIA stores <https://handbook.datalad.org/en/latest/beyond_basics/101-147-riastores.html#cloning-and-updating-from-ria-stores>`_
#. Then use the path to the cloned dataset as the input dataset directory.
#. :octicon:`alert-fill` :bdg-warning:`warning`
   Please refer to :ref:`how-to-define-name-of-input-dataset` for restrictions in data organizing
   and naming for a zipped dataset.

.. Developer's Notes: In theory the user could directly provide ``ria+file://xxx/output_ria#~data`` as the path to the input dataset in ``babs-init``,
..      but we hope they could test if this string is correct by letting them clone once.

================================================================
Examples input BIDS datasets for BABS
================================================================
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
