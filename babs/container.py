"""Module for handling container configuration and execution in BABS."""

import os
import os.path as op

import yaml
from jinja2 import Environment, PackageLoader

from .utils import (
    validate_type_session,
)


class Container:
    """Class for handling container configuration and execution in BABS.

    Parameters
    ----------
    container_ds : str
        Path to the container dataset
    container_name : str
        Name of the container
    config_yaml_file : str
        Path to the container configuration YAML file
    """

    def __init__(self, container_ds, container_name, config_yaml_file):
        """Initialize Container class.

        Parameters
        ----------
        container_ds : str
            Path to the container dataset
        container_name : str
            Name of the container
        config_yaml_file : str
            Path to the container configuration YAML file
        """
        self.container_ds = container_ds
        self.container_name = container_name
        self.config_yaml_file = config_yaml_file
        self.config = self.read_container_config_yaml()

    def sanity_check(self, analysis_path):
        """Perform sanity checks on the container configuration.

        Parameters
        ----------
        analysis_path : str
            Path to the analysis directory

        Raises
        ------
        Exception
            If any sanity check fails
        """
        # Check if container dataset exists
        if not op.exists(self.container_ds):
            raise Exception('Container dataset does not exist: ' + self.container_ds)

        # Check if container name is valid
        if not self.container_name:
            raise Exception('Container name cannot be empty')

        # Check if config file exists
        if not op.exists(self.config_yaml_file):
            raise Exception('Container config file does not exist: ' + self.config_yaml_file)

        # Check if config file is readable
        if not os.access(self.config_yaml_file, os.R_OK):
            raise Exception('Container config file is not readable: ' + self.config_yaml_file)

        # Check if config file is valid YAML
        try:
            self.read_container_config_yaml()
        except yaml.YAMLError as e:
            raise Exception('Container config file is not valid YAML: ' + str(e))

    def read_container_config_yaml(self):
        """Read the container configuration YAML file.

        Returns
        -------
        dict
            Container configuration dictionary

        Raises
        ------
        Exception
            If the YAML file cannot be read or is invalid
        """
        with open(self.config_yaml_file) as f:
            return yaml.safe_load(f)

    def generate_bash_run_bidsapp(self, bash_path, input_ds, type_session):
        """Generate bash script to run BIDS app.

        Parameters
        ----------
        bash_path : str
            Path to the bash script to generate
        input_ds : str
            Path to the input dataset
        type_session : str
            "multi-ses" or "single-ses"

        Raises
        ------
        Exception
            If script generation fails
        """
        type_session = validate_type_session(type_session)
        env = Environment(loader=PackageLoader('babs', 'templates'))
        template = env.get_template('run_bidsapp.sh.jinja2')
        with open(bash_path, 'w') as f:
            f.write(
                template.render(
                    input_ds=input_ds,
                    type_session=type_session,
                    container_name=self.container_name,
                    **self.config,
                )
            )

    def generate_bash_participant_job(self, bash_path, input_ds, type_session, system):
        """Generate bash script for participant job.

        Parameters
        ----------
        bash_path : str
            Path to the bash script to generate
        input_ds : str
            Path to the input dataset
        type_session : str
            "multi-ses" or "single-ses"
        system : System
            System configuration object

        Raises
        ------
        Exception
            If script generation fails
        """
        type_session = validate_type_session(type_session)
        env = Environment(loader=PackageLoader('babs', 'templates'))
        template = env.get_template('participant_job.sh.jinja2')
        with open(bash_path, 'w') as f:
            f.write(
                template.render(
                    input_ds=input_ds,
                    type_session=type_session,
                    container_name=self.container_name,
                    system=system.get_dict(),
                    **self.config,
                )
            )

    def generate_bash_test_job(self, folder_check_setup, system):
        """Generate bash script for test job.

        Parameters
        ----------
        folder_check_setup : str
            Path to the check setup folder
        system : System
            System configuration object

        Raises
        ------
        Exception
            If script generation fails
        """
        env = Environment(loader=PackageLoader('babs', 'templates'))
        template = env.get_template('test_job.sh.jinja2')
        with open(op.join(folder_check_setup, 'test_job.sh'), 'w') as f:
            f.write(
                template.render(
                    container_name=self.container_name, system=system.get_dict(), **self.config
                )
            )

    def generate_job_submit_template(self, yaml_path, babs, system, test=False):
        """Generate job submission template.

        Parameters
        ----------
        yaml_path : str
            Path to the YAML file to generate
        babs : BABS
            BABS instance
        system : System
            System configuration object
        test : bool
            Whether this is a test job template

        Raises
        ------
        Exception
            If template generation fails
        """
        env = Environment(loader=PackageLoader('babs', 'templates'))
        template = env.get_template('job_submit.yaml.jinja2')
        with open(yaml_path, 'w') as f:
            f.write(
                template.render(
                    babs=babs,
                    system=system.get_dict(),
                    test=test,
                    container_name=self.container_name,
                    **self.config,
                )
            )
