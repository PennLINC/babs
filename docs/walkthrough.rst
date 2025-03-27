*******************
Example walkthrough
*******************

.. contents:: Table of Contents

.. developer's note:
.. This walkthru is prepared:
..  at: '/cbica/projects/BABS/babs_demo_prep'
..  using conda env 'babs_demo'
.. TODO before copying anything to this doc:
..  1. replace 'babs_demo_prep' with 'babs_demo'

In this example walkthrough, we will use toy BIDS data and a toy BIDS App
to demonstrate how to use BABS.

By following the :doc:`the installation page <installation>`,
on the cluster, you should have successfully installed BABS and its dependent software
(``DataLad``, ``Git``, ``git-annex``, ``datalad-container``)
in an environment called ``babs``. In addition, because the toy BIDS data
you'll use is on OSF, you also need to install ``datalad-osf``.

Here is the list of software versions we used to prepare this walkthrough.
It is a good idea to use the versions at or above the versions listed:

.. developer's note: these were installed on 3/19/2025.

..  code-block:: console

    $ python --version
    Python 3.11.11
    $ datalad --version
    datalad 1.1.5
    $ git --version
    git version 2.49.0
    $ git-annex version
    git-annex version: 10.20230626-g8594d49
    $ datalad containers-add --version
    datalad_container 1.2.5
    $ datalad osf-credentials --version
    datalad_osf 0.3.0

We used ``BABS version 0.0.9`` to prepare this example walkthrough.
We encourage you to use the **latest BABS version available on PyPI**.
There might be minor differences in the printed messages or generated code,
however you can still follow the same steps instructed here.
To check your BABS's version, you can run this command:

..  code-block:: console

    $ pip show babs
    Name: babs
    Version: x.x.x   # e.g., 0.0.9
    ...

Let's create a folder called ``babs_demo`` in root directory
as the working directory in this example walkthrough:

..  code-block:: console

    $ mamba activate babs
    $ mkdir -p ~/babs_demo
    $ cd babs_demo

Step 0: Ensure dependencies and data access
===========================================

*Notes: This Step 0 is only required for clusters
where there is no Internet connection on compute nodes;
otherwise, you may skip this step.
However we do recommend going through this step if this is your first time
running this example walkthrough.*

Before you start, you can test if you have all the dependencies
(including ``datalad-osf``) installed properly. Let's try installing
the toy, multi-session BIDS dataset you'll use in this example walkthrough:

..  code-block:: console

    $ datalad clone https://osf.io/w2nu3/ raw_BIDS_multi-ses

The printed messages should look like below.
Note that the absolute path to ``babs_demo`` (i.e., ``/cbica/projects/BABS/babs_demo``)
would probably be different from yours due to different clusters, which is fine:

.. code-block:: console

    install(ok): /cbica/projects/BABS/babs_demo/raw_BIDS_multi-ses (dataset)

.. dropdown:: Why do I also see ``[INFO]`` messages?

    It's normal to see additional messages from DataLad like below:

    ..  code-block:: console

        [INFO   ] Remote origin uses a protocol not supported by git-annex; setting annex-ignore


There are two subjects (``sub-01`` and ``sub-02``) and six sessions in this toy dataset.
Now let's try getting a file's content:

..  code-block:: console

    $ cd raw_BIDS_multi-ses
    $ datalad get sub-01/ses-A/anat/sub-01_ses-A_T1w.nii.gz

You should see:

..  code-block:: console

    get(ok): sub-01/ses-A/anat/sub-01_ses-A_T1w.nii.gz (file) [from osf-storage...]

You can now view this image in image viewers.
Note that the intensities of images in this dataset have been zero-ed out, so it's normal to
see all-black images in image viewers.

.. dropdown:: If there is no Internet connection on compute nodes

    In the later steps, jobs for executing the BIDS App will run on compute nodes,
    and will fetch the file contents of the input BIDS dataset.
    As this input BIDS dataset we use for this example walkthrough is available on OSF,
    by default, jobs will fetch the file contents from OSF via Internet connections.
    This would be a problem for clusters without Internet connection on compute nodes.

    If the cluster you're using does not have Internet connection on compute nodes,
    to avoid issues when running the jobs,
    please fetch all the file contents now by running:

    ..  code-block:: console

        $ datalad get *

    You should see these printed messages from ``datalad`` at the end:

    .. code-block:: console

        action summary:
          get (notneeded: 1, ok: 47)

    Then, please skip the step in the next code block below,
    i.e., do NOT drop file content or remove the local copy of this dataset.


By now, you have made sure you can successfully install this dataset and get the file contents.
Now you can drop the file content and remove this local copy of this dataset,
as you can directly use its OSF link for input dataset for BABS:

..  code-block:: console

    $ datalad drop sub-01/ses-A/anat/sub-01_ses-A_T1w.nii.gz
    $ cd ..
    $ datalad remove -d raw_BIDS_multi-ses

.. dropdown:: Printed messages you'll see

    ..  code-block:: console

        # from `datalad drop`:
        drop(ok): sub-01/ses-A/anat/sub-01_ses-A_T1w.nii.gz (file)

        # from `datalad remove`:
        uninstall(ok): . (dataset)


Step 1. Get prepared
====================
There are three things required by BABS as input:

#. DataLad dataset of BIDS dataset(s);
#. DataLad dataset of containerized BIDS App;
#. A YAML file regarding how the BIDS App should be executed.

Step 1.1. Prepare DataLad dataset(s) of BIDS dataset(s)
-------------------------------------------------------
As mentioned above, you will use a toy, multi-session BIDS dataset available on OSF:
https://osf.io/w2nu3/.
You'll directly copy this link as the path to the input dataset,
so no extra work needs to be done here.

.. dropdown:: If there is no Internet connection on compute nodes

    When providing the path to the input BIDS dataset,
    please do not use the OSF http link;
    instead, please use the path to the local copy of this dataset.
    We will provide more guidance when we reach that step.

Step 1.2. Prepare a DataLad dataset of the containerized BIDS App
-----------------------------------------------------------------
For this walkthrough, we have prepared a `toy BIDS App <https://hub.docker.com/r/pennlinc/toy_bids_app>`_
that performs a simple task: if the input dataset is a raw BIDS dataset (unzipped),
the toy BIDS App will count non-hidden files in a subject's folder. Note that
even if the input dataset is multi-session dataset, it will still count at the subject-level
(instead of session-level).

You now need to pull our toy BIDS App as a Singularity image (the latest version is ``0.0.7``):

..  code-block:: console

    $ cd ~/babs_demo
    $ singularity build \
        toybidsapp-0.0.7.sif \
        docker://pennlinc/toy_bids_app:0.0.7

Now you should see the file ``toybidsapp-0.0.7.sif`` in the current directory.

.. dropdown:: Having trouble building this Singularity image?

    It might be because the Singularity software's version you're using is too old.
    You can check your Singularity's version via ``singularity --version``.
    We've tested that these versions work fine:
    ``singularity-ce version 3.9.5`` and ``apptainer version 1.1.8-1.el7``.


Then create a DataLad dataset of this container (i.e., let DataLad track this Singularity image):

.. dropdown:: I'm confused - Why is the container another DataLad `dataset`?

    Here, "DataLad dataset of the container" means
    "a collection of container image(s) in a folder tracked by DataLad".
    It's the same as a DataLad dataset of input BIDS dataset - it's tracked by DataLad;
    but different from input BIDS dataset, a "DataLad dataset of the container"
    contains container image(s), and it won't `be processed`.

.. code-block:: console

    $ datalad create -D "toy BIDS App" toybidsapp-container
    $ cd toybidsapp-container
    $ datalad containers-add \
        --url ${PWD}/../toybidsapp-0.0.7.sif \
        toybidsapp-0-0-7

.. dropdown:: Printed messages you'll see

    .. code-block:: bash

        # from `datalad create`:
        create(ok): /cbica/projects/BABS/babs_demo/toybidsapp-container (dataset)

        # from `datalad containers-add`:
        [INFO   ] Copying local file /cbica/projects/BABS/babs_demo/toybidsapp-container/../toybidsapp-0.0.7.sif to /cbica/projects/BABS/babs_demo/toybidsapp-container/.datalad/environments/toybidsapp-0-0-7/image
        add(ok): .datalad/environments/toybidsapp-0-0-7/image (file)
        add(ok): .datalad/config (file)
        save(ok): . (dataset)
        action summary:
          add (ok: 2)
          save (ok: 1)
        add(ok): .datalad/environments/toybidsapp-0-0-7/image (file)
        add(ok): .datalad/config (file)
        save(ok): . (dataset)
        containers_add(ok): /cbica/projects/BABS/babs_demo/toybidsapp-container/.datalad/environments/toybidsapp-0-0-7/image (file)
        action summary:
          add (ok: 2)
          containers_add (ok: 1)
          save (ok: 1)

Now, the DataLad dataset containing the toy BIDS App container ``toybidsapp-container`` is ready to use.

.. developer's note: no need:
..  Please get its full path for later use by calling ``echo $PWD``.

As the ``sif`` file has been copied into ``toybidsapp-container``,
you can remove the original ``sif`` file:

.. code-block:: console

    $ cd ..
    $ rm toybidsapp-0.0.7.sif

.. developer's note: for my case, it's ``/cbica/projects/BABS/babs_demo/toybidsapp-container``

Step 1.3. Prepare a YAML file for the BIDS App
----------------------------------------------

Finally, you'll prepare a YAML file that instructs BABS for how to run the BIDS App.
Below is an example YAML file for toy BIDS App:

.. developer's note: ref below: https://www.sphinx-doc.org/en/master/usage/restructuredtext/directives.html#directive-literalinclude
..  `:lines:` is the line ranges in the original file
..  `:emphasize-lines:`: line # in the selected lines defined in `:lines:`

.. literalinclude:: ../notebooks/eg_toybidsapp-0-0-7_rawBIDS-walkthrough.yaml
   :language: yaml
   :linenos:
   :emphasize-lines: 23,24,26,27,30

As you can see, there are several sections in this YAML file.

Here, in section ``bids_app_args``, ``$SUBJECT_SELECTION_FLAG`` designates the flag used for selecting participants in the BIDS app.
. Additionally, both ``--dummy`` and ``-v`` are dummy arguments to this toy BIDS Apps:
argument ``--dummy`` can take any value afterwards, whereas argument ``-v`` does not take values.
Here we use these arguments to show examples of:

* how to add values after arguments: e.g., ``--dummy: "2"``;
* how to add arguments without values: e.g., ``--no-zipped: ""`` and ``-v: ""``;
* and it's totally fine to mix flags with prefix of ``--`` and ``-``.

Section ``zip_foldernames`` tells BABS to zip the output folder named ``toybidsapp``
as a zip file as ``${sub-id}_${ses-id}_toybidsapp-0-0-7.zip`` for each subject's each session,
where ``${sub-id}`` is a subject ID, ``${ses-id}`` is a session ID.

You can copy the above content and save it as file ``config_toybidsapp_demo.yaml`` in ``~/babs_demo`` directory.

.. dropdown:: How to copy above content using ``Vim`` with correct indent?

    After copying above content, and initializing a new file using ``vim``, you need to enter::

        :set paste

    hit ``Enter`` key,
    hit ``i`` to start ``INSERT (paste)`` mode, then paste above content into the file. Otherwise, you'll see wrong indent.
    After pasting, hit ``escape`` key and enter::

        :set nopaste

    and hit ``Enter`` key to turn off pasting.
    You now can save this file by typing ``:w``. Close the file by entering ``:q`` and hitting ``Enter`` key.

There are several lines (highlighted above) that require customization based on the cluster you are using:

* Section ``cluster_resources``:

    * Check out if line #13 ``interpreting_shell`` looks appropriate for your cluster.
      Some SLURM clusters may recommend adding ``-l`` at the end,
      i.e.,::

        interpreting_shell: "/bin/bash -l"

      See :ref:`cluster-resources` for more explanations about this line.

    * For SLURM clusters, if you would like to use specific partition(s),
      as requesting partition is currently not a pre-defined key in BABS,
      you can use ``customized_text`` instead, and add line #3-4 highlighted in the block below:

        ..  code-block:: yaml
            :linenos:
            :emphasize-lines: 3,4

            cluster_resources:
                ...
                customized_text: |
                    #SBATCH -p <partition_names>

      Please replace ``<partition_names>`` with the partition name(s) you would like to use.
      And please replace ``...`` with other lines with pre-defined keys from BABS,
      such as ``interpreting_shell`` and ``hard_memory_limit``.

    * If needed, you may add more requests for other resources,
      e.g., runtime limit of 20min (``hard_runtime_limit: "00:20:00"``),
      temporary disk space of 20GB (``temporary_disk_space: 20G``),
      Or even resources without pre-defined keys from BABS.
      See :ref:`cluster-resources` for how to do so.


.. developer's note: if YAML file of walkthrough was changed:
..  also need to change above copied section "cluster_resources"!
.. developer's note: for MSI SLURM cluster: need to add `hard_runtime_limit: "20"`
..  without it, when using e.g. `k40` partition, one job was success (branch pushed to output RIA)
..  but "TIMEOUT" in `sacct`, leaving last 2 lines of stdout message of "deleting branch:\n job-xx-xx-xx"

* Section ``script_preamble``:

    * You might need to adjust the highlighted line #18 of the ``source`` command
      based on your cluster and environment name.

    * You might need to add another line to ``module load`` any necessary modules,
      such as ``singularity``.
      This section will looks like this after you add it:

      .. code-block:: yaml

            script_preamble: |
                source "${CONDA_PREFIX}"/bin/activate babs
                module load xxxx

    * For more, please see: :ref:`script-preamble`.

* Section ``job_compute_space``:

    * You need to change ``/tmp`` to the temporary compute space available on your cluster
      where you will be running jobs,
      e.g., ``"/path/to/some_temporary_compute_space"``.
      Here ``"/tmp"`` is NOT a good choice, check your cluster's documentation for the correct path.
    * For more, please see: :ref:`job-compute-space`.

.. developer's note:
..  before proceeding, make sure you changed the env name in `script_preamble` in YAML file
..  to `babs_demo`!

By now, you have prepared these in the ``~/babs_demo`` folder:

.. code-block:: console

    config_toybidsapp_demo.yaml
    toybidsapp-container/

.. developer's note:
..  It's optional to have cloned dataset ``raw_BIDS_multi-ses`` locally, as we can directly use its OSF link
..  for input dataset for BABS. Unless there is no internet connection on compute node.

.. dropdown:: If there is no Internet connection on compute nodes

    In this folder, you should also see the local copy of the input BIDS dataset
    ``raw_BIDS_multi-ses``.

Now you can start to use BABS for data analysis.

Step 2. Create a BABS project
=============================

Step 2.1. Use ``babs init`` to create a BABS project
----------------------------------------------------
A BABS project is the place where all the inputs are cloned to, all scripts are generated,
and results and provenance are saved. An example command of ``babs init`` is as follows:

.. developer's note: reset `$TEMPLATEFLOW_HOME` for now: `unset TEMPLATEFLOW_HOME`

..  code-block:: console
    :linenos:
    :emphasize-lines: 9

    $ cd ~/babs_demo
    $ babs init \
        --datasets BIDS=https://osf.io/w2nu3/ \
        --container_ds ${PWD}/toybidsapp-container \
        --container_name toybidsapp-0-0-7 \
        --container_config ${PWD}/config_toybidsapp_demo.yaml \
        --processing_level session \
        --queue slurm \
        ${PWD}/my_BABS_project

.. dropdown:: If there is no Internet connection on compute nodes

    Please replace line #5 with ``--datasets BIDS=/path/to/cloned_input_BIDS_dataset``,
    and please replace ``/path/to/cloned_input_BIDS_dataset`` with the correct path
    to the local copy of the input BIDS dataset,
    e.g., ``${PWD}/raw_BIDS_multi-ses``.

Here you will create a BABS project called ``my_BABS_project`` in directory ``~/babs_demo``.
The input dataset will be called ``BIDS``, and you can just provide the OSF link as its path (line #5).
For container, you will use the DataLad-tracked ``toybidsapp-container`` and the YAML file you just prepared (line #6-8).
It is important to make sure the string ``toybidsapp-0-0-7`` used in ``--container_name`` (line #7)
is consistent with the image name you specified when preparing
the DataLad dataset of the container (``datalad containers-add``).
If you wish to process data on a session-wise basis, you should specify this as ``--processing_level session`` (line #9).


If ``babs init`` succeeded, you should see this message at the end:

..  code-block:: console

    `babs init` was successful!


.. dropdown:: Full printed messages from ``babs init``

    .. literalinclude:: walkthrough_babs-init_printed_messages.txt
       :language: console
.. developer's note: cannot change the `language` to `bash` here...
.. TODO before copying:
..  1. check if `miniconda3/envs/` env name is `babs` as instructed in the this example walkthrough!
..  2. 'babs_demo_prep' foldername used by developer --> 'babs_demo'
..  3. annoying but not useful warning from git-annex
.. TODO after copying:
..  1. check the tracked changes!

.. dropdown:: Warning regarding TemplateFlow? Fine to toy BIDS App!

    You may receive this warning from ``babs init`` if you did not set up
    the environment variable ``$TEMPLATEFLOW_HOME``::

        UserWarning: Usually BIDS App depends on TemplateFlow, but environment
        variable `TEMPLATEFLOW_HOME` was not set up.
        Therefore, BABS will not bind its directory or inject this environment
        variable into the container when running the container.
        This may cause errors.

    This is totally fine for the toy BIDS App we're using here, and it won't use TemplateFlow.
    However, a lot of BIDS Apps would use it.
    Make sure you set it up when you use those BIDS Apps.


It's very important to check if the generated ``singularity run`` command is what you desire.
The command below can be found in the printed messages from ``babs init``:

..  code-block:: console

    singularity run --cleanenv \
        -B ${PWD} \
        containers/.datalad/environments/toybidsapp-0-0-7/image \
        inputs/data/BIDS \
        outputs \
        participant \
        --no-zipped \
        --dummy 2 \
        -v \
        --participant-label "${subid}"


As you can see, BABS has automatically handled the positional arguments of BIDS App
(i.e., input directory, output directory, and analysis level - 'participant').
``--participant-label`` is also covered by BABS, too.

It's also important to check if the generated directives for job submission are what you desire.
You can get them via:

..  code-block:: console

    $ cd ~/babs_demo/my_BABS_project    # make sure you're in `my_BABS_project` folder
    $ head analysis/code/participant_job.sh

The first several lines starting with ``#`` and before the line ``# Script preambles:``
are directives for job submissions.
It should be noted that, when using different types of cluster systems (e.g., SLURM),
you will see different generated directives.
In addition, depending on the BABS version, you'll see slightly different directives, too.
If you used the YAML file above *without further modification*,
the generated directives would be:

.. developer's note: below: not all the 10 lines from `head participant_job.sh`, but only lines of directives.

.. dropdown:: If on a SLURM cluster + using BABS version >0.0.3, you'll see:

    ..  code-block:: console

        #!/bin/bash
        #SBATCH --mem=2G

.. developer's note: below is generated based on `tree -L 3 .`

.. dropdown:: What's inside the created BABS project ``my_BABS_project``?

    ..  code-block:: console

        .
        ├── analysis
        │   ├── CHANGELOG.md
        │   ├── code
        │   │   ├── babs_proj_config.yaml
        │   │   ├── babs_proj_config.yaml.lock
        │   │   ├── check_setup
        │   │   ├── participant_job.sh
        │   │   ├── README.md
        │   │   ├── submit_job_template.yaml
        │   │   ├── sub_ses_final_inclu.csv
        │   │   └── toybidsapp-0-0-7_zip.sh
        │   ├── containers
        │   ├── inputs
        │   │   └── data
        │   ├── logs
        │   └── README.md
        ├── input_ria
        └── output_ria

    Here, ``analysis`` is a DataLad dataset that includes generated scripts in ``code/``,
    a cloned container DataLad dataset ``containers/``, and a cloned input dataset in ``inputs/data``.
    Input and output RIA stores (``input_ria`` and ``output_ria``) are
    DataLad siblings of the ``analysis`` dataset.
    When running jobs, inputs are cloned from input RIA store,
    and results and provenance will be pushed to output RIA store.


Step 2.2. Use ``babs check-setup`` to make sure it's good to go
---------------------------------------------------------------
It's important to let BABS check to be sure that the project has been initialized correctly.
In addition, it's often a good idea to run a test job to make sure
that the environment and cluster resources specified in the YAML file are workable.

Note that starting from this step in this example walkthrough, without further instructions,
all BABS functions will be called from where the BABS project
is located: ``~/babs_demo/my_BABS_project``.
This is to make the BABS commands a little shorter - they assume the
BABS project is located in the current working directory.
Therefore, please make sure you switch to this directory before calling them.

..  code-block:: console

    $ cd ~/babs_demo/my_BABS_project    # make sure you're in `my_BABS_project` folder
    $ babs check-setup --job-test

It might take a bit time to finish, depending on how busy your cluster is,
and how much resources you requested in the YAML file - in this example,
you only requested very minimal resources.

You'll see this message at the end if ``babs check-setup`` was successful:

..  code-block:: console

    `babs check-setup` was successful!

Before moving on, please make sure you review the summarized information of
the designated environment, especially the version numbers:

..  code-block:: console

    Below is the information of the designated environment and temporary workspace:

    workspace_writable: true
    which_python: '/cbica/projects/BABS/miniconda3/envs/babs/bin/python'
    version:
      datalad: 'datalad 1.1.5'
      git: 'git version 2.49.0'
      git-annex: 'git-annex version: 10.20230626-g8594d49'
      datalad_containers: 'datalad_container 1.2.5'

.. dropdown:: Full printed messages from ``babs check-setup``

    .. literalinclude:: walkthrough_babs-check-setup_printed_messages.txt
       :language: console

.. developer's note:
.. TODO before copying:
..  1. check if `miniconda3/envs/` env name is `babs` as instructed in the this example walkthrough!
..  2. 'babs_demo_prep' foldername used by developer --> 'babs_demo'
..  3. annoying but not useful warning from git-annex
.. TODO after copying:
..  1. check the tracked changes!

Now it's ready for job submissions.

Step 3. Submit jobs and check job status
========================================
We'll iteratively use ``babs submit`` and ``babs status`` to submit jobs and check job status.

We first use ``babs status`` to check the number of jobs we initially expect to finish successfully.
In this example walkthrough, as no initial list was provided,
BABS determines this number based on the number of sessions in the input BIDS dataset.
We did not request extra filtering (based on required files) in our YAML file either,
so BABS will submit one job for each session.

..  code-block:: console

    $ cd ~/babs_demo/my_BABS_project    # make sure you're in `my_BABS_project` folder
    $ babs status

You'll see:

..  code-block:: console
    :emphasize-lines: 4

    Did not request resubmit based on job states (no `--resubmit`).

    Job status:
    There are in total of 6 jobs to complete.
    0 job(s) have been submitted; 6 job(s) haven't been submitted.

Let's use ``babs submit`` to submit one job and see if it will finish successfully.
By default, ``babs submit`` will only submit one job.
If you would like to submit all jobs, you can use the ``--all`` argument.

.. code-block:: console

    $ babs submit

You'll see something like this (the job ID will probably be different):

..  code-block:: console

    Job for sub-01, ses-A has been submitted (job ID: 4639278).
    sub_id ses_id  has_submitted   job_id  job_state_category  job_state_code  duration  is_done  is_failed
    0  sub-01  ses-A           True  4639278                 NaN             NaN       NaN    False        NaN  \
    1  sub-01  ses-B          False       -1                 NaN             NaN       NaN    False        NaN
    2  sub-01  ses-C          False       -1                 NaN             NaN       NaN    False        NaN
    3  sub-02  ses-A          False       -1                 NaN             NaN       NaN    False        NaN
    4  sub-02  ses-B          False       -1                 NaN             NaN       NaN    False        NaN
    5  sub-02  ses-D          False       -1                 NaN             NaN       NaN    False        NaN

                    log_filename  last_line_stdout_file  alert_message
    0  toy_sub-01_ses-A.*4639278                    NaN            NaN
    1                        NaN                    NaN            NaN
    2                        NaN                    NaN            NaN
    3                        NaN                    NaN            NaN
    4                        NaN                    NaN            NaN
    5                        NaN                    NaN            NaN

You can check the job status via ``babs status``:

..  code-block:: console

    $ babs status

..
   when pending::

        Did not request resubmit based on job states (no `--resubmit`).

        Job status:
        There are in total of 6 jobs to complete.
        1 job(s) have been submitted; 5 job(s) haven't been submitted.
        Among submitted jobs,
        0 job(s) are successfully finished;
        1 job(s) are pending;
        0 job(s) are running;
        0 job(s) are failed.

        All log files are located in folder: /cbica/projects/BABS/babs_demo/my_BABS_project/analysis/logs

If it's successfully finished, you'll see:

..  code-block:: console
    :emphasize-lines: 5,7

    Did not request resubmit based on job states (no `--resubmit`).

    Job status:
    There are in total of 6 jobs to complete.
    1 job(s) have been submitted; 5 job(s) haven't been submitted.
    Among submitted jobs,
    1 job(s) are successfully finished;
    0 job(s) are pending;
    0 job(s) are running;
    0 job(s) are failed.

    All log files are located in folder: /cbica/projects/BABS/babs_demo/my_BABS_project/analysis/logs

Now, you can submit all other jobs by specifying ``--all``:

.. code-block:: console

    $ babs submit --all

..
    printed messages you'll see:

    Job for sub-01, ses-B has been submitted (job ID: 4648997).
    Job for sub-01, ses-C has been submitted (job ID: 4649000).
    Job for sub-02, ses-A has been submitted (job ID: 4649003).
    Job for sub-02, ses-B has been submitted (job ID: 4649006).
    Job for sub-02, ses-D has been submitted (job ID: 4649009).
    sub_id ses_id  has_submitted   job_id  job_state_category  job_state_code  duration  is_done is_failed
    0  sub-01  ses-A           True  4639278                 NaN             NaN       NaN     True     False  \
    1  sub-01  ses-B           True  4648997                 NaN             NaN       NaN    False       NaN
    2  sub-01  ses-C           True  4649000                 NaN             NaN       NaN    False       NaN
    3  sub-02  ses-A           True  4649003                 NaN             NaN       NaN    False       NaN
    4  sub-02  ses-B           True  4649006                 NaN             NaN       NaN    False       NaN
    5  sub-02  ses-D           True  4649009                 NaN             NaN       NaN    False       NaN

                    log_filename last_line_stdout_file  alert_message
    0  toy_sub-01_ses-A.*4639278               SUCCESS            NaN
    1  toy_sub-01_ses-B.*4648997                   NaN            NaN
    2  toy_sub-01_ses-C.*4649000                   NaN            NaN
    3  toy_sub-02_ses-A.*4649003                   NaN            NaN
    4  toy_sub-02_ses-B.*4649006                   NaN            NaN
    5  toy_sub-02_ses-D.*4649009                   NaN            NaN

You can again call ``babs status`` to check status.
If those 5 jobs are pending (submitted but not yet run by the cluster), you'll see:

..  code-block:: console
    :linenos:
    :emphasize-lines: 5,8

    Did not request resubmit based on job states (no `--resubmit`).

    Job status:
    There are in total of 6 jobs to complete.
    6 job(s) have been submitted; 0 job(s) haven't been submitted.
    Among submitted jobs,
    1 job(s) are successfully finished;
    5 job(s) are pending;
    0 job(s) are running;
    0 job(s) are failed.

    All log files are located in folder: /cbica/projects/BABS/babs_demo/my_BABS_project/analysis/logs

If some jobs are running or have failed, you'll see non-zero numbers in line #9 or #10.

If all jobs have finished successfully, you'll see:

..  code-block:: console
    :emphasize-lines: 7,8

    Did not request resubmit based on job states (no `--resubmit`).

    Job status:
    There are in total of 6 jobs to complete.
    6 job(s) have been submitted; 0 job(s) haven't been submitted.
    Among submitted jobs,
    6 job(s) are successfully finished;
    All jobs are completed!

    All log files are located in folder: /cbica/projects/BABS/babs_demo/my_BABS_project/analysis/logs

.. developer's note:
.. TODO before copying:
..  1. 'babs_demo_prep' foldername used by developer --> 'babs_demo'

Step 4. After jobs have finished
================================

Step 4.1. Use ``babs merge`` to merge all results and provenance
----------------------------------------------------------------
After all jobs have finished successfully,
we will merge all the results and provenance.
Each job was executed on a different branch, so we must
merge them together into the mainline branch.

We now run ``babs merge`` in the root directory of ``my_BABS_project``:

..  code-block:: console

    $ babs merge

If it was successful, you'll see this message at the end:

..  code-block:: console

    `babs merge` was successful!


.. dropdown:: Full printed messages from ``babs merge``

    .. literalinclude:: walkthrough_babs-merge_printed_messages.txt
       :language: console

.. developer's note:
.. TODO before copying:
..  1. 'babs_demo_prep' foldername used by developer --> 'babs_demo'
..  2. annoying but not useful warning from git-annex
.. TODO after copying:
..  1. check the tracked changes!

Now you're ready to consume the results.

Step 4.2. Consume results
-------------------------

To consume the results, you should not access the output RIA store
or ``merge_ds`` directories inside the BABS project.
Instead, clone the output RIA as another folder (e.g., called ``my_BABS_project_outputs``)
to a location external to the BABS project:

..  code-block:: console

    $ cd ..   # Now, you should be in folder `babs_demo`, where `my_BABS_project` locates
    $ datalad clone \
        ria+file://${PWD}/my_BABS_project/output_ria#~data \
        my_BABS_project_outputs

You'll see:

..  code-block:: console

    [INFO   ] Configure additional publication dependency on "output-storage"
    configure-sibling(ok): . (sibling)
    install(ok): /cbica/projects/BABS/babs_demo/my_BABS_project_outputs (dataset)
    action summary:
      configure-sibling (ok: 1)
      install (ok: 1)

Let's go into this new folder and see what's inside:

..  code-block:: console

    $ cd my_BABS_project_outputs
    $ ls

You'll see:

..  code-block:: console

    CHANGELOG.md				sub-01_ses-B_toybidsapp-0-0-7.zip@
    code/			                sub-01_ses-C_toybidsapp-0-0-7.zip@
    containers/					sub-02_ses-A_toybidsapp-0-0-7.zip@
    inputs/					sub-02_ses-B_toybidsapp-0-0-7.zip@
    README.md					sub-02_ses-D_toybidsapp-0-0-7.zip@
    sub-01_ses-A_toybidsapp-0-0-7.zip@

.. developer's note: do NOT change the indents above! In the html the 2nd column is aligned...

As you can see, each session's results have been saved in a zip file.
Before unzipping a zip file, you need to get its content first:

..  code-block:: console

    $ datalad get sub-01_ses-A_toybidsapp-0-0-7.zip
    $ unzip sub-01_ses-A_toybidsapp-0-0-7.zip

You'll see printed messages like this:

..  code-block:: console

    # from `datalad get`:
    get(ok): sub-01_ses-A_toybidsapp-0-0-7.zip (file) [from output-storage...]

    # from unzip:
    Archive:  sub-01_ses-A_toybidsapp-0-0-7.zip
       creating: toybidsapp/
     extracting: toybidsapp/num_nonhidden_files.txt

From the zip file, you got a folder called ``toybidsapp``.

..  code-block:: console

    $ cd toybidsapp
    $ ls

In this folder, there is a file called ``num_nonhidden_files.txt``.
This is the result from toy BIDS App, which is the number of non-hidden files in this subject.
Note that for raw BIDS dataset, toy BIDS App counts at subject-level, even though
current dataset is a multi-session dataset.

..  code-block:: console

    $ cat num_nonhidden_files.txt
    67

Here, ``67`` is the expected number for ``sub-01`` (which you're looking at),
``56`` is the expected number for ``sub-02``.
This means that toy BIDS App and BABS ran as expected :).
