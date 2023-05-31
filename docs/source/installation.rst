**********************
Installation
**********************

.. contents:: Table of Contents

Step 1. Prepare a conda environment for BABS
=============================================

After installing conda, let's initialize a new environment (e.g., named ``babs``)
where we can install BABS:: 

    conda create -n babs python=3.9.16
    conda activate babs

Step 2. Install dependent software
=====================================

Required dependencies
------------------------------
BABS is dependent on ``DataLad``, DataLad extension ``datalad-container``, ``Git``, and ``git-annex``.
Below is an example way of installing dependent software on Linux system::

    # Install DataLad, Git, and git-annex:
    conda install -c conda-forge datalad git git-annex

    # Install datalad-container:
    pip install datalad_container

If commands above do not work out, please refer to `Installation reference`_ for alternative and updated ways.


Optional dependencies
-------------------------------
Besides required software listed above, you also need to install ``datalad-osf`` only if:

* if you're an end user and your input DataLad dataset is on OSF;

    * e.g., when you follow :doc:`the example walkthrough <walkthrough>`;

* or if you're a developer and you will be running our ``pytest``;

How to install ``datalad-osf``::

    # Install datalad-osf:
    pip install datalad-osf

    # Provide your OSF credentials (token) - this step is very important!
    datalad osf-credentials


Installation reference
---------------------------

- ``DataLad``, ``Git``, and ``git-annex``: https://handbook.datalad.org/en/latest/intro/installation.html
- ``datalad-container``: https://github.com/datalad/datalad-container
- (optional) ``datalad-osf``: http://docs.datalad.org/projects/osf/en/latest/settingup.html

Check if you have everything installed and up-to-date
--------------------------------------------------------
.. warning::
    Before moving on, please check if you have up-to-date required dependencies! Sometimes although
    dependent software has been installed, the version might be too old or not up-to-date, causing
    future errors hard to debug.

Check dependencies' versions using commands below::

    # required dependencies:
    datalad --version
    git --version
    git-annex version
    datalad containers-add --version

    # optional dependencies:
    datalad osf-credentials --version


Step 3. Install BABS
============================

Way 1: Install from PyPI (recommended way for end users)
-------------------------------------------------------------

To install BABS from `PyPI <https://pypi.org/project/babs/>`_::

    pip install babs

If you have already installed BABS but now hope to upgrade it::

    pip install --upgrade babs

Way 2: Install from GitHub
-----------------------------

.. warning::

    The version you will install from GitHub might be an unstable version.
    Therefore installing from GitHub is not the recommended way for **end users**,
    unless you're specifically looking for an unstable version
    that's not available on PyPI.

To install BABS from `GitHub <https://github.com/PennLINC/babs>`_::

    git clone https://github.com/PennLINC/babs.git
    cd babs
    pip install .   # for end user

    # You may remove the original source code if you are an end user:
    cd ..
    rm -r babs

If you are a developer, and if there is any update in the source code locally,
you may update the installation with::

    # Suppose you are in root directory of babs source code:
    pip install -e .    # for developer to update

If you are a developer and you'd like to run our ``pytest`` locally, please install BABS in the following way
so that necessary packages for our testing infrastructure will also be installed: ``pip install -e .[tests]``.

Step 4. (Optional) Check BABS version
======================================

You can use command below to check the BABS version you installed::

    pip show babs

.. developer's note: above command works for both installation ways:
..  install from pypi and install from github
