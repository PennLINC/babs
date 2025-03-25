from babs.generate_bidsapp_runscript import container_args_from_config, get_input_unzipping_cmds

input_datasets_prep = [
    {
        'name': 'bids',
        'path_now_rel': 'inputs/data/bids',
        'is_zipped': False,
    },
]

input_datasets_fmriprep_ingressed_anat = [
    {
        'name': 'freesurfer',
        'path_now_rel': 'inputs/data/freesurfer',
        'is_zipped': True,
    },
    {
        'name': 'bids',
        'path_now_rel': 'inputs/data/bids',
        'is_zipped': False,
    },
]

input_datasets_xcpd = [
    {
        'name': 'fmriprep',
        'path_now_rel': 'inputs/data/fmriprep',
        'is_zipped': True,
    },
]

input_datasets_qsirecon = [
    {
        'name': 'qsiprep',
        'path_now_rel': 'inputs/data/qsiprep',
        'is_zipped': True,
    },
]

input_datasets_qsirecon_ingressed_anat_zipped = [
    {
        'name': 'freesurfer',
        'path_now_rel': 'inputs/data/freesurfer',
        'is_zipped': True,
    },
    {
        'name': 'qsiprep',
        'path_now_rel': 'inputs/data/qsiprep',
        'is_zipped': True,
    },
]

input_datastes_qsirecon_hsvs = []


def test_get_input_unipping_cmds():
    """Test that the input unzipping commands are generated correctly."""
    assert get_input_unzipping_cmds(input_datasets_prep) == ''

    assert len(get_input_unzipping_cmds(input_datasets_fmriprep_ingressed_anat)) > 0

    assert len(get_input_unzipping_cmds(input_datasets_xcpd)) > 0

    assert len(get_input_unzipping_cmds(input_datasets_qsirecon)) > 0

    assert len(get_input_unzipping_cmds(input_datasets_qsirecon_ingressed_anat_zipped)) > 0

    assert len(get_input_unzipping_cmds(input_datastes_qsirecon_hsvs)) > 0


def test_container_args_from_config():
    """Test that the container arguments are generated correctly."""
    assert container_args_from_config(input_datasets_prep) == ''

    assert len(container_args_from_config(input_datasets_fmriprep_ingressed_anat)) > 0
