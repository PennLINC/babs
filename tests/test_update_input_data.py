"""Test the babs workflow."""

import os
import os.path as op
import shutil
import time
from pathlib import Path

import datalad.api as dl
import pytest
from conftest import get_config_simbids_path, update_yaml_for_run

from babs.cli import (
    babs_check_setup_main,
    babs_init_main,
    babs_merge_main,
    babs_status_main,
    babs_submit_main,
    babs_update_input_data_main,
)
from babs.scheduler import squeue_to_pandas


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

    # Submit a single job with the initial input data
    babs_submit_main(project_root=project_root, select=None, inclusion_file=None, count=1)

    # babs status:
    babs_status_main(project_root=project_root)

    finished = False
    for waitnum in [5, 8, 10, 15, 30, 60, 120]:
        time.sleep(waitnum)
        print(f'Waiting {waitnum} seconds...')
        df = squeue_to_pandas()
        print(df)
        if df.empty:
            finished = True
            break

    if not finished:
        raise RuntimeError('Jobs did not finish in time')

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
    assert bbs._get_results_branches() == []
    # But there should be a merged zip file
    merged_zip_file = bbs._get_merged_results_from_analysis_dir()
    assert not merged_zip_file.empty

    # Check that the job completion dataframe has the new subject
    job_completion_df = bbs.get_job_status_df()
    assert job_completion_df['has_results'].sum() > 0

    # Check that the job status dataframe has the new subject
    post_update_job_status_df = bbs.get_job_status_df()
    assert post_update_job_status_df.shape[0] > pre_update_job_status_df.shape[0]
