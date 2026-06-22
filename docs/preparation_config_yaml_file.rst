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

* **input_datasets**: the input datasets to be used in this BABS project
* **cluster_resources**: how much cluster resources are needed to run this BIDS App?
* **script_preamble**: the preamble in the script to run a participant's job;
* **job_compute_space**: where to run the jobs?
* **singularity_args**: the arguments for ``singularity run``;
* **bids_app_args**: the arguments for the BIDS App;
* **imported_files**: the files to be copied into the datalad dataset;
* **output_dir**: the folder the BIDS App writes its results into;
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


Section ``input_datasets``
==========================

This section is required. 
It defines the input datasets to be used in this BABS project.
Note that the ``origin_url`` is the path to the input dataset on your local machine.
The ``--datasets`` argument is no longer allowed in ``babs init`` and is replaced by this section.


Example section **input_datasets**
----------------------------------

..  code-block:: yaml

    input_datasets:
        BIDS:
            required_files:
                - "dwi/*_dwi.nii*"
                - "anat/*_T1w.nii*"
            is_zipped: false
            origin_url: "/path/to/BIDS"
            path_in_babs: inputs/data/BIDS
        FreeSurfer:
            required_files:
                - "*freesuefer*.zip"
            is_zipped: true
            origin_url: "/path/to/FreeSurfer"
            unzipped_path_containing_subject_dirs: "freesurfer"
            path_in_babs: inputs/data/freesurfer

This example shows two input datasets: 
one is a raw BIDS dataset, and the other is a zipped FreeSurfer results from another BABS project.
Previously, the commandline to use something like this would have required::

  babs init --datasets BIDS=/path/to/BIDS --datasets freesurfer=/path/to/FreeSurfer

You can see that the dataset names are specified as ``BIDS`` and ``freesurfer``
in the yaml file such that the name is the key and the path to the dataset is in ``origin_url``.

``required_files`` is currently not implemented but will be soon.
This section is defined per input.

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


.. _section-hooks:

Section ``hooks``
=================

This section is optional. It lets you splice your own shell commands into each
participant job at two **splice points** that bracket the BIDS App run:

- ``pre_run`` — runs just **before** the ``datalad run`` that executes the BIDS App.
- ``post_run`` — runs just **after** that ``datalad run`` completes (its outputs
  already committed), but **before** the results are pushed to the output RIA.

Each splice point is a list; entries run in the order you list them.

Example section **hooks**
-------------------------

..  code-block:: yaml

    hooks:
      pre_run:
        - echo "starting ${subid}"                 # a raw shell snippet
        - script: "/path/to/validate-inputs.sh"    # a script copied into the project
      post_run:
        - script: "/path/to/validate-outputs.sh"
        - builtin: zip                             # a built-in shipped with BABS

Three entry forms are supported:

- **snippet** — a bare string. It is spliced **verbatim** into the job script
  and runs *inline*. You own its quoting and safety (this is shell injection by
  the config author, by design).
- **script** — ``{script: <path>}``. ``<path>`` is an **absolute** local path
  (copied into the project the same way as ``imported_files``). BABS copies it to
  ``code/hooks/<basename>.sh`` at ``babs init`` and the splice runs
  ``bash ./code/hooks/<basename>.sh`` — a **separate process**.
- **built-in** — ``{builtin: <name>}``. The hook ships with BABS; ``babs init``
  copies it into ``code/hooks/<name>.sh`` (git-tracked, so you can read exactly
  what will run) and the splice runs it like a script hook. Keys beyond
  ``builtin`` are parameters for that built-in, passed as **arguments** at the
  splice site — several instances of the same built-in (e.g. several zip hooks)
  share one script and differ only in their arguments.

Built-in: ``zip``
-----------------

``{builtin: zip}`` archives one output folder as a ``post_run`` hook. Its two
optional parameters:

- ``path`` — the folder to zip, relative to the dataset root. Defaults to the
  top-level ``output_dir``, so the argless form covers the common case of
  archiving the whole app output.
- ``name`` — the archive-name stem: the hook zips ``path`` into
  ``${subid}[_${sesid}]_<name>.zip`` at the dataset root. Defaults to
  ``path``'s basename. Set it when the BIDS App controls the folder name and
  you want a versioned archive name (e.g. ``path: outputs/freesurfer`` with
  ``name: freesurfer-24-1-1``).

The hook zips inside its **own** ``datalad run`` (so the archive is committed
with provenance), then removes the granular folder in a follow-up commit. The
archive contains the folder itself (e.g. ``fmriprep_minimal-25-2-5/``) at its
top level. To produce several separate archives, list several zip hooks, each
with its own ``path``.

The runtime contract
--------------------

Both splice points run with the working directory set to the cloned dataset and
with these variables **exported** (so a separate-process ``script`` hook can read
them): ``subid``; ``sesid`` (session-level processing only); ``BRANCH``;
``PROJECT_ROOT``; ``JOB_SCRATCH_DIR``. Each splice runs in a **subshell** under
``set -e``: a hook's ``cd`` or variable changes do **not** leak into the rest of
the job, and a non-zero exit **aborts the job**.

Persisting hook output
----------------------

Hooks splice **outside** the ``datalad run`` wrapper, so their filesystem effects
are **not** captured by it. A ``post_run`` hook that merely writes files into the
dataset leaves **uncommitted** changes — ``datalad push`` ships committed content,
so those files are **not pushed**. The common, safe use is **validation that fails
the job**: a ``post_run`` validator that exits non-zero aborts the job *before*
the push, so bad results never leave the node. If a hook needs to **persist**
output, it must run its **own** ``datalad run``/``datalad save`` to commit it.

Using ``datalad run`` inside a hook script
------------------------------------------

When a hook runs its own ``datalad run`` to commit output (the pattern above),
two ``datalad run`` behaviours commonly trip up a hand-written command. The
built-in ``zip`` hook (``code/hooks/zip.sh`` after ``babs init``) is a worked
example you can read.

- **The words after ``--`` are executed directly, without a shell.** So a
  command that relies on shell features — ``&&``, pipes, redirects, ``cd`` — is
  treated as a single program name and fails with something like
  ``/bin/sh: cd ... && ...: No such file or directory``. Wrap such a command in
  an explicit shell::

      datalad run --explicit -o out.zip -m "zip" -- \
          bash -c "cd outputs && 7z a ../out.zip deriv"

- **``datalad run`` substitutes its own ``{placeholder}`` fields over the
  command** (``{inputs}``, ``{outputs}``, ``{pwd}``, …). A literal brace —
  including an ordinary shell ``${VAR}`` — must be **doubled** or ``datalad``
  rejects it with ``unrecognized placeholder: 'VAR'``. Write ``${{VAR}}``;
  ``datalad`` collapses it back to ``${VAR}`` for the job's shell to expand, and
  it stays literal in the run record (so ``datalad rerun`` re-resolves it rather
  than baking in a value)::

      datalad run --explicit -o out.zip -m "zip" -- \
          bash -c "cd outputs && 7z a \"\${{OLDPWD}}/out.zip\" deriv"


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

    * :octicon:`alert-fill` :bdg-warning:`warning` If you have more than one input for a BABS project, the
      first listed input will be used for the positional input argument. We removed ``$INPUT_PATH`` from the
      configuration YAML file.

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
      the ``analysis/code`` folder.

.. developer's note: for SLURM: ref: https://login.scg.stanford.edu/faqs/cores/
..  other ref: https://docs.mpcdf.mpg.de/doc/computing/clusters/aux/migration-from-sge-to-slurm



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


Section ``output_dir``
======================

``output_dir`` is the folder the BIDS App writes its results into, relative to
the dataset root. It carries the full versioned derivative name (e.g.
``outputs/fmriprep-24-1-1``) and is the single source for that name: the same
string is the app's write directory, the ``datalad run`` output declaration,
and the default folder the built-in :ref:`zip hook <section-hooks>` archives.

Note that ``output_dir`` only *declares* the folder and commits whatever the
app writes there -- zipping is opt-in, configured as a ``post_run`` zip hook
(see Section ``hooks`` above). No zip hook = results are pushed as granular
files.

Which folder to point it at depends on the BIDS App's output layout:

Example #1: the BIDS App writes directly into the output directory
-------------------------------------------------------------------

Recent ``fMRIPrep`` (version >= 21.0) uses
`BIDS output layout <https://fmriprep.org/en/stable/outputs.html#layout>`_:
it writes files like ``sub-<label>.html`` and ``dataset_description.json``
directly into the directory it is given. Point ``output_dir`` at a versioned
folder and (optionally) archive it with an argless zip hook:

..  code-block:: yaml
    :linenos:

    output_dir: outputs/fmriprep-23-1-3
    hooks:
        post_run:
            - builtin: zip

The results land in ``outputs/fmriprep-23-1-3/`` and the zip hook archives
that folder into ``${sub-id}(_${ses-id})_fmriprep-23-1-3.zip``, where
``${sub-id}`` is the subject ID (e.g., ``sub-01``) and ``${ses-id}`` is the
session ID (e.g., ``ses-A``; session-level processing only).

Example #2: the BIDS App creates its own wrapper folder(s)
-----------------------------------------------------------

Older ``fMRIPrep`` (version < 21.0) uses the
`legacy output layout <https://fmriprep.org/en/stable/outputs.html#legacy-layout>`_:
given an output directory, it creates wrapper folders inside it::

    outputs/
        fmriprep/
        freesurfer/

Here the *app* controls the folder names, so point ``output_dir`` at the
parent and give each zip hook an explicit ``path`` (the folder to archive)
plus a ``name`` (the archive-name stem, keeping the version in the archive
name):

..  code-block:: yaml
    :linenos:

    output_dir: outputs
    hooks:
        post_run:
            - builtin: zip
              path: outputs/fmriprep
              name: fmriprep-20-2-3
            - builtin: zip
              path: outputs/freesurfer
              name: freesurfer-20-2-3

This zips ``outputs/fmriprep`` into ``${sub-id}(_${ses-id})_fmriprep-20-2-3.zip``
and ``outputs/freesurfer`` into ``${sub-id}(_${ses-id})_freesurfer-20-2-3.zip``.

Other detailed instructions
---------------------------

* The version number in ``output_dir`` (or in a zip hook's ``name``) should be
  consistent with that in *image NAME* when :ref:`create-a-container-datalad-dataset`,
  and with ``--container-name`` when calling ``babs init`` --
  e.g., ``output_dir: outputs/fmriprep-23-1-3`` alongside
  ``--container-name fmriprep-23-1-3``.
* Please use dashes ``-`` instead of dots ``.`` when indicating the version number,
  e.g., ``20-2-3`` instead of ``20.2.3``.


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


