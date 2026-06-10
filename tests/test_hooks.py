"""Unit tests for `babs.hooks.resolve_hooks` (pure; no I/O, no docker)."""

import pytest

from babs.hooks import (
    CopyIn,
    Render,
    Verbatim,
    resolve_hooks,
)


def test_none_config_resolves_empty():
    assert resolve_hooks(None) == ([], [], [])


def test_empty_config_resolves_empty():
    assert resolve_hooks({}) == ([], [], [])


def test_missing_or_empty_lists_resolve_empty():
    cfg = {'pre_run': None, 'post_run': []}
    assert resolve_hooks(cfg) == ([], [], [])


def test_raw_snippet_is_verbatim_with_no_materialization():
    cfg = {'pre_run': ['echo hello']}
    pre_run, post_run, materializations = resolve_hooks(cfg)
    assert pre_run == ['echo hello']
    assert post_run == []
    assert materializations == []


def test_script_path_used_verbatim():
    # `script:` is an absolute local path used as-is (like imported_files);
    # the destination name is its basename.
    cfg = {'pre_run': [{'script': '/proj/hooks/validate.sh'}]}
    pre_run, _, materializations = resolve_hooks(cfg)
    assert pre_run == ['bash ./code/hooks/validate.sh']
    assert materializations == [CopyIn(original_path='/proj/hooks/validate.sh', name='validate')]
    assert materializations[0].as_import() == {
        'original_path': '/proj/hooks/validate.sh',
        'analysis_path': 'code/hooks/validate.sh',
    }


def test_default_name_only_strips_trailing_sh():
    # a source without a .sh suffix keeps its basename as the name
    cfg = {'pre_run': [{'script': '/tools/runme'}]}
    pre_run, _, _ = resolve_hooks(cfg)
    assert pre_run == ['bash ./code/hooks/runme.sh']


def test_order_preserved_within_and_across_splice_points():
    cfg = {
        'pre_run': ['echo a', 'echo b'],
        'post_run': ['echo c'],
    }
    pre_run, post_run, _ = resolve_hooks(cfg)
    assert pre_run == ['echo a', 'echo b']
    assert post_run == ['echo c']


def test_different_sources_same_name_collide():
    cfg = {
        'pre_run': [{'script': '/a/validate.sh'}],
        'post_run': [{'script': '/b/validate.sh'}],
    }
    msg = r"Duplicate hook name 'validate' \('pre_run' and 'post_run'\)"
    with pytest.raises(ValueError, match=msg):
        resolve_hooks(cfg)


def test_same_point_same_name_collide():
    # Two different scripts with the same basename in one splice point: the
    # message names the single point, not "'pre_run' and 'pre_run'".
    cfg = {'pre_run': [{'script': '/a/validate.sh'}, {'script': '/b/validate.sh'}]}
    with pytest.raises(ValueError, match=r"Duplicate hook name 'validate' \('pre_run'\)"):
        resolve_hooks(cfg)


def test_same_script_at_both_points_materializes_once():
    # The identical hook reused at pre_run and post_run (e.g. a validator) is
    # copied once and referenced from each list -- not a collision.
    cfg = {
        'pre_run': [{'script': '/proj/hooks/validate.sh'}],
        'post_run': [{'script': '/proj/hooks/validate.sh'}],
    }
    pre_run, post_run, materializations = resolve_hooks(cfg)
    assert pre_run == ['bash ./code/hooks/validate.sh']
    assert post_run == ['bash ./code/hooks/validate.sh']
    assert materializations == [CopyIn(original_path='/proj/hooks/validate.sh', name='validate')]


def test_render_equality_distinguishes_context():
    # The collision rule keys on descriptor equality; Render carries `context`,
    # so the same template rendered two ways into one name is a real conflict.
    assert Render('zip.sh.jinja2', 'zip', {'a': 1}) == Render('zip.sh.jinja2', 'zip', {'a': 1})
    assert Render('zip.sh.jinja2', 'zip', {'a': 1}) != Render('zip.sh.jinja2', 'zip', {'a': 2})


def test_unknown_splice_point_raises():
    with pytest.raises(ValueError, match='Unknown hook splice point'):
        resolve_hooks({'pre-app': ['echo x']})


def test_non_mapping_config_raises():
    with pytest.raises(ValueError, match='must be a mapping'):
        resolve_hooks(['echo x'])


@pytest.mark.parametrize('entry', [{'container': 'nordic'}, {'unknown': 'x'}, 42])
def test_unsupported_entry_forms_raise(entry):
    # The container-running form is still deferred; arbitrary dicts / scalars are invalid.
    with pytest.raises(ValueError, match='Unsupported hook entry'):
        resolve_hooks({'pre_run': [entry]})


@pytest.mark.parametrize('extra_key', ['name', 'singularity_args'])
def test_unknown_key_in_script_entry_raises(extra_key):
    # `name` is rejected too: there is no override in this version.
    cfg = {'pre_run': [{'script': '/x.sh', extra_key: 'whatever'}]}
    with pytest.raises(ValueError, match='Unsupported key'):
        resolve_hooks(cfg)


@pytest.mark.parametrize('bad_source', ['/some/dir/', '..', '.'])
def test_source_with_invalid_derived_name_raises(bad_source):
    # The destination name is the source basename; a source whose basename is
    # empty or '.'/'..' has no usable name.
    cfg = {'pre_run': [{'script': bad_source}]}
    with pytest.raises(ValueError, match='Invalid hook name'):
        resolve_hooks(cfg)


def test_builtin_resolves_to_render():
    cfg = {'post_run': [{'builtin': 'zip'}]}
    pre_run, post_run, materializations = resolve_hooks(cfg)
    assert pre_run == []
    assert post_run == ['bash ./code/hooks/zip.sh']
    assert materializations == [
        Render(template_path='hooks/zip.sh.jinja2', name='zip', context={})
    ]
    assert materializations[0].analysis_path == 'code/hooks/zip.sh'


def test_builtin_extra_keys_become_context():
    # per-hook params (e.g. zip's optional `path`) flow into the render context
    cfg = {'post_run': [{'builtin': 'zip', 'path': 'outputs/freesurfer-7-3-2'}]}
    _, _, materializations = resolve_hooks(cfg)
    assert materializations == [
        Render(
            template_path='hooks/zip.sh.jinja2',
            name='zip',
            context={'path': 'outputs/freesurfer-7-3-2'},
        )
    ]


def test_builtin_same_name_different_context_collides():
    # descriptor equality includes context -> same name rendered two ways collides
    cfg = {
        'pre_run': [{'builtin': 'zip'}],
        'post_run': [{'builtin': 'zip', 'path': 'outputs/x'}],
    }
    with pytest.raises(ValueError, match='Duplicate hook name'):
        resolve_hooks(cfg)


def test_builtin_invalid_name_raises():
    cfg = {'post_run': [{'builtin': '../escape'}]}
    with pytest.raises(ValueError, match='Invalid hook name'):
        resolve_hooks(cfg)


def test_verbatim_dataclass_shape():
    assert Verbatim(command='echo hi').command == 'echo hi'
