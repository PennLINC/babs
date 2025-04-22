"""Test the check_setup functionality."""

from pathlib import Path

from babs import BABSCheckSetup, BABSUpdate


def test_sync_code(babs_project_sessionlevel):
    """Test that missing config parts raise an error."""

    babs_proj = BABSUpdate(babs_project_sessionlevel)

    # Edit a file in analysis/code/
    (Path(babs_proj.analysis_path) / 'code' / 'test.py').write_text('print("Hello, world!")')

    # Run the update
    babs_proj.babs_sync_code('add test.py')

    # Check that the project is good
    check = BABSCheckSetup(babs_project_sessionlevel)
    check.babs_check_setup(submit_a_test_job=False)
