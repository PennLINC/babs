# This is the main module.

import os
import os.path as op
# from re import L
import subprocess
import warnings
import pandas as pd
import glob
import shutil
import tempfile
import yaml

import datalad.api as dlapi
from datalad_container.find_container import find_container_

from babs.utils import (get_immediate_subdirectories,
                        check_validity_unzipped_input_dataset, generate_cmd_envvar,
                        generate_cmd_filterfile,
                        generate_cmd_singularityRun_from_config, generate_cmd_unzip_inputds,
                        generate_cmd_zipping_from_config,
                        validate_type_session,
                        generate_bashhead_resources,
                        generate_cmd_datalad_run)

# import pandas as pd


class BABS():
    """The BABS class is for babs projects of BIDS Apps"""

    def __init__(self, project_root, type_session, type_system):
        '''
        Parameters:
        ------------
        project_root: str
            absolute path to the root of this babs project
        type_session: str
            whether the input dataset is "multi-ses" or "single-ses"
        type_system: str
            the type of job scheduling system, "sge" or "slurm"

        Attributes:
        ---------------
        project_root: str
            absolute path to the root of this babs project
        type_session: str
            whether the input dataset is "multi-ses" or "single-ses"
        type_system: str
            the type of job scheduling system, "sge" or "slurm"
        analysis_path: str
            path to the `analysis` folder.
        analysis_datalad_handle: datalad dataset
            the `analysis` datalad dataset
        input_ria_path: str
            Path to the input RIA store, the sibling of `analysis`.
            The computation of each job will start with a clone from this input RIA store.
        output_ria_path: str
            Path to the output RIA store, the sibling of `analysis`.
            The results of jobs will be pushed to this output RIA store.
        input_ria_url: str
            URL of input RIA store, starting with "ria+file://".
        output_ria_url: str
            URL of output RIA store, starting with "ria+file://".
        output_ria_data_dir: str
            Path to the output RIA's data directory.
            Example: /full/path/to/project_root/output_ria/e48/03bc1-9eec-4543-9387-90415ca3477e
        '''

        self.project_root = project_root
        self.type_session = type_session
        self.type_system = type_system

        self.analysis_path = op.join(project_root, "analysis")
        self.analysis_datalad_handle = None

        self.input_ria_path = op.join(project_root, "input_ria")
        self.output_ria_path = op.join(project_root, "output_ria")

        self.input_ria_url = "ria+file://" + self.input_ria_path
        self.output_ria_url = "ria+file://" + self.output_ria_path

        self.output_ria_data_dir = None     # not known yet before output_ria is created

    def babs_bootstrap(self, input_ds, container_ds, container_name, container_config_yaml_file,
                       system):
        """
        Bootstrap a babs project: initialize datalad-tracked RIAs, generate scripts to be used, etc

        Parameters:
        -------------
        input_ds: class `Input_ds`
            Input dataset(s).
        container_ds: str
            path to the container datalad dataset which the user provides
        container_name: str
            TODO: add desc!
        container_config_yaml_file: str
            TODO: add desc!
        system: class System
            information about the cluster management system
        """

        # entry_pwd = os.getcwd()

        # ==============================================================
        # Initialize:
        # ==============================================================

        # make a directory of project_root:
        if not op.exists(self.project_root):
            os.makedirs(self.project_root)

        # create `analysis` folder:
        print("\nCreating `analysis` folder (also a datalad dataset)...")
        if op.exists(self.analysis_path):
            # check if it's a datalad dataset:
            try:
                _ = dlapi.status(dataset=self.analysis_path)
                print("Folder 'analysis' exists in the `project_root` and is a datalad dataset; "
                      "not to re-create it.")
                self.analysis_datalad_handle = dlapi.Dataset(self.analysis_path)
            except:
                raise Exception("Folder 'analysis' exists but is not a datalad dataset. "
                                "Please remove this folder and rerun.")
        else:
            self.analysis_datalad_handle = dlapi.create(self.analysis_path,
                                                        cfg_proc='yoda',
                                                        annex=True)

        # Create output RIA sibling:
        print("\nCreating output and input RIA...")
        if op.exists(self.output_ria_path):
            pass
            # TODO: add sanity check: if the input_ria and output_ria have been created,
            # check if they are analysis's siblings + they are ria siblings;
            # then, update them with datalad push from anlaysis folder
        else:
            self.analysis_datalad_handle.create_sibling_ria(name="output",
                                                            url=self.output_ria_url,
                                                            new_store_ok=True)
        # ^ ref: in python environment:
            # import datalad; help(datalad.distributed.create_sibling_ria)
            # sometimes, have to first `temp = dlapi.Dataset("/path/to/analysis/folder")`,
            # then `help(temp.create_sibling_ria)`, you can stop here,
            # or now you can help(datalad.distributed.create_sibling_ria)
            # seems there is no docs online?
        # source code:
            # https://github.com/datalad/datalad/blob/master/datalad/distributed/create_sibling_ria.py

        # get the `self.output_ria_data_dir`,
            # e.g., /full/path/output_ria/e48/03bc1-9eec-4543-9387-90415ca3477e
        analysis_git_path = op.join(self.analysis_path, ".git")
        proc_output_ria_data_dir = subprocess.run(
            ["git", "--git-dir", analysis_git_path, "remote", "get-url", "--push", "output"],
            stdout=subprocess.PIPE)
        # another way to change the wd temporarily: add `cwd=self.xxx` in `subprocess.run()`
        # if success: no output; if failed: will raise CalledProcessError
        proc_output_ria_data_dir.check_returncode()
        self.output_ria_data_dir = proc_output_ria_data_dir.stdout.decode('utf-8')
        if self.output_ria_data_dir[-1:] == "\n":
            # remove the last 2 characters
            self.output_ria_data_dir = self.output_ria_data_dir[:-1]

        # Create input RIA sibling:
        if op.exists(self.input_ria_path):
            pass
            # TODO: add sanity check: if the input_ria and output_ria have been created,
            # check if they are analysis's siblings + they are ria siblings;
            # then, update them with datalad push from anlaysis folder
        else:
            self.analysis_datalad_handle.create_sibling_ria(name="input",
                                                            url=self.input_ria_url,
                                                            storage_sibling=False,   # False is `off` in CLI of datalad
                                                            new_store_ok=True)

        # Register the input dataset(s):
        print("\nRegistering the input dataset(s)...")
        for i_ds in range(0, input_ds.num_ds):
            # path to cloned dataset:
            i_ds_path = op.join(self.analysis_path,
                                input_ds.df["path_now_rel"][i_ds])
            if op.exists(i_ds_path):
                print("The input dataset #" + str(i_ds+1) + " '"
                      + input_ds.df["name"][i_ds] + "'"
                      + " has been copied into `analysis` folder; "
                      "not to copy again.")
                pass
                # TODO: add sanity check: if its datalad sibling is input dataset
            else:
                print("Cloning input dataset #" + str(i_ds+1) + ": '"
                      + input_ds.df["name"][i_ds] + "'")
                # clone input dataset(s) as sub-dataset into `analysis` dataset:
                dlapi.clone(dataset=self.analysis_path,
                            source=input_ds.df["path_in"][i_ds],    # input dataset(s)
                            path=i_ds_path)  # path to clone into

                # amend the previous commit with a nicer commit message:
                proc_git_commit_amend = subprocess.run(
                    ["git", "commit", "--amend", "-m",
                     "Register input data dataset '" + input_ds.df["name"][i_ds]
                     + "' as a subdataset"],
                    cwd=self.analysis_path,
                    stdout=subprocess.PIPE
                )
                proc_git_commit_amend.check_returncode()

        # get the current absolute path to the input dataset:
        input_ds.assign_path_now_abs(self.analysis_path)

        # Check the type of each input dataset: (zipped? unzipped?)
        #   this also includes a sanity check of the foldername within the zip file (for zipped ds)
        print("\nChecking whether each input dataset is a zipped or unzipped dataset...")
        input_ds.check_if_zipped()

        # Check validity of unzipped ds:
        #   if multi-ses, has `ses-*` in each `sub-*`; if single-ses, has a `sub-*`
        check_validity_unzipped_input_dataset(input_ds, self.type_session)

        # Add container as sub-dataset of `analysis`:
        # # TO ASK: WHY WE NEED TO CLONE IT FIRST INTO `project_root`???
        # dlapi.clone(source = container_ds,    # container datalad dataset
        #             path = op.join(self.project_root, "containers"))   # path to clone into

        # directly add container as sub-dataset of `analysis`:
        print("\nAdding the container as a sub-dataset of `analysis` dataset...")
        if op.exists(op.join(self.analysis_path, "containers")):
            print("The container has been added as a sub-dataset; not to do it again.")
            pass
            # TODO: check if the container has been successfully added as a sub-dataset!
        else:
            # clone input dataset(s) as sub-dataset into `analysis` dataset
            dlapi.install(dataset=self.analysis_path,
                          source=container_ds,    # container datalad dataset
                          path=op.join(self.analysis_path, "containers"))
            # into `analysis\containers` folder

        # original bash command, if directly going into as sub-dataset:
        # datalad install -d . --source ../../toybidsapp-container-docker/ containers

        # from our the way:
        # cd ${PROJECTROOT}/analysis
        # datalad install -d . --source ${PROJECTROOT}/pennlinc-containers

        # ==============================================================
        # Bootstrap scripts: TODO
        # ==============================================================

        container = Container(container_ds, container_name, container_config_yaml_file)

        # Generate `<containerName>_zip.sh`: ----------------------------------
        # which is a bash script of singularity run + zip
        # in folder: `analysis/code`
        print("\nGenerating bash script for running container and zipping the outputs...")
        print("This bash script will be named as `" + container_name + "_zip.sh`")
        bash_path = op.join(self.analysis_path, "code", container_name + "_zip.sh")
        container.generate_bash_run_bidsapp(bash_path, input_ds, self.type_session)

        # Generate `participant_job.sh`: --------------------------------------
        # TODO: ^^
        print("\nGenerating bash script for running jobs at participant level...")
        print("This bash script will be named as `participant_job.sh`")
        bash_path = op.join(self.analysis_path, "code", "participant_job.sh")
        container.generate_bash_participant_job(bash_path, input_ds, self.type_session,
                                                system)

        # Finish up and get ready for clusters running: -----------------------
        # datalad save:
        # TODO (not necessary in this function):
        """
        datalad save -m "Participant compute job implementation"
        """

        # create folder `logs` in `analysis`; future log files go here
        log_path = op.join(self.analysis_path, "logs")
        if not op.exists(log_path):
            os.makedirs(log_path)

        # write into .gitignore so won't be tracked by git:
        gitignore_path = op.join(self.analysis_path, ".gitignore")
        gitignore_file = open(gitignore_path, "a")   # open in append mode

        gitignore_file.write("\nlogs")   # not to track `logs` folder
        # not to track `.*_datalad_lock`:
        if system.type == "sge":
            gitignore_file.write("\n.SGE_datalad_lock")
        elif system.type == "slurm":
            # TODO: add command for `slurm`!!!
            print("Not supported yet... To work on...")
        gitignore_file.write("\n")

        gitignore_file.close()

        print()
        # ==============================================================
        # Clean up: TODO
        # ==============================================================

class Input_ds():
    """This class is for input dataset(s)"""

    def __init__(self, input_cli):
        """
        This is to initalize Container class.

        Parameters:
        --------------
        input_cli: nested list of strings - see CLI `babs-init --input` for more

        Attributes:
        --------------
        df: pandas DataFrame
            includes necessary information:
            - name: str: a name the user gives
            - path_in: str: the path to the input ds
            - path_now_rel: the path to where the input ds is cloned, relative to `analysis` folder
            - path_now_abs: the absolute path to the input ds
            - path_data_rel: the path to where the input data (for a sub or a ses) is,
                relative to `analysis` folder.
                If it's zipped ds, `path_data_rel` = `path_now_rel`/`name`,
                i.e., extra layer of folder got from unzipping
                If it's an unzipped ds, `path_data_rel` = `path_now_rel`
            - is_zipped: True or False, is the input data zipped or not
        num_ds: int
            number of input dataset(s)
        """

        # create an empty pandas DataFrame:
        self.df = pd.DataFrame(None,
                               index=list(range(0, len(input_cli))),
                               columns=['name', 'path_in', 'path_now_rel',
                                        'path_now_abs', 'path_data_rel',
                                        'is_zipped'])

        # number of dataset(s):
        self.num_ds = self.df.shape[0]   # number of rows in `df`

        # change the `input_cli` from nested list to a pandas dataframe:
        for i in range(0, self.num_ds):
            self.df["name"][i] = input_cli[i][0]
            self.df["path_in"][i] = input_cli[i][1]
            self.df["path_now_rel"][i] = op.join("inputs/data", self.df["name"][i])

        # sanity check: input ds names should not be identical:
        if len(set(self.df["name"].tolist())) != self.num_ds:  # length of the set = number of ds
            raise Exception("There are identical names in input datasets' names!")

    def assign_path_now_abs(self, analysis_path):
        """
        This is the assign the absolute path to input dataset

        Parameters:
        --------------
        analysis_path: str
            absolute path to the `analysis` folder.
        """

        for i in range(0, self.num_ds):
            self.df["path_now_abs"][i] = op.join(analysis_path,
                                                 self.df["path_now_rel"][i])

    def check_if_zipped(self):
        """
        This is to check if each input dataset is zipped, and assign `path_data_rel`.
        If it's a zipped ds, it will:
            1) also do a sanity check to make sure the 1st level folder in zipfile
                is consistent to this input dataset's name;
                Only checks the first zipfile.
            2) `path_data_rel` = `path_now_rel`/`name`,
                i.e., extra layer of folder got from unzipping

        If it's an unzipped ds, `path_data_rel` = `path_now_rel`
        """

        for i_ds in range(0, self.num_ds):
            temp_list = glob.glob(self.df["path_now_abs"][i_ds] + "/sub-*")
            count_zip = 0
            count_dir = 0
            for i_temp in range(0, len(temp_list)):
                if op.isdir(temp_list[i_temp]):
                    count_dir += 1
                elif temp_list[i_temp][-4:] == ".zip":
                    count_zip += 1

            if (count_zip > 0) & (count_dir == 0):   # all are zip files:
                self.df["is_zipped"][i_ds] = True
                print("input dataset '" + self.df["name"][i_ds] + "'"
                      + " is considered as a zipped dataset.")
            elif (count_dir > 0) & (count_zip == 0):   # all are directories:
                self.df["is_zipped"][i_ds] = False
                print("input dataset '" + self.df["name"][i_ds] + "'"
                      + " is considered as an unzipped dataset.")
            elif (count_zip > 0) & (count_dir > 0):  # detect both:
                self.df["is_zipped"][i_ds] = True   # consider as zipped
                print("input dataset '" + self.df["name"][i_ds] + "'"
                      + " has both zipped files and unzipped folders;"
                      + " thus it's considered as a zipped dataset.")
            else:   # did not detect any of them...
                raise Exception("BABS did not detect any folder or zip file of `sub-*`"
                                + " in input dataset '" + self.df["name"][i_ds] + "'.")

        if True in list(self.df["is_zipped"]):  # there is at least one dataset is zipped
            print("Performing sanity check for any zipped input dataset..."
                  " Getting example zip file(s) to check...")
        for i_ds in range(0, self.num_ds):
            if self.df["is_zipped"][i_ds] is True:   # zipped ds
                # Sanity check: -----------------------------------
                # find a zipfile, `datalad get`
                temp_list = glob.glob(self.df["path_now_abs"][i_ds]
                                      + "/sub-*" + self.df["name"][i_ds] + "*.zip")
                if len(temp_list) == 0:    # did not find any matched
                    raise Exception("In zipped input dataset #" + str(i_ds + 1)
                                    + " (named '" + self.df["name"][i_ds] + "'),"
                                    + " there is no zip file"
                                    + " whose filename includes the dataset's name: '"
                                    + self.df["name"][i_ds] + "'")
                temp_zipfile = temp_list[0]   # try out the first one
                temp_zipfilename = op.basename(temp_zipfile)
                dlapi.get(path=temp_zipfile, dataset=self.df["path_now_abs"][i_ds])
                # unzip to a temporary folder and get the foldername
                temp_unzip_to = tempfile.mkdtemp()
                shutil.unpack_archive(temp_zipfile, temp_unzip_to)
                list_unzip_foldernames = get_immediate_subdirectories(temp_unzip_to)
                # remove the temporary folder:
                shutil.rmtree(temp_unzip_to)
                # `datalad drop` the zipfile:
                dlapi.drop(path=temp_zipfile, dataset=self.df["path_now_abs"][i_ds])

                # check if there is folder named as ds's name:
                if self.df["name"][i_ds] not in list_unzip_foldernames:
                    warnings.warn("In input dataset #" + str(i_ds + 1)
                                  + " (named '" + self.df["name"][i_ds]
                                  + "'), there is no folder called '"
                                  + self.df["name"][i_ds] + "' in zipped input file '"
                                  + temp_zipfilename + "'. This may cause error"
                                  + " when running BIDS App for this subject/session")

                # Assign `path_data_rel`: ----------------------------------
                self.df["path_data_rel"][i_ds] = op.join(self.df["path_now_rel"][i_ds],
                                                         self.df["name"][i_ds])
            else:   # unzipped ds:
                # Assign `path_data_rel`:
                self.df["path_data_rel"][i_ds] = self.df["path_now_rel"][i_ds]


class System():
    """This class is for cluster management system"""

    def __init__(self, system_type):
        """
        This is to initialize System class.

        Parameters:
        -------------
        system_type: str
            Type of the cluster management system.
            Options are: "sge" and "slurm"

        Attributes:
        -------------
        type: str
            Type of the cluster management system.
            Options are: "sge" and "slurm"
        dict: dict
            Guidance dict (loaded from `dict_cluster_systems.yaml`)
            for how to run this type of cluster.
        """
        self.type = system_type
        self.validate_name()

        # get attribute `dict` - the guidance dict for how to run this type of cluster:
        self.get_dict()

    def validate_name(self):
        """
        To validate if the type of the cluster system is valid.
        For valid ones, the type string will be changed to lower case.
        """
        if self.type.lower() in ["sge", "slurm"]:
            self.type = self.type.lower()   # change to lower case, if needed
        else:
            raise Exception("Invalid cluster system type: '" + self.type + "'!")

    def get_dict(self):
        with open("babs/dict_cluster_systems.yaml") as f:
            dict = yaml.load(f, Loader=yaml.FullLoader)
            # ^^ dict is a dict; elements can be accessed by `dict["key"]["sub-key"]`

        # sanity check:
        if self.type not in dict:
            raise Exception("There is no key called '" + self.type + "' in"
                            + " file `dict_cluster_systems.yaml`!")

        self.dict = dict[self.type]
        f.close()


class Container():
    """This class is for the BIDS App Container"""

    def __init__(self, container_ds, container_name, config_yaml_file):
        """
        This is to initialize Container class.

        Parameters:
        --------------
        container_ds: str
            The path to the container datalad dataset as the input of `babs-init`.
            This container datalad ds is prepared by the user.
        container_name: str
            The name of the container when adding to datalad dataset(e.g., `NAME` in
            `datalad containers-add NAME`),
             e.g., fmriprep-0-0-0
        config_yaml_file: str
            The YAML file that contains the configurations of how to run the container

        Attributes:
        --------------
        container_ds: str
            The path to the container datalad dataset as the input of `babs-init`.
            This container datalad ds is prepared by the user.
        container_name: str
            The name of the container when adding to datalad dataset(e.g., `NAME` in
            `datalad containers-add NAME`),
             e.g., fmriprep-0-0-0
        config_yaml_file: str
            The YAML file that contains the configurations of how to run the container
            This is optional argument (of the CLI `babs-init`)
        config: dict
            The configurations regaring running the BIDS App on a cluster
            read from `config_yaml_file`.
        container_path_relToAnalysis: str
            The path to the container image saved in BABS project;
            this path is relative to `analysis` folder.
            e.g., `containers/.datalad/environments/fmriprep-0-0-0/image`
        """

        self.container_ds = container_ds
        self.container_name = container_name
        self.config_yaml_file = config_yaml_file

        # sanity check if `config_yaml_file` exists:
        if op.exists(self.config_yaml_file) is False:
            raise Exception("The yaml file of the container's configurations '"
                            + self.config_yaml_file + "' does not exist!")

        # read the container's config yaml file and get the `config`:
        self.read_container_config_yaml()

        self.container_path_relToAnalysis = op.join("containers", ".datalad", "environments",
                                                    self.container_name, "image")

        # TODO: validate that this `container_name` really exists in `container_ds`...

    def read_container_config_yaml(self):
        """
        This is to get the config dict from `config_yaml_file`
        """
        with open(self.config_yaml_file) as f:
            self.config = yaml.load(f, Loader=yaml.FullLoader)
            # ^^ config is a dict; elements can be accessed by `config["key"]["sub-key"]`
        f.close()

    def generate_bash_run_bidsapp(self, bash_path, input_ds, type_session):
        """
        This is to generate a bash script that runs the BIDS App singularity image.

        Parameters:
        -------------
        bash_path: str
            The path to the bash file to be generated. It should be in the `analysis/code` folder.
        input_ds: class `Input_ds`
            input dataset(s) information
        type_session: str
            multi-ses or single-ses.

        Notes:
        --------------
        When writing `singularity run` part, each chunk to write should start with " \\" + "\n\t",
        meaning, starting with space, a backward slash, a return, and a tab.
        """

        type_session = validate_type_session(type_session)
        output_foldername = "outputs"    # folername of BIDS App outputs

        # Check if the folder exist; if not, create it:
        bash_dir = op.dirname(bash_path)
        if not op.exists(bash_dir):
            os.makedirs(bash_dir)

        # TODO: continue adding commands......

        # check if `self.config` from the YAML file contains information we need:
        if "babs_singularity_run" not in self.config:
            print("The key 'babs_singularity_run' was not included "
                  "in the `container_config_yaml_file`. "
                  "Therefore we will not refer to the yaml file for `singularity run` arguments, "
                  "but will use regular `singularity run` command.")
        #       "command of singularity run will be read from information "
        #       "saved by `call-fmt` when `datalad containers-add.`")
            cmd_singularity_flags = "\n\t"
        else:
            # print("Generate singularity run command from `container_config_yaml_file`")
            # # contain \ for each key-value

            # read config from the yaml file:
            cmd_singularity_flags, flag_fs_license, singuRun_input_dir = \
                generate_cmd_singularityRun_from_config(self.config, input_ds)

        print()

        # TODO: also corporate the `call-fmt` in `datalad containers-add`

        # Check if the bash file already exist:
        if op.exists(bash_path):
            os.remove(bash_path)  # remove it

        # Write into the bash file:
        bash_file = open(bash_path, "a")   # open in append mode

        bash_file.write("#!/bin/bash\n")
        bash_file.write("set -e -u -x\n")

        bash_file.write('\nsubid="$1"\n')

        if type_session == "multi-ses":
            # also have the input of `sesid`:
            bash_file.write('sesid="$2"\n')

        bash_file.write("\n")

        # Check if `--bids-filter-file "${filterfile}"` is needed:
        flag_filterfile = False
        if type_session == "multi-ses":
            if any(ele in self.container_name.lower() for ele in ["fmriprep", "qsiprep"]):
                # ^^ if the container_name contains `fmriprep` or `qsiprep`:
                # ^^ case insensitive (as have changed to lower case), accept "fMRIPrep-0-0-0"
                flag_filterfile = True

                # generate the command of generating the `$filterfile`,
                # i.e., `${sesid}_filter.json`:
                cmd_filterfile = generate_cmd_filterfile(self.container_name)
                bash_file.write(cmd_filterfile)

        # Check if any dataset is zipped; if so, add commands of unzipping:
        cmd_unzip_inputds = generate_cmd_unzip_inputds(input_ds, type_session)
        if len(cmd_unzip_inputds) > 0:   # not "":
            bash_file.write(cmd_unzip_inputds)

        # Other necessary commands for preparation:
        bash_file.write("\n")

        # Export environment variable:
        cmd_envvar, templateflow_home, singularityenv_templateflow_home = generate_cmd_envvar(
            self.config, self.container_name)
        bash_file.write(cmd_envvar)

        # Write the head of the command `singularity run`:
        bash_file.write("mkdir -p ${PWD}/.git/tmp/wkdir\n")
        cmd_head_singularityRun = "singularity run --cleanenv -B ${PWD}"

        # check if `templateflow_home` needs to be bind:
        if templateflow_home is not None:
            cmd_head_singularityRun += "," + templateflow_home + ":"
            cmd_head_singularityRun += singularityenv_templateflow_home
            # ^^ bind to dir in container

        cmd_head_singularityRun += " \\" + "\n\t"
        cmd_head_singularityRun += self.container_path_relToAnalysis
        cmd_head_singularityRun += " \\" + "\n\t"
        cmd_head_singularityRun += singuRun_input_dir  # inputs/data/<name>
        cmd_head_singularityRun += " \\" + "\n\t"
        cmd_head_singularityRun += output_foldername   # output folder

        # if not xcp-d (which does not support `participant` positional argu):
        if any(ele in self.container_name.lower() for ele in ["xcp"]):
            pass
        else:
            cmd_head_singularityRun += " \\" + "\n\t"
            cmd_head_singularityRun += "participant"  # at participant-level

        bash_file.write(cmd_head_singularityRun)

        # Write the named arguments + values:
        # add more arguments that are covered by BABS (instead of users):
        if flag_filterfile is True:
            # also needs a $filterfile flag:
            cmd_singularity_flags += " \\" + "\n\t"
            cmd_singularity_flags += '--bids-filter-file "${filterfile}"'  # <- TODO: test out!!

        cmd_singularity_flags += " \\" + "\n\t"
        cmd_singularity_flags += '--participant-label "${subid}"'   # standard argument in BIDS App

        bash_file.write(cmd_singularity_flags)
        bash_file.write("\n\n")

        print("Below is the generated `singularity run` command:")
        print(cmd_head_singularityRun + cmd_singularity_flags)

        # Zip:
        cmd_zip = generate_cmd_zipping_from_config(self.config, type_session, output_foldername)
        bash_file.write(cmd_zip)

        # Delete folders and files:
        """
        rm -rf prep .git/tmp/wkdir
        rm ${filterfile}
        """
        cmd_clean = "rm -rf " + output_foldername + " " + ".git/tmp/wkdir" + "\n"
        if flag_filterfile is True:
            cmd_clean += "rm ${filterfile}" + " \n"

        bash_file.write(cmd_clean)

        # Done generating `<containerName>_zip.sh`:
        bash_file.write("\n")
        bash_file.close()

        # Execute necessary commands:
        # change the permission of this bash file:
        proc_chmod_bashfile = subprocess.run(
            ["chmod", "+x", bash_path],  # e.g., chmod +x code/fmriprep_zip.sh
            stdout=subprocess.PIPE
            )
        proc_chmod_bashfile.check_returncode()

        # if needed, copy Freesurfer license:
        if flag_fs_license is True:
            # check if `${FREESURFER_HOME}/license.txt` exists: if not, error.. # <-- TODO
            freesurfer_home = os.getenv('FREESURFER_HOME')  # get env variable
            if freesurfer_home is None:    # did not set
                raise Exception(
                    "FreeSurfer's license will be used"
                    + " but `$FREESURFER_HOME` was not set."
                    + " Therefore, BABS cannot copy and paste FreeSurfer's license..."
                    )
            fs_license_path_from = op.join(freesurfer_home, "license.txt")
            if op.exists(fs_license_path_from) is False:
                raise Exception("There is no `license.txt` file in $FREESURFER_HOME to be copied!")

            fs_license_path_to = op.join(bash_dir, "license.txt")  # `bash_dir` is `analysis/code`
            proc_copy_fs_license = subprocess.run(
                # e.g., cp ${FREESURFER_HOME}/license.txt code/license.txt
                ["cp", fs_license_path_from, fs_license_path_to],
                stdout=subprocess.PIPE
            )
            proc_copy_fs_license.check_returncode()

        # print()

    def generate_bash_participant_job(self, bash_path, input_ds, type_session,
                                      system):
        """
        This is to generate a bash script that runs jobs for each participant (or session).

        Parameters:
        -------------
        bash_path: str
            The path to the bash file to be generated. It should be in the `analysis/code` folder.
        input_ds: class `Input_ds`
            input dataset(s) information
        type_session: str
            "multi-ses" or "single-ses".
        system: class `System`
            information on cluster management system
        """

        # Sanity check:
        if type_session not in ["multi-ses", "single-ses"]:
            raise Exception("Invalid `type_session`: " + type_session)

        # Check if the bash file already exist:
        if op.exists(bash_path):
            os.remove(bash_path)  # remove it

        # Write into the bash file:
        bash_file = open(bash_path, "a")   # open in append mode

        bash_file.write("#!/bin/bash\n")

        # Cluster resources requesting:
        cmd_bashhead_resources = generate_bashhead_resources(system, self.config)
        bash_file.write(cmd_bashhead_resources)

        # Set up correct conda environment:
        bash_file.write("\n# Set up the conda environment:\n")

        # sanity check:
        if "script_preamble" not in self.config:
            raise Exception("Did not find the required section 'script_preamble'"
                            + " in `container_config_yaml_file`!")
        if "conda_env_name" not in self.config["script_preamble"]:
            raise Exception("Did not find the required key 'conda_env_name'"
                            + " in section 'script_preamble'"
                            + " in `container_config_yaml_file`!")

        if system.type == "sge":
            bash_file.write("source ${CONDA_PREFIX}/bin/activate"
                            + self.config["script_preamble"]["conda_env_name"]
                            + "\n")
        # TODO: add slurm's

        bash_file.write("echo I\'m in $PWD using `which python`\n")

        # Change how this bash file is run:
        bash_file.write("\n# Fail whenever something is fishy,"
                        + " use -x to get verbose logfiles:\n")
        bash_file.write("set -e -u -x\n")

        # Inputs of the bash script:
        bash_file.write("\n")
        bash_file.write('dssource="$1"\n')
        bash_file.write('pushgitremote="$2"\t# i.e., `output_ria`\n')
        bash_file.write('subid="$3"\n')

        if type_session == "multi-ses":
            # also have the input of `sesid`:
            bash_file.write('sesid="$4"\n')
            bash_file.write('where_to_run="$5"\n')
        elif type_session == "single-ses":
            bash_file.write('where_to_run="$4"\n')

        # TODO: if `where_to_run` is not specified, change to default = ??

        bash_file.write("\n# Change to a temporary directory or compute space:\n")
        bash_file.write("cd ${where_to_run}" + "\n")

        # Setups: ---------------------------------------------------------------
        # set up the branch:
        bash_file.write("\n# Branch name (also used as temporary directory):\n")
        if system.type == "sge":
            varname_jobid = "JOB_ID"
        elif system.type == "slurm":
            varname_jobid = "SLURM_JOBID"

        if type_session == "multi-ses":
            bash_file.write('BRANCH="job-${' + varname_jobid + '}-${subid}-${sesid}"' + '\n')
        elif type_session == "single-ses":
            bash_file.write('BRANCH="job-${' + varname_jobid + '}-${subid}"' + '\n')

        bash_file.write('mkdir ${BRANCH}' + '\n')
        bash_file.write('cd ${BRANCH}' + '\n')

        # datalad clone the input ria:
        bash_file.write("\n# Clone the data from input RIA:\n")
        bash_file.write('datalad clone "${dssource}" ds' + "\n")
        bash_file.write("cd ds")

        # set up the result deposition:
        bash_file.write("\n# Register output RIA as remote for result deposition:\n")
        bash_file.write('git remote add outputstore "${pushgitremote}"' + "\n")
        # ^^ `git remote add <give a name> <folder where the remote is>`
        #   is to add a new remote to your git repo

        # set up a new branch:
        bash_file.write("\n# Create a new branch for this job's results:" + "\n")
        bash_file.write('git checkout -b "${BRANCH}"' + "\n")

        # Start of the application-specific code: ------------------------------
        # # pull the input data ????????:
        # bash_file.write("\n# Pull down input data manully:")
        # bash_file.write('datalad get -n "inputs/data/${subid}"')
        # ^^ TODO: if to include, change:
        # 1) based on type_session
        # 2) zip or not
        # checkout: fmriprep; fmriprep_ingressed_fs

        # `datalad get` the container??????
        # TODO: include ^^?

        # `datalad run`:
        bash_file.write("\n# datalad run:\n")
        cmd_datalad_run = generate_cmd_datalad_run(self, input_ds, type_session)

        # Finish up:

        # Done generating `participant_job.sh`:
        bash_file.write("\n")
        bash_file.close()

        # TODO: add: change permission of this bash script
        # see: end of `generate_bash_run_bidsapp()`!

        print("")
