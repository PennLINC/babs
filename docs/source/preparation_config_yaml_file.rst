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
This section defines how much cluster resources each participant's job will use.

Example section **cluster_resources** for ``fMRIPrep``::

    cluster_resources:
        interpreting_shell: /bin/bash
        hard_memory_limit: 25G
        temporary_disk_space: 200G

These will be turned into options in the preambles of ``participant_job.sh`` on an SGE cluster
(this script could be found at: ``/path/to/my_BABS_project/analysis/code``) shown as below::

    #$ -S /bin/bash
    #$ -l h_vmem=25G
    #$ -l tmpfree=200G

For example, a job requires no more than 25 GB of memory,
i.e., on SGE clusters, ``-l h_vmem=25G``.
You may simply specify: ``hard_memory_limit: 25G``.

The table below lists all the named cluster resources requests that BABS supports.
You may not need all of them.
BABS will replace ``$VALUE`` with the value you provide.
The second row in each cell, which is also in (), is an example.

.. .. list-table:: Cluster resources requrests that BABS supports
..     :widths: 10 10 10 10
..     :header-rows: 1

..     * - key in ``cluster_resources``
..       - format in generated preamble
..       - example key-value in ``cluster_resources``
..       - example outcome in the preamble (SGE cluster)
..     * - interpreting_shell
..       - ``-S $VALUE``
..       - ``interpreting_shell: /bin/bash``
..       - ``-S /bin/bash``

+------------------------------------------+---------------------------------------+
| | Section ``cluster_resources`` in YAML  | | Generated preamble for SGE clusters |
| |         (example key-value)            | |           (example outcome)         |
+==========================================+=======================================+
| | ``interpreting_shell: $VALUE``         | | ``-S $VALUE``                       |
| | (``interpreting_shell: /bin/bash``)    | | (``-S /bin/bash``)                  |
+------------------------------------------+---------------------------------------+
| | ``hard_memory_limit: $VALUE``          | | ``-l h_vmem=$VALUE``                |
| | (``hard_memory_limit: 25G``)           | | (``-l h_vmem=25G``)                 |
+------------------------------------------+---------------------------------------+
| | ``soft_memory_limit: $VALUE``          | | ``-l s_vmem=$VALUE``                |
| | (``soft_memory_limit: 23.5G``)         | | (``-l s_vmem=23.5G``)               |
+------------------------------------------+---------------------------------------+
| | ``temporary_disk_space: $VALUE``       | | ``-l tmpfree=$VALUE``               |
| | (``temporary_disk_space: 200G``)       | | (``-l tmpfree=200G``)               |
+------------------------------------------+---------------------------------------+
| | ``number_of_cpus: "$VALUE"``           | | ``-pe threaded $VALUE``             |
| | (``number_of_cpus: "6"``)              | | (``-pe threaded 6``)                |
+------------------------------------------+---------------------------------------+
| | ``hard_runtime_limit: "$VALUE"``       | | ``-l h_rt=$VALUE``                  |
| | (``hard_runtime_limit: "24:00:00"``)   | | (``-l h_rt=24:00:00``)              |
+------------------------------------------+---------------------------------------+

If you cannot find the one you want in the above table, you can still add it by ``customized_text``.
Below is an example for SGE cluster::

    cluster_resources:
        <here goes keys defined in above table>: <$VALUE>
        customized_text: |
            #$ -abc this_is_an_example_customized_option_to_appear_in_preamble
            #$ -zzz there_can_be_multiple_lines_of_customized_option

Note that:

* Remember to add ``|`` after ``customized_text:``;
* As customized texts will be directly copied to the script ``participant_job.sh`` (without translation), please remember to add any necessary prefix before the option, e.g., ``#$`` for SGE clusters.

TODO: check all example YAML file i have, also check their `participant_job.sh`

script_preamble
====================
This part also goes to the preamble of the script ``participant_job.sh``
(located at: ``/path/to/my_BABS_project/analysis/code``). Different from **cluster_resources**
that provides options for cluster resources requests, this section **script_preamble** is for necessary
bash commands that are required by job running. An example would be to activate the conda environment;
however, different clusters may require different commands to do so. Therefore, BABS asks the user to
provide it.

Example section **cluster_resources** for a specific cluster::

    script_preamble: |
        source ${CONDA_PREFIX}/bin/activate babs    # replace `babs` with your conda environment name for running jobs

This will appear as below in the ``participant_job.sh``::

    # Script preambles:
    source ${CONDA_PREFIX}/bin/activate babs

.. warning::
    Above command may not apply to your cluster; check how to activate conda environment on your cluster and replace above command.

Notes:

* Remember to add ``|`` after ``script_preamble:``;
* You can also add more necessary commands by adding new lines;
* Please do NOT quote the commands in this section!

.. _required_files:

required_files
==================
You may have a dataset where not all the subjects (and sessions) have the required files for
running the BIDS App. You can simply provide this list of required files, and BABS will exclude those
subjects and sessions who don't have any of listed required files.

Example section **required_files** for ``fMRIPrep``::

    required_files:
        $INPUT_DATASET_#1:
            - "func/*_bold.nii*"
            - "anat/*_T1w.nii*"

In this example case, we specify that for the input raw BIDS dataset, which is also input dataset #1, each subject (and session) must have:

#. At least one BOLD file (``*_bold.nii*``) in folder ``func``;
#. At least one T1-weighted file (``*_T1w.nii*``) in folder ``anat``.


Notes:

* If needed, you can change ``$INPUT_DATASET_#1`` to other index of input dataset (e.g., ``$INPUT_DATASET_#2``);
* To determine the index of the input dataset to specify, please check the order of the datasets when you call ``babs-init --input``. This index starts from 1, and is a positive integer.

    * For example, to use ``fMRIPrep`` with FreeSurfer results ingressed, by calling ``babs-init --input BIDS /path/to/BIDS --input freesurfer /path/to/freesurfer_outputs``, and you hope to filter subjects based on files in raw BIDS data (here named ``BIDS``), then you should specify ``$INPUT_DATASET_#1``.
* We recommend adding ``*`` after ``.nii`` as there might only be unzipped NIfTI file (e.g., ``.nii`` instead of ``.nii.gz``) in the input dataset;
* Currently we only support checking required files in unzipped input dataset (e.g., raw BIDS dataset).


.. _keywords_alert:

keywords_alert
================
This section is optional.

This section is to define a list of alerting keywords to be searched in log files,
and these keywords may indicates failure of a job.

Example section **keywords_alert** for fMRIPrep::

    keywords_alert:
        o_file:
            - "Exception: No T1w images found for"  # not needed if setting T1w in `required_files`
            - "Excessive topologic defect encountered"
            - "Cannot allocate memory"
            - "mris_curvature_stats: Could not open file"
            - "Numerical result out of range"
            - "fMRIPrep failed"
        e_file:
            - "xxxxx"    # change this to any keywords to be found in `*.e*` file; if there is no keywords for `*.e*` file, delete `e_file` and this line


Usually there are two log files that are useful for debugging purpose, ``*.o*`` and ``*.e*``, for example, ``<jobname>.o<jobid>`` and ``<jobname>.o<jobid>``. You can define alerting keywords in either or both files, i.e., by filling out ``o_file`` (for ``*.o*`` file) and/or ``e_file`` (for ``*.e*`` file).

Detection of the keyword is performed in the order provided by the user. If ``o_file`` is former (e.g., in above case), then detection of it will be performed earlier; if a keyword is former, then that will be checked earlier. BABS also follows "detect and break" rule, i.e., for each job,

* If any keyword is detected, the detected keyword will be thrown into the ``job_status.csv``, and BABS won't detect any further keyword down in the list.
* If a keyword has been detected in the first file (``o_file`` for above example), then won't detect any keyword in the other log file (``e_file`` for above example).

.. warning::
    Detecting the keywords in the log files by BABS is case-sensitve! So please make sure the cases of keywords are in the way you hope.
