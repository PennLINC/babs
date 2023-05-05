# This is to test `babs-init`.
import os
import os.path as op
import sys
import argparse
import pytest
from unittest import mock
sys.path.append("..")
sys.path.append("../babs")
from babs.utils import (read_yaml)   # noqa
from babs.cli import (    # noqa
    babs_init_main,
    babs_check_setup_main)
from get_data import (   # noqa
    get_input_data,
    container_ds_path,
    where_now,
    if_circleci,
    __location__,
    INFO_2ND_INPUT_DATA,
    LIST_WHICH_BIDSAPP,
    TOYBIDSAPP_VERSION_DASH,
    TEMPLATEFLOW_HOME
)

@pytest.mark.order(index=1)
@pytest.mark.parametrize(
    "which_bidsapp,which_input,type_session,if_input_local,if_two_input",
    #  test toybidsapp: BIDS/zipped x single/multi-ses:
    #    the input data will also be remote by default:
    [("toybidsapp", "BIDS", "single-ses", False, False),
     ("toybidsapp", "BIDS", "multi-ses", False, False),
     ("toybidsapp", "fmriprep", "single-ses", False, False),
     ("toybidsapp", "fmriprep", "multi-ses", False, False),
     # test if input is local:
     ("toybidsapp", "BIDS", "single-ses", True, False),
     # test fmriprep: single/multi-ses
     ("fmriprep", "BIDS", "single-ses", False, False),
     ("fmriprep", "BIDS", "multi-ses", False, False),
     # test qsiprep multi-ses: remove sessions without dMRI
     ("qsiprep", "BIDS", "multi-ses", False, False),
     # test 2 input datasets (2nd one will be zipped fmriprep derivatives):
     ("fmriprep", "BIDS", "single-ses", False, True),
     ("fmriprep", "BIDS", "multi-ses", False, True),
     ])
def test_babs_init(which_bidsapp, which_input, type_session, if_input_local, if_two_input,
                   tmp_path, tmp_path_factory,
                   container_ds_path, if_circleci,
                   ):
    """
    This is to test `babs-init` in different cases.

    Parameters:
    --------------
    which_bidsapp: str
        The name of a BIDS App. However here we only use `toybidsapp` to test, even though you
        specified e.g., fmriprep; we'll make sure the BIDS App to be tested is reflected in
        `container_name` which BABS cares.
        It must be one of the string in `LIST_WHICH_BIDSAPP`.
    which_input: str
        which input dataset. Options see keys in `origin_input_dataset.yaml`
    type_session: str
        multi-ses or single-ses
    if_input_local: bool
        whether the input dataset is a local copy (True), or it's remote (False)
    if_two_input: bool
        whether to use two input datasets
    tmp_path: fixture from pytest
    tmp_path_factory: fixture from pytest
    container_ds_path: fixture; str
        Path to the container datalad dataset
    if_circleci: fixture; bool
        Whether currently in CircleCI
    """
    # Sanity checks:
    assert which_bidsapp in LIST_WHICH_BIDSAPP

    # Get the path to input dataset:
    path_in = get_input_data(which_input, type_session, if_input_local, tmp_path_factory)
    input_ds_cli = [[which_input, path_in]]
    if if_two_input:
        # get another input dataset: qsiprep derivatives
        assert INFO_2ND_INPUT_DATA["which_input"] != which_input   # avoid repeated input ds name
        path_in_2nd = get_input_data(
            INFO_2ND_INPUT_DATA["which_input"],
            type_session,   # should be consistent with the 1st dataset
            INFO_2ND_INPUT_DATA["if_input_local"],
            tmp_path_factory)
        input_ds_cli.append([INFO_2ND_INPUT_DATA["which_input"], path_in_2nd])

    # Container dataset - has been set up by fixture `prep_container_ds_toybidsapp()`
    assert op.exists(container_ds_path)
    assert op.exists(op.join(container_ds_path, ".datalad/config"))

    # Preparation of freesurfer: for fmriprep and qsiprep:
    # check if `--fs-license-file` is included in YAML file:
    container_config_yaml_filename = "example_container_" + which_bidsapp + ".yaml"
    if (which_bidsapp == "fmriprep") & if_two_input:
        container_config_yaml_filename = \
            "example_container_" + which_bidsapp + "_ingressed_fs.yaml"
    container_config_yaml_file = op.join(op.dirname(__location__), "notebooks",
                                         container_config_yaml_filename)
    container_config_yaml = read_yaml(container_config_yaml_file)

    if "--fs-license-file" in container_config_yaml["singularity_run"]:
        # ^^ this way is consistent with BABS re: how to determine if fs license is needed;
        flag_requested_fs_license = True
        str_fs_license_file = container_config_yaml["singularity_run"]["--fs-license-file"]
    else:
        flag_requested_fs_license = False
        str_fs_license_file = ""

    # Preparation of env variable `TEMPLATEFLOW_HOME`:
    os.environ["TEMPLATEFLOW_HOME"] = TEMPLATEFLOW_HOME
    assert os.getenv('TEMPLATEFLOW_HOME') is not None    # assert env var has been set
    # as env var has been set up, expect that BABS will generate necessary cmd for templateflow

    # Get the cli of `babs-init`:
    where_project = tmp_path.absolute().as_posix()   # turn into a string
    project_name = "my_babs_project"
    project_root = op.join(where_project, project_name)
    container_name = which_bidsapp + "-" + TOYBIDSAPP_VERSION_DASH

    babs_init_opts = argparse.Namespace(
        where_project=where_project,
        project_name=project_name,
        input=input_ds_cli,
        list_sub_file=None,
        container_ds=container_ds_path,
        container_name=container_name,
        container_config_yaml_file=container_config_yaml_file,
        type_session=type_session,
        type_system="sge",
        keep_if_failed=False
    )

    # run `babs-init`:
    with mock.patch.object(
            argparse.ArgumentParser, 'parse_args', return_value=babs_init_opts):
        babs_init_main()

    # ================== ASSERT ============================
    # Assert by running `babs-check-setup`
    babs_check_setup_opts = argparse.Namespace(
        project_root=project_root,
        job_test=False
    )
    # Run `babs-check-setup`:
    with mock.patch.object(
            argparse.ArgumentParser, 'parse_args', return_value=babs_check_setup_opts):
        babs_check_setup_main()

    # Check if necessary commands in ``<container_name>-0-0-0_zip.sh`:
    # 1) for templateflow - for all BIDS Apps:
    #   currently strategy in BABS: if env var `$TEMPLATEFLOW_HOME` exists, set this up in cmd;
    #   and in this pytest, we have set this env var up at the beginning of this test.
    # 2) for generating `--bids-filter-file` file + command
    #   only when qsiprep/fmriprep + multi-ses
    # 3) for freesurfer: flag `--fs-license-file`

    # first, read in `<container_name>-0-0-0_zip.sh`:
    fn_bash_container_zip = op.join(project_root, "analysis/code", container_name + "_zip.sh")
    file_bash_container_zip = open(fn_bash_container_zip, 'r')
    lines_bash_container_zip = file_bash_container_zip.readlines()
    file_bash_container_zip.close()
    # check:
    if_bind_templateflow = False   # `singularity run -B` to bind a path to container
    if_bind_freesurfer = False
    str_bind_freesurfer = "-B " + str_fs_license_file \
        + ":/SGLR/FREESURFER_HOME/license.txt"
    print(str_bind_freesurfer)   # FOR DEBUGGING

    if_set_singu_templateflow = False  # `singularity run --env` to set env var within container
    if_generate_bidsfilterfile = False
    if_flag_bidsfilterfile = False
    if_flag_fs_license = False
    flag_fs_license = '--fs-license-file /SGLR/FREESURFER_HOME/license.txt'
    for line in lines_bash_container_zip:
        if "--env TEMPLATEFLOW_HOME=/SGLR/TEMPLATEFLOW_HOME" in line:
            if_set_singu_templateflow = True
        if all(ele in line for ele in ["-B",
                                       TEMPLATEFLOW_HOME + ":/SGLR/TEMPLATEFLOW_HOME"]):
            # e.g., `-B /test/templateflow_home:/SGLR/TEMPLATEFLOW_HOME \`
            if_bind_templateflow = True
        if str_bind_freesurfer in line:
            if_bind_freesurfer = True
        if "filterfile=${PWD}/${sesid}_filter.json" in line:
            if_generate_bidsfilterfile = True
        if '--bids-filter-file "${filterfile}"' in line:
            if_flag_bidsfilterfile = True
        if flag_fs_license in line:
            if_flag_fs_license = True
    # assert they are found:
    # 1) TemplateFlow: should be found in all cases:
    assert if_bind_templateflow, \
        "Env variable 'TEMPLATEFLOW_HOME' has been set," \
        + " but Templateflow home path did not get bound in 'singularity run'" \
        + " with `-B` in '" + container_name + "_zip.sh'."
    assert if_set_singu_templateflow, \
        "Env variable 'TEMPLATEFLOW_HOME' has been set," \
        + " but env variable 'SINGULARITYENV_TEMPLATEFLOW_HOME' was not set" \
        + " with `--env` in '" + container_name + "_zip.sh'."
    # 2) BIDS filter file: only when qsiprep/fmriprep & multi-ses:
    if (which_bidsapp in ["qsiprep", "fmriprep"]) & (type_session == "multi-ses"):
        assert if_generate_bidsfilterfile, \
            "This is BIDS App '" + which_bidsapp + "' and " + type_session + "," \
            + " however, filterfile to be used in `--bids-filter-file` was not generated" \
            + " in '" + container_name + "_zip.sh'."
        assert if_flag_bidsfilterfile, \
            "This is BIDS App '" + which_bidsapp + "' and " + type_session + "," \
            + " however, flag `--bids-filter-file` was not included in `singularity run`" \
            + " in '" + container_name + "_zip.sh'."
    else:
        assert (not if_generate_bidsfilterfile) & (not if_flag_bidsfilterfile), \
            "This is BIDS App '" + which_bidsapp + "' and " + type_session + "," \
            + " so `--bids-filter-file` should not be generated or used in `singularity run`" \
            + " in '" + container_name + "_zip.sh'."
    # 3) freesurfer license:
    if flag_requested_fs_license:
        assert if_bind_freesurfer, \
            "`--fs-license-file` was requested in container's YAML file," \
            + " but FreeSurfer license path did not get bound in 'singularity run'" \
            + " with `-B` in '" + container_name + "_zip.sh'."
        assert if_flag_fs_license, \
            "`--fs-license-file` was requested in container's YAML file," \
            + " but flag `" + flag_fs_license + "` was not found in the `singularity run`" \
            + " in '" + container_name + "_zip.sh'." \
            + " Path to YAML file: '" + container_config_yaml_file + "'."

    # Check `sub_ses_final_inclu.csv`:
    #   if qsiprep + multi-ses:  one session without dMRI should not be included
    if (which_bidsapp == "qsiprep") & (type_session == "multi-ses"):
        # load `sub_ses_final_inclu.csv`:
        fn_list_final_inclu = op.join(project_root, "analysis/code", "sub_ses_final_inclu.csv")
        file_list_final_inclu = open(fn_list_final_inclu, 'r')
        lines_list_final_inclu = file_list_final_inclu.readlines()
        file_list_final_inclu.close()
        for line in lines_list_final_inclu:
            if_inclu_missing_session = False
            if 'sub-02,ses-A' in line:
                if_inclu_missing_session = True
        assert not if_inclu_missing_session, \
            "'sub-02,ses-A' without dMRI was included in the BABS project of " \
            + which_bidsapp + ", " + type_session

    # Note: No need to manually remove temporary dirs; those are created by pytest's fixtures
    #   and will be automatically removed after 3 runs of pytests. ref below:
    #   https://docs.pytest.org/en/7.1.x/how-to/tmp_path.html#the-default-base-temporary-directory
