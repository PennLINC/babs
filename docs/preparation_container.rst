***************************************************
Prepare containerized BIDS App as a DataLad dataset
***************************************************

Understand the concept "container DataLad dataset"
==================================================
BIDS Apps, by definition, are container images that process BIDS-formatted datasets [Gorgolewski2017]_.
Besides input BIDS datasets, BABS also requires BIDS App container to be in a *DataLad dataset*.
It's a bit hard at first to understand
the concept of "container DataLad dataset" - why container is a dataset now?
Here, "DataLad dataset" is a DataLad concept: "a dataset" means "a collection of files in folders",
and this "DataLad dataset" is version tracked by DataLad. So "container DataLad dataset" means "a collection of
container image(s) in a folder tracked by DataLad".

Within that dataset, each image is *registered* under a name with
`datalad-container <http://docs.datalad.org/projects/container/>`_.
BABS reads the registration to find the image file, so the image can live anywhere
in the dataset: ``babs init`` takes the dataset path (``--container_ds``) and the
registered name (``--container_name``), and resolves the rest.

There are two ways to get such a dataset.
The first is the quickest, and covers most published BIDS Apps.

.. _use-repronim-containers:

Option 1. Use ReproNim/containers
=================================
`ReproNim/containers <https://github.com/ReproNim/containers>`_ is a DataLad dataset
of ready-to-use Singularity images of BIDS Apps (fMRIPrep, QSIPrep, MRIQC, ...),
one registration per app, versioned, and maintained by the ReproNim team.
It is a container DataLad dataset with nothing to build, and its URL can be given
to ``babs init`` directly:

.. code-block:: console

    babs init \
        --container_ds https://github.com/ReproNim/containers.git \
        --container_name bids-fmriprep \
        ...

``babs init`` clones it into the BABS project, and the jobs fetch the image
when they first need it.
The registered names follow the pattern ``bids-<app>`` (``bids-fmriprep``, ``bids-qsiprep``, ``bids-mriqc``);
the full list is what ``datalad containers-list`` prints in a clone of the dataset (see below).

If you will create more than one BABS project, if your compute nodes have no
internet access, or if you need a version other than the newest,
clone it once and pass the clone's path instead:

.. code-block:: console

    datalad clone https://github.com/ReproNim/containers.git containers
    cd containers
    datalad containers-list
    datalad get images/bids/bids-fmriprep--25.2.5.sif

The images are annexed, so the clone holds only pointers until ``datalad get``.
Getting the image you need there means every BABS project made from this clone
copies it locally rather than downloading it again.

.. dropdown:: Messages about ``annex-ignore`` when cloning?

    ``datalad clone`` may print
    ``Remote origin not usable by git-annex; setting annex-ignore``
    a few times. GitHub hosts the git part of the dataset only; the image content
    comes from ReproNim's own storage, which ``datalad get`` finds on its own.
    These messages are harmless.

Either way, pass the dataset (URL or clone path) as ``--container_ds`` and the
registered name as ``--container_name`` when running ``babs init``
(see :doc:`babs-init` for a full example).

.. note::

    **Versions.** ReproNim/containers keeps many versions of each app under ``images/``
    (``bids-fmriprep--24.1.1.sing``, ``bids-fmriprep--25.2.5.sif``, ...), but a name
    is registered once and points at one of them; ``datalad containers-list`` shows which.
    To have ``bids-fmriprep`` point at another version, run the dataset's
    ``scripts/freeze_versions`` in your clone, for example
    ``scripts/freeze_versions bids-fmriprep=24.1.1``, before ``babs init``.
    See `Freezing Container Image Versions <https://github.com/ReproNim/containers#freezing-container-image-versions>`_
    in the ReproNim/containers README.

If the BIDS App you need is not in ReproNim/containers, or you need a version it does not carry,
build your own dataset instead.

.. _build-your-own-container-dataset:

Option 2. Build your own container DataLad dataset
==================================================

Toy BIDS App
------------
We prepared a toy BIDS App that can be used for quick testing. It counts non-hidden files
in a subject's (or a session's) folder. The detailed descriptions can be found
`here <https://github.com/PennLINC/babs_tests/blob/main/docker/README.md>`_.

Step 1. Get BIDS App container image
------------------------------------

As the data processing will be performed on a cluster, and usually clusters only accept
Singularity image (but not Docker image), you probably need to build the BIDS App as a Singularity image.
Below is an example of building a Singularity image of SIMBIDS from
`Docker Hub <https://hub.docker.com/r/pennlinc/simbids>`_:

.. code-block:: console

    simbids_version="0.0.3"
    simbids_version_dash="0-0-3"
    singularity build \
        simbids-${simbids_version}.sif \
        docker://pennlinc/simbids:${simbids_version}

.. _create-a-container-datalad-dataset:

Step 2. Create a container DataLad dataset
------------------------------------------
You may use DataLad command ``datalad containers-add`` to add the built Singularity image
(sif file) of the BIDS App to a DataLad dataset:

.. code-block:: console

    datalad create -D "SIMBIDS dataset" simbids-container
    cd simbids-container
    datalad containers-add \
        --url /full/path/to/simbids-${simbids_version}.sif \
        simbids-${simbids_version_dash}

Note the last argument is the *image NAME* in the container DataLad dataset.
This string can only have characters and dashes in it.
Remember what you assign as the *image NAME* because you will copy it for argument
``--container_name`` when ``babs init``.

From here on it is used exactly like a ReproNim/containers clone:
the dataset is ``--container_ds`` and the *image NAME* is ``--container_name``.

.. Note: above steps have been tested on CUBIC cluster. MC 4/16/2025.

References
==========
For more details, please refer to:

* `ReproNim/containers <https://github.com/ReproNim/containers>`_ and its README, for the list of available BIDS Apps
* ``datalad containers-add``'s command-line interface: `DataLad documentation <http://docs.datalad.org/projects/container/en/latest/generated/man/datalad-containers-add.html>`_
* `DataLad Handbook: containers <https://handbook.datalad.org/en/latest/basics/101-133-containersrun.html>`_.

.. [Gorgolewski2017] Gorgolewski, K. J., Alfaro-Almagro, F., Auer, T., Bellec, P., Capotă, M., Chakravarty, M. M., Churchill, N. W., Cohen, A. L.,
   Craddock, R. C., Devenyi, G. A., Eklund, A., Esteban, O., Flandin, G., Ghosh, S. S., Guntupalli, J. S., Jenkinson, M., Keshavan, A., Kiar, G.,
   Liem, F., … Poldrack, R. A. (2017). BIDS apps: Improving ease of use, accessibility, and reproducibility of neuroimaging data analysis methods.
   PLoS Computational Biology, 13(3), e1005209. https://doi.org/10.1371/journal.pcbi.1005209
