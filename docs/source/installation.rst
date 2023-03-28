**********************
Installation
**********************

Prepare a conda environment for BABS
=====================================

After installing conda, let's initiate a conda environment (e.g., named ``babs``) for running BABS::

    conda create -n babs python=3.9.12
    conda activate babs

Install dependent software
================================

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
Besides required software listed above,
if your input DataLad dataset is on OSF, you also need to install ``datalad-osf``::

    # Install datalad-osf:
    pip install datalad-osf

    # Provide your OSF credentials (token) - this step is very important!
    datalad osf-credentials


Installation reference
---------------------------

- ``DataLad``, ``Git``, and ``git-annex``: https://handbook.datalad.org/en/latest/intro/installation.html
- ``datalad-container``: https://github.com/datalad/datalad-container
- (optional) ``datalad-osf``: http://docs.datalad.org/projects/osf/en/latest/settingup.html





Install BABS
============================

Currently we only support installing BABS from GitHub::

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

If you are a developer and you'd like to run ``pytest`` locally, please install BABS in the following way
so that necessary packages for pytest will also be installed: ``pip install -e .[tests]``.
