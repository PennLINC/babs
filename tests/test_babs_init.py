# This is to test `babs init`.
import argparse
import os
import os.path as op
import sys
from pathlib import Path
from unittest import mock

import pytest
import yaml

sys.path.append('..')
from get_data import (  # noqa
    INFO_2ND_INPUT_DATA,
    SUPPORTED_BIDS_APPS,
    TEMPLATEFLOW_HOME,
    TOYBIDSAPP_VERSION_DASH,
    __location__,
    container_ds_path,
    get_container_config_yaml_filename,
    get_input_data,
    in_circleci,
    exec_environment,
)

from babs.cli import _enter_check_setup, _enter_init  # noqa
from babs.utils import read_yaml, write_yaml  # noqa


@pytest.mark.order(index=1)
@pytest.mark.parametrize(
    (
        'bids_app',
        'input_data_name',
        'processing_level',
        'input_is_local',
        'two_inputs',
    ),
    #  test toybidsapp: BIDS/zipped x single/session:
    #    the input data will also be remote by default:
    [
        ('toybidsapp', 'BIDS', 'subject', False, False),
        ('toybidsapp', 'BIDS', 'session', False, False),
        ('toybidsapp', 'fmriprep', 'subject', False, False),
        ('toybidsapp', 'fmriprep', 'session', False, False),
        # test if input is local:
        ('toybidsapp', 'BIDS', 'subject', True, False),
        # test fmriprep: single/session
        ('fmriprep', 'BIDS', 'subject', False, False),
        ('fmriprep', 'BIDS', 'session', False, False),
        # test qsiprep session: remove sessions without dMRI
        ('qsiprep', 'BIDS', 'session', False, False),
        # test 2 input datasets (2nd one will be zipped fmriprep derivatives):
        ('fmriprep', 'BIDS', 'subject', False, True),
        ('fmriprep', 'BIDS', 'session', False, True),
    ],
)
def test_babs_init(
    bids_app,
    input_data_name,
    processing_level,
    input_is_local,
    two_inputs,
    tmp_path,
    tmp_path_factory,
    container_ds_path,
    in_circleci,
):
    """
    This is to test `babs init` in different cases.

    Parameters
    ----------
    bids_app: str
        The name of a BIDS App. However here we only use `toybidsapp` to test, even though you
        specified e.g., fmriprep; we'll make sure the BIDS App to be tested is reflected in
        `container_name` which BABS cares.
        It must be one of the string in `SUPPORTED_BIDS_APPS`.
    input_data_name: str
        which input dataset. Options see keys in `origin_input_dataset.yaml`
    processing_level : {'subject', 'session'}
        whether processing is done on a subject-wise or session-wise basis
    input_is_local: bool
        whether the input dataset is a local copy (True), or it's remote (False)
    two_inputs: bool
        whether to use two input datasets
    tmp_path: fixture from pytest
    tmp_path_factory: fixture from pytest
    container_ds_path: fixture; str
        Path to the container datalad dataset
    in_circleci: fixture; bool
        Whether currently in CircleCI

    TODO: add `queue` and to test out Slurm version!
    """
    # Sanity checks:
    assert bids_app in SUPPORTED_BIDS_APPS

    # Get the path to input dataset:
    path_in = get_input_data(
        input_data_name,
        processing_level,
        input_is_local,
        tmp_path_factory,
    )
    input_ds_cli = {input_data_name: path_in}
    if two_inputs:
        # get another input dataset: qsiprep derivatives
        assert (
            INFO_2ND_INPUT_DATA['input_data_name'] != input_data_name
        )  # avoid repeated input ds name
        path_in_2nd = get_input_data(
            INFO_2ND_INPUT_DATA['input_data_name'],
            processing_level,  # should be consistent with the 1st dataset
            INFO_2ND_INPUT_DATA['input_is_local'],
            tmp_path_factory,
        )
        input_ds_cli[INFO_2ND_INPUT_DATA['input_data_name']] = path_in_2nd

    # Container dataset - has been set up by fixture `prep_container_ds_toybidsapp()`
    assert op.exists(container_ds_path)
    assert op.exists(op.join(container_ds_path, '.datalad/config'))

    # Preparation of freesurfer: for fmriprep and qsiprep:
    # check if `--fs-license-file` is included in YAML file:
    container_config_yaml_filename = get_container_config_yaml_filename(
        bids_app, input_data_name, two_inputs, queue='slurm'
    )
    container_config = op.join(
        op.dirname(__location__), 'notebooks', container_config_yaml_filename
    )
    assert op.exists(container_config)
    container_config_yaml = read_yaml(container_config)

    # Create temporary files for each of the imported files:
    needs_yaml_rewrite = False
    for imported_file in container_config_yaml.get('imported_files', []):
        # create a temporary file:
        fn_imported_file = tmp_path / imported_file['original_path'].lstrip('/')
        fn_imported_file.parent.mkdir(parents=True, exist_ok=True)
        with open(fn_imported_file, 'w') as f:
            f.write('FAKE DATA')
        imported_file['original_path'] = fn_imported_file
        needs_yaml_rewrite = True
    if needs_yaml_rewrite:
        print('Rewriting container config YAML file to include temporary files')
        yaml_data = container_config_yaml.copy()
        for imported_file in yaml_data.get('imported_files', []):
            imported_file['original_path'] = str(imported_file['original_path'])
        with open(container_config, 'w') as f:
            yaml.dump(yaml_data, f)

    if '--fs-license-file' in container_config_yaml['bids_app_args']:
        # ^^ this way is consistent with BABS re: how to determine if fs license is needed;
        flag_requested_fs_license = True
        str_fs_license_file = container_config_yaml['bids_app_args']['--fs-license-file']
    else:
        flag_requested_fs_license = False
        str_fs_license_file = ''

    # Preparation of env variable `TEMPLATEFLOW_HOME`:
    os.environ['TEMPLATEFLOW_HOME'] = TEMPLATEFLOW_HOME
    assert os.getenv('TEMPLATEFLOW_HOME') is not None  # assert env var has been set
    # as env var has been set up, expect that BABS will generate necessary cmd for templateflow

    # Get the cli of `babs init`:
    project_parent = tmp_path.absolute().as_posix()  # turn into a string
    project_name = 'my_babs_project'
    project_root = Path(op.join(project_parent, project_name))
    container_name = bids_app + '-' + TOYBIDSAPP_VERSION_DASH

    babs_init_opts = argparse.Namespace(
        project_root=project_root,
        datasets=input_ds_cli,
        list_sub_file=None,
        container_ds=container_ds_path,
        container_name=container_name,
        container_config=container_config,
        processing_level=processing_level,
        queue='slurm',
        keep_if_failed=False,
    )

    # run `babs init`:
    with mock.patch.object(argparse.ArgumentParser, 'parse_args', return_value=babs_init_opts):
        _enter_init()

    # ================== ASSERT ============================
    # Assert by running `babs check-setup`
    babs_check_setup_opts = argparse.Namespace(project_root=project_root, job_test=False)
    # Run `babs check-setup`:
    with mock.patch.object(
        argparse.ArgumentParser, 'parse_args', return_value=babs_check_setup_opts
    ):
        _enter_check_setup()

    # Check if necessary commands in ``<container_name>-0-0-0_zip.sh`:
    # 1) for templateflow - for all BIDS Apps:
    #   currently strategy in BABS: if env var `$TEMPLATEFLOW_HOME` exists, set this up in cmd;
    #   and in this pytest, we have set this env var up at the beginning of this test.
    # 2) for generating `--bids-filter-file` file + command
    #   only when qsiprep/fmriprep + session
    # 3) for freesurfer: flag `--fs-license-file`

    # first, read in `<container_name>-0-0-0_zip.sh`:
    fn_bash_container_zip = op.join(project_root, 'analysis/code', container_name + '_zip.sh')
    file_bash_container_zip = open(fn_bash_container_zip)
    lines_bash_container_zip = file_bash_container_zip.readlines()
    file_bash_container_zip.close()
    # check:
    # needs_binded_templateflow = False  # `singularity run -B` to bind a path to container
    freesurfer_bound_in_cmd = False
    str_bind_freesurfer = f'-B "{str_fs_license_file}":"/SGLR/FREESURFER_HOME/license.txt"'
    print(str_bind_freesurfer)  # FOR DEBUGGING

    # if_set_singu_templateflow = False  # `singularity run --env` to set env var within container
    bids_filterfile_added = False
    bids_filterfile_in_bids_app_cmd = False
    fs_license_file_in_bids_app_cmd = False
    flag_fs_license = '--fs-license-file /SGLR/FREESURFER_HOME/license.txt'
    for line in lines_bash_container_zip:
        # if '--env TEMPLATEFLOW_HOME=/SGLR/TEMPLATEFLOW_HOME' in line:
        #     if_set_singu_templateflow = True
        # if all(ele in line for ele in ['-B ${TEMPLATEFLOW_HOME}:/SGLR/TEMPLATEFLOW_HOME']):
        #     # previously, `-B /test/templateflow_home:/SGLR/TEMPLATEFLOW_HOME \`
        #     # but now change to new bind, `-B ${TEMPLATEFLOW_HOME}:/SGLR/TEMPLATEFLOW_HOME \`
        #     needs_binded_templateflow = True
        if str_bind_freesurfer in line:
            freesurfer_bound_in_cmd = True
        if 'filterfile="${PWD}/${sesid}_filter.json"' in line:
            bids_filterfile_added = True
        if '--bids-filter-file "${filterfile}"' in line:
            bids_filterfile_in_bids_app_cmd = True
        if flag_fs_license in line:
            fs_license_file_in_bids_app_cmd = True
    # assert they are found:
    # 1) TemplateFlow: should be found in all cases:
    # assert needs_binded_templateflow, (
    #     "Env variable 'TEMPLATEFLOW_HOME' has been set,"
    #     " but Templateflow home path did not get bound in 'singularity run'"
    #     " with `-B` in '" + container_name + "_zip.sh'."
    # )
    # assert if_set_singu_templateflow, (
    #     "Env variable 'TEMPLATEFLOW_HOME' has been set,"
    #     " but env variable 'SINGULARITYENV_TEMPLATEFLOW_HOME' was not set"
    #     " with `--env` in '" + container_name + "_zip.sh'."
    # )
    # 2) BIDS filter file: only when qsiprep/fmriprep & session:
    if (bids_app in ['qsiprep', 'fmriprep']) & (processing_level == 'session'):
        assert bids_filterfile_added, (
            "This is BIDS App '"
            + bids_app
            + "' and "
            + processing_level
            + ','
            + ' however, filterfile to be used in `--bids-filter-file` was not generated'
            + " in '"
            + container_name
            + "_zip.sh'."
        )
        assert bids_filterfile_in_bids_app_cmd, (
            "This is BIDS App '"
            + bids_app
            + "' and "
            + processing_level
            + ','
            + ' however, flag `--bids-filter-file` was not included in `singularity run`'
            + " in '"
            + container_name
            + "_zip.sh'."
        )
    else:
        assert (not bids_filterfile_added) & (not bids_filterfile_in_bids_app_cmd), (
            "This is BIDS App '"
            + bids_app
            + "' and "
            + processing_level
            + ','
            + ' so `--bids-filter-file` should not be generated or used in `singularity run`'
            + " in '"
            + container_name
            + "_zip.sh'."
        )
    # 3) freesurfer license:
    if flag_requested_fs_license:
        assert freesurfer_bound_in_cmd, (
            "`--fs-license-file` was requested in container's YAML file,"
            " but FreeSurfer license path did not get bound in 'singularity run'"
            " with `-B` in '" + container_name + "_zip.sh'."
        )
        assert fs_license_file_in_bids_app_cmd, (
            "`--fs-license-file` was requested in container's YAML file,"
            ' but flag `' + flag_fs_license + '` was not found in the `singularity run`'
            " in '" + container_name + "_zip.sh'."
            " Path to YAML file: '" + container_config + "'."
        )

    # Check `sub_ses_final_inclu.csv`:
    #   if qsiprep + session:  one session without dMRI should not be included
    if (bids_app == 'qsiprep') & (processing_level == 'session'):
        # load `sub_ses_final_inclu.csv`:
        fn_list_final_inclu = op.join(project_root, 'analysis/code', 'sub_ses_final_inclu.csv')
        file_list_final_inclu = open(fn_list_final_inclu)
        lines_list_final_inclu = file_list_final_inclu.readlines()
        file_list_final_inclu.close()
        for line in lines_list_final_inclu:
            missing_session_erroneously_included = False
            if 'sub-02,ses-A' in line:
                missing_session_erroneously_included = True
        assert not missing_session_erroneously_included, (
            "'sub-02,ses-A' without dMRI was included in the BABS project of "
            + bids_app
            + ', '
            + processing_level
        )
