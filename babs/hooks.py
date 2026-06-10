"""Resolve a `hooks:` config block into spliceable commands + materializations.

A BABS container config may carry a top-level ``hooks:`` block with
``pre_run:`` / ``post_run:`` lists. Each entry names a snippet of work to run
at the corresponding splice point in ``participant_job.sh`` (added in the
splice-points step). This module turns those config entries into:

- the **runtime command strings** spliced into the job script, and
- the **file materializations** BABS must perform at ``babs init`` (copying a
  user script into ``code/hooks/<name>.sh``).

`resolve_hooks` is **pure** (config in -> commands + descriptors out, no I/O);
the caller (`Bootstrap`) performs the materializations.

Entry forms supported in this version:

- **snippet** -- a bare string, spliced verbatim (``Verbatim``).
- **script** -- ``{script: <path>}``; copied into
  ``code/hooks/<basename>.sh`` and invoked as ``bash ./code/hooks/<basename>.sh``
  (``CopyIn``). ``<path>`` is an absolute local path used verbatim -- the same
  convention as ``imported_files.original_path``, which this reuses. The
  destination name is the source basename. The *same* script may appear at
  multiple splice points (e.g. a validator at ``pre_run`` and ``post_run``) --
  it is copied once and referenced from each. Two *different* sources sharing a
  basename collide (no name override yet -- add one if needed).
- **built-in** -- ``{builtin: <name>}``; babs renders a shipped
  ``templates/hooks/<name>.sh.jinja2`` into ``code/hooks/<name>.sh`` at init
  (``Render``). Keys beyond ``builtin`` are per-hook params for the template;
  bootstrap merges in the top-level/derived render context (e.g. ``output_dir``).
  ``zip`` is the first built-in.

The **container-running templated built-in** (a babs-shipped ``singularity run``
template parameterised by per-hook ``singularity_args``/``bids_app_args``) also
lands as a ``Render``, but is still deferred -- ``{container: ...}`` entries are
rejected for now. User-provided jinja templates are intentionally *not*
supported: a template is inert without babs code to populate its context.
"""

import os.path as op
from dataclasses import dataclass, field

# Where copied/rendered hook scripts land inside the analysis dataset.
HOOKS_SUBDIR = op.join('code', 'hooks')

# The splice points a hooks config may target, in run order.
SPLICE_POINTS = ('pre_run', 'post_run')


@dataclass(frozen=True)
class Verbatim:
    """Snippet hook: a raw shell snippet spliced inline. No file materialization."""

    command: str


@dataclass(frozen=True)
class CopyIn:
    """Script hook (or static built-in): copy ``original_path`` -> ``code/hooks/<name>.sh``."""

    original_path: str
    name: str

    @property
    def analysis_path(self):
        """Destination relative to the analysis dataset root."""
        return op.join(HOOKS_SUBDIR, f'{self.name}.sh')

    def as_import(self):
        """Shape consumed by ``Bootstrap._init_import_files``."""
        return {'original_path': self.original_path, 'analysis_path': self.analysis_path}


@dataclass(frozen=True)
class Render:
    """Templated built-in: render ``template_path`` -> ``code/hooks/<name>.sh``.

    ``template_path`` is loader-relative (``PackageLoader('babs', 'templates')``).
    ``context`` is the config-derived part (per-hook params); bootstrap merges in
    the top-level/derived part (e.g. ``output_dir``) before rendering. Produced for
    ``{builtin: <name>}`` entries; the ``{container: ...}`` scaffold is still deferred.
    """

    template_path: str
    name: str
    context: dict = field(default_factory=dict)

    @property
    def analysis_path(self):
        """Destination relative to the analysis dataset root."""
        return op.join(HOOKS_SUBDIR, f'{self.name}.sh')


def _validate_name(name, entry):
    """Reject a hook name that would escape ``code/hooks/`` or is empty."""
    if not name or name in ('.', '..') or op.basename(name) != name:
        raise ValueError(
            f'Invalid hook name {name!r} from entry {entry!r}: a hook name must be '
            'a bare filename (no path separators, not "." or "..").'
        )


def _default_name(source):
    """Derive a hook name from a source path: basename with a trailing ``.sh`` dropped."""
    base = op.basename(source)
    return base[:-3] if base.endswith('.sh') else base


def _resolve_entry(entry):
    """Classify a single config entry into a materialization mode.

    Parameters
    ----------
    entry : str or dict
        One item from a ``pre_run:`` / ``post_run:`` list.

    Returns
    -------
    Verbatim, CopyIn, or Render
        The classified mode.
    """
    if isinstance(entry, str):
        return Verbatim(command=entry)

    if isinstance(entry, dict) and 'script' in entry:
        unknown = set(entry) - {'script'}
        if unknown:
            raise ValueError(
                f'Unsupported key(s) {sorted(unknown)} in script hook entry {entry!r}; '
                'expected only "script".'
            )
        source = entry['script']
        # The destination name is derived from the source basename; there is no
        # override yet, so two sources with the same basename collide (see below).
        name = _default_name(source)
        _validate_name(name, entry)
        # `source` is used verbatim as the copy source -- same convention as
        # `imported_files.original_path` (an absolute local path; resolved by
        # `_init_import_files`, which raises FileNotFoundError on a bad path).
        return CopyIn(original_path=source, name=name)

    if isinstance(entry, dict) and 'builtin' in entry:
        name = entry['builtin']
        _validate_name(name, entry)
        # Keys beyond `builtin` are per-hook parameters for the built-in's
        # template (e.g. zip's optional `path`). They are the *config-derived*
        # part of the render context; bootstrap merges in the top-level/derived
        # part (e.g. `output_dir`, `processing_level`) at render time. The
        # template path is loader-relative (PackageLoader('babs', 'templates'));
        # an unknown built-in fails as TemplateNotFound at init.
        context = {k: v for k, v in entry.items() if k != 'builtin'}
        return Render(template_path=f'hooks/{name}.sh.jinja2', name=name, context=context)

    raise ValueError(
        f'Unsupported hook entry: {entry!r}. This version supports a raw shell '
        'string, a {script: <path>} mapping, or a {builtin: <name>} mapping.'
    )


def _command_for(mode):
    """The runtime command string a classified mode contributes to its splice list."""
    if isinstance(mode, Verbatim):
        return mode.command
    if isinstance(mode, (CopyIn, Render)):
        return f'bash ./{mode.analysis_path}'
    raise TypeError(f'Unknown hook mode: {mode!r}')


def resolve_hooks(hooks_config):
    """Resolve a ``hooks:`` config block into spliceable commands + materializations.

    Parameters
    ----------
    hooks_config : dict or None
        The top-level ``hooks:`` block (``{'pre_run': [...], 'post_run': [...]}``),
        or ``None`` when no hooks are configured.

    Returns
    -------
    pre_run : list of str
        Command strings to splice at the ``pre_run`` point, in order.
    post_run : list of str
        Command strings to splice at the ``post_run`` point, in order.
    materializations : list of (CopyIn or Render)
        Files BABS must copy/render into ``code/hooks/`` at ``babs init``.
        `Verbatim` entries contribute no materialization.

    Raises
    ------
    ValueError
        On an unknown splice-point key, an unsupported entry form, an invalid
        hook name, or two *different* hooks resolving to the same name in the
        (shared) ``code/hooks/`` namespace. The identical hook reused at
        multiple splice points is allowed (materialized once).
    """
    if hooks_config is None:
        return [], [], []
    if not isinstance(hooks_config, dict):
        raise ValueError(
            f'`hooks:` must be a mapping with keys {list(SPLICE_POINTS)}, '
            f'got {hooks_config!r}.'
        )
    unknown_points = set(hooks_config) - set(SPLICE_POINTS)
    if unknown_points:
        raise ValueError(
            f'Unknown hook splice point(s) {sorted(unknown_points)}; '
            f'expected only {list(SPLICE_POINTS)}.'
        )

    resolved = {point: [] for point in SPLICE_POINTS}
    materializations = []
    seen = {}  # name -> (descriptor, splice point that first claimed it)

    for point in SPLICE_POINTS:
        for entry in hooks_config.get(point) or []:
            mode = _resolve_entry(entry)
            resolved[point].append(_command_for(mode))
            if isinstance(mode, (CopyIn, Render)):
                # Collision is about the materialized file, not the name alone:
                # the *same* hook used at multiple splice points (identical
                # descriptor) is fine -- copy/render once, reference it from
                # each list. Only a *different* descriptor claiming the same
                # name is a real conflict (one would clobber the other). For a
                # Render this includes a differing `context` -- same template
                # rendered two ways into one file collides.
                if mode.name in seen:
                    prior, prior_point = seen[mode.name]
                    if mode == prior:
                        continue  # same file; already materialized
                    where = (
                        repr(point) if prior_point == point else f'{prior_point!r} and {point!r}'
                    )
                    raise ValueError(
                        f'Duplicate hook name {mode.name!r} ({where}): two different '
                        f'hooks both resolve to {op.join(HOOKS_SUBDIR, mode.name + ".sh")!r}.'
                    )
                seen[mode.name] = (mode, point)
                materializations.append(mode)

    return resolved['pre_run'], resolved['post_run'], materializations
