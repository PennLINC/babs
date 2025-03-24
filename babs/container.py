"""This module is for the BIDS App Container"""

import os
import os.path as op
import shutil
import subprocess
import warnings

import yaml
from jinja2 import Environment, PackageLoader

from babs.utils import (
    generate_bashhead_resources,
    generate_cmd_datalad_run,
    generate_cmd_determine_zipfilename,
    generate_cmd_job_compute_space,
    generate_cmd_script_preamble,
    generate_cmd_set_envvar,
    generate_cmd_singularityRun_from_config,
    generate_cmd_unzip_inputds,
    generate_cmd_zipping_from_config,
    get_info_zip_foldernames,
    validate_processing_level,
)


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

        self.container_ds = container_ds
        self.container_name = container_name

        if not op.exists(self.config_yaml_file):
            raise FileNotFoundError(f"The yaml file '{self.config_yaml_file}' does not exist!")

        # read the container's config yaml file and get the `config`:
        with open(self.config_yaml_file) as f:
            self.config = yaml.safe_load(f)
        self.config_yaml_file = config_yaml_file

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
        # path to the symlink/folder `image`:
        container_path_abs = op.join(analysis_path, self.container_path_relToAnalysis)
        assert op.exists(op.dirname(container_path_abs)), (
            f"There is no valid image named '{self.container_name}' in the "
            'provided container DataLad dataset!'
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
        Generate a bash script that runs the containerized BIDS App.

        Parameters
        ----------
        bash_path: str
            The path to the bash file to be generated. It should be in the `analysis/code` folder.
        input_ds: class `InputDatasets`
            input dataset(s) information
        processing_level : {'subject', 'session'}
            whether processing is done on a subject-wise or session-wise basis
        """
        from jinja2 import Environment

        from .constants import OUTPUT_MAIN_FOLDERNAME, PATH_FS_LICENSE_IN_CONTAINER

        processing_level = validate_processing_level(processing_level)

        # Check if the folder exist; if not, create it:
        bash_dir = op.dirname(bash_path)
        if not op.exists(bash_dir):
            os.makedirs(bash_dir)

        # check if `self.config` from the YAML file contains information we need:
        # 1. check `bids_app_args` section:
        if 'bids_app_args' not in self.config:
            # sanity check: there should be only one input ds
            #   otherwise need to specify in this section:
            assert input_ds.num_ds == 1, (
                "Section 'bids_app_args' is missing in the provided"
                ' `container_config`. As there are more than one'
                ' input dataset, you must include this section to specify'
                ' to which argument that each input dataset will go.'
            )
            # if there is only one input ds, fine:
            print("Section 'bids_app_args' was not included in the `container_config`. ")
            cmd_singularity_flags = ''  # should be empty
            # Make sure other returned variables from `generate_cmd_singularityRun_from_config`
            #   also have values:
            # as "--fs-license-file" was not one of the value in `bids_app_args` section:
            flag_fs_license = False
            path_fs_license = None
            # copied from `generate_cmd_singularityRun_from_config`:
            singuRun_input_dir = input_ds.df.loc[0, 'path_data_rel']
        else:
            # read config from the yaml file:
            (
                cmd_singularity_flags,
                subject_selection_flag,
                flag_fs_license,
                path_fs_license,
                singuRun_input_dir,
            ) = generate_cmd_singularityRun_from_config(self.config, input_ds)

        # 2. check `zip_foldernames` section:
        dict_zip_foldernames, if_mk_output_folder, path_output_folder = get_info_zip_foldernames(
            self.config
        )

        # 3. check `singularity_args` section:
        singularity_args = self.config.get('singularity_args', [])

        # Check if the bash file already exist:
        if op.exists(bash_path):
            os.remove(bash_path)  # remove it

        # Check if `--bids-filter-file "${filterfile}"` is needed:
        flag_filterfile = False
        if processing_level == 'session':
            if any(ele in self.container_name.lower() for ele in ['fmriprep', 'qsiprep']):
                flag_filterfile = True

        # Check if any dataset is zipped; if so, add commands of unzipping:
        cmd_unzip_inputds = generate_cmd_unzip_inputds(input_ds, processing_level)

        # Environment variables in container:
        # get environment variables to be injected into container and whose value to be bound:
        templateflow_home_on_disk, templateflow_in_container = generate_cmd_set_envvar(
            'TEMPLATEFLOW_HOME'
        )

        # Generate zip command
        cmd_zip = generate_cmd_zipping_from_config(dict_zip_foldernames, processing_level)

        # Render the template
        env = Environment(
            loader=PackageLoader('babs', 'templates'),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False,
        )
        template = env.get_template('bidsapp_run.sh.jinja2')

        rendered_script = template.render(
            processing_level=processing_level,
            input_ds=input_ds,
            container_name=self.container_name,
            flag_filterfile=flag_filterfile,
            cmd_unzip_inputds=cmd_unzip_inputds,
            templateflow_home_on_disk=templateflow_home_on_disk,
            templateflow_in_container=templateflow_in_container,
            flag_fs_license=flag_fs_license,
            path_fs_license=path_fs_license,
            PATH_FS_LICENSE_IN_CONTAINER=PATH_FS_LICENSE_IN_CONTAINER,
            container_path_relToAnalysis=self.container_path_relToAnalysis,
            singuRun_input_dir=singuRun_input_dir,
            path_output_folder=path_output_folder,
            cmd_singularity_flags=cmd_singularity_flags,
            cmd_zip=cmd_zip,
            OUTPUT_MAIN_FOLDERNAME=OUTPUT_MAIN_FOLDERNAME,
            singularity_args=singularity_args,
        )
        with open(bash_path, 'w') as f:
            f.write(rendered_script)

        # Execute necessary commands:
        # change the permission of this bash file:
        proc_chmod_bashfile = subprocess.run(
            ['chmod', '+x', bash_path],  # e.g., chmod +x code/fmriprep_zip.sh
            stdout=subprocess.PIPE,
        )
        proc_chmod_bashfile.check_returncode()

        print('Below is the generated BIDS App run script:')
        print(rendered_script)

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

        env = Environment(
            loader=PackageLoader('babs', 'templates'),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False,
        )
        template = env.get_template('participant_job.sh.jinja2')

        # Cluster resources requesting:
        cmd_bashhead_resources = generate_bashhead_resources(system, self.config)

        # Script preambles:
        cmd_script_preamble = generate_cmd_script_preamble(self.config)

        # Change path to a temporary job compute workspace:
        cmd_job_compute_space = generate_cmd_job_compute_space(self.config)

        # Determine zip filename:
        cmd_determine_zipfilename = generate_cmd_determine_zipfilename(input_ds, processing_level)

        # Generate datalad run command:
        cmd_datalad_run = generate_cmd_datalad_run(self, input_ds, processing_level)

        with open(bash_path, 'w') as f:
            f.write(
                template.render(
                    cmd_bashhead_resources=cmd_bashhead_resources,
                    cmd_script_preamble=cmd_script_preamble,
                    cmd_job_compute_space=cmd_job_compute_space,
                    cmd_determine_zipfilename=cmd_determine_zipfilename,
                    cmd_datalad_run=cmd_datalad_run,
                    system=system,
                    processing_level=processing_level,
                    input_ds=input_ds,
                )
            )

        # change the permission of this bash file:
        proc_chmod_bashfile = subprocess.run(
            ['chmod', '+x', bash_path],  # e.g., chmod +x code/participant_job.sh
            stdout=subprocess.PIPE,
        )
        proc_chmod_bashfile.check_returncode()

    def generate_bash_test_job(self, folder_check_setup, system):
        """Generate bash script for test job.

        Parameters
        ----------
        folder_check_setup : str
            Path to the check_setup folder
        system : System
            System object containing system-specific information
        # Render the template
        env = Environment(loader=PackageLoader('babs', 'templates'), autoescape=True)
        template = env.get_template('test_job.sh.jinja2')
        folder_check_setup : str
            Path to the check_setup folder
        system : System
            System object containing system-specific information
        """
        # Render the template
        env = Environment(loader=PackageLoader('babs', 'templates'), autoescape=True)
        template = env.get_template('test_job.sh.jinja2')

        fn_call_test_job = op.join(folder_check_setup, 'call_test_job.sh')
        fn_test_job = op.join(folder_check_setup, 'test_job.py')

        # ==============================================================
        # Generate `call_test_job.sh`, similar to `participant_job.sh`
        # ==============================================================
        # Check if the bash file already exist:
        if op.exists(fn_call_test_job):
            os.remove(fn_call_test_job)  # remove it

        # Cluster resources requesting:
        cmd_bashhead_resources = generate_bashhead_resources(system, self.config)

        # Script preambles:
        cmd_script_preamble = generate_cmd_script_preamble(self.config)

        # Change path to a temporary job compute workspace:
        cmd_job_compute_space = generate_cmd_job_compute_space(self.config)

        with open(fn_call_test_job, 'w') as f:
            f.write(
                template.render(
                    cmd_bashhead_resources=cmd_bashhead_resources,
                    cmd_script_preamble=cmd_script_preamble,
                    cmd_job_compute_space=cmd_job_compute_space,
                    folder_check_setup=folder_check_setup,
                    fn_test_job=fn_test_job,
                )
            )

        # change the permission of this bash file:
        proc_chmod_bashfile = subprocess.run(
            ['chmod', '+x', fn_call_test_job],  # e.g., chmod +x code/participant_job.sh
            stdout=subprocess.PIPE,
        )
        proc_chmod_bashfile.check_returncode()

        # ==============================================================
        # Generate `test_job.py`, similar to `container_zip.sh`
        # ==============================================================
        # Check if the bash file already exist:
        if op.exists(fn_test_job):
            os.remove(fn_test_job)  # remove it

        # Copy the existing python script to this BABS project:
        # location of current python script:
        #   `op.abspath()` is to make sure always returns abs path, regardless of python version
        #   ref: https://note.nkmk.me/en/python-script-file-path/
        __location__ = op.realpath(op.dirname(op.abspath(__file__)))
        fn_from = op.join(__location__, 'template_test_job.py')
        # copy:
        shutil.copy(fn_from, fn_test_job)

        # change the permission of this bash file:
        proc_chmod_pyfile = subprocess.run(
            ['chmod', '+x', fn_test_job],  # e.g., chmod +x code/participant_job.sh
            stdout=subprocess.PIPE,
        )
        proc_chmod_pyfile.check_returncode()

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
        from jinja2 import Environment

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
        env = Environment(loader=PackageLoader('babs', 'templates'), autoescape=True)
        env = Environment(loader=PackageLoader('babs', 'templates'), autoescape=True)
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
