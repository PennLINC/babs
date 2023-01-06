Prepare input dataset(s)
==============================
You can provide one or more BIDS dataset(s) as input. It can be raw BIDS dataset(s), or zipped BIDS derivatives (e.g., zipped results from another BABS' project), or a mix of these two. BABS is compatible to both multi-session datasets (more than one session per subject) and single-session datasets.

Regardless, each BIDS dataset should be presented as a DataLad dataset, which is tracked by DataLad and can be cloned to another directory. A DataLad dataset can be created with DataLad command ``datalad create``. For more details, please refer to `its documentation <http://docs.datalad.org/en/stable/generated/man/datalad-create.html>`_, and `DataLad Handbook <https://handbook.datalad.org/en/latest/basics/101-101-create.html>`__.

If you hope to use zipped results from another BABS' project ("BABS project A") as input dataset for your current BABS project ("BABS project B"), you may:

#. Clone the results out from the output RIA of BABS project A, by

    * If BABS project A is on the local file system that current directory has access to, you may clone its output RIA by ``datalad clone ria+file:///absolute/path/to/my_BABS_project_A/output_ria#~data``;
    * For more details and/or other RIA scenarios, please refer to `datalad clone's documentation <https://docs.datalad.org/en/stable/generated/man/datalad-clone.html>`_ and `DataLad Handbook about cloning from RIA stores <https://handbook.datalad.org/en/latest/beyond_basics/101-147-riastores.html#cloning-and-updating-from-ria-stores>`_
#. Then use the path to the cloned dataset as the input dataset directory.

.. Developer's Notes: In theory the user could directly provide ``ria+file://xxx/output_ria#~data`` as the path to the input dataset in ``babs-init``,
..      but we hope they could test if this string is correct by letting them clone once.


Examples input datasets for BABS
----------------------------------
.. list-table:: Example input datasets available on OSF
   :widths: 25 25 25
   :header-rows: 1

   * -
     - single-session data
     - multi-session data
   * - raw BIDS data
     - https://osf.io/t8urc/
     - https://osf.io/w2nu3/
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
