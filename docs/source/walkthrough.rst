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
that performs a simple task: count non-hidden files in a subject's folder. Note that
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

..  code-block:: console

    $ cd ~/babs_demo/my_BABS_project
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

Step 3. Submit jobs and check job status
==========================================

Step 4. After jobs are finished
===================================