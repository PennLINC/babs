import subprocess
from pathlib import Path

import datalad.api as dlapi
import pytest

from babs.bootstrap import BABSBootstrap
from babs.templateflow import (
    TEMPLATEFLOW_PATH_IN_BABS,
    TemplateflowConfig,
    templateflow_from_config,
)

URL = 'https://github.com/templateflow/templateflow.git'


def _config(**section):
    return {'templateflow': section}


def test_absent_section_is_none():
    assert templateflow_from_config({'input_datasets': {}}) is None


def test_minimal_section():
    tf = templateflow_from_config(
        _config(url=URL, required=['tpl-OASIS30ANTs/tpl-OASIS30ANTs_res-01_T1w.nii.gz'])
    )
    assert tf == TemplateflowConfig(
        url=URL,
        clone_from=None,
        version=None,
        required=['tpl-OASIS30ANTs/tpl-OASIS30ANTs_res-01_T1w.nii.gz'],
    )


def test_templates_are_the_distinct_first_components():
    tf = templateflow_from_config(
        _config(
            url=URL,
            version='abc123',
            required=[
                'tpl-MNI152NLin2009cAsym/*_res-02_T1w.nii.gz',
                'tpl-MNI152NLin2009cAsym/*_res-02_desc-brain_mask.nii.gz',
                'tpl-OASIS30ANTs',
            ],
        )
    )
    assert tf.version == 'abc123'
    assert tf.templates == ['tpl-MNI152NLin2009cAsym', 'tpl-OASIS30ANTs']


@pytest.mark.parametrize(
    ('section', 'message'),
    [
        ({'url': URL, 'required': ['tpl-X/a'], 'versoin': 'x'}, 'Unknown key'),
        ({'required': ['tpl-X/a']}, 'url'),
        ({'url': '', 'required': ['tpl-X/a']}, 'url'),
        ({'url': URL, 'clone_from': '', 'required': ['tpl-X/a']}, 'clone_from'),
        ({'url': URL, 'clone_from': '$HOME/tf', 'required': ['tpl-X/a']}, 'only the placeholder'),
        ({'url': URL, 'clone_from': '${TEMPLATEFLOW_HOME}', 'required': ['tpl-X/a']}, 'only'),
        ({'url': URL, 'version': '', 'required': ['tpl-X/a']}, 'version'),
        ({'url': URL}, 'required'),
        ({'url': URL, 'required': []}, 'required'),
        ({'url': URL, 'required': 'tpl-X/a'}, 'required'),
        ({'url': URL, 'required': ['/abs/tpl-X/a']}, 'relative'),
        ({'url': URL, 'required': ['tpl-X/../tpl-Y/a']}, r"'\.\.'"),
        ({'url': URL, 'required': ['tpl-*/a']}, 'literal template'),
        ({'url': URL, 'required': ['sub-01/a']}, 'literal template'),
        ({'url': URL, 'required': ['']}, 'non-empty'),
    ],
)
def test_malformed_section_is_refused(section, message):
    with pytest.raises(ValueError, match=message):
        templateflow_from_config(_config(**section))


def test_clone_from_resolution(monkeypatch):
    def tf(clone_from):
        return templateflow_from_config(
            _config(url=URL, clone_from=clone_from, required=['tpl-X/a'])
        )

    assert tf(None).resolve_clone_from() == URL
    assert tf('/site/templateflow').resolve_clone_from() == '/site/templateflow'
    monkeypatch.setenv('TEMPLATEFLOW_HOME', '/site/tf-home')
    assert tf('$TEMPLATEFLOW_HOME').resolve_clone_from() == '/site/tf-home'
    monkeypatch.delenv('TEMPLATEFLOW_HOME')
    with pytest.raises(ValueError, match='not set'):
        tf('$TEMPLATEFLOW_HOME').resolve_clone_from()


def test_section_must_be_a_mapping():
    with pytest.raises(TypeError, match='mapping'):
        templateflow_from_config({'templateflow': ['tpl-X/a']})


# --- registration at `babs init` -------------------------------------------------


def _git(cwd, *args):
    return subprocess.run(
        ['git', *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def fake_templateflow(tmp_path):
    """A templateflow-shaped superdataset with one `tpl-Foo` subdataset, two commits.

    Returns the path and the first commit, so a pinned `version` has somewhere to go.
    """
    tf = dlapi.create(tmp_path / 'templateflow')
    dlapi.create(dataset=tf.path, path=tmp_path / 'templateflow' / 'tpl-Foo')
    first = _git(tf.path, 'rev-parse', 'HEAD')
    (tmp_path / 'templateflow' / 'README').write_text('later\n')
    tf.save(message='a later commit')
    return tmp_path / 'templateflow', first


def _bootstrap(tmp_path, **section):
    bs = BABSBootstrap(tmp_path / 'project')
    dlapi.create(bs.analysis_path)
    bs.templateflow = templateflow_from_config({'templateflow': section})
    return bs


def _registered_commit(bs):
    return _git(bs.analysis_path, 'rev-parse', f'HEAD:{TEMPLATEFLOW_PATH_IN_BABS}')


def test_register_keeps_cloned_version_when_unpinned(tmp_path, fake_templateflow):
    tf_path, _ = fake_templateflow
    bs = _bootstrap(tmp_path, url=str(tf_path), required=['tpl-Foo/*'])
    bs._register_templateflow()
    assert _registered_commit(bs) == _git(tf_path, 'rev-parse', 'HEAD')
    # only templateflow itself is installed; the template subdataset waits for the job
    assert not (Path(bs.analysis_path) / TEMPLATEFLOW_PATH_IN_BABS / 'tpl-Foo' / '.git').exists()
    assert _git(bs.analysis_path, 'status', '--porcelain') == ''


def test_register_pins_version(tmp_path, fake_templateflow):
    tf_path, first = fake_templateflow
    bs = _bootstrap(tmp_path, url=str(tf_path), version=first, required=['tpl-Foo/*'])
    bs._register_templateflow()
    assert _registered_commit(bs) == first
    assert _git(bs.analysis_path, 'status', '--porcelain') == ''


def test_register_refuses_unknown_version(tmp_path, fake_templateflow):
    tf_path, _ = fake_templateflow
    bs = _bootstrap(tmp_path, url=str(tf_path), version='no-such-ref', required=['tpl-Foo/*'])
    with pytest.raises(ValueError, match='could not be checked out'):
        bs._register_templateflow()


def test_register_refuses_unknown_template(tmp_path, fake_templateflow):
    tf_path, _ = fake_templateflow
    bs = _bootstrap(tmp_path, url=str(tf_path), required=['tpl-Bar/*'])
    with pytest.raises(ValueError, match='tpl-Bar, which is not a template subdataset'):
        bs._register_templateflow()


def test_register_clones_from_local_copy_records_url(tmp_path, fake_templateflow, monkeypatch):
    """`clone_from` is only where init clones from; `.gitmodules` records `url`."""
    tf_path, _ = fake_templateflow
    monkeypatch.setenv('TEMPLATEFLOW_HOME', str(tf_path))
    bs = _bootstrap(
        tmp_path,
        url='https://example.org/templateflow.git',
        clone_from='$TEMPLATEFLOW_HOME',
        required=['tpl-Foo/*'],
    )
    bs._register_templateflow()
    assert _registered_commit(bs) == _git(tf_path, 'rev-parse', 'HEAD')
    recorded = _git(
        bs.analysis_path,
        'config',
        '--file',
        '.gitmodules',
        f'submodule.{TEMPLATEFLOW_PATH_IN_BABS}.url',
    )
    assert recorded == 'https://example.org/templateflow.git'
    assert _git(bs.analysis_path, 'status', '--porcelain') == ''
