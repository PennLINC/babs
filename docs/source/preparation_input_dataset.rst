Prepare input dataset(s)
==============================
You can provide one or more BIDS dataset(s) as input. It can be raw BIDS dataset(s), or zipped BIDS derivatives (e.g., zipped results from another BABS' project), or a mix of these two. BABS is compatible to both multi-session datasets (more than one session per subject) and single-session datasets.

Regardless, each BIDS dataset should be presented as a DataLad dataset, which is tracked by DataLad and can be cloned to another directory. A DataLad dataset can be created with DataLad command ``datalad create``. For more details, please refer to `its documentation <http://docs.datalad.org/en/stable/generated/man/datalad-create.html>`_, and `DataLad Handbook <https://handbook.datalad.org/en/latest/basics/101-101-create.html>`__.


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
