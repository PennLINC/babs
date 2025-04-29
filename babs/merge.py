import math
import os.path as op
import re
import shutil
import subprocess
import warnings

import datalad.api as dlapi

from babs.base import BABS
from babs.utils import get_git_show_ref_shasum


class BABSMerge(BABS):
    """BABSMerge is for merging results and provenance from finished jobs."""

    def babs_merge(self, chunk_size=1000, trial_run=False):
        """
        This function merges results and provenance from all successfully finished jobs.

        Parameters
        ----------
        chunk_size: int
            Number of branches in a chunk when merging at a time.
        trial_run: bool
            Whether to run as a trial run which won't push the merging actions back to output RIA.
            This option should only be used by developers for testing purpose.
        """

        # First, make sure all the results branches are reflected in the results dataframe
        self._update_results_status()

        warning_encountered = False
        self.wtf_key_info()  # get `self.analysis_dataset_id`
        # path to `merge_ds`:
        merge_ds_path = op.join(self.project_root, 'merge_ds')

        if op.exists(merge_ds_path):
            raise Exception(
                "Folder 'merge_ds' already exists. `babs merge` won't proceed."
                " If you're sure you want to rerun `babs merge`,"
                ' please remove this folder before you rerun `babs merge`.'
                " Path to 'merge_ds': '" + merge_ds_path + "'. "
            )

        # Define (potential) text files:
        #   in 'merge_ds/code' folder
        #   as `merge_ds` should not exist at the moment,
        #   no need to check existence/remove these files.
        # define path to text file of invalid job list exists:
        fn_list_invalid_jobs = op.join(merge_ds_path, 'code', 'list_invalid_job_when_merging.txt')
        # define path to text file of files with missing content:
        fn_list_content_missing = op.join(merge_ds_path, 'code', 'list_content_missing.txt')
        # define path to printed messages from `git annex fsck`:
        # ^^ this will be absolutely used if `babs merge` does not fail:
        fn_msg_fsck = op.join(merge_ds_path, 'code', 'log_git_annex_fsck.txt')

        # Clone output RIA to `merge_ds`:
        print("Cloning output RIA to 'merge_ds'...")
        # get the path to output RIA:
        #   'ria+file:///path/to/BABS_project/output_ria#0000000-000-xxx-xxxxxxxx'
        output_ria_source = self.output_ria_url + '#' + self.analysis_dataset_id
        # clone: `datalad clone ${outputsource} merge_ds`
        dlapi.clone(source=output_ria_source, path=merge_ds_path)

        # List all branches in output RIA:
        print('\nListing all branches in output RIA...')
        list_branches_jobs = self._get_results_branches()

        if len(list_branches_jobs) == 0:
            raise ValueError(
                'There is no successfully finished job yet. Please run `babs submit` first.'
            )

        # Find all valid branches (i.e., those with results --> have different SHASUM):
        print('\nFinding all valid job branches to merge...')
        # get default branch's name: master or main:
        #   `git remote show origin | sed -n '/HEAD branch/s/.*: //p'`
        proc_git_remote_show_origin = subprocess.run(
            ['git', 'remote', 'show', 'origin'],
            cwd=merge_ds_path,
            stdout=subprocess.PIPE,
        )
        proc_git_remote_show_origin.check_returncode()
        msg = proc_git_remote_show_origin.stdout.decode('utf-8')
        # e.g., '... HEAD branch: master\n....': search between 'HEAD branch: ' and '\n':
        temp = re.search('HEAD branch: ' + '(.+?)' + '\n', msg)
        if temp:  # not empty:
            default_branch_name = temp.group(1)  # what's between those two keywords
            # another way: `default_branch_name = msg.split("HEAD branch: ")[1].split("\n")[0]`
        else:
            raise Exception('There is no HEAD branch in output RIA!')
        print("Git default branch's name of output RIA is: '" + default_branch_name + "'")

        # get current git commit SHASUM before merging as a reference:
        git_ref, _ = get_git_show_ref_shasum(default_branch_name, merge_ds_path)

        # check if each job branch has a new commit
        #   that's different from current git commit SHASUM (`git_ref`):
        list_branches_no_results = []
        list_branches_with_results = []
        for branch_job in list_branches_jobs:
            # get the job's `git show-ref`:
            git_ref_branch_job, _ = get_git_show_ref_shasum(branch_job, merge_ds_path)
            if git_ref_branch_job == git_ref:  # no new commit --> no results in this branch
                list_branches_no_results.append(branch_job)
            else:  # has results:
                list_branches_with_results.append(branch_job)

        # check if there is any valid job (with results):
        if len(list_branches_with_results) == 0:  # empty:
            raise Exception(
                'There is no job branch in output RIA that has results yet,'
                ' i.e., there is no successfully finished job yet.'
                ' Please run `babs submit` first.'
            )

        # check if there is invalid job (without results):
        if len(list_branches_no_results) > 0:  # not empty
            # save to a text file:
            #   note: this file has been removed at the beginning of babs_merge() if it existed)
            warning_encountered = True
            warnings.warn(
                'There are invalid job branch(es) in output RIA,'
                ' and these job(s) do not have results.'
                ' The list of such invalid jobs will be saved to'
                " the following text file: '" + fn_list_invalid_jobs + "'."
                ' Please review it.',
                stacklevel=2,
            )
            with open(fn_list_invalid_jobs, 'w') as f:
                f.write('\n'.join(list_branches_no_results))
                f.write('\n')  # add a new line at the end
        # NOTE to developers: when testing ^^:
        #   You can `git branch job-test` in `output_ria/000/000-000` to make a fake branch
        #       that has the same SHASUM as master branch's
        #       then you should see above warning.
        #   However, if you finish running `babs merge`, this branch `job-test` will have
        #       a *different* SHASUM from master's, making it a "valid" job now.
        #   To continue testing above warning, you need to delete this branch:
        #       `git branch --delete job-test` in `output_ria/000/000-000`
        #       then re-create a new one: `git branch job-test`

        # Merge valid branches chunk by chunk:
        print('\nMerging valid job branches chunk by chunk...')
        print('Total number of job branches to merge = ' + str(len(list_branches_with_results)))
        print(f'Chunk size (number of job branches per chunk) = {chunk_size}')

        # Split into chunks of size chunk_size
        num_chunks = math.ceil(len(list_branches_with_results) / chunk_size)
        print(f'--> Number of chunks = {num_chunks}')
        all_chunks = [
            list_branches_with_results[i : i + chunk_size]
            for i in range(0, len(list_branches_with_results), chunk_size)
        ]
        # ^^ e.g., [['1', '7', '0'], ['6', '2'], ['5', '6']]

        # iterate across chunks:
        for i_chunk in range(0, num_chunks):
            print(
                'Merging chunk #'
                + str(i_chunk + 1)
                + ' (total of '
                + str(num_chunks)
                + ' chunk[s] to merge)...'
            )
            the_chunk = all_chunks[i_chunk]  # e.g., array(['a', 'b', 'c'])
            # join all branches in this chunk:
            joined_by_space = ' '.join(the_chunk)  # e.g., 'a b c'
            # command to run:
            commit_msg = 'merge results chunk ' + str(i_chunk + 1) + '/' + str(num_chunks)
            # ^^ okay to not to be quoted,
            #   as in `subprocess.run` this is a separate element in the `cmd` list

            # Prepend 'origin/' to each branch name
            remote_branches = ['origin/' + branch for branch in joined_by_space.split(' ')]
            cmd = ['git', 'merge', '-m', commit_msg] + remote_branches
            proc_git_merge = subprocess.run(cmd, cwd=merge_ds_path, capture_output=True, text=True)
            if proc_git_merge.returncode != 0:
                print(f'Git merge failed with error:\n{proc_git_merge.stderr}')
                proc_git_merge.check_returncode()
            print(proc_git_merge.stdout)

        # Push merging actions back to output RIA:
        if trial_run:
            print('')  # new empty line
            warnings.warn(
                '`--trial-run` was requested, not to push merging actions to output RIA.',
                stacklevel=2,
            )
            print('\n`babs merge` did not fully finish yet!')
            return

        print('\nPushing merging actions to output RIA...')
        # `git push`:
        proc_git_push = subprocess.run(['git', 'push'], cwd=merge_ds_path, stdout=subprocess.PIPE)
        proc_git_push.check_returncode()
        print(proc_git_push.stdout.decode('utf-8'))

        # Get file availability information: which is very important!
        # `git annex fsck --fast -f output-storage`:
        #   `git annex fsck` = file system check
        #   We've done the git merge of the symlinks of the files,
        #   now we need to match the symlinks with the data content in `output-storage`.
        #   `--fast`: just use the existing MD5, not to re-create a new one
        proc_git_annex_fsck = subprocess.run(
            ['git', 'annex', 'fsck', '--fast', '-f', 'output-storage'],
            cwd=merge_ds_path,
            stdout=subprocess.PIPE,
        )
        proc_git_annex_fsck.check_returncode()
        # if printing the returned msg,
        #   will be a long list of "fsck xxx.zip (fixing location log) ok"
        #   or "fsck xxx.zip ok"
        # instead, save it into a text file:
        with open(fn_msg_fsck, 'w') as f:
            f.write(
                '# Below are printed messages from `git annex fsck --fast -f output-storage`:\n\n'
            )
            f.write(proc_git_annex_fsck.stdout.decode('utf-8'))
            f.write('\n')
        # now we can delete `proc_git_annex_fsck` to save memory:
        del proc_git_annex_fsck

        # Double check: there should not be file content that's not in `output-storage`:
        #   This should not print anything - we never has this error before
        # `git annex find --not --in output-storage`
        proc_git_annex_find_missing = subprocess.run(
            ['git', 'annex', 'find', '--not', '--in', 'output-storage'],
            cwd=merge_ds_path,
            stdout=subprocess.PIPE,
        )
        proc_git_annex_find_missing.check_returncode()
        msg = proc_git_annex_find_missing.stdout.decode('utf-8')
        # `msg` should be empty:
        if msg != '':  # if not empty:
            # save into a file:
            with open(fn_list_content_missing, 'w') as f:
                f.write(msg)
                f.write('\n')
            raise Exception(
                'Unable to find file content for some file(s).'
                " The information has been saved to this text file: '"
                + fn_list_content_missing
                + "'."
            )

        # `git annex dead here`:
        #   stop tracking clone `merge_ds`,
        #   i.e., not to get data from this `merge_ds` sibling:
        proc_git_annex_dead_here = subprocess.run(
            ['git', 'annex', 'dead', 'here'],
            cwd=merge_ds_path,
            stdout=subprocess.PIPE,
        )
        proc_git_annex_dead_here.check_returncode()
        print(proc_git_annex_dead_here.stdout.decode('utf-8'))

        # Final `datalad push` to output RIA:
        # `datalad push --data nothing`:
        #   pushing to `git` branch in output RIA: has done with `git push`;
        #   pushing to `git-annex` branch in output RIA: hasn't done after `git annex fsck`
        #   `--data nothing`: don't transfer data from this local annex `merge_ds`
        proc_datalad_push = subprocess.run(
            ['datalad', 'push', '--data', 'nothing'],
            cwd=merge_ds_path,
            stdout=subprocess.PIPE,
        )
        proc_datalad_push.check_returncode()
        print(proc_datalad_push.stdout.decode('utf-8'))

        # Done:
        if warning_encountered:
            print(
                '\n`babs merge` has finished but had warning(s)!'
                ' Please check out the warning message(s) above!'
            )
        else:
            print('\n`babs merge` was successful!')

        # delete the merge_ds folder
        shutil.rmtree(merge_ds_path)

        # Delete all the merged branches from the output RIA
        for n_chunk, chunk in enumerate(all_chunks):
            print(f'Deleting merged branches for chunk #{n_chunk + 1}...')
            proc_git_branch_delete = subprocess.run(
                ['git', 'branch', '--delete'] + chunk,
                cwd=self.output_ria_data_dir,
                stdout=subprocess.PIPE,
            )
            proc_git_branch_delete.check_returncode()
            print(proc_git_branch_delete.stdout.decode('utf-8'))
