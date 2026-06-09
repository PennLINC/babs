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
    cfg = {'pre_app': None, 'post_run': []}
    assert resolve_hooks(cfg) == ([], [], [])


def test_raw_snippet_is_verbatim_with_no_materialization():
    cfg = {'pre_app': ['echo hello']}
    pre_app, post_run, materializations = resolve_hooks(cfg)
    assert pre_app == ['echo hello']
    assert post_run == []
    assert materializations == []


def test_script_path_used_verbatim():
    # `script:` is an absolute local path used as-is (like imported_files);
    # the destination name is its basename.
    cfg = {'pre_app': [{'script': '/proj/hooks/validate.sh'}]}
    pre_app, _, materializations = resolve_hooks(cfg)
    assert pre_app == ['bash ./code/hooks/validate.sh']
    assert materializations == [
        CopyIn(original_path='/proj/hooks/validate.sh', name='validate')
    ]
    assert materializations[0].as_import() == {
        'original_path': '/proj/hooks/validate.sh',
        'analysis_path': 'code/hooks/validate.sh',
    }


def test_default_name_only_strips_trailing_sh():
    # a source without a .sh suffix keeps its basename as the name
    cfg = {'pre_app': [{'script': '/tools/runme'}]}
    pre_app, _, _ = resolve_hooks(cfg)
    assert pre_app == ['bash ./code/hooks/runme.sh']


def test_order_preserved_within_and_across_splice_points():
    cfg = {
        'pre_app': ['echo a', 'echo b'],
        'post_run': ['echo c'],
    }
    pre_app, post_run, _ = resolve_hooks(cfg)
    assert pre_app == ['echo a', 'echo b']
    assert post_run == ['echo c']


def test_different_sources_same_name_collide():
    cfg = {
        'pre_app': [{'script': '/a/validate.sh'}],
        'post_run': [{'script': '/b/validate.sh'}],
    }
    with pytest.raises(ValueError, match='Duplicate hook name'):
        resolve_hooks(cfg)


def test_same_script_at_both_points_materializes_once():
    # The identical hook reused at pre_app and post_run (e.g. a validator) is
    # copied once and referenced from each list -- not a collision.
    cfg = {
        'pre_app': [{'script': '/proj/hooks/validate.sh'}],
        'post_run': [{'script': '/proj/hooks/validate.sh'}],
    }
    pre_app, post_run, materializations = resolve_hooks(cfg)
    assert pre_app == ['bash ./code/hooks/validate.sh']
    assert post_run == ['bash ./code/hooks/validate.sh']
    assert materializations == [
        CopyIn(original_path='/proj/hooks/validate.sh', name='validate')
    ]


def test_render_equality_distinguishes_context():
    # The collision rule keys on descriptor equality; Render carries `context`,
    # so the same template rendered two ways into one name is a real conflict.
    # (Render isn't produced by resolve_hooks yet -- this pins the invariant.)
    assert Render('zip.sh.jinja2', 'zip', {'a': 1}) == Render('zip.sh.jinja2', 'zip', {'a': 1})
    assert Render('zip.sh.jinja2', 'zip', {'a': 1}) != Render('zip.sh.jinja2', 'zip', {'a': 2})


def test_unknown_splice_point_raises():
    with pytest.raises(ValueError, match='Unknown hook splice point'):
        resolve_hooks({'pre-app': ['echo x']})


def test_non_mapping_config_raises():
    with pytest.raises(ValueError, match='must be a mapping'):
        resolve_hooks(['echo x'])


@pytest.mark.parametrize('entry', [{'builtin': 'zip'}, {'container': 'nordic'}, 42])
def test_unsupported_entry_forms_raise(entry):
    with pytest.raises(ValueError, match='Unsupported hook entry'):
        resolve_hooks({'pre_app': [entry]})


@pytest.mark.parametrize('extra_key', ['name', 'singularity_args'])
def test_unknown_key_in_script_entry_raises(extra_key):
    # `name` is rejected too: there is no override in this version.
    cfg = {'pre_app': [{'script': '/x.sh', extra_key: 'whatever'}]}
    with pytest.raises(ValueError, match='Unsupported key'):
        resolve_hooks(cfg)


@pytest.mark.parametrize('bad_source', ['/some/dir/', '..', '.'])
def test_source_with_invalid_derived_name_raises(bad_source):
    # The destination name is the source basename; a source whose basename is
    # empty or '.'/'..' has no usable name.
    cfg = {'pre_app': [{'script': bad_source}]}
    with pytest.raises(ValueError, match='Invalid hook name'):
        resolve_hooks(cfg)


def test_render_is_defined_but_never_produced():
    # The forward-compat seam exists as a type...
    r = Render(template_path='t.sh.jinja2', name='zip', context={'k': 'v'})
    assert r.analysis_path == 'code/hooks/zip.sh'
    # ...but resolve_hooks never returns one in this version (no config form maps to it).
    _, _, materializations = resolve_hooks(
        {'post_run': ['echo verbatim', {'script': '/x.sh'}]}
    )
    assert all(isinstance(m, CopyIn) for m in materializations)


def test_verbatim_dataclass_shape():
    assert Verbatim(command='echo hi').command == 'echo hi'
