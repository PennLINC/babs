************
Installation
************

.. contents:: Table of Contents

Step 0. System requirements
===========================

Currently BABS supports applications on high performance computing (HPC) clusters,
specifically and SLURM clusters.
Please make sure Singularity or one of its successors
(i.e. SingularityCE or Apptainer which BABS currently supports) is available on the cluster.

Currently, BABS is **not** compatible with:

* cloud-based computing platforms (e.g., Amazon Web Services [AWS]);
* local computers where a job scheduling system or Singularity software is not installed;
* computing nodes without job scheduling systems.

Step 1. Choose an environment manager for BABS
==============================================
For this, we strongly recommend `miniforge/mamba <https://github.com/conda-forge/miniforge>`_
or optionally `micromamba <https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html>`_.
These packages work the same as ``conda``, but they are open-source and will never move to a pay-structure as
anaconda has recently done.

Step 2. Install BABS and dependent software
===========================================

We have a `yaml` file on our repo for easily installing BABS and its dependencies with a single command::

    # Get the evironment_hpc.yaml file from github:
    wget https://raw.githubusercontent.com/PennLINC/babs/refs/heads/main/environment_hpc.yml

    # Install into a new environment called babs:
    mamba create -f evironment_hpc.yml

    # Activate the environment:
    mamba activate babs

.. note::
    If you are using ``conda`` or ``micromamba`` instead of ``mamba``, simply replace ``mamba``
    with either ``conda`` or ``micromamba`` in the commands above.

Before proceeding, make sure your ``Git`` identity has been configured.
You can check whether this has already been done via::

    git config --get user.name
    git config --get user.email

If this returns nothing, you need to configure your ``Git`` identity::

    git config --global user.name "John Doe"
    git config --global user.email johndoe@example.com

Please replace ``"John Doe"`` and ``johndoe@example.com`` with your name and your email.
You only need to do this step once on a given system.

.. developer's note:
..  ref: https://psychoinformatics-de.github.io/rdm-course/01-content-tracking-with-datalad/index.html#setting-up
..  ref: https://git-scm.com/book/en/v2/Getting-Started-First-Time-Git-Setup

Optional: set-up ``datalad-osf``
--------------------------------
You also need to configure ``datalad-osf`` only if:

* if you're an end user and your input DataLad dataset is on OSF;

    * e.g., when you follow :doc:`the example walkthrough <walkthrough>`;

* or if you're a developer and you will be running our ``pytest``;

How to configure ``datalad-osf``::

    # Provide your OSF credentials  - this step is very important!
    datalad osf-credentials --method userpassword

For up-to-date information on configuring ``datalad-osf`` see: http://docs.datalad.org/projects/osf/en/latest/settingup.html

Check if you have everything installed and up-to-date
-----------------------------------------------------
.. warning::
    Before moving on, please check if you have up-to-date required dependencies! Sometimes although
    dependent software has been installed, the version might be too old or not up-to-date, causing
    future errors hard to debug.

Check dependencies' versions using commands below::

    # dependencies:
    datalad --version
    git --version
    git-annex version
    datalad containers-add --version
    datalad osf-credentials --version

    # babs
    pip show babs

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
    $ pip show babs
    Name: babs
    Version: 0.0.9
