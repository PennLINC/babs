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

You'll see:

..  code-block:: console

    get(ok): sub-01/ses-A/anat/sub-01_ses-A_T1w.nii.gz (file) [from osf-storage...]

We can drop the file content now to save space:

..  code-block:: console

    $ datalad drop sub-01/ses-A/anat/sub-01_ses-A_T1w.nii.gz
    $ cd ..

You'll see:

..  code-block:: console

    drop(ok): sub-01/ses-A/anat/sub-01_ses-A_T1w.nii.gz (file)

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

We now needs to pull it as a Singularity image (the current latest version is ``0.0.6``):

..  code-block:: console

    $ cd ~/babs_demo
    $ singularity build \
        toybidsapp-0.0.6.sif \
        docker://pennlinc/toy_bids_app:0.0.6

Now you should see the file ``toybidsapp-0.0.6.sif`` in the current directory.
Then create a DataLad dataset of this container (i.e., let DataLad tracks this Singularity image):

.. code-block:: console

    $ datalad create -D "toy BIDS App" toybidsapp-container
    $ cd toybidsapp-container
    $ datalad containers-add \
        --url ${PWD}/../toybidsapp-0.0.6.sif \
        toybidsapp-0-0-6

.. dropdown:: Printed messages you'll see

    .. code-block:: bash

        # from `datalad create`:
        create(ok): /cbica/projects/BABS/babs_demo/toybidsapp-container (dataset)

        # from `datalad containers-add`:
        [INFO   ] Copying local file /cbica/projects/BABS/babs_demo/toybidsapp-container/../toybidsapp-0.0.6.sif to /cbica/projects/BABS/babs_demo/toybidsapp-container/.datalad/environments/toybidsapp-0-0-6/image 
        add(ok): .datalad/environments/toybidsapp-0-0-6/image (file)                                                                                  
        add(ok): .datalad/config (file)                                                                                                               
        save(ok): . (dataset)                                                                                                                         
        action summary:                                                                                                                               
        add (ok: 2)
        save (ok: 1)
        add(ok): .datalad/environments/toybidsapp-0-0-6/image (file)
        add(ok): .datalad/config (file)
        save(ok): . (dataset)
        containers_add(ok): /cbica/projects/BABS/babs_demo/toybidsapp-container/.datalad/environments/toybidsapp-0-0-6/image (file)
        action summary:
        add (ok: 2)
        containers_add (ok: 1)
        save (ok: 1)

Now, the DataLad dataset of toy BIDS App container ``toybidsapp-container`` is ready to use.
Please get its full path for later use by calling ``echo $PWD``.

.. developer's note: for my case, it's ``/cbica/projects/BABS/babs_demo/toybidsapp-container``

Step 1.3. Prepare a YAML file for the BIDS App
-------------------------------------------------------------

Finally, we'll prepare a YAML file that instructs BABS for how to run the BIDS App.
You can copy the example YAML file for toy BIDS App as below:

.. code-block:: yaml
   :linenos:
   :emphasize-lines: 18

    # Arguments in `singularity run`:
    babs_singularity_run:
        --no-zipped: ""
        -v: ""

    # Zip foldernames of the results, with BIDS App version included:
    babs_zip_foldername:
        toybidsapp: "0-0-6"

    # How much cluster resources it needs:
    cluster_resources:
        interpreting_shell: /bin/bash
        hard_memory_limit: 2G
        temporary_disk_space: 20G

    # Necessary commands to be run first:
    script_preamble: |
        source ${CONDA_PREFIX}/bin/activate babs    # for Penn Med CUBIC cluster

    # Where to run the jobs:
    job_compute_space: "${CBICA_TMPDIR}"   # for Penn Med CUBIC cluster tmp space


And save it as file ``config_toybidsapp_demo.yaml`` in ``~/babs_demo`` directory.

There are several place you need to change for your cluster:

* Section ``script_preamble``:

    * You might need to change the highlighted line #18 of ``source`` command
      for how to activate the conda environment ``babs``;
    * You might need to add another line to ``module_load`` any necessary modules,
      such as ``singularity``.
      This section will looks like this after you add it:

      .. code-block:: yaml

            script_preamble: |
                source ${CONDA_PREFIX}/bin/activate babs
                module_load xxxx


Step 2. Create a BABS project
=================================


Step 3. Submit jobs and check job status
==========================================

Step 4. After jobs are finished
===================================