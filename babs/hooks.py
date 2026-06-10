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
- **built-in** -- ``{builtin: <name>}``; the hook is a static script shipped
  inside the babs package (``templates/hooks/<name>.sh``), copied in like a
  script hook (``CopyIn``). Its per-hook params become shell **arguments** at
  the splice site, with defaults resolved at config time (e.g. zip's ``path``
  defaults to the top-level ``output_dir``) -- so several instances share one
  script and differ only in args. ``zip`` is the first built-in.

The **container-running built-in** (a babs-shipped hook composing the
``singularity run`` invocation from per-hook ``singularity_args``/
``bids_app_args``) is still deferred -- ``{container: ...}`` entries are
rejected for now. An earlier *rendered* (init-time jinja) built-in form was
prototyped and removed; reintroduce it alongside the container-running
built-ins (NORDIC) only if runtime arg/env composition turns out not to
suffice. User-provided jinja templates are intentionally *not* supported:
a template is inert without babs code to populate its context.
"""

import os.path as op
import shlex
from dataclasses import dataclass

# Where copied hook scripts land inside the analysis dataset.
HOOKS_SUBDIR = op.join('code', 'hooks')

# Where the packaged built-in hook files live.
BUILTIN_SOURCE_DIR = op.join(op.dirname(__file__), 'templates', 'hooks')

# The splice points a hooks config may target, in run order.
SPLICE_POINTS = ('pre_run', 'post_run')

# Known built-ins and the per-hook params each accepts. Also the registry of
# valid `{builtin: <name>}` names, so a typo'd name or param fails at
# resolve time. Every built-in is a static `templates/hooks/<name>.sh`;
# params become splice-site arguments.
BUILTIN_PARAMS = {'zip': {'path', 'name'}}


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


def _builtin_args(name, entry, output_dir):
    """Resolve a static built-in's params into its splice-site arguments.

    zip: ``<path> [<name>]``. ``path`` defaults to the config's top-level
    ``output_dir`` (the argless common case: archive the whole app output);
    ``name`` is only passed when configured (the script defaults it to
    ``path``'s basename).
    """
    path = entry.get('path', output_dir)
    if not path:
        raise ValueError(
            f'The {name!r} built-in needs a folder to archive: give it a '
            '`path` param or set the top-level `output_dir`.'
        )
    return (path,) if 'name' not in entry else (path, entry['name'])


def _resolve_entry(entry, output_dir=None):
    """Classify a single config entry into a materialization mode + arguments.

    Parameters
    ----------
    entry : str or dict
        One item from a ``pre_run:`` / ``post_run:`` list.
    output_dir : str or None
        The config's top-level ``output_dir``; defaults static built-in args
        (zip's ``path``).

    Returns
    -------
    mode : Verbatim or CopyIn
        The classified mode.
    args : tuple of str
        Splice-site arguments for the hook's command (built-ins only; empty
        otherwise). Args belong to the *command*, not the materialization:
        several instances of one built-in share a single materialized file
        and differ only in args.
    """
    if isinstance(entry, str):
        return Verbatim(command=entry), ()

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
        return CopyIn(original_path=source, name=name), ()

    if isinstance(entry, dict) and 'builtin' in entry:
        name = entry['builtin']
        if name not in BUILTIN_PARAMS:
            raise ValueError(
                f'Unknown built-in hook {name!r}; available: {sorted(BUILTIN_PARAMS)}.'
            )
        unknown = set(entry) - {'builtin'} - BUILTIN_PARAMS[name]
        if unknown:
            raise ValueError(
                f'Unsupported key(s) {sorted(unknown)} for built-in hook {name!r}; '
                f'it accepts {sorted(BUILTIN_PARAMS[name])}.'
            )
        # A built-in is copied in like a script hook; its params become
        # splice-site arguments (resolved here, at config time, so defaults
        # like zip's path <- output_dir are visible in participant_job.sh).
        source = op.join(BUILTIN_SOURCE_DIR, f'{name}.sh')
        return CopyIn(original_path=source, name=name), _builtin_args(name, entry, output_dir)

    raise ValueError(
        f'Unsupported hook entry: {entry!r}. This version supports a raw shell '
        'string, a {script: <path>} mapping, or a {builtin: <name>} mapping.'
    )


def _command_for(mode, args=()):
    """The runtime command string a classified mode contributes to its splice list."""
    if isinstance(mode, Verbatim):
        return mode.command
    if isinstance(mode, CopyIn):
        command = f'bash ./{mode.analysis_path}'
        if args:
            command += ' ' + ' '.join(shlex.quote(str(arg)) for arg in args)
        return command
    raise TypeError(f'Unknown hook mode: {mode!r}')


def resolve_hooks(hooks_config, output_dir=None):
    """Resolve a ``hooks:`` config block into spliceable commands + materializations.

    Parameters
    ----------
    hooks_config : dict or None
        The top-level ``hooks:`` block (``{'pre_run': [...], 'post_run': [...]}``),
        or ``None`` when no hooks are configured.
    output_dir : str or None
        The config's top-level ``output_dir``; used to default static
        built-in arguments (the argless ``{builtin: zip}`` archives it).
        Only consulted when such a hook is configured.

    Returns
    -------
    pre_run : list of str
        Command strings to splice at the ``pre_run`` point, in order.
    post_run : list of str
        Command strings to splice at the ``post_run`` point, in order.
    materializations : list of CopyIn
        Files BABS must copy into ``code/hooks/`` at ``babs init``.
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
            f'`hooks:` must be a mapping with keys {list(SPLICE_POINTS)}, got {hooks_config!r}.'
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
            mode, args = _resolve_entry(entry, output_dir)
            resolved[point].append(_command_for(mode, args))
            if isinstance(mode, CopyIn):
                # Collision is about the materialized file, not the name alone:
                # the *same* hook used at multiple splice points (identical
                # descriptor) is fine -- copy once, reference it from each
                # list. Only a *different* descriptor claiming the same name
                # is a real conflict (one would clobber the other).
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
