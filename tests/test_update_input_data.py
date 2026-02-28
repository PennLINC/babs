"""Test the babs workflow."""

import os
import os.path as op
import shutil
import time
from pathlib import Path

import datalad.api as dl
import pytest
from conftest import (
    ensure_container_image,
    gather_slurm_job_diagnostics,
    get_config_simbids_path,
    update_yaml_for_run,
)

from babs.cli import (
    babs_check_setup_main,
    babs_init_main,
    babs_merge_main,
    babs_status_main,
    babs_submit_main,
    babs_update_input_data_main,
)
from babs.utils import get_results_branches_via_ls_remote


def _gather_result_branch_diagnostics(project_root, babs_proj):
    """Gather diagnostics when result branches never appear (for error message and logs)."""
    project_root = Path(project_root)
    lines = []

    # output RIA path and existence
    ria_dir = getattr(babs_proj, 'output_ria_data_dir', None)
    lines.append(f'output_ria_data_dir={ria_dir!r}')
    if ria_dir:
        lines.append(f'output_ria_data_dir exists={op.exists(ria_dir)}')
        if op.exists(ria_dir):
            lines.append(f'output_ria_data_dir is_dir={op.isdir(ria_dir)}')
            git_dir = op.join(ria_dir, '.git')
            has_git = op.exists(ria_dir) and (op.exists(git_dir) or op.isfile(git_dir))
            lines.append(f'has .git (or is bare)={has_git}')

    lines.append(gather_slurm_job_diagnostics(project_root))
    return '\n'.join(lines)


def manually_add_new_subject_to_input_data(input_data_path: str):
    """Manually update the input data to include a new subject.

    This function finds the first sub-* directory in input_data_path and
    copies it to a new directory called sub-new. All instances of sub-*
    in the file names are then replaced with sub-new. Finally, the new
    files are datalad saved. The current commit hash is returned.
    """
    # Find the first sub-* directory
    input_path = Path(input_data_path)
    sub_dirs = list(input_path.glob('sub-*'))
    if not sub_dirs:
        raise ValueError(f'No sub-* directories found in {input_data_path}')

    source_dir = sub_dirs[0]
    source_sub = source_dir.name  # e.g. 'sub-01'
    target_dir = input_path / 'sub-new'

    # Get the dataset
    ds = dl.Dataset(input_data_path)

    # Get all files in the source directory first
    ds.get(str(source_dir), recursive=True)

    # Copy the directory
    shutil.copytree(source_dir, target_dir)

    # Rename files recursively and collect updated paths
    updated_paths = []
    for root, _, files in os.walk(target_dir):
        for file in files:
            if source_sub in file:
                old_path = op.join(root, file)
                new_path = op.join(root, file.replace(source_sub, 'sub-new'))
                os.rename(old_path, new_path)
                # Add relative path from input_data_path
                updated_paths.append(str(Path(new_path).relative_to(input_path)))

    # Save with datalad
    ds.save(path=updated_paths, message='Added new subject')

    # Get the current commit hash
    commit_hash = ds.repo.get_hexsha()
    return commit_hash


@pytest.mark.parametrize('processing_level', ['subject', 'session'])
def test_babs_update_input_data(
    tmp_path_factory,
    templateflow_home,
    bids_data_singlesession,
    bids_data_multisession,
    processing_level,
    simbids_container_ds,
    capsys,
):
    """
    This is to test `babs init` on raw BIDS data.
    """
    from babs import BABSUpdate

    # Check the container dataset
    assert op.exists(simbids_container_ds)
    assert op.exists(op.join(simbids_container_ds, '.datalad/config'))

    # Check the bids input dataset:
    bids_data_source = (
        bids_data_singlesession if processing_level == 'subject' else bids_data_multisession
    )
    assert op.exists(bids_data_source)
    assert op.exists(op.join(bids_data_source, '.datalad/config'))

    # Clone the bids_data_singlesession dataset
    bids_data_source_clone = tmp_path_factory.mktemp('bids_data_source_clone')
    dl.clone(bids_data_source, bids_data_source_clone)

    # get the commit hash of the bids_data_source_clone dataset
    original_commit_hash = dl.Dataset(bids_data_source_clone).repo.get_hexsha()

    # Preparation of env variable `TEMPLATEFLOW_HOME`:
    os.environ['TEMPLATEFLOW_HOME'] = str(templateflow_home)
    assert os.getenv('TEMPLATEFLOW_HOME')

    # Get the cli of `babs init`:
    project_base = tmp_path_factory.mktemp('project')
    project_root = project_base / 'my_babs_project'
    container_name = 'simbids-0-0-3'

    # Use config_simbids.yaml instead of eg_fmriprep
    config_simbids_path = get_config_simbids_path()
    container_config = update_yaml_for_run(
        project_base,
        config_simbids_path.name,
        {'BIDS': str(bids_data_source_clone.absolute())},
    )

    # initialize the project with the original input data, check the setup, and submit a job
    babs_init_main(
        project_root=project_root,
        list_sub_file=None,
        container_ds=simbids_container_ds,
        container_name=container_name,
        container_config=container_config,
        processing_level=processing_level,
        queue='slurm',
        keep_if_failed=False,
    )
    babs_check_setup_main(project_root=project_root, job_test=True)

    # Make sure that "Input dataset BIDS is up to date." is printed:
    # Clear any previous output
    _ = capsys.readouterr()
    babs_update_input_data_main(project_root=project_root, dataset_name='BIDS')
    captured = capsys.readouterr()
    assert 'Input dataset BIDS is up to date.' in captured.out

    # Check the original inclusion dataframe:
    babs_proj = BABSUpdate(project_root=project_root)
    original_inclusion_df = babs_proj.inclusion_dataframe.copy()
    assert not original_inclusion_df.empty

    ensure_container_image(project_root, 'simbids-0-0-3')

    # Submit a single job with the initial input data
    babs_submit_main(project_root=project_root, select=None, inclusion_file=None, count=1)

    # babs status (same as workflow tests)
    babs_status_main(project_root=project_root)

    # Wait until queue is empty
    finished = False
    for waitnum in [5, 8, 10, 15, 30, 60, 120]:
        time.sleep(waitnum)
        print(f'Waiting {waitnum} seconds for job queue to empty...')
        currently_running_df = babs_proj.get_currently_running_jobs_df()
        print(currently_running_df)
        if currently_running_df.empty:
            finished = True
            break

    if not finished:
        raise RuntimeError('Jobs did not finish in time')

    # Refresh status from output RIA so we see pushed branches (same as workflow tests)
    babs_status_main(project_root=project_root)

    # Wait until at least one result branch exists before merge (ensures job completed and pushed).
    # Use git ls-remote to list branches; git branch --list in RIA store can hang in CI.
    babs_proj = BABSUpdate(project_root=project_root)
    ria_dir = babs_proj.output_ria_data_dir
    exists = op.exists(ria_dir) if ria_dir else False
    print(f'[DEBUG] Checking result branches at output_ria_data_dir={ria_dir!r} exists={exists}')
    branches_appeared = False
    for waitnum in [5, 8, 10, 15, 30, 60]:
        time.sleep(waitnum)
        print(f'Waiting {waitnum} seconds for result branch in output RIA...')
        result_branches = get_results_branches_via_ls_remote(babs_proj.output_ria_data_dir)
        print(f'Result branches: {result_branches}')
        if result_branches:
            branches_appeared = True
            break

    if not branches_appeared:
        diag = _gather_result_branch_diagnostics(project_root, babs_proj)
        print('[DEBUG] No result branches in output RIA. Diagnostics:\n' + diag)
        msg = (
            'No result branches appeared in output RIA after job queue emptied. '
            'Job may have failed; run babs status and check analysis/logs.\n'
            'Diagnostics:\n' + diag
        )
        raise RuntimeError(msg)

    # Now update the input data manually:
    new_commit_hash = manually_add_new_subject_to_input_data(
        str(bids_data_source_clone.absolute())
    )
    assert new_commit_hash != original_commit_hash

    babs_merge_main(project_root=project_root, chunk_size=200, trial_run=False)
    pre_update_job_status_df = babs_proj.get_job_status_df().copy()

    # Perform the input data update
    babs_update_input_data_main(project_root=project_root, dataset_name='BIDS')

    bbs = BABSUpdate(project_root=project_root)

    # The results branch should have been deleted after the merge happened
    assert get_results_branches_via_ls_remote(bbs.output_ria_data_dir) == []
    # But there should be a merged zip file
    merged_zip_file = bbs._get_merged_results_from_analysis_dir()
    assert not merged_zip_file.empty

    # Check that the job completion dataframe has the new subject
    job_completion_df = bbs.get_job_status_df()
    assert job_completion_df['has_results'].sum() > 0

    # Check that the job status dataframe has the new subject
    post_update_job_status_df = bbs.get_job_status_df()
    assert post_update_job_status_df.shape[0] > pre_update_job_status_df.shape[0]
