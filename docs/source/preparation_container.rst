Prepare containerized BIDS App
=================================
As the data processing will be performed on a cluster, and usually clusters only accept Singularity image (but not Docker image), you may need to pull the BIDS App as a Singularity image.

BABS also requires BIDS App to be a DataLad dataset. You may use DataLad command ``datalad containers-add`` to add a containerized BIDS App to a DataLad dataset. For more details, please refer to `this command's documentation <http://docs.datalad.org/projects/container/en/latest/generated/man/datalad-containers-add.html>`_ and `DataLad Handbook <https://handbook.datalad.org/en/latest/basics/101-133-containersrun.html>`_.



