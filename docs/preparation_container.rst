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

Toy BIDS App
============
We prepared a toy BIDS App that can be used for quick testing. It counts non-hidden files
in a subject's (or a session's) folder. The detailed descriptions can be found
`here <https://github.com/PennLINC/babs_tests/blob/main/docker/README.md>`_.
Its docker image is publicly available on `Docker Hub <https://hub.docker.com/r/pennlinc/toy_bids_app>`_.

How to prepare a container DataLad dataset of BIDS App?
=======================================================

Step 1. Get BIDS App container image
------------------------------------

As the data processing will be performed on a cluster, and usually clusters only accept
Singularity image (but not Docker image), you probably need to build the BIDS App as a Singularity image.
Below is an example of building a Singularity image of toy BIDS App from
`Docker Hub <https://hub.docker.com/r/pennlinc/toy_bids_app>`_:

.. code-block:: console

    toybidsapp_version="0.0.7"   # or the latest tagged version
    toybidsapp_version_dash="0-0-7"   # same version, just in different format: connected by dashes
    singularity build \
        toybidsapp-${toybidsapp_version}.sif \
        docker://pennlinc/toy_bids_app:${toybidsapp_version}

.. _create-a-container-datalad-dataset:

Step 2. Create a container DataLad dataset
------------------------------------------
You may use DataLad command ``datalad containers-add`` to add the built Singularity image
(sif file) of BIDS App to a DataLad dataset:

.. code-block:: console

    datalad create -D "Note about the container" toybidsapp-container
    cd toybidsapp-container
    datalad containers-add \
        --url /full/path/to/toybidsapp-${toybidsapp_version}.sif \
        toybidsapp-${toybidsapp_version_dash}

Note the last argument is the *image NAME* in the container DataLad dataset.
This string can only have characters and dashes in it.
Remember what you assign as the *image NAME* because you will copy it for argument
``--container_ds`` when ``babs init``.

(Optional) Step 3. Delete the original sif file
-----------------------------------------------
Lastly, as you have copied the sif file into this container DataLad dataset,
you can delete the original sif file:

.. code-block:: console

    rm /full/path/to/toybidsapp-${toybidsapp_version}.sif


.. Note: above steps have been tested on CUBIC cluster. CZ 4/3/2023.

References
==========
For more details, please refer to:

* ``datalad containers-add``'s command-line interface: `DataLad documentation <http://docs.datalad.org/projects/container/en/latest/generated/man/datalad-containers-add.html>`_
* `DataLad Handbook: containers <https://handbook.datalad.org/en/latest/basics/101-133-containersrun.html>`_.

.. [Gorgolewski2017] Gorgolewski, K. J., Alfaro-Almagro, F., Auer, T., Bellec, P., Capotă, M., Chakravarty, M. M., Churchill, N. W., Cohen, A. L.,
   Craddock, R. C., Devenyi, G. A., Eklund, A., Esteban, O., Flandin, G., Ghosh, S. S., Guntupalli, J. S., Jenkinson, M., Keshavan, A., Kiar, G.,
   Liem, F., … Poldrack, R. A. (2017). BIDS apps: Improving ease of use, accessibility, and reproducibility of neuroimaging data analysis methods.
   PLoS Computational Biology, 13(3), e1005209. https://doi.org/10.1371/journal.pcbi.1005209
