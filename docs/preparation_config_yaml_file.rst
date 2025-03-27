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
=================================================

Sections in the configuration YAML file
-----------------------------------------

* **cluster_resources**: how much cluster resources are needed to run this BIDS App?
* **script_preamble**: the preamble in the script to run a participant's job;
* **job_compute_space**: where to run the jobs?
* **singularity_args**: the arguments for ``singularity run``;
* **bids_app_args**: the arguments for the BIDS App;
* **imported_files**: the files to be copied into the datalad dataset;
* **all_results_in_one_zip**: whether to zip all results in one zip file;
* **zip_foldernames**: the results foldername(s) to be zipped;
* **required_files**: to only keep subjects (sessions) that have this list of required files in input dataset(s);
* **alert_log_messages**: alert messages in the log files that may be helpful for debugging errors in failed jobs;

Among these sections, these sections are optional:

* **bids_app_args**

  * Only if you are sure that besides arguments handled by BABS, you don't need any other argument,
    you may exclude this section from the YAML file.
  * You must include this section if there are more one input dataset.

* **required_files**
* **alert_log_messages**
* **imported_files**


Example/prepopulated configuration YAML files
---------------------------------------------

Example/prepopulated configuration YAML files can be found in ``notebooks/`` folder of BABS GitHub repository.
See `here <https://github.com/PennLINC/babs/blob/main/notebooks/README.md>`_ for a full list and descriptions.

These include example YAML files for:

* Different BIDS Apps: fMRIPrep, QSIPrep, XCP-D, as well as toy BIDS App, etc.
* Cases with different input BIDS datasets, including one raw BIDS dataset, one zipped BIDS derivates dataset,
  and the combination of these two.

These YAML files can be customized for your cluster.

.. developer's note: ^^ using main branch on github.


Terminology when describing a YAML file:
----------------------------------------
Below is an example "section" in a YAML file::

    section_name:
        key: value

In a section, the string before ``:`` is called ``key``, the string after ``:`` is called ``value``.

Below are the details for each section in this configuration YAML file.

Section ``singularity_args``
============================

Singularity/Apptainer are configured differently for different clusters.
The arguments here are specified as a list and are added directly to the ``singularity run`` command.

Example section **singularity_args**
------------------------------------

For maximum isolation, you can use ``--containall`` and ``--writable-tmpfs``::

..  code-block:: yaml

    singularity_args:
        - --containall
        - --writable-tmpfs

But this doesn't always work for all clusters.
Add/remove arguments as needed.
If you need to use a GPU, this would be where to add an ``--nv`` flag.


Section ``imported_files``
==========================

This section is optional. If you need to copy files into your datalad dataset, you can specify them here.
These will be copied into the datalad dataset from your local machine. This is particularly useful for
specifying a custom ``recon_spec.yaml`` file for ``qsirecon``.

Example section **imported_files**
----------------------------------

..  code-block:: yaml

    imported_files:
        - original_path: "/path/to/recon_spec.yaml"
          analysis_path: "code/recon_spec.yaml"

The ``analysis_path`` is the path to the file in your datalad dataset.
In this example, it would guarantee that when running ``qsirecon``,
the ``recon_spec.yaml`` file will be available at ``"${PWD}/code/recon_spec.yaml``.
This means I can use ``"${PWD}"/code/recon_spec.yaml`` in the ``bids_app_args`` section.
It also means that the ``recon_spec.yaml`` file will be tracked by datalad.

**Important**: If you are importing a large file this mechanism will not work.


Section ``bids_app_args``
=========================
Currently, BABS does not support using configurations of running a BIDS App
that are defined in ``datalad containers-add --call-fmt``.
Instead, users are expected to define these in this section, **bids_app_args**.

Example **bids_app_args**
-------------------------

Below is example section **bids_app_args** for ``fMRIPrep``:

..  code-block:: yaml

    bids_app_args:
        -w: "$BABS_TMPDIR"   # this is a placeholder for temporary workspace
        --n_cpus: '1'
        --stop-on-first-crash: ""   # argument without value
        --fs-license-file: "/path/to/freesurfer/license.txt"
        --skip-bids-validation: Null  # Null or NULL is also a placeholder for argument without value
        --output-spaces: MNI152NLin6Asym:res-2
        --force-bbr: ""
        --cifti-output: 91k
        -v: '-v'   # this is for double `-v`

This section will be turned into commands (here also showing the Singularity run command) as below:

    ..  code-block:: bash
        :linenos:

        mkdir -p ${PWD}/.git/tmp/wkdir
        singularity run --cleanenv \
            -B ${PWD} \
            -B /test/templateflow_home:/SGLR/TEMPLATEFLOW_HOME \
            -B /path/to/freesurfer/license.txt:/SGLR/FREESURFER_HOME/license.txt \
            --env TEMPLATEFLOW_HOME=/SGLR/TEMPLATEFLOW_HOME \
            containers/.datalad/environments/fmriprep-20-2-3/image \
                inputs/data/BIDS \
                outputs \
                participant \
                -w ${PWD}/.git/tmp/wkdir \
                --n_cpus 1 \
                --stop-on-first-crash \
                --fs-license-file /SGLR/FREESURFER_HOME/license.txt \
                --skip-bids-validation \
                --output-spaces MNI152NLin6Asym:res-2 \
                --force-bbr \
                --cifti-output 91k \
                -v -v \
                --bids-filter-file "${filterfile}" \
                --participant-label "${subid}"


Basics - Manual of writing section ``bids_app_args``
----------------------------------------------------

* What arguments should I provide in this section? All arguments for running the BIDS App?

    * No, not all arguments. Usually you only need to provide named arguments
      (i.e., those with flags starting with ``-`` or ``--``),
      but not positional arguments.
    * :octicon:`alert-fill` :bdg-warning:`warning` Exception for named arguments:
      Make sure you do NOT include these named arguments, as they've already been handled by BABS:

        * ``--participant-label``
        * ``--bids-filter-file``

            * See below :ref:`advanced_manual_singularity_run` --> bullet point regarding
              ``--bids-filter-file`` for explanations.
            * See :doc:`babs-init` for examples of ``--list_sub_file``/``--list-sub-file`` to filter subjects and sessions.

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

    * Yes you can! When running ``babs init`` it will print out ``singularity run`` command for you to check.


.. _advanced_manual_singularity_run:

Advanced - Manual of writing section ``bids_app_args``
------------------------------------------------------

* How to specify a number as a value?

    * If you hope to make sure the number format will be exactly passed into ``singularity run``,
      it will be a good idea to quote it, e.g. in QSIPrep::

        --output-resolution: "2.0"

    * This is especially encouraged when there are only numbers in the value (without letters).
      Quoting will make sure that when BABS generates scripts, it will keep the string format of the value
      and pass the value exactly as it is,
      without the risk of data type changes (e.g., integers are changed to float numbers; and vice versa).

* How to specify "path where intermediate results should be stored" (e.g., ``-w`` in fMRIPrep or QSIPrep)?

    * You can use ``"$BABS_TMPDIR"``. It is a value placeholder recognized by BABS for temporary directory
      for holding intermediate results.
      Example would be::

        -w: "$BABS_TMPDIR"

      By default BABS will automatically create such temporary directory if you use ``$BABS_TMPDIR``.

.. developer's note: it will be changed ``-w ${PWD}/.git/tmp/wkdir`` - see the example above.

* How to provide FreeSurfer license for argument ``--fs-license-file`` of BIDS App?

    * You should provide it as you normally do when running the BIDS App:
      just provide the path to your FreeSurfer license on the cluster.
      For example::

        --fs-license-file: "/path/to/freesurfer/license.txt"

    * When there is argument ``--fs-license-file`` in ``bids_app_args`` section,
      BABS will bind this provided license file path to container in ``singularity run`` command, so that
      the BIDS App container can directly use that file (which is outside the container, on "host machine").
    * Example generated ``singularity run`` by ``babs init``::

        singualrity run ... \
            -B /path/to/freesurfer/license.txt:/SGLR/FREESURFER_HOME/license.txt \
            ...
            --fs-license-file /SGLR/FREESURFER_HOME/license.txt \
            ...

      After binding this license file, the value for ``--fs-license-file`` is changed to
      the path *within* the container by BABS.


* Can I use a job environment variable, e.g., number of CPUs?

    * Yes you can! For number of CPUs (e.g., ``--n_cpus`` in QSIPrep),
      if you also use ``number_of_cpus`` in **cluster_resources** section (see below),
      then you can use environment variable for this Singularity run argument.
    * For *SLURM* clusters, you can use environment variable ``$NSLOTS``, and you can specify it as::

        --n_cpus: "$SLURM_CPUS_PER_TASK"

    * Not sure how many CPUs or other resources you need?
      You can run ``babs submit --count N`` with the first N (10-20) subjects and then use
      ``reportseff`` (`library here <https://github.com/troycomi/reportseff>`_) or ``seff_array`` to check the resource
      usage. You can then edit the resources in the ``<bids_app>_zip.sh`` and ``participant_job.sh`` in
      the ``analysis/code`` folder. Make sure to run ``babs sync-code`` after editing the files before
      re-submitting with ``babs submit --all``.

.. developer's note: for SLURM: ref: https://login.scg.stanford.edu/faqs/cores/
..  other ref: https://docs.mpcdf.mpg.de/doc/computing/clusters/aux/migration-from-sge-to-slurm

* When **more than one** input BIDS dataset: You need to specify which dataset goes to the positional argument
  ``input_dataset`` in the BIDS App, which dataset goes to another named argument.

  * Use ``$INPUT_PATH`` to specify for the positional argument ``input_dataset`` in the BIDS App:

    * ``$INPUT_PATH`` is a key placeholder recognized by BABS
    * We recommend using ``$INPUT_PATH`` as the first key in this section **bids_app_args**,
      i.e., before other arguments.

  * How do you write the path to the input dataset? Here we use an example configuration YAML file of
    fMRIPrep with existing FreeSurfer results ingressed - you can find this example YAML file
    `here <https://github.com/PennLINC/babs/blob/main/notebooks/README.md>`_.

    * For the positional argument ``input_dataset``, say we want to use (unzipped) raw BIDS dataset called ``BIDS``;

        * Then we can specify: ``$INPUT_PATH: inputs/data/BIDS``
          which means that we want to use input BIDS dataset named ``BIDS`` for this positional argument ``input_dataset``.
        * Note that you need to add ``inputs/data/`` before the dataset's name, and what you'll use for
          ``<name>`` when calling ``babs init --datasets <name>=/path/to/BIDS`` should also be ``BIDS``.

    * For the named argument ``--fs-subjects-dir``, say we want to use *zipped* BIDS derivates of FreeSurfer called ``freesurfer``;

        * For fMRIPrep version < 21.0, then we can specify: ``--fs-subjects-dir: inputs/data/freesurfer/freesurfer``.
        * As mentioned above, ``freesurfer`` should also show up as a dataset's name (``<name>``)
          in ``babs init --datasets <name>=/path/to/freesurfer_dataset``
        * Note that, as this is a zipped dataset, you need to repeat ``freesurfer`` twice.

            * .. dropdown:: Why we need to repeat it twice?

                  This is because, ``freesurfer`` dataset will locate at ``inputs/data/freesurfer``, and after unzipping
                  a subject's (or a session's) freesurfer zipped folder, there will be
                  another folder called ``freesurfer``, so the path to the unzipped folder will be ``inputs/data/freesurfer/freesurfer``.

        * For fMRIPrep version >= 21.0, please refer to example YAML files for examples.

    * :octicon:`alert-fill` :bdg-warning:`warning` Please check :ref:`how-to-define-name-of-input-dataset` for
      restrictions in naming each dataset when calling ``babs init``!

.. Note to developers: It's probably not a good idea to use information from ``babs_proj_config.yaml``,
   e.g., ``path_data_rel`` to determine the path, as for zipped folder it will be ``inputs/data/freesurfer``,
   instead of ``inputs/data/freesurfer/freesurfer`` that user needs to specify here.

* ``--bids-filter-file``: When will BABS automatically add it?

    * When BIDS App is fMRIPrep, QSIPrep or ASLPrep, and input BIDS dataset(s) are multi-session data.
    * How BABS determine it's fMRIPrep, QSIPrep or ASLPrep?

        * Based on ``container_name`` provided when calling ``babs init``:
          If ``container_name`` contains ``fMRIPrep``, ``QSIPrep`` or ``ASLPrep`` (not case sensitive).
    * When BABS adds ``--bids-filter-file`` here for Singularity run,
      BABS will also automatically generate a filter file (JSON format) when running each session's data,
      so that only data from a specific session will be included for analysis.

* Will BABS handle `TemplateFlow <https://www.templateflow.org/>`_ environment variable?

    * Yes, BABS assumes all BIDS Apps use TemplateFlow, and will handle its environment variable ``$TEMPLATEFLOW_HOME``
      *if* this environmental variable exists in the terminal environment where ``babs init`` will be run.
    * For BIDS Apps that truly depend on TemplateFlow (e.g., fMRIPrep, QSIPrep, XCP-D),
      before you run ``babs init``, please make sure you:

        #. Find a directory for holding TemplateFlow's templates.

            * If no (or not all necessary) TemplateFlow's templates has been downloaded
              in this directory, then this directory must be writable, so that when running the BIDS App,
              necessary templates can be downloaded in this directory;
            * if all necessary templates have been downloaded in this directory,
              then this directory should at least be readable.
        #. Export environment variable
           ``$TEMPLATEFLOW_HOME`` to set its value as the path to this directory you prepared.
           This step should be done in the terminal environment where ``babs init`` will be used.

    * If ``babs init`` detects environment variable ``$TEMPLATEFLOW_HOME``, when generating ``singularity run`` command,
      ``babs init`` will:

        #. Bind the path provided in this environment variable to the container;
        #. Set the corresponding environment variable *within* the container.
    * For example,
      BABS will add these in command ``singularity run`` of the container::

            singularity run ... \
                ... \
                -B /path/to/templateflow_home:/SGLR/TEMPLATEFLOW_HOME \
                --env TEMPLATEFLOW_HOME=/SGLR/TEMPLATEFLOW_HOME \
                ...

      where ``/path/to/templateflow_home`` is the value of environment variable ``$TEMPLATEFLOW_HOME``.

* How to specify multiple spaces in argument ``--output-spaces`` (e.g., in fMRIPrep)?

    * Just to follow the guidelines from fMRIPrep, using space to separate different output spaces.
    * For
      example::

        --output-spaces: "MNI152NLin6Asym:res-2 MNI152NLin2009cAsym"

      Here, ``MNI152NLin6Asym:res-2`` and ``MNI152NLin2009cAsym`` are two example spaces.

    * We recommend quoting this value if there are multiple spaces (like this example).
      This is because there is space in the value of this argument.
      Quoting makes sure that BABS will take
      the entire value string as a whole and pass it into ``singularity run``.

.. developer's note:
..  also tested without quoting when there is space; generated ``singularity run`` is also good.

.. Go thru all YAML files for any missing notes: done 4/4/2023
.. toybidsapp: done
.. toybidsapp, zipped input: done
.. qsiprep: done
.. fmriprep: done
.. fmriprep with fs ingressed: done
.. `notebooks/inDev_*.yaml` in `babs_tests` repo: done


Section ``zip_foldernames``
===========================

This section defines the name(s) of the expected output folder(s).
BABS will zip those folder(s) into separate zip file(s).

Here we provide two examples. :ref:`Example #1 <example_zip_foldernames_for_fmriprep_legacy_output_layout>`
is for regular use cases,
where the BIDS App will generate one or several folders that wrap all derivative files.
Example use cases are ``fMRIPrep`` with legacy output layout, as well as ``QSIPrep`` and ``XCP-D``.

If the BIDS App won't generate one or several folders that wrap all derivative files,
users should ask BABS to create a folder as an extra layer by specifying ``all_results_in_one_zip: true``.
We explain how to do so in :ref:`Example #2 <example_zip_foldernames_for_fmriprep_BIDS_output_layout>`.
An example use case is ``fMRIPrep`` with BIDS output layout.


.. _example_zip_foldernames_for_fmriprep_legacy_output_layout:

Example #1: for ``fMRIPrep`` *legacy* output layout
---------------------------------------------------

Here we use ``fMRIPrep`` (*legacy* output layout) as an example to show you
how to write this ``zip_foldernames`` section. For this case, all derivative files
are wrapped in folders generated by fMRIPrep. Similar use cases are ``QSIPrep``
(e.g., generating a folder called ``qsiprep``), and ``XCP-D`` (generating a folder called ``xcp_d``).

Older versions of ``fMRIPrep`` (version < 21.0) generate
`legacy output layout <https://fmriprep.org/en/stable/outputs.html#legacy-layout>`_
which looks like below::

    <output_dir>/
        fmriprep/
        freesurfer/

In this case, ``fMRIPrep`` generates two folders, ``fmriprep`` and ``freesurfer``,
which include all derivatives. Therefore, we can directly tell BABS the expected foldernames,
without asking BABS to create them.

Example section **zip_foldernames** for ``fMRIPrep`` *legacy* output layout:

..  code-block:: yaml
    :linenos:

    zip_foldernames:
        fmriprep: "20-2-3"
        freesurfer: "20-2-3"

Here, we write the expected folders in line #2 and #3.
For other BIDS Apps, if there is only one expected output folder, simply provide only one.

In addition to the folder name(s), please also add the version of the BIDS App as the value.

Above example means that:

* BABS will zip output folder ``fmriprep`` into zip file ``${sub-id}_${ses-id}_fmriprep-20-2-3.zip``;
* BABS will zip output folder ``freesurfer`` into zip file ``${sub-id}_${ses-id}_freesurfer-20-2-3.zip``;

Here, ``${sub-id}`` is the subject ID (e.g., ``sub-01``),
and ``${ses-id}`` is the session ID (e.g., ``ses-A``).
In other words, each subject (or session) will have their specific zip file(s).


.. _example_zip_foldernames_for_fmriprep_BIDS_output_layout:

Example #2: for ``fMRIPrep`` *BIDS* output layout: asking BABS to create additional output folder
-------------------------------------------------------------------------------------------------

Recent ``fMRIPrep`` (version >= 21.0) uses
`BIDS output layout <https://fmriprep.org/en/stable/outputs.html#layout>`_
which looks like below::

    <output_dir>/
        logs/
        sub-<label>/
        sub-<label>.html
        dataset_description.json
        .bidsignore

As you can see, there are files like ``sub-<label>.html`` and ``dataset_description.json``
which do not belong to any folders (except ``<output_dir>``,
which is a standard BIDS output directory).
However, BABS expects there are
one or more folders in ``<output_dir>`` that are generated by the BIDS App,
and wrap all derivative files,
so that BABS can directly zip these "wrapper" folders.
Therefore, users need to ask BABS to create an additional folder to wrap all the derivatives.

Example section **zip_foldernames** for ``fMRIPrep`` *BIDS* output layout:

..  code-block:: yaml
    :linenos:

    all_results_in_one_zip: true
    zip_foldernames:
        fmriprep: "23-1-3"

Line #1 ``all_results_in_one_zip: true`` asks BABS to create an additional folder,
i.e., ``fmriprep`` specified in line #3, to wrap all derivatives.
In this way, the output will look like below::

    <output_dir>/fmriprep/
        logs/
        sub-<label>/
        sub-<label>.html
        dataset_description.json
        .bidsignore

Note that all derivatives will locate in the "wrapper" folder called ``fmriprep``.
BABS will zip this folder into zip file ``${sub-id}_${ses-id}_fmriprep-23-1-3.zip``.

In addition, when using ``all_results_in_one_zip: true``,
you must only provide one foldername in ``zip_foldernames``.

Other detailed instructions
---------------------------

* The version number should be consistent as that in *image NAME* when :ref:`create-a-container-datalad-dataset`.

    * In example #1, you probably use ``fmriprep-20-2-3`` for *image NAME*;
    * In example #2, you probably use ``fmriprep-23-1-3`` for *image NAME*.

* When calling ``babs init``, argument ``--container-name`` should use the same version too, i.e.,

    * ``--container-name fmriprep-20-2-3`` in example #1;
    * ``--container-name fmriprep-23-1-3`` in example #2;

* Please use dashes ``-`` instead of dots ``.`` when indicating the version number,
  e.g., ``20-2-3`` instead of ``20.2.3``.
* If there are multiple folders to zip, we recommend using the consistent version string across these folders.
  In example #1, the ``fMRIPrep`` BIDS App's version is ``20.2.3``, so we specify ``20-2-3`` for
  both folders ``fmriprep`` and ``freesurfer``,
  although the version of ``FreeSurfer`` included in this ``fMRIPrep`` may not be ``20.2.3``.


.. _cluster-resources:

Section ``cluster_resources``
=============================
This section defines the cluster resources each job will use,
and the interpreting shell for executing the job script.

Example section **cluster_resources**
-------------------------------------

Example section **cluster_resources** for ``QSIPrep``:

..  code-block:: yaml

    cluster_resources:
        interpreting_shell: /bin/bash
        hard_memory_limit: 32G
        temporary_disk_space: 200G
        number_of_cpus: "6"

These will be turned into options in the directives (at the beginning) of ``participant_job.sh`` shown as below.

For example, a job requires no more than 32 GB of memory,
i.e., on SGE clusters, ``-l h_vmem=32G``.
You may simply specify: ``hard_memory_limit: 32G``.

.. warning::
    Make sure you add ``interpreting_shell``!
    It is very important.
    For SGE, you might need: ``interpreting_shell: /bin/bash``;
    For SLURM, you might need: ``interpreting_shell: /bin/bash -l``.
    Check what it should be like in the manual of your cluster!


Named cluster resources readily available
------------------------------------------

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

.. developer's note: actually the width is not working here....
..  tried `||` and `| |` for each row's beginning but did not help...
.. table::
    :widths: 60 40 40

    +------------------------------------------+------------------------------------------+-------------------------------------------+
    | | Section ``cluster_resources`` in YAML  | | Generated directives for SGE clusters  | | Generated directives for SLURM clusters |
    | |         (example key-value)            | |           (example outcome)            | |           (example outcome)             |
    +==========================================+==========================================+===========================================+
    | | ``interpreting_shell: $VALUE``         | | ``#!$VALUE``                           | | ``#!$VALUE``                            |
    | | (``interpreting_shell: /bin/bash``)    | | (``#!/bin/bash``)                      | | (``#!/bin/bash``)                       |
    +------------------------------------------+------------------------------------------+-------------------------------------------+
    | | ``hard_memory_limit: $VALUE``          | | ``#$ -l h_vmem=$VALUE``                | | ``#SBATCH --mem=$VALUE``                |
    | | (``hard_memory_limit: 25G``)           | | (``#$ -l h_vmem=25G``)                 | | (``#SBATCH --mem=25G``)                 |
    +------------------------------------------+------------------------------------------+-------------------------------------------+
    | | ``soft_memory_limit: $VALUE``          | | ``#$ -l s_vmem=$VALUE``                | Not applicable.                           |
    | | (``soft_memory_limit: 23.5G``)         | | (``#$ -l s_vmem=23.5G``)               |                                           |
    +------------------------------------------+------------------------------------------+-------------------------------------------+
    | | ``temporary_disk_space: $VALUE``       | | ``#$ -l tmpfree=$VALUE``               | | ``#SBATCH --tmp=$VALUE``                |
    | | (``temporary_disk_space: 200G``)       | | (``#$ -l tmpfree=200G``)               | | (``#SBATCH --tmp=200G``)                |
    +------------------------------------------+------------------------------------------+-------------------------------------------+
    | | ``number_of_cpus: "$VALUE"``           | | ``#$ -pe threaded $VALUE``             | | ``#SBATCH --cpus-per-task=$VALUE``      |
    | | (``number_of_cpus: "6"``)              | | (``#$ -pe threaded 6``)                | | (``#SBATCH --cpus-per-task=6``)         |
    +------------------------------------------+------------------------------------------+-------------------------------------------+
    | | ``hard_runtime_limit: "$VALUE"``       | | ``#$ -l h_rt=$VALUE``                  | | ``#SBATCH --time=$VALUE``               |
    | | (``hard_runtime_limit: "24:00:00"``)   | | (``#$ -l h_rt=24:00:00``)              | | (``#SBATCH --time=24:00:00``)           |
    +------------------------------------------+------------------------------------------+-------------------------------------------+


Note the following:

* For values with numbers only (without letters), it's recommended to quote the value,
  e.g., ``number_of_cpus: "6"``. This is to make sure that when BABS generates scripts,
  it will keep the string format of the value and pass the value exactly as is,
  without the risk of data type changes (e.g., integers are changed to float numbers; and vice versa).


Customized cluster resource requests
--------------------------------------

If you cannot find the one you want in the above table, you can still add it by ``customized_text``.
Below is an example for **SGE** clusters::

    cluster_resources:
        <here goes keys defined in above table>: <$VALUE>
        customized_text: |
            #$ -abc this_is_an_example_customized_option_to_appear_in_preamble
            #$ -zzz there_can_be_multiple_lines_of_customized_option

Note that:

* Some clusters might not allow for specific settings (e.g. ``temporary_disk_space``).
  If you get an error that the setting is not allowed,
  simply remove the line that causes the issue.

* Remember to add ``|`` after ``customized_text:``. This is to make sure
  BABS can read in multiple lines under ``customized_text``.

* As customized texts will be directly copied to the script ``participant_job.sh`` (without translation),
  please remember to add any necessary prefix before the option:

    * ``#SBATCH`` for SLURM clusters

* For values with numbers only (without letters), it's recommended to quote the value,
  e.g., ``number_of_cpus: "6"``.
  This is to make sure that when BABS generates scripts, it will keep the string format of the value
  and pass the value exactly as it is,
  without the risk of data type changes (e.g., integers are changed to float numbers; and vice versa).

.. developer's note: With this sign ``|``, the lines between ``customized_text`` and next section
      will all be read into BABS if the lines are aligned with ``customized_text``, so be careful when you add comments there.
.. developer's note: If there is only one line, you could also write in this way (not suggested):
..  customized_text: "#$ -R y"

.. checked all example YAML file i have for this section ``cluster_resources``. CZ 4/4/2023.

.. _script-preamble:

Section ``script_preamble``
===========================
This part also goes to the preamble of the script ``participant_job.sh``
(located at: ``/path/to/my_BABS_project/analysis/code``). Different from **cluster_resources**
that provides options for cluster resources requests, this section **script_preamble** is for necessary
bash commands that are required by job running. An example would be to activate the conda environment;
however, different clusters may require different commands to do so. Therefore, BABS asks the user to
provide it.

Example section **script_preamble** for a specific cluster:

..  code-block:: yaml

    script_preamble: |
        source "${CONDA_PREFIX}"/bin/activate babs    # Penn Med CUBIC cluster; replace 'babs' with your conda env name
        echo "I am running BABS."   # this is an example command to show how to add another line; not necessary to include.

This will appear as below in the ``participant_job.sh``::

    # Script preambles:
    source "${CONDA_PREFIX}"/bin/activate babs     # Penn Med CUBIC cluster; replace 'babs' with your conda env name
    echo "I am running BABS."   # this is an example command to show how to add another line; not necessary to include.

.. warning::
    Above command may not apply to your cluster; check how to activate conda environment on your cluster and replace above command.
    You may also need to add command ``module_load`` for some modules (like FreeSurfer) too.

.. warning::
    Different from other sections, please do **NOT** quote the commands in this section!

Notes:

* Remember to add ``|`` after ``script_preamble:``;
* You can also add more necessary commands by adding new lines.
* You can delete the 2nd line ``echo "I am running BABS."`` as that's just a demonstration of
  how to add another line in the preamble.
* As you can see, the comments after the commands also show up in the generated script preambles.
  This is normal and fine.

.. _job-compute-space:

Section ``job_compute_space``
=============================
The jobs will be computed in ephemeral (temporary) compute space.
Specifically, this space could be temporary space on a cluster node, or some scratch space.
It's totally fine (and recommended!) if the data or the directory in the space will be removed
after the job finishes - all results will be pushed back to (saved in) the output RIA (i.e., a permanent storage) where your BABS project locates.

.. dropdown:: Why recommending space where data/directory will be automatically removed after the job finishes?

    If a job fails, and if the data or the directory won't be automatically removed,
    data will be accumulated and takes up space.

    We recommend using space that automatically cleans after the job finishes especially for large-scale dataset
    which has a large amount of jobs to do.

Example section **job_compute_space**:

..  code-block:: yaml

    job_compute_space: "/tmp"

Here, ``"/tmp"`` is NOT a good choice, check your cluster's documentation for
the correct path.
This environment variable might not be recognized by your cluster,
but you can use the path that's specific to yours::

    job_compute_space: "/path/to/some_temporary_compute_space"

You can also use an environment variable recognized by your clusters.

.. developer's note: for Penn Medicine CUBIC cluster, you might also use ``comp_space``.
.. However if jobs failed, the results data won't be automatically cleaned from this space,
.. causing accumulations of data that takes up space. Only use this space when you're debugging BABS.
.. job_compute_space: "/cbica/comp_space/$(basename $HOME)"   # PennMed CUBIC cluster compute space

.. note::

    Best to quote (``""``) the string of the path to the space as shown in the examples above.

Notes:

* What's the different between this section and the argument "path where intermediate results should be stored"
  in some BIDS Apps (e.g., ``-w`` in fMRIPrep or QSIPrep)?

    * The space specified in this section is for job computing by BABS, and such job computing includes not only
      ``singularity run`` of the BIDS App, but also other necessary data version tracking steps done by BABS.
    * The "path where intermediate results should be stored" (e.g., ``-w``) is directly used by BIDS Apps.
      It is also a sub-folder of the space specified in this section.

.. _required_files:

Section ``required_files``
==========================
This section is optional.

You may have a dataset where not all the subjects (and sessions) have the required files for
running the BIDS App. You can simply provide this list of required files, and BABS will exclude those
subjects and sessions who don't have any of listed required files.

Example section **required_files** for ``fMRIPrep``:

..  code-block:: yaml

    required_files:
        $INPUT_DATASET_#1:
            - "func/*_bold.nii*"
            - "anat/*_T1w.nii*"

In this example case, we specify that for the input raw BIDS dataset,
 which is also input dataset #1, each subject (and session) must have:

#. At least one BOLD file (``*_bold.nii*``) in folder ``func``;
#. At least one T1-weighted file (``*_T1w.nii*``) in folder ``anat``.


Notes:

* If needed, you can change ``$INPUT_DATASET_#1`` to other index of input dataset
  (e.g., ``$INPUT_DATASET_#2``);
* To determine the index of the input dataset to specify,
  please check the order of the datasets when you call ``babs init --datasets``.
  This index starts from 1, and is a positive integer.

    * For example, to use ``fMRIPrep`` with FreeSurfer results ingressed, you want to call command below,
      and you hope to filter subjects based on files in raw BIDS data (here named ``BIDS``),
      then you should specify ``$INPUT_DATASET_#1``.

      .. code-block::

            babs init \
                ...
                --datasets \
                BIDS=/path/to/BIDS \
                freesurfer=/path/to/freesurfer_outputs \
                ...

* We recommend adding ``*`` after ``.nii`` as there might only be unzipped NIfTI file
  (e.g., ``.nii`` instead of ``.nii.gz``) in the input dataset;
* :octicon:`alert-fill` :bdg-warning:`warning` Currently we only support checking required files
  in unzipped input dataset (e.g., raw BIDS dataset).


.. _alert_log_messages:

Section ``alert_log_messages``
==============================
This section is optional.

This section is to define a list of alert messages to be searched in log files,
and these messages may indicates failure of a job.

Example section **alert_log_messages** for fMRIPrep:

..  code-block:: yaml

    alert_log_messages:
        stdout:
            - "Exception: No T1w images found for"  # not needed if setting T1w in `required_files`
            - "Excessive topologic defect encountered"
            - "Cannot allocate memory"
            - "mris_curvature_stats: Could not open file"
            - "Numerical result out of range"
            - "fMRIPrep failed"
        stderr:
            - "xxxxx"    # change this to any messages to be found in `stderr` file; if there is no messages for `stderr` file, delete line `stderr:` and this line


Usually there are two log files that are useful for debugging purpose, ``stdout`` and ``stderr``,
for example, ``<jobname>.o<jobid>`` and ``<jobname>.e<jobid>``.
You can define alert messages in either or both files, i.e., by filling out ``stdout`` section
(for ``stdout`` file) and/or ``stderr`` section (for ``stderr`` file).

Detection of the message is performed in the order provided by the user.
If ``stdout`` is former (e.g., in example above), then detection of it will be performed earlier;
if a message is former, then that will be checked earlier.
BABS also follows "detect and break" rule, i.e., for each job:

* If any message is detected, the detected message will be thrown into the ``job_status.csv``,
  and BABS won't detect any further message down in the list in **alert_log_messages**.
* If a message has been detected in the first file (``stdout`` for above example),
  then won't detect any message in the other log file (``stderr`` for above example).

.. warning::
    Detecting the messages in the log files by BABS is case-sensitive! So please make sure the cases of messages are in the way you hope.
