*******************************************************
Prepare a configuration YAML file for the BIDS App
*******************************************************

.. contents:: Table of Contents

A BIDS App usually has a few arguments, and different Apps may require different amount of cluster resources. To make sure BABS can run in a tailored way, it is required to prepare a YAML file to define a few configurations when running the BIDS App.

`YAML <https://yaml.org/>`_ is a serialization language that is often used to define configurations. A YAML file for running BABS includes a few "sections". These sections not only define how exactly the BIDS App will be run, but also will be helpful in filtering out unnecessary subjects (and sessions), and in an informative debugging.

Overview of the YAML file structure
========================================
The YAML file required by BABS includes these sections:

* **babs_singularity_run**: the arguments for ``singularity run`` of the BIDS App;
* **babs_zip_foldername**: the results foldername(s) to be zipped;
* **cluster_resources**: how much cluster resources are needed to run this BIDS App?
* **script_preamble**: the preambles in the script to run a participant's job;
* **required_files**: to only keep subjects (sessions) that have this list of required files in input dataset(s);
* **keywords_alert**: keywords in alerting messages in the log files that may be helpful for debugging the error;


Example/prepopulated YAML files:

* One, unzipped input dataset: `YAML file for fMRIPrep <https://github.com/PennLINC/babs/blob/main/notebooks/example_container_fmriprep.yaml>`_
* One, zipped input dataset: `YAML file for XCP-D <https://github.com/PennLINC/babs/blob/main/notebooks/example_container_xcpd.yaml>`_
* Two input datasets (one unzipped, one zipped): `YAML file for fMRIPrep with FreeSurfer results ingressed <https://github.com/PennLINC/babs/blob/main/notebooks/example_container_fmriprep_ingressed_fs.yaml>`_

TODO: add if each section is optional ___________

Terminology when describing YAML file: Below is an example "section" in a YAML file::

    section_name:
        key: value

In a section, the string before ``:`` is called ``key``, the string after ``:`` is called ``value``.

Below are the details for each section in this configuration YAML file.

babs_singularity_run
========================
Currently, BABS does not support using configurations of running a BIDS App
that are defined in ``datalad containers-add --call-fmt``.
Instead, users are expected to define these in this section, **babs_singularity_run**.

Example **babs_singularity_run** for ``fMRIPrep``::

    babs_singularity_run:
        -w: "$BABS_TMPDIR"   # this is a placeholder for temporary workspace
        --n_cpus: '1'
        --stop-on-first-crash: ""   # argument without value
        --fs-license-file: "$FREESURFER_LICENSE" # this is a placeholder.
        --skip-bids-validation: Null  # Null or NULL is also a placeholder for argument without value
        --output-spaces: "MNI152NLin6Asym:res-2"
        --force-bbr: ""
        -v: '-v'   # this is for double `-v`

This section will be turned into a Singularity run command as below::

    TODO: add generated singularity run command!

Notes:

* Usually you only need to provide named arguments, but not positional arguments. However, if you have more than one input datasets, you must use ``$INPUT_PATH`` to specify which dataset to use for the positional argument BIDS dataset. See below bullet point "Key placeholders:" -> ``$INPUT_PATH`` for more.
* Basic format: if you want to specify ``--my_argument its_value``, simply write as one of following format:

    * ``--my_argument: 'its_value'``    (value in single quotation marks)
    * ``--my_argument: "its_value"``    (value in double quotation marks)
    * ``--my_argument: its_value``    (value without quotation marks; avoid using this format for values of numbers)
* Mixing: You can mix arguments that begins with double dashes ``--`` and those with single dash ``-``;
* Arguments without values: There are several ways to specify arguments without values; just choose one of formats as follows:

    * ``my_key: ""``    (empty value string)
    * ``my_key: Null``    (``Null`` is a placeholder)
    * ``my_key: NULL``    (``NULL`` is a placeholder)
* Repeated arguments: As this YAML section will be read as a dictionary by BABS, each key before ``:`` can not be repeated. If you need to specify repeated arguments, e.g., ``-v -v``, please specify it as ``-v : '-v'`` as in the example above; for tripple ``-v``, specify as ``-v: '-v -v'``
* Value placeholders: There are several placeholders for values available in BABS:

    * ``"$BABS_TMPDIR"`` is a value placeholder for temporary working directory. You might use this for arguments e.g., working directory.
    * ``"$FREESURFER_LICENSE"`` is a value placeholder for FreeSurfer license, e.g., ``--fs-license-file: "$FREESURFER_LICENSE"``. BABS will use the license from ``$FREESURFER_HOME``.
* Key placeholders:

    * ``$INPUT_PATH`` is a placeholder for positional argument input dataset (or BIDS directory). This must be included if there are more than one input dataset, to tell BABS which input dataset to use for this positional argument. Also, this must be used as the first key/value in this section **babs_singularity_run**, i.e., before other arguments.

        * For example, if you hope to specify an input dataset called ``BIDS`` for this positional argument, simply write ``$INPUT_PATH: inputs/data/BIDS``. Replace ``BIDS`` with your input dataset's name, but make sure you keep ``inputs/data/`` which is needed by BABS. For more, please see the example YAML file for more than one dataset: `fMRIPrep with FreeSurfer results ingressed <https://github.com/PennLINC/babs/blob/main/notebooks/example_container_fmriprep_ingressed_fs.yaml>`_.
        * ERROR! TOOD: ^^ should be depending on unzipped or zipped dataset (e.g., "inputs/data/freesurfer/freesurfer")!
* path to the dataset, zipped or unzipped
    * e.g., ``$INPUT_PATH`` in fMRIPrep with FreeSurfer results ingressed
    * e.g., ``--fs-subjects-dir`` in fMRIPrep with FreeSurfer results ingressed
* TODO: go thru all yaml file for any missing notes!!


babs_zip_foldername
=======================

This section defines the output folder name(s) that get saved and zipped.
This also includes the version of the BIDS App you use.

Example section **babs_zip_foldername** for ``fMRIPrep``::

    babs_zip_foldername:
        fmriprep: "20-2-3"
        freesurfer: "20-2-3"

As you can see in this example, we expect that fMRIPrep will generate two folders,
one is called ``fmriprep``, the other is called ``freesurfer``.
If there is only one folder that you hope BABS to save and zip, simply provide only one.

In addition to the folder name(s), please also add the version of the BIDS App as the value.
Please use the same string as that in ``--container-name`` when calling ``babs-init``.
We recommend using dashes ``-`` instead of dots ``.`` when indicating the version number, e.g., ``20-2-3`` instead of ``20.2.3``.
If there are multiple folders to zip, we recommend using the consistent version string across these folders.
In this example case, the ``fMRIPrep`` BIDS App's version is ``20.2.3``, so we specify ``20-2-3`` for
both folders ``fmriprep`` and ``freesurfer``,
although the version of ``FreeSurfer`` included in this ``fMRIPrep`` may not be ``20.2.3``.


cluster_resources
=====================

script_preamble
====================

required_files
==================

keywords_alert
================