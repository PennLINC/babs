**********************
Example walkthrough
**********************

.. contents:: Table of Contents

In this example walkthrough, we will use toy BIDS data and toy BIDS App
to demonstrate how to use BABS.

By following the :doc:`the installation page <installation>`, 
on the cluster, you should have successfully installed BABS and its dependent software
(``DataLad``, ``Git``, ``git-annex``, ``datalad-container``)
in a conda environment called ``babs``. In addition, because the toy BIDS data
we'll use is on OSF, you also need to install ``datalad-osf``.

Here is the list of software versions we used to prepare this walkthrough.
You don't need to get the exact versions as below, but please check if yours are too old:

.. developer's note: these were installed on 4/19/2023.

..  code-block:: console

    $ python --version
    Python 3.9.16
    $ datalad --version
    datalad 0.18.3
    $ git --version
    git version 2.34.1
    $ git-annex version
    git-annex version: 10.20230215-gd24914f2a
    $ datalad containers-add --version
    datalad_container 1.1.9
    $ datalad osf-credentials --version
    datalad_osf 0.2.3.1

Let's create a folder called ``babs_demo`` in root directory
as the working directory in this example walkthrough:

..  code-block:: console

    $ conda activate babs
    $ mkdir -p ~/babs_demo
    $ cd babs_demo

Before we start, to test if you have all the dependencies
(including ``datalad-osf``) installed properly, let's try if you can install
the toy, multi-session BIDS dataset we'll use in this example walkthrough:

..  code-block:: console

    $ datalad clone https://osf.io/w2nu3/ raw_BIDS_multi-ses

The printed messages should be like this:

.. code-block:: console

    install(ok): /cbica/projects/BABS/babs_demo/raw_BIDS_multi-ses (dataset)

There are two subjects (``sub-01`` and ``sub-02``), in total of six sessions in this toy dataset.
Now let's try getting a file's content:

..  code-block:: console

    $ cd raw_BIDS_multi-ses
    $ datalad get sub-01/ses-A/anat/sub-01_ses-A_T1w.nii.gz

You should see:

..  code-block:: console

    get(ok): sub-01/ses-A/anat/sub-01_ses-A_T1w.nii.gz (file) [from osf-storage...]

These mean that you can successfully install this dataset, and get the file contents.

Now we can drop the file content and remove this local copy of this dataset,
as we can directly use its OSF link for input dataset for BABS:

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
===========================
There are three things required by BABS as input:

#. DataLad dataset of BIDS dataset(s);
#. DataLad dataset of containerized BIDS App;
#. A YAML file regarding how the BIDS App should be executed.

Step 1.1. Prepare DataLad dataset(s) of BIDS dataset(s)
---------------------------------------------------------
As mentioned above,
we will use a toy, multi-session BIDS dataset available on OSF:
https://osf.io/w2nu3/. We'll directly copy this link as the path to the input dataset,
so no extra work needs to be done here.

Step 1.2. Prepare DataLad dataset of containerized BIDS App
-------------------------------------------------------------
For BIDS App, we have prepared a [toy BIDS App](https://hub.docker.com/r/pennlinc/toy_bids_app)
that performs a simple task: if the input dataset is a raw BIDS dataset (unzipped),
toy BIDS App will count non-hidden files in a subject's folder. Note that
even if the input dataset is multi-session dataset, it will still count at subject-level
(instead of session-level).

We now needs to pull it as a Singularity image (the current latest version is ``0.0.7``):

..  code-block:: console

    $ cd ~/babs_demo
    $ singularity build \
        toybidsapp-0.0.7.sif \
        docker://pennlinc/toy_bids_app:0.0.7

Now you should see the file ``toybidsapp-0.0.7.sif`` in the current directory.
Then create a DataLad dataset of this container (i.e., let DataLad tracks this Singularity image):

.. dropdown:: I'm confused - Why the container is another DataLad `dataset`?

    Here, "DataLad dataset of container" means "a collection of container image(s) in a folder tracked by DataLad".
    Same as DataLad dataset of input BIDS dataset, it's tracked by DataLad;
    but different from input BIDS dataset, it contains container, and it won't `be processed`.

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

Now, the DataLad dataset of toy BIDS App container ``toybidsapp-container`` is ready to use.
.. developer's note: no need:
..  Please get its full path for later use by calling ``echo $PWD``.

As the ``sif`` file has been copied into ``toybidsapp-container``,
you can remove the original ``sif`` file:

.. code-block:: console

    $ cd ..
    $ rm toybidsapp-0.0.7.sif

.. developer's note: for my case, it's ``/cbica/projects/BABS/babs_demo/toybidsapp-container``

Step 1.3. Prepare a YAML file for the BIDS App
-------------------------------------------------------------

Finally, we'll prepare a YAML file that instructs BABS for how to run the BIDS App.
Below is an example YAML file for toy BIDS App:

.. developer's note: ref below: https://www.sphinx-doc.org/en/master/usage/restructuredtext/directives.html#directive-literalinclude
..  `:lines:` is the line ranges in the original file
..  `:emphasize-lines:`: line # in the selected lines defined in `:lines:`

.. literalinclude:: ../../notebooks/example_container_toybidsapp_walkthrough.yaml
   :language: yaml
   :lines: 21-
   :linenos:
   :emphasize-lines: 12,18,19,22

As you can see, there are several sections in this YAML file.

Here, in section ``babs_singularity_run``,
both ``--dummy`` and ``-v`` are dummy arguments to this toy BIDS Apps,
where ``--dummy`` can take any value afterwards, whereas ``-v`` does not take values.
Here we use them to show examples of:

* how to add values after flags: e.g., ``--dummy: "2"``;
* how to add flags without values: e.g., ``--no-zipped: ""`` and ``-v: ""``;
* and it's totally fine to mix flags with prefix of ``--`` and ``-``.

You can copy above content and save it as file ``config_toybidsapp_demo.yaml`` in ``~/babs_demo`` directory.

.. dropdown:: How to copy above content using ``Vim`` with correct indent?

    After copying above content, and initializing a new file using ``vim``, you need to enter::
        
        :set paste
        
    hit ``Enter`` key,
    hit ``i`` to start ``INSERT (paste)`` mode, then paste above content into the file. Otherwise, you'll see wrong indent.
    After pasting, hit ``escape`` key and enter::
        
        :set nopaste
    
    and hit ``Enter`` key to turn off pasting.
    You now can save this file by typing ``:w``. Close the file by entering ``:q`` and hitting ``Enter`` key.

Before moving forward, there are several lines (highlighted above) requires customization for your cluster:

* Section ``cluster_resources``:

    * If needed, you may add requests for other resources. See :ref:`cluster-resources`
      for how to do so.

* Section ``script_preamble``:

    * You might need to change the highlighted line #19 of ``source`` command
      for how to activate the conda environment ``babs``;

        * In addition, if you wants to use a conda environment that has different name than ``babs``,
          please replace ``babs`` with the name you're using.

    * You might need to add another line to ``module_load`` any necessary modules,
      such as ``singularity``.
      This section will looks like this after you add it:

      .. code-block:: yaml

            script_preamble: |
                source ${CONDA_PREFIX}/bin/activate babs
                module_load xxxx
    
    * For more, please see: :ref:`script-preamble`.

* Section ``job_compute_space``:

    * You need to change ``"${CBICA_TMPDIR}"`` to temporary compute space available on your cluster,
      e.g., ``"/path/to/some_temporary_compute_space"``.
      Here ``"${CBICA_TMPDIR}"`` is for Penn Medicine CUBIC cluster only.
    * For more, please see: :ref:`job-compute-space`.


By now, we have prepared these in the ``~/babs_demo`` folder:

.. code-block:: console

    config_toybidsapp_demo.yaml
    toybidsapp-container/

.. developer's note: 
..  It's optional to have cloned dataset ``raw_BIDS_multi-ses`` locally, as we can directly use its OSF link
..  for input dataset for BABS.

We now start to use BABS for data analysis.

Step 2. Create a BABS project
=================================

Step 2.1. Use ``babs-init`` to create a BABS project
-----------------------------------------------------------
A BABS project is the place where all the inputs are cloned to, all scripts are generated,
and results and provenance are saved. An example command of ``babs-init`` is as follows:

.. developer's note: reset `$TEMPLATEFLOW_HOME` for now: `unset TEMPLATEFLOW_HOME`

..  code-block:: console
    :linenos:
    :emphasize-lines: 10

    $ cd ~/babs_demo
    $ babs-init \
        --where_project ${PWD} \
        --project_name my_BABS_project \
        --input BIDS https://osf.io/w2nu3/ \
        --container_ds ${PWD}/toybidsapp-container \
        --container_name toybidsapp-0-0-7 \
        --container_config_yaml_file ${PWD}/config_toybidsapp_demo.yaml \
        --type_session multi-ses \
        --type_system sge

Here we will create a BABS project called ``my_BABS_project`` in directory ``~/babs_demo``.
The input dataset will be called ``BIDS``, and we can just provide the OSF link as its path (line #5).
For container, we will use the DataLad-tracked ``toybidsapp-container`` and the YAML file we just prepared (line #6-8).
It is important to make sure the string ``toybidsapp-0-0-7`` used in ``--container_name`` (line #7)
is consistent with the image name we specified when preparing
the DataLad dataset of the container (``datalad containers-add``).
As this input dataset is multi-session dataset, we specify it as ``--type_session multi-ses`` (line #9).
Finally, please change the cluster system type ``--type_system`` (highlighted line #10) to yours;
currently BABS supports ``sge`` and ``slurm``.

If ``babs-init`` succeeded, you should see this message at the end:

..  code-block:: console

    `babs-init` was successful!


.. dropdown:: Full printed messages from ``babs-init``

    .. literalinclude:: walkthrough_babs-init_printed_messages.txt
       :language: console
.. developer's note: cannot change the `language` to `bash` here...
.. developer's note: check if `miniconda3/envs/` env name is `babs` as instructed in the this example walkthrough!

.. dropdown:: Warning regarding TemplateFlow? Fine to toy BIDS App!

    You may receive this warning from ``babs-init`` if you did not set up environment variable ``$TEMPLATEFLOW_HOME``::

        UserWarning: Usually BIDS App depends on TemplateFlow, but environment variable `TEMPLATEFLOW_HOME` was not set up.
        Therefore, BABS will not export it or bind its directory when running the container. This may cause errors.

    This is totally fine to toy BIDS App, and it won't use TemplateFlow.
    However, a lot of BIDS Apps would use it. Make sure you set it up when you use those BIDS Apps.


It's very important to check if the generated ``singularity run`` command is what you desire:

..  code-block:: console

    singularity run --cleanenv -B ${PWD} \
        containers/.datalad/environments/toybidsapp-0-0-7/image \
        inputs/data/BIDS \
        outputs \
        participant \
        --no-zipped \
        --dummy 2 \
        -v \
        --participant-label "${subid}"


As you can see, BABS has automatically handled the positional arguments of BIDS App (i.e., input directory,
output directory, and analysis level - 'participant'). ``--participant-label`` will also be covered by BABS, too.

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
    cloned container DataLad dataset ``containers/``, and cloned input dataset in ``inputs/data``.
    Input and output RIA stores (``input_ria`` and ``output_ria``) are DataLad siblings of ``analysis``.
    When job running, inputs are cloned from input RIA store,
    and results and provenance will be pushed to output RIA store. 


Step 2.2. Use ``babs-check-setup`` to make sure it's good to go
--------------------------------------------------------------------
It's important to let BABS checks if everything has been correctly set up. In addition,
it's a good idea to run a toy, test job to make sure the environment you specified in the YAML file
is working as expected.

Note that starting from this step, without further instructions,
all BABS commands should be called from where the BABS project
is located: ``~/babs_demo/my_BABS_project``,
so please make sure you switch to this directory before calling them.

..  code-block:: console

    $ cd ~/babs_demo/my_BABS_project    # make sure you're in `my_BABS_project` folder
    $ babs-check-setup \
        --project-root ${PWD} \
        --job-test

It might take a bit time to finish, depending on how busy your cluster is,
and how much resources you requested in the YAML file - in this example,
we only requested very minimal amount of resources.

You'll see this message at the end if ``babs-check-setup`` was successful:

..  code-block:: console

    `babs-check-setup` was successful!

Before moving on, please make sure you review the summarized information of designated environment,
especially the version numbers:

..  code-block:: console

    Below is the information of designated environment and temporary workspace:

    workspace_writable: true
    which_python: '/cbica/projects/BABS/miniconda3/envs/babs/bin/python'
    version:
      datalad: 'datalad 0.18.3'
      git: 'git version 2.34.1'
      git-annex: 'git-annex version: 10.20230215-gd24914f2a'
      datalad_containers: 'datalad_container 1.1.9'

.. dropdown:: Full printed messages from ``babs-check-setup``

    .. literalinclude:: walkthrough_babs-check-setup_printed_messages.txt
       :language: console

Now it's ready for job submissions.

Step 3. Submit jobs and check job status
==========================================
We'll iteratively use ``babs-submit`` and ``babs-status`` to submit jobs and check job status.

We first use ``babs-status`` to check how many jobs to complete.
The list of jobs to complete was determined during ``babs-init``:
As no initial list was provided, BABS dived into the input BIDS dataset,
and got the list of subjects and sessions to process. As we did not specify
required files in the container's configuration YAML file, BABS would not
perform extra filtering.

..  code-block:: console

    $ cd ~/babs_demo/my_BABS_project    # make sure you're in `my_BABS_project` folder
    $ babs-status --project-root $PWD

You'll see:

..  code-block:: console
    :emphasize-lines: 4

    Did not request resubmit based on job states (no `--resubmit`).

    Job status:
    There are in total of 6 jobs to complete.
    0 job(s) have been submitted; 6 job(s) haven't been submitted.

Let's use ``babs-submit`` submit one job to see if it will successfully finish.
If only argument ``--project-root`` is provided, ``babs-submit`` will only submit
one job to avoid all jobs getting submitted by mistake:

.. code-block:: console

    $ babs-submit --project-root $PWD

You'll see something like this (the job ID will probably be different):

..  code-block:: console

    Job for sub-01, ses-A has been submitted (job ID: 4475292).
    sub_id ses_id  has_submitted   job_id  job_state_category  job_state_code  duration  is_done  is_failed   
    0  sub-01  ses-A           True  4475292                 NaN             NaN       NaN    False        NaN  \
    1  sub-01  ses-B          False       -1                 NaN             NaN       NaN    False        NaN   
    2  sub-01  ses-C          False       -1                 NaN             NaN       NaN    False        NaN   
    3  sub-02  ses-A          False       -1                 NaN             NaN       NaN    False        NaN   
    4  sub-02  ses-B          False       -1                 NaN             NaN       NaN    False        NaN   
    5  sub-02  ses-D          False       -1                 NaN             NaN       NaN    False        NaN   

                    log_filename  last_line_o_file  alert_message  job_account  
    0  toy_sub-01_ses-A.*4475292               NaN            NaN          NaN  
    1                        NaN               NaN            NaN          NaN  
    2                        NaN               NaN            NaN          NaN  
    3                        NaN               NaN            NaN          NaN  
    4                        NaN               NaN            NaN          NaN  
    5                        NaN               NaN            NaN          NaN  

We can check the job status via ``babs-status``:

..  code-block:: console

    $ babs-status --project-root $PWD

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

Now, we can submit all other jobs by specifying ``--all``:

.. code-block:: console

    $ babs-submit --project-root $PWD --all

You can again call ``babs-status --project-root $PWD`` to check status.
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

If some jobs are running or failed, you'll see non-zero numbers in line #9 or #10.

If all jobs are successfully completed, you'll see:

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

Step 4. After jobs are finished
===================================

Step 4.1. Use ``babs-merge`` to merge all results and provenance
--------------------------------------------------------------------
After all jobs are successfully finished,
we will first merge all the results and provenance.
This is because each job was executed on a different branch,
we need to merge them together onto the default branch.

We now run ``babs-merge`` in the root directory of ``my_BABS_project``:

..  code-block:: console

    $ babs-merge --project-root $PWD

If it was successfull, you'll see this message at the end:

..  code-block:: console

    `babs-merge` was successful!


.. dropdown:: Full printed messages from ``babs-merge``

    .. literalinclude:: walkthrough_babs-merge_printed_messages.txt
       :language: console


Now, we have reached the end of the BABS workflow, and we're ready to consume the results.

Step 4.2. Consume results
------------------------------

To consume the results, we should not directly go into output RIA to check results there;
instead, we should clone the output RIA as another folder (e.g., called ``my_BABS_project_outputs``)
outside the original BABS project:

..  code-block:: console

    $ cd ~/babs_demo    # outside of `my_BABS_project`
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
Before unzipping a zip file, we need to get its content first:

..  code-block:: console

    $ datalad get sub-01_ses-A_toybidsapp-0-0-7.zip
    $ unzip sub-01_ses-A_toybidsapp-0-0-7.zip

You'll see:

..  code-block:: console

    # from `datalad get`:
    get(ok): sub-01_ses-A_toybidsapp-0-0-7.zip (file) [from output-storage...]

    # from unzip:
    Archive:  sub-01_ses-A_toybidsapp-0-0-7.zip
       creating: toybidsapp/
     extracting: toybidsapp/num_nonhidden_files.txt 

From the zip file, we got a folder called ``toybidsapp``.

..  code-block:: console

    $ cd toybidsapp
    $ ls

In this folder, there is a file called ``num_nonhidden_files.txt``.
This is the result from toy BIDS App, which is the number of non-hidden files in this subject.
Note that for raw BIDS dataset, toy BIDS App counts at subject-level, even though
current dataset is multi-session dataset.

..  code-block:: console

    $ cat num_nonhidden_files.txt
    67

Here, ``67`` is the expected number for ``sub-01`` (which we're looking at),
``56`` is the expected number for ``sub-02``.
This means that toy BIDS App and BABS ran as expected :).
