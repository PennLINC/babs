"""This is the main module."""

import os
import os.path as op
import time
from urllib.parse import urlparse

from babs.base import BABS
from babs.constants import CHECK_MARK
from babs.scheduler import (
    request_all_job_status,
    submit_one_test_job,
)
from babs.utils import (
    compare_repo_commit_hashes,
    get_immediate_subdirectories,
    print_versions_from_yaml,
    read_yaml,
)


class BABSCheckSetup(BABS):
    """The BABS class is for babs projects of BIDS Apps"""

    def babs_check_setup(self, submit_a_test_job):
        """
        This function validates the setup by babs init.

        Parameters
        ----------
        submit_a_test_job: bool
            Whether to submit and run a test job.
        """
        babs_proj_config = read_yaml(self.config_path, use_filelock=True)

        print('Checking setup of BABS project located at: ' + self.project_root)
        if submit_a_test_job:
            print('Will submit a test job for testing; will take longer time.')
        else:
            print('Did not request `--job-test`; will not submit a test job.')

        # Print out the saved configuration info: ----------------
        print(
            'Below is the configuration information saved during `babs init`'
            " in file 'analysis/code/babs_proj_config.yaml':\n"
        )
        with open(op.join(self.analysis_path, 'code/babs_proj_config.yaml')) as f:
            file_contents = f.read()
        print(file_contents)

        # Check the project itself: ---------------------------
        print('Checking the BABS project itself...')
        if not op.exists(self.analysis_path):
            raise FileNotFoundError(
                "Folder 'analysis' does not exist in this BABS project!"
                ' Current path to analysis folder: ' + self.analysis_path
            )
        print(CHECK_MARK + ' All good!')

        # Check `analysis` datalad dataset: ----------------------
        print("\nCheck status of 'analysis' DataLad dataset...")
        # Are there anything unsaved? ref: CuBIDS function
        analysis_statuses = {
            status['state']
            for status in self.analysis_datalad_handle.status(eval_subdataset_state='commit')
        }

        # statuses should be all "clean", without anything else e.g., "modified":
        if not analysis_statuses == {'clean'}:
            problem_statuses = [
                status
                for status in self.analysis_datalad_handle.status(eval_subdataset_state='commit')
                if status['state'] != 'clean'
            ]
            raise ValueError(
                "Analysis DataLad dataset's status is not clean. "
                'Consider running `babs sync-code` to save any edited code. '
                'There are the following issues:' + str(problem_statuses)
            )

        print(CHECK_MARK + ' All good!')

        # Check input dataset(s): ---------------------------
        print('\nChecking input dataset(s)...')
        # check if there is at least one folder in the `inputs/data` dir:
        temp_list = get_immediate_subdirectories(op.join(self.analysis_path, 'inputs/data'))
        if not temp_list:
            raise ValueError(
                "There is no sub-directory (i.e., no input dataset) in 'inputs/data'!"
                " Full path to folder 'inputs/data': " + op.join(self.analysis_path, 'inputs/data')
            )

        # check each input ds:
        for idx, in_ds in enumerate(self.input_datasets):
            abs_path = in_ds.babs_project_analysis_path
            dataset_name = in_ds.name

            # check if the dir of this input ds exists:
            if not op.exists(abs_path):
                raise FileNotFoundError(
                    f'The path to the cloned input dataset #{idx + 1} '
                    f"'{dataset_name}' does not exist: {abs_path}"
                )

            # check if dir of input ds is a datalad dataset:
            if not op.exists(op.join(abs_path, '.datalad/config')):
                raise ValueError(
                    f'The input dataset #{idx + 1} '
                    f"'{dataset_name}' is not a valid DataLad dataset:"
                    f" There is no file '.datalad/config' in its directory: {abs_path}"
                )
        print(CHECK_MARK + ' All good!')

        # Check container datalad dataset: ---------------------------
        print('\nChecking container datalad dataset...')
        folder_container = op.join(self.analysis_path, 'containers')

        # Check if this is a pipeline configuration
        if self.pipeline is not None:
            print(f'Checking {len(self.pipeline)} containers in pipeline...')
            for i, step in enumerate(self.pipeline):
                step_container_name = step['container_name']
                print(f'  Checking container {i + 1}/{len(self.pipeline)}: {step_container_name}')
                container_path = op.join(
                    folder_container, '.datalad/environments', step_container_name, 'image'
                )
                if not op.exists(container_path):
                    raise FileNotFoundError(
                        f'Container {step_container_name} not found at: {container_path}'
                    )
            container_name = self.pipeline[0]['container_name']  # Use first for compatibility
        else:
            container_name = babs_proj_config['container']['name']
            # assert it's a datalad ds in `containers` folder:
            if not op.exists(op.join(folder_container, '.datalad/config')):
                raise FileNotFoundError(
                    'There is no containers DataLad dataset in folder: ' + folder_container
                )
        print(CHECK_MARK + ' All good!')

        # Check `analysis/code`: ---------------------------------
        print('\nChecking `analysis/code/` folder...')
        # folder `analysis/code` should exist:
        if not op.exists(op.join(self.analysis_path, 'code')):
            raise FileNotFoundError("Folder 'code' does not exist in 'analysis' folder!")

        # assert the list of files in the `code` folder,
        #   and bash files should be executable:
        if self.pipeline is not None:
            list_files_code = [
                'babs_proj_config.yaml',
                'pipeline_zip.sh',  # Pipeline uses unified script
                'participant_job.sh',
                'submit_job_template.yaml',
            ]
        else:
            list_files_code = [
                'babs_proj_config.yaml',
                container_name + '_zip.sh',
                'participant_job.sh',
                'submit_job_template.yaml',
            ]
        if self.processing_level == 'subject':
            list_files_code.append('processing_inclusion.csv')
        else:
            list_files_code.append('processing_inclusion.csv')

        for temp_filename in list_files_code:
            temp_fn = op.join(self.analysis_path, 'code', temp_filename)
            # the file should exist:
            if not op.isfile(temp_fn):
                raise FileNotFoundError(
                    "Required file '"
                    + temp_filename
                    + "' does not exist"
                    + " in 'analysis/code' folder in this BABS project!"
                )
            # check if bash files are executable:
            if op.splitext(temp_fn)[1] == '.sh':  # extension is '.sh':
                if not os.access(temp_fn, os.X_OK):
                    raise PermissionError('This code file should be executable: ' + temp_fn)
        print(CHECK_MARK + ' All good!')

        # Check input and output RIA: ----------------------
        print('\nChecking input and output RIA...')

        # check if they are siblings of `analysis`:
        actual_output_ria_data_dir = urlparse(
            os.readlink(op.join(self.output_ria_path, 'alias/data'))
        ).path  # get the symlink of `alias/data` then change to path
        if not op.exists(actual_output_ria_data_dir):
            raise FileNotFoundError(
                'The output RIA data directory does not exist: ' + actual_output_ria_data_dir
            )
        # get '000/0000-0000-0000-0000':
        data_foldername = op.join(
            op.basename(op.dirname(actual_output_ria_data_dir)),
            op.basename(actual_output_ria_data_dir),
        )
        # input_ria:
        actual_input_ria_data_dir = op.join(self.input_ria_path, data_foldername)
        if not op.exists(actual_input_ria_data_dir):
            raise FileNotFoundError(
                'The input RIA data directory does not exist: ' + actual_input_ria_data_dir
            )

        print("\tDatalad dataset `analysis`'s siblings:")
        analysis_siblings = self.analysis_datalad_handle.siblings(action='query')
        has_sibling_input = False
        has_sibling_output = False
        for i_sibling in range(0, len(analysis_siblings)):
            the_sibling = analysis_siblings[i_sibling]
            if the_sibling['name'] == 'output':  # output ria:
                has_sibling_output = True
                if the_sibling['url'] != actual_output_ria_data_dir:
                    raise ValueError(
                        "The `analysis` datalad dataset's sibling 'output' url does not match"
                        ' the path to the output RIA.'
                        ' Former = ' + the_sibling['url'] + ';'
                        ' Latter = ' + actual_output_ria_data_dir
                    )
            if the_sibling['name'] == 'input':  # input ria:
                has_sibling_input = True

        if not has_sibling_input:
            raise ValueError(
                "Did not find a sibling of 'analysis' DataLad dataset"
                " that's called 'input'. There may be something wrong when"
                ' setting up input RIA!'
            )
        if not has_sibling_output:
            raise ValueError(
                "Did not find a sibling of 'analysis' DataLad dataset"
                " that's called 'output'. There may be something wrong when"
                ' setting up output RIA!'
            )

        # check that our RIAs are in sync:
        compare_repo_commit_hashes(
            self.analysis_path,
            actual_input_ria_data_dir,
            'analysis',
            'input RIA',
        )

        compare_repo_commit_hashes(
            self.analysis_path,
            actual_output_ria_data_dir,
            'analysis',
            'output RIA',
        )
        print(CHECK_MARK + ' All good!')

        # Submit a test job (if requested) --------------------------------
        if not submit_a_test_job:
            print(
                '\n'
                " We recommend running a test job with `--job-test` if you haven't done so;"
                ' It will gather setup information in the designated environment'
                ' and make sure future BABS jobs with current setup'
                ' will be able to finish successfully.'
            )
            print('\n`babs check-setup` was successful! ')
        else:
            self._submit_test_job()

    def _submit_test_job(self):
        print('\nSubmitting test job(s), will take a while to finish...')
        print(
            'Although the script will be submitted to a compute node,'
            ' this test job will not run the BIDS App;'
            ' instead, this test job will gather setup information'
            ' in the designated environment'
            ' and make sure future BABS jobs with the current setup'
            ' will be able to finish successfully.'
        )

        if self.pipeline is not None:
            # Test all containers in the pipeline
            print(f'Testing {len(self.pipeline)} containers in pipeline...')
            for i, step in enumerate(self.pipeline):
                step_container_name = step['container_name']
                print(f'\nTesting container {i + 1}/{len(self.pipeline)}: {step_container_name}')

                # Submit test job for this specific container
                step_check_setup = op.join(
                    self.analysis_path, 'code/check_setup', f'step_{i + 1}_{step_container_name}'
                )
                job_id = submit_one_test_job(step_check_setup, self.queue)

                # Wait for job completion
                job_status = new_job_status = request_all_job_status(self.queue, job_id)
                sleeptime = 0
                while not new_job_status.empty:
                    sleeptime += 1
                    time.sleep(sleeptime)
                    job_status = new_job_status.copy()
                    new_job_status = request_all_job_status(self.queue, job_id)

                if not job_status.shape[0] == 1:
                    raise Exception(
                        f'Expected 1 job for {step_container_name}, got {job_status.shape[0]}'
                    )

                test_info = job_status.iloc[0].to_dict()
                stdout_path = op.join(
                    self.analysis_path,
                    'logs',
                    f'{test_info["name"]}.o{test_info["job_id"]}_{test_info["task_id"]}',
                )

                if not op.exists(stdout_path):
                    raise FileNotFoundError(
                        f'The test job for {step_container_name} failed to produce an output log.'
                    )

                # Check environment for this container
                fn_check_env_yaml = op.join(step_check_setup, 'check_env.yaml')
                if op.exists(fn_check_env_yaml):
                    flag_writable, flag_all_installed = print_versions_from_yaml(fn_check_env_yaml)
                    if not flag_writable:
                        raise Exception(
                            f'The designated workspace is not writable for {step_container_name}!'
                            ' Please change it in the YAML file'
                            ' used in `babs init --container-config`,'
                            ' then rerun `babs init` with updated YAML file.'
                        )
                    if not flag_all_installed:
                        raise Exception(
                            f'Some required package(s) were not installed for '
                            f'{step_container_name} in the designated environment!'
                            ' Please install them in the designated environment,'
                            ' or change the designated environment you hope to use'
                            ' in `--container-config` and rerun `babs init`!'
                        )
                    print(f'{CHECK_MARK} All good in test job for {step_container_name}!')
        else:
            # Single container case
            job_id = submit_one_test_job(self.analysis_path, self.queue)
            job_status = new_job_status = request_all_job_status(self.queue, job_id)

            # Check until the job is out of the queue:
            sleeptime = 0
            while not new_job_status.empty:
                sleeptime += 1
                time.sleep(sleeptime)
                job_status = new_job_status.copy()
                new_job_status = request_all_job_status(self.queue, job_id)

            if not job_status.shape[0] == 1:
                raise Exception(f'Expected 1 job, got {job_status.shape[0]}')

            test_info = job_status.iloc[0].to_dict()

            stdout_path = op.join(
                self.analysis_path,
                'logs',
                f'{test_info["name"]}.o{test_info["job_id"]}_{test_info["task_id"]}',
            )

            if not op.exists(stdout_path):
                raise FileNotFoundError('The test job failed to produce an output log.')

            # go thru `code/check_setup/check_env.yaml`: check if anything wrong:
            fn_check_env_yaml = op.join(self.analysis_path, 'code/check_setup', 'check_env.yaml')
            flag_writable, flag_all_installed = print_versions_from_yaml(fn_check_env_yaml)
            if not flag_writable:
                raise Exception(
                    'The designated workspace is not writable!'
                    ' Please change it in the YAML file'
                    ' used in `babs init --container-config`,'
                    ' then rerun `babs init` with updated YAML file.'
                )
                # NOTE: ^^ currently this is not aligned with YAML file sections;
                # this will make more sense after adding section of workspace path in YAML file
            if not flag_all_installed:
                raise Exception(
                    'Some required package(s) were not installed'
                    ' in the designated environment!'
                    ' Please install them in the designated environment,'
                    ' or change the designated environment you hope to use'
                    ' in `--container-config` and rerun `babs init`!'
                )

            print(
                'Please check if above versions are the ones you hope to use!'
                ' If not, please change the version in the designated environment,'
                ' or change the designated environment you hope to use'
                ' in `--container-config` and rerun `babs init`.'
            )
            print(f'{CHECK_MARK} All good in test job!')

        print('\n`babs check-setup` was successful! ')
