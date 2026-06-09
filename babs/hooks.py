"""Resolve a `hooks:` config block into spliceable commands + materializations.

A BABS container config may carry a top-level ``hooks:`` block with
``pre_app:`` / ``post_run:`` lists. Each entry names a snippet of work to run
at the corresponding splice point in ``participant_job.sh`` (added in the
splice-points step). This module turns those config entries into:

- the **runtime command strings** spliced into the job script, and
- the **file materializations** BABS must perform at ``babs init`` (copying a
  user script into ``code/hooks/<name>.sh``).

`resolve_hooks` is **pure** (config in -> commands + descriptors out, no I/O);
the caller (`Bootstrap`) performs the materializations.

Entry forms supported in this version:

- **(a) raw snippet** -- a bare string, spliced verbatim (``Verbatim``).
- **(b) user script** -- ``{script: <path>}``; copied into
  ``code/hooks/<basename>.sh`` and invoked as ``bash ./code/hooks/<basename>.sh``
  (``CopyIn``). The destination name is the source basename; two sources sharing
  a basename collide (no override yet -- add one if it proves needed).

`Render` (rendering a shipped ``*.sh.jinja2`` through the shared singularity
partial) is defined here as the forward-compatible seam, but `resolve_hooks`
does not yet produce one -- entries requiring it are rejected. See the
pipeline-of-one design notes for the builtin/container forms it will carry.
"""

import os.path as op
from dataclasses import dataclass, field

# Where copied/rendered hook scripts land inside the analysis dataset.
HOOKS_SUBDIR = op.join('code', 'hooks')

# The splice points a hooks config may target, in run order.
SPLICE_POINTS = ('pre_app', 'post_run')


@dataclass(frozen=True)
class Verbatim:
    """Form (a): a raw shell snippet spliced inline. No file materialization."""

    command: str


@dataclass(frozen=True)
class CopyIn:
    """Form (b) / static built-in: copy ``original_path`` -> ``code/hooks/<name>.sh``."""

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
    """Form (c) / templated built-in: render ``template_path`` -> ``code/hooks/<name>.sh``.

    Defined as the forward-compatible seam; `resolve_hooks` does not yet produce
    one (wired in a later step alongside the shared singularity partial).
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


def _resolve_entry(entry, source_base):
    """Classify a single config entry into a materialization mode.

    Parameters
    ----------
    entry : str or dict
        One item from a ``pre_app:`` / ``post_run:`` list.
    source_base : str
        Directory that relative ``script:`` paths resolve against (the
        ``babs init`` invocation cwd). Absolute paths pass through unchanged.

    Returns
    -------
    Verbatim or CopyIn
        The classified mode. (`Render` is not produced in this version.)
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
        original_path = source if op.isabs(source) else op.join(source_base, source)
        return CopyIn(original_path=original_path, name=name)

    raise ValueError(
        f'Unsupported hook entry: {entry!r}. This version supports a raw shell '
        'string or a {script: <path>} mapping.'
    )


def _command_for(mode):
    """The runtime command string a classified mode contributes to its splice list."""
    if isinstance(mode, Verbatim):
        return mode.command
    if isinstance(mode, (CopyIn, Render)):
        return f'bash ./{mode.analysis_path}'
    raise TypeError(f'Unknown hook mode: {mode!r}')


def resolve_hooks(hooks_config, *, source_base):
    """Resolve a ``hooks:`` config block into spliceable commands + materializations.

    Parameters
    ----------
    hooks_config : dict or None
        The top-level ``hooks:`` block (``{'pre_app': [...], 'post_run': [...]}``),
        or ``None`` when no hooks are configured.
    source_base : str
        Directory that relative ``script:`` paths resolve against (the
        ``babs init`` invocation cwd).

    Returns
    -------
    pre_app : list of str
        Command strings to splice at the ``pre_app`` point, in order.
    post_run : list of str
        Command strings to splice at the ``post_run`` point, in order.
    materializations : list of (CopyIn or Render)
        Files BABS must copy/render into ``code/hooks/`` at ``babs init``.
        `Verbatim` entries contribute no materialization.

    Raises
    ------
    ValueError
        On an unknown splice-point key, an unsupported entry form, an invalid
        hook name, or a name collision across the (shared) ``code/hooks/``
        namespace.
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
    seen_names = {}  # name -> splice point that claimed it (for collision messages)

    for point in SPLICE_POINTS:
        for entry in hooks_config.get(point) or []:
            mode = _resolve_entry(entry, source_base=source_base)
            resolved[point].append(_command_for(mode))
            if isinstance(mode, (CopyIn, Render)):
                if mode.name in seen_names:
                    raise ValueError(
                        f'Duplicate hook name {mode.name!r} (in {point!r} and '
                        f'{seen_names[mode.name]!r}); both would write '
                        f'{op.join(HOOKS_SUBDIR, mode.name + ".sh")!r}.'
                    )
                seen_names[mode.name] = point
                materializations.append(mode)

    return resolved['pre_app'], resolved['post_run'], materializations
