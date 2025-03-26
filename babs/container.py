import os
import os.path as op
import warnings
from importlib import resources

import yaml
from jinja2 import Environment, PackageLoader, StrictUndefined

from babs.generate_bidsapp_runscript import generate_bidsapp_runscript
from babs.generate_submit_script import generate_submit_script, generate_test_submit_script
from babs.utils import app_output_settings_from_config


class Container:
    """This class is for the BIDS App Container"""

    def __init__(self, container_ds, container_name, config_yaml_file):
        """
        This is to initialize Container class.

        Parameters
        ----------
        container_ds: str
            The path to the container datalad dataset as the input of `babs init`.
            This container datalad ds is prepared by the user.
        container_name: str
            The name of the container when adding to datalad dataset(e.g., `NAME` in
            `datalad containers-add NAME`),
             e.g., fmriprep-0-0-0
        config_yaml_file: str
            The YAML file that contains the configurations of how to run the container

        Attributes
        ----------
        container_ds: str
            The path to the container datalad dataset as the input of `babs init`.
            This container datalad ds is prepared by the user, not the cloned one.
        container_name: str
            The name of the container when adding to datalad dataset(e.g., `NAME` in
            `datalad containers-add NAME`),
             e.g., fmriprep-0-0-0
        config_yaml_file: str
            The YAML file that contains the configurations of how to run the container
            This is optional argument (of the CLI `babs init`)
        config: dict
            The configurations regarding running the BIDS App on a cluster
            read from `config_yaml_file`.
        container_path_relToAnalysis: str
            The path to the container image saved in BABS project;
            this path is relative to `analysis` folder.
            e.g., `containers/.datalad/environments/fmriprep-0-0-0/image`
            This `image` could be a symlink (`op.islink()`, more likely for singularity container)
            or a folder (`op.isdir()`, more likely for docker container)
        """

        # sanity check if `config_yaml_file` exists:
        if not op.exists(config_yaml_file):
            raise FileNotFoundError(
                "The yaml file of the container's configurations '"
                + config_yaml_file
                + "' does not exist!"
            )
        self.container_ds = container_ds
        self.container_name = container_name
        self.config_yaml_file = config_yaml_file

        with open(self.config_yaml_file) as f:
            self.config = yaml.safe_load(f)

        self.container_path_relToAnalysis = op.join(
            'containers', '.datalad', 'environments', self.container_name, 'image'
        )

    def sanity_check(self, analysis_path):
        """
        This is a sanity check to validate the cloned container ds.

        Parameters
        ----------
        analysis_path: str
            Absolute path to the `analysis` folder in a BABS project.
        """
        # e.g.:
        #   '/path/to/BABS_project/analysis/containers/.datalad/environments/container_name/image'
        container_path_abs = op.join(analysis_path, self.container_path_relToAnalysis)

        # Sanity check: the path to `container_name` should exist in the cloned `container_ds`:
        # e.g., '/path/to/BABS_project/analysis/containers/.datalad/environments/container_name'
        assert op.exists(op.dirname(container_path_abs)), (
            "There is no valid image named '"
            + self.container_name
            + "' in the provided container DataLad dataset!"
        )

        # the 'image' symlink or folder should exist:
        assert op.exists(container_path_abs) or op.islink(container_path_abs), (
            "the folder 'image' of container DataLad dataset does not exist,"
            " and there is no symlink called 'image' either;"
            " Path to 'image' in cloned container DataLad dataset should be: '"
            + container_path_abs
            + "'."
        )

    def generate_bash_run_bidsapp(self, bash_path, input_ds, processing_level):
        """
        This is to generate a bash script that runs the BIDS App singularity image.

        Parameters
        ----------
        bash_path: str
            The path to the bash file to be generated. It should be in the `analysis/code` folder.
        input_ds: class `InputDatasets`
            input dataset(s) information
        processing_level : {'subject', 'session'}
            whether processing is done on a subject-wise or session-wise basis
        """

        # Check if the folder exist; if not, create it:
        bash_dir = op.dirname(bash_path)
        if not op.exists(bash_dir):
            os.makedirs(bash_dir)

        input_datasets = input_ds.df.to_dict(orient='records')
        templateflow_home = os.getenv('TEMPLATEFLOW_HOME')

        # What should the outputs look like?
        dict_zip_foldernames, bids_app_output_dir = app_output_settings_from_config(self.config)

        script_content = generate_bidsapp_runscript(
            input_datasets,
            processing_level,
            container_name=self.container_name,
            relative_container_path=self.container_path_relToAnalysis,
            bids_app_output_dir=bids_app_output_dir,
            dict_zip_foldernames=dict_zip_foldernames,
            bids_app_args=self.config.get('bids_app_args', None),
            singularity_args=self.config.get('singularity_args', []),
            templateflow_home=templateflow_home,
        )

        with open(bash_path, 'w') as f:
            f.write(script_content)
        os.chmod(bash_path, 0o700)  # rwx------ (owner only)

        print('Below is the generated BIDS App run script:')
        print(script_content)

    def generate_bash_participant_job(self, bash_path, input_ds, processing_level, system):
        """Generate bash script for participant job.

        Parameters
        ----------
        bash_path: str
            The path to the bash file to be generated. It should be in the `analysis/code` folder.
        input_ds: class `InputDatasets`
            input dataset(s) information
        processing_level : {'subject', 'session'}
            whether processing is done on a subject-wise or session-wise basis
        system: class `System`
            information on cluster management system
        """

        script_content = generate_submit_script(
            queue_system=system.type,
            cluster_resources_config=self.config['cluster_resources'],
            script_preamble=self.config['script_preamble'],
            job_scratch_directory=self.config['job_compute_space'],
            input_datasets=input_ds.df.to_dict(orient='records'),
            processing_level=processing_level,
            container_name=self.container_name,
            zip_foldernames=self.config['zip_foldernames'],
        )

        with open(bash_path, 'w') as f:
            f.write(script_content)
        os.chmod(bash_path, 0o700)  # rwx------ (owner only)

    def generate_bash_test_job(self, folder_check_setup, system):
        """Generate scripts for test job.

        Parameters
        ----------
        folder_check_setup : str
            Path to the check_setup folder
        system : System
            System object containing system-specific information
        """

        fn_call_test_job = op.join(folder_check_setup, 'call_test_job.sh')
        fn_test_job = op.join(folder_check_setup, 'test_job.py')

        script_content = generate_test_submit_script(
            queue_system=system.type,
            cluster_resources_config=self.config['cluster_resources'],
            script_preamble=self.config['script_preamble'],
            job_scratch_directory=self.config['job_compute_space'],
            check_setup_directory=folder_check_setup,
            check_setup_python_script=fn_test_job,
        )

        with open(fn_call_test_job, 'w') as f:
            f.write(script_content)
        os.chmod(fn_call_test_job, 0o700)

        # Copy the template file into the check_setup folder
        with resources.files('babs').joinpath('template_test_job.py').open('rb') as src:
            with open(fn_test_job, 'wb') as dst:
                dst.write(src.read())
        os.chmod(fn_test_job, 0o700)

    def generate_job_submit_template(self, yaml_path, babs, system, test=False):
        """
        This is to generate a YAML file that serves as a template
        of job submission of one participant (or session),
        or test job submission in `babs check-setup`.

        Parameters
        ----------
        yaml_path: str
            The path to the yaml file to be generated. It should be in the `analysis/code` folder.
            It has several fields: 1) cmd_template; 2) job_name_template
        babs: class `BABS`
            information about the BABS project
        system: class `System`
            information on cluster management system
        test: bool
            flag to set to True if generating the test job submit template
            for `babs check-setup`.
        """

        # Section 1: Command for submitting the job: ---------------------------
        # Flags when submitting the job:
        if system.type == 'slurm':
            submit_head = 'sbatch'
            env_flags = '--export=DSLOCKFILE=' + babs.analysis_path + '/.SLURM_datalad_lock'
        else:
            warnings.warn('not supporting systems other than slurm...', stacklevel=2)

        # Check if the bash file already exist:
        if op.exists(yaml_path):
            os.remove(yaml_path)  # remove it

        # Variables to use:
        if not test:
            # `dssource`: Input RIA:
            dssource = babs.input_ria_url + '#' + babs.analysis_dataset_id
            # `pushgitremote`: Output RIA:
            pushgitremote = babs.output_ria_data_dir

        # Generate the command:
        if system.type == 'slurm':
            name_flag_str = ' --job-name '

        # Section 2: Job name: ---------------------------
        # Job name:
        if test:
            job_name = self.container_name[0:3] + '_' + 'test_job'
        else:
            job_name = self.container_name[0:3]

        # Now, we can define stdout and stderr file names/paths:
        if system.type == 'slurm':
            # slurm clusters also need exact filenames:
            eo_args = (
                '-e '
                + babs.analysis_path
                + f'/logs/{job_name}.e%A_%a '
                + '-o '
                + babs.analysis_path
                + f'/logs/{job_name}.o%A_%a'
            )
            # array task id starts from 0 so that max_array == count
            if test:  # no max_array for `submit_test_job_template.yaml`
                array_args = '--array=1'
            else:  # need max_array for for `submit_job_template.yaml`
                array_args = '--array=1-${max_array}'

        # Render the template
        env = Environment(
            loader=PackageLoader('babs', 'templates'),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False,
            undefined=StrictUndefined,
        )
        template = env.get_template('job_submit.yaml.jinja2')

        with open(yaml_path, 'w') as f:
            f.write(
                template.render(
                    test=test,
                    submit_head=submit_head,
                    env_flags=env_flags,
                    name_flag_str=name_flag_str,
                    job_name=job_name,
                    eo_args=eo_args,
                    array_args=array_args,
                    babs=babs,
                    dssource=dssource if not test else '',
                    pushgitremote=pushgitremote if not test else '',
                )
            )
