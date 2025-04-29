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
    $ babs update-input-data --dataset-name BIDS

    Added 1 job(s) to process:
        sub_id
    2   sub-0003

You can see that sub-0003 that we created is now in the job status dataframe.
Let's take a look at the analysis directory.
You will see that the already-completed jobs are now present as zip files.
This is because we needed to merge the previous results into the project before we could update the input data.
For very large projects, this can add a lot of zip files and possible make running the next batch of jobs take longer.

..  code-block:: console

    $ ls analysis/
    CHANGELOG.md  README.md  code  containers  inputs  logs  sub-0001_fmriprep_anat-24-1-1.zip  sub-0002_fmriprep_anat-24-1-1.zip

    $ babs status
    Job status:
    There are in total of 3 jobs to complete.

    2 job(s) have been submitted; 1 job(s) haven't been submitted.

    Among submitted jobs,
    2 job(s) successfully finished;
    0 job(s) are pending;
    0 job(s) are running;
    0 job(s) failed.

    All log files are located in folder: ~/babs_demo/my_BABS_project/analysis/logs
 

And to submit our remaining job, we can run:

..  code-block:: console

    $ babs submit
    No jobs in the queue
    Submitting the following jobs:
        sub_id  submitted  is_failed  job_id  task_id state time_used time_limit  nodes  cpus partition name  has_results
    0  sub-0003      False      False       3        1   nan       nan        nan   <NA>  <NA>       nan  nan        False


This job is submitted like any other job. 
When it finishes we see the expected output:

..  code-block:: console

    $ babs status
    Job status:
    There are in total of 3 jobs to complete.

    3 job(s) have been submitted; 0 job(s) haven't been submitted.

    Among submitted jobs,
    3 job(s) successfully finished;
    All jobs are completed!

    All log files are located in folder: ~/babs_demo/my_BABS_project/analysis/logs

And to finalize the new subject we run babs merge:

..  code-block:: console

    $ babs merge

    `babs merge` was successful!
    Deleting merged branches for chunk #1...
    Deleted branch job-3-1-sub-0003 (was a011f3c).

