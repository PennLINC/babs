******************************
Handling changes in input data
******************************

.. contents:: Table of Contents


What happens if the input data changes?
=======================================

We often run BABS on a dataset, only to find that there are more data available.
Or maybe some of the images or metadata need to be changed.
This presents a problem for BABS because we need to have specific commits in the git history
that correspond to changes in the input data - otherwise we can run into merge conflicts.
While it **is** possible to make changes to the input data after the BABS project has been created,
we discourage it because it makes the sharing of the results more difficult.
Specifically, 
the input data needs to have objects in the git annex that may not be present in updated input data.

Changes in the input data need to be incorporated into the BABS project and synced to the remote datasets.
The list of completed subjects/sessions also needs to be updated to reflect the updated input data.
We added the ``babs update-input-data`` command to help with this process. 

Follow the example walkthrough until all the jobs are finished and merged.
Specifically, you should see the following message:


..  code-block:: console

    `babs merge` was successful!




Adding another session
----------------------

You may have noticed that sub-0002 only has one session, ses-01.
Let's add ses-02 to the input data and see how BABS handles it.

..  code-block:: console

    $ cd ~/babs_demo/simbids/
    $ cp -r --preserve=links sub-0002 sub-0003
    $ find sub-0003 -depth -name "*sub-0002*" -execdir sh -c 'mv "$1" "$(echo "$1" | sed "s/sub-0002/sub-0003/g")"' sh {} \;
    $ datalad save -m "Add sub-0003 to simbids"

Now we've changed the input data in its original location.
We need to make this change in the BABS project as well.

..  code-block:: console

    $ cd ~/babs_demo/my_BABS_project
    $ datalad update-input-data --dataset-name BIDS

