*******************************************************
Prepare a configuration YAML file for the BIDS App
*******************************************************

.. contents:: Table of Contents

A BIDS App usually has a few arguments, and different Apps may require different amount of cluster resources.
To make sure BABS can run in a tailored way, it is required to prepare a YAML file to define a few configurations
when running the BIDS App container.

`YAML <https://yaml.org/>`_ is a serialization language that is often used to define configurations.
A YAML file for running BABS includes a few "sections".
These sections not only define how exactly the BIDS App will be run, but also will be helpful
in filtering out unnecessary subjects (and sessions), and in an informative debugging.

Overview of the configuration YAML file structure
====================================================

Sections in the configuration YAML file
-----------------------------------------

* **babs_singularity_run**: the arguments for ``singularity run`` of the BIDS App;
* **babs_zip_foldername**: the results foldername(s) to be zipped;
* **cluster_resources**: how much cluster resources are needed to run this BIDS App?
* **script_preamble**: the preambles in the script to run a participant's job;
* **required_files**: to only keep subjects (sessions) that have this list of required files in input dataset(s);
* **keywords_alert**: keywords in alerting messages in the log files that may be helpful for debugging the error;

Among these sections, these sections are optional:

* **required_files**
* **keywords_alert**



Example/prepopulated configuration YAML files
-----------------------------------------------

* One, unzipped input dataset:

    * `example configuration YAML file for toy BIDS App <https://github.com/PennLINC/babs/blob/main/notebooks/example_container_toybidsapp.yaml>`_
    * `example configuration YAML file for fMRIPrep (version xxxx) <https://github.com/PennLINC/babs/blob/main/notebooks/example_container_fmriprep.yaml>`_
    * `example configuration YAML file for QSIPrep (version xxxx) <https://github.com/PennLINC/babs/blob/main/notebooks/example_container_qsiprep.yaml>`_
    * `example configuration YAML file for XCP-D (version xxxx)  <https://github.com/PennLINC/babs/blob/main/notebooks/example_container_xcpd.yaml>`_

* One, zipped input dataset: 

    * `example configuration YAML file toy BIDS App for zipped input dataset <https://github.com/PennLINC/babs/blob/main/notebooks/example_container_zipped_toybidsapp.yaml>`_

* Two input datasets (one unzipped, one zipped):

    * `example configuration YAML file for fMRIPrep (version xxx) with FreeSurfer results ingressed <https://github.com/PennLINC/babs/blob/main/notebooks/example_container_fmriprep_ingressed_fs.yaml>`_


Terminology when describing a YAML file: 
------------------------------------------
Below is an example "section" in a YAML file::

    section_name:
        key: value

In a section, the string before ``:`` is called ``key``, the string after ``:`` is called ``value``.

Below are the details for each section in this configuration YAML file.


Section ``babs_singularity_run``
==================================
Currently, BABS does not support using configurations of running a BIDS App
that are defined in ``datalad containers-add --call-fmt``.
Instead, users are expected to define these in this section, **babs_singularity_run**.

Example **babs_singularity_run**
-----------------------------------

Below is example section **babs_singularity_run** for ``fMRIPrep``::

    babs_singularity_run:
        -w: "$BABS_TMPDIR"   # this is a placeholder for temporary workspace
        --n_cpus: '1'
        --stop-on-first-crash: ""   # argument without value
        --fs-license-file: "$FREESURFER_LICENSE" # this is a placeholder.
        --skip-bids-validation: Null  # Null or NULL is also a placeholder for argument without value
        --output-spaces: MNI152NLin6Asym:res-2
        --force-bbr: ""
        --cifti-output: 91k
        -v: '-v'   # this is for double `-v`

This section will be turned into commands (including a Singularity run command) as below::

    export SINGULARITYENV_TEMPLATEFLOW_HOME=/TEMPLATEFLOW_HOME
    mkdir -p ${PWD}/.git/tmp/wkdir
    singularity run --cleanenv -B ${PWD},/test/templateflow_home:/TEMPLATEFLOW_HOME \
            containers/.datalad/environments/fmriprep-20-2-3/image \
            inputs/data/BIDS \
            outputs \
            participant \
            -w ${PWD}/.git/tmp/wkdir \
            --n_cpus 1 \
            --stop-on-first-crash \
            --fs-license-file code/license.txt \
            --skip-bids-validation \
            --output-spaces MNI152NLin6Asym:res-2 \
            --force-bbr \
            --cifti-output 91k \
            -v -v \
            --bids-filter-file "${filterfile}" \
            --participant-label "${subid}"

TODO: update ^^ after fixing FreeSurfer license copying + templateflow!


Basics - Manual of writing section ``babs_singularity_run``
------------------------------------------------------------

* What arguments should I provide in this section? All arguments for running the BIDS App?

    * No, not all arguments. Usually you only need to provide named arguments
      (i.e., those with flags starting with ``-`` or ``--``),
      but not positional arguments.
    * :octicon:`alert-fill` :bdg-warning:`warning` Exception for named arguments:
      Make sure you do NOT include these named arguments, as they've already been handled by BABS:

        * ``--participant-label``
        * ``--bids-filter-file``

            * See below :ref:`advanced_manual_singularity_run` --> bullet point _____
              for explanations.

    * :octicon:`alert-fill` :bdg-warning:`warning` Exception for positional arguments: if you have more than one input datasets,
      you must use ``$INPUT_PATH`` to specify which dataset to use for the positional argument input BIDS dataset.
      See :ref:`advanced_manual_singularity_run` --> bullet point "When more than one input dataset" for more.

* What's the format I should follow when providing an argument?
    
    * Say, you want to specify ``--my_argument its_value``, simply write as one of following format:
    * ``--my_argument: 'its_value'``    (value in single quotation marks)
    * ``--my_argument: "its_value"``    (value in double quotation marks)
    * ``--my_argument: its_value``    (value without quotation marks; avoid using this format for values of numbers)

* Can I mix arguments with flags that begins with double dashes (``--``) and those with single dash (``-``)?

    * Yes you can!

* How about arguments without values (e.g., ``--force-bbr`` in above example of fMRIPrep)?

    * There are several ways to specify arguments without values; just choose one of formats as follows:
    * ``my_key: ""``    (empty value string)
    * ``my_key: Null``    (``Null`` is a placeholder recognized by BABS)
    * ``my_key: NULL``    (``NULL`` is a placeholder recognized by BABS)
    * And then replace ``my_key`` with your keys, e.g., ``--force-bbr``. Do not forget the dashes (``-`` or ``--``) if needed!

* Can I have repeated arguments?

    * Yes you can. However you need to follow a specific format.
    * This is because each YAML section will be read as a dictionary by BABS, so each *key* before ``:``
      cannot be repeated, e.g., repeated key of ``-v`` in more than one line is not allowed. 
    * If you need to specify repeated arguments, e.g., ``-v -v``,
      please specify it as ``-v : '-v'`` as in the example above;
    * For triple ``-v``, please specify as ``-v: '-v -v'``

* Can I see the ``singularity run`` command that BABS generated?

    * Yes you can! When running ``babs-init`` it will print out ``singularity run`` command for you to check. 


.. _advanced_manual_singularity_run:

Advanced - Manual of writing section ``babs_singularity_run``
-----------------------------------------------------------------

* How to specify a number as a value?

    * If you hope to make sure the number format will be exactly passed into ``singularity run``,
      it will be a good idea to quote it, e.g. in QSIPrep::

        --output-resolution: "2.0"
    
    * This is especially encouraged when there are only numbers in the value (without letters).

* How to specify working directory (e.g., ``-w`` in fMRIPrep)?

    * You can use ``"$BABS_TMPDIR"``. It is a value placeholder recognized by BABS for temporary working directory.
      Example would be: ``-w: "$BABS_TMPDIR"``.
      By default BABS will automatically create a working directory.

* How to provide FreeSurfer license (e.g., for ``--fs-license-file``)?

    * You can use ``"$FREESURFER_LICENSE"``. It is a value placeholder recognized by BABS for FreeSurfer license,
      e.g., ``--fs-license-file: "$FREESURFER_LICENSE"``. BABS will use the license from ``$FREESURFER_HOME``.
    * TODO: update ^^ after changing the strategy of providing freesurfer license!

* Can I use a job environment variable, e.g., number of CPUs?

    * Yes you can! For number of CPUs (e.g., ``--n_cpus`` in QSIPrep), for *SGE* clusters,
      you can use environment variable ``$NSLOTS``, and you can specify it as::

        --n_cpus: "$NSLOTS"
      
      as long as you also set ``number_of_cpus`` in **cluster_resources** section (see below).
    
    * :octicon:`alert-fill` :bdg-warning:`warning` However *Slurm* clusters probably have different environment variable name
      for this - please check out its manual!

.. developer's note: for Slurm it might be ``$SLURM_NTASKS`` (below ref), however did not find for MSI cluster..
.. ref: https://docs.mpcdf.mpg.de/doc/computing/clusters/aux/migration-from-sge-to-slurm

* When **more than one** input BIDS dataset: You need to specify which dataset goes to the positional argument 
  ``input_dataset`` in the BIDS App, which dataset goes to another named argument.

  * Use ``$INPUT_PATH`` to specify for the positional argument ``input_dataset`` in the BIDS App:
    
    * ``$INPUT_PATH`` is a key placeholder recognized by BABS
    * We recommend using ``$INPUT_PATH`` as the first key in this section **babs_singularity_run**, 
      i.e., before other arguments.

  * How to write the path to the input dataset? Here we use `example configuration YAML file of
    fMRIPrep with FreeSurfer results ingressed <https://github.com/PennLINC/babs/blob/main/notebooks/example_container_fmriprep_ingressed_fs.yaml>`_:

    * For the positional argument ``input_dataset``, sawy we want to use (unzipped) raw BIDS dataset called ``BIDS``;

        * Then we can specify: ``$INPUT_PATH: inputs/data/BIDS`` 
          which means that we want to use input BIDS dataset named ``BIDS`` for this positional argument ``input_dataset``.
        * Note that you need to add ``inputs/data/`` before the dataset's name, and what you'll use for
          ``<name>`` when calling ``babs-init --input <name> /path/to/BIDS`` should also be ``BIDS``.

    * For the named argument ``--fs-subjects-dir``, sawy we want to use *zipped* BIDS derivates of FreeSurfer called ``freesurfer``;

        * Then we can specify: ``--fs-subjects-dir: inputs/data/freesurfer/freesurfer``.
        * As mentioned above, ``freesurfer`` should also show up as a dataset's name (``<name>``)
          in ``babs-init --input <name> /path/to/freesurfer_dataset``
        * Note that, as this is a zipped dataset, you need to repeat ``freesurfer`` twice.

            * .. dropdown:: Why we need to repeat it twice?

                  This is because, ``freesurfer`` dataset will locate at ``inputs/data/freesurfer``, and after unzipping
                  a subject's (or a session's) freesurfer zipped folder, there will be
                  another folder called ``freesurfer``, so the path to the unzipped folder will be ``inputs/data/freesurfer/freesurfer``.

    * :octicon:`alert-fill` :bdg-warning:`warning` Please check :ref:`how-to-define-name-of-input-dataset` for
      restrictions in naming each dataset when calling ``babs-init``!
  
.. Note to developers: It's probably not a good idea to use information from ``babs_proj_config.yaml``,
   e.g., ``path_data_rel`` to determine the path, as for zipped folder it will be ``inputs/data/freesurfer``,
   instead of ``inputs/data/freesurfer/freesurfer`` that user needs to specify here.

* ``--bids-filter-file``: When will BABS automatically add it?
    
    * When BIDS App is fMRIPrep or QSIPrep, and input BIDS dataset(s) are multi-session data.
    * How BABS determine it's fMRIPrep or QSIPrep?

        * Based on ``container_name`` provided when calling ``babs-init``:
          If ``container_name`` contains ``fMRIPrep`` or ``QSIPrep`` (not case sensitive).
    * When BABS adds ``--bids-filter-file`` here for Singularity run,
      BABS will also automatically generate a filter file (JSON format) when running each session's data,
      so that only data from a specific session will be included for analysis.   

* Will BABS handle `Templateflow <https://www.templateflow.org/>`_ environment variable? 

    * Yes, BABS assumes all BIDS Apps use Templateflow and will always handle its environment variable if
      environment variable ``$TEMPLATEFLOW_HOME`` exists.
    * For BIDS Apps that truly depend on Templateflow (e.g., fMRIPrep, QSIPrep, XCP-D),
      please make sure you have Templateflow installed and export environment variable
      ``$TEMPLATEFLOW_HOME``.
    * Example generated commands by BABS
      as below::

        export SINGULARITYENV_TEMPLATEFLOW_HOME=/TEMPLATEFLOW_HOME
        ...
        singularity run --cleanenv -B ${PWD},/path/to/templateflow_home:/TEMPLATEFLOW_HOME \
        ...
      
      where ``/path/to/templateflow_home`` is the value of environment variable ``$TEMPLATEFLOW_HOME``

    * TODO: update ^^ after fixing the bug in exporting templateflow!

.. Go thru all YAML files for any missing notes: done 4/4/2023
.. toybidsapp: done
.. toybidsapp, zipped input: done
.. qsiprep: done
.. fmriprep: done
.. fmriprep with fs ingressed: done
.. `notebooks/inDev_*.yaml` in `babs_tests` repo: done


Section ``babs_zip_foldername``
================================

This section defines the output folder name(s) that get saved and zipped.
This also includes the version of the BIDS App you use.

Example section **babs_zip_foldername** for ``fMRIPrep``::

    babs_zip_foldername:
        fmriprep: "20-2-3"
        freesurfer: "20-2-3"

As you can see in this example, we expect that fMRIPrep will generate two folders,
one is called ``fmriprep``, the other is called ``freesurfer``.
If there is only one folder that you hope BABS to save and zip, simply provide only one.

In addition to the folder name(s), please also add the version of the BIDS App as the value:

* The version number should be consistent as that in *image NAME* when :ref:`create-a-container-datalad-dataset`.
  For this example, you probably use ``fmriprep-20-2-3`` for *image NAME*.
* When calling ``babs-init``, argument ``--container-name`` should use the same version too,
  i.e., ``--container-name fmriprep-20-2-3`` for current example.
* Please use dashes ``-`` instead of dots ``.`` when indicating the version number,
  e.g., ``20-2-3`` instead of ``20.2.3``.
* If there are multiple folders to zip, we recommend using the consistent version string across these folders.
  In this example case, the ``fMRIPrep`` BIDS App's version is ``20.2.3``, so we specify ``20-2-3`` for
  both folders ``fmriprep`` and ``freesurfer``,
  although the version of ``FreeSurfer`` included in this ``fMRIPrep`` may not be ``20.2.3``.


Section ``cluster_resources``
=================================
This section defines how much cluster resources each participant's job will use.

Example section **cluster_resources** for ``QSIPrep``::

    cluster_resources:
        interpreting_shell: /bin/bash
        hard_memory_limit: 32G
        temporary_disk_space: 200G
        number_of_cpus: "6" 

These will be turned into options in the preambles of ``participant_job.sh`` on an SGE cluster
(this script could be found at: ``/path/to/my_BABS_project/analysis/code``) shown as below::

    #!/bin/bash
    #$ -S /bin/bash
    #$ -l h_vmem=32G
    #$ -l tmpfree=200G
    #$ -pe threaded 6

For example, a job requires no more than 32 GB of memory,
i.e., on SGE clusters, ``-l h_vmem=32G``.
You may simply specify: ``hard_memory_limit: 32G``.

The table below lists all the named cluster resources requests that BABS supports.
You may not need all of them.
BABS will replace ``$VALUE`` with the value you provide.
The second row in each cell, which is also in (), is an example.

.. .. list-table:: Cluster resources requests that BABS supports
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
* For values with numbers only (without letters), it's recommended to quote the value,
  e.g., ``number_of_cpus: "6"``

.. checked all example YAML file i have for this section ``cluster_resources``. CZ 4/4/2023.

Section ``script_preamble``
=============================
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
    You may also need to add command ``module_load`` for some modules (like FreeSurfer) too.

Notes:

* Remember to add ``|`` after ``script_preamble:``;
* You can also add more necessary commands by adding new lines;
* :octicon:`alert-fill` :bdg-warning:`warning` Please do NOT quote the commands in this section!

.. _required_files:

Section ``required_files``
============================
This section is optional.

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

    * For example, to use ``fMRIPrep`` with FreeSurfer results ingressed, you want to call command below,
      and you hope to filter subjects based on files in raw BIDS data (here named ``BIDS``),
      then you should specify ``$INPUT_DATASET_#1``.

      .. code-block::

            babs-init \
                ...
                --input BIDS /path/to/BIDS \
                --input freesurfer /path/to/freesurfer_outputs \
                ...

* We recommend adding ``*`` after ``.nii`` as there might only be unzipped NIfTI file (e.g., ``.nii`` instead of ``.nii.gz``) in the input dataset;
* :octicon:`alert-fill` :bdg-warning:`warning` Currently we only support checking required files
  in unzipped input dataset (e.g., raw BIDS dataset).


.. _keywords_alert:

Section ``keywords_alert``
==============================
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
            - "xxxxx"    # change this to any keywords to be found in `*.e*` file; if there is no keywords for `*.e*` file, delete line `e_file:` and this line


Usually there are two log files that are useful for debugging purpose, ``*.o*`` and ``*.e*``,
for example, ``<jobname>.o<jobid>`` and ``<jobname>.e<jobid>``.
You can define alerting keywords in either or both files, i.e., by filling out ``o_file`` section
(for ``*.o*`` file) and/or ``e_file`` section (for ``*.e*`` file).

Detection of the keyword is performed in the order provided by the user.
If ``o_file`` is former (e.g., in example above), then detection of it will be performed earlier;
if a keyword is former, then that will be checked earlier.
BABS also follows "detect and break" rule, i.e., for each job:

* If any keyword is detected, the detected keyword will be thrown into the ``job_status.csv``,
  and BABS won't detect any further keyword down in the list in **keywords_alert**.
* If a keyword has been detected in the first file (``o_file`` for above example),
  then won't detect any keyword in the other log file (``e_file`` for above example).

.. warning::
    Detecting the keywords in the log files by BABS is case-sensitive! So please make sure the cases of keywords are in the way you hope.
