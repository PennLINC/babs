**********************
Get prepared
**********************

BABS requires three items:

#. Input BIDS dataset(s): DataLad dataset(s)
#. A containerized BIDS App: also a DataLad dataset
#. A configuration YAML file for the BIDS App

1. Input BIDS dataset(s)
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
* To clone a dataset:

.. code-block:: console

    $ conda activate <datalad_env>
    #   ^^ `<datalad_env>`: the conda environment where DataLad is installed

    $ datalad clone https://osf.io/<id>/ <local_foldername>
    #   ^^ replace `<id>` and `<local_foldername>` accordingly
    #   e.g., `datalad clone https://osf.io/t8urc/ raw_BIDS_single-ses`


2. Containerized BIDS App
=============================
As the data processing will be performed on a cluster, and usually clusters only accept Singularity image (but not Docker image), you may need to pull the BIDS App as a Singularity image.

BABS also requires BIDS App to be a DataLad dataset. You may use DataLad command ``datalad containers-add`` to add a containerized BIDS App to a DataLad dataset. For more details, please refer to `this command's documentation <http://docs.datalad.org/projects/container/en/latest/generated/man/datalad-containers-add.html>`_ and `DataLad Handbook <https://handbook.datalad.org/en/latest/basics/101-133-containersrun.html>`_.


3. A configuration YAML file for the BIDS App
=================================================
A BIDS App usually has a few arguments, and different Apps may require different amount of cluster resources. To make sure BABS can run in a tailored way, it is required to prepare a YAML file to define a few configurations when running the BIDS App.

`YAML <https://yaml.org/>`_ is a serialization language that is often used to define configurations. A YAML file for running BABS includes a few "sections". These sections not only define how exactly the BIDS App will be run, but also will be helpful in filtering out unnecessary subjects (and sessions), and in an informative debugging.

Overview of the YAML file structure
---------------------------------------
The YAML file required by BABS includes these sections:

* **babs_singularity_run**: the arguments for ``singularity run`` of the BIDS App;
* **babs_zip_foldername**: the results foldername(s) to be zipped;
* **cluster_resources**: how much cluster resources are needed to run this BIDS App?
* **script_preamble**: the preambles in the script to run a participant's job;
* **required_files**: to only keep subjects (sessions) that have this list of required files in input dataset(s);
* **keywords_alert**: keywords in alerting messages in the log files that may be helpful for debugging the error;


An example/prepopulated YAML file can be found here ___TODO: add_______

TODO: add if each section is optional ___________

Below are the details for each section.

babs_singularity_run
------------------------
Currently, BABS does not support using configurations of running a BIDS App that are defined in ``datalad containers-add --call-fmt``. Instead, users are expected to define these in this section, **babs_singularity_run**.

