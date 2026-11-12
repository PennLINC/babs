"""This module is for the optional `templateflow` section of the container config."""

import os
import re
from dataclasses import dataclass

# Where templateflow is registered as a subdataset, relative to `analysis`.
TEMPLATEFLOW_PATH_IN_BABS = 'sourcedata/templateflow'

# The one placeholder `clone_from` recognizes, resolved from the environment at `babs init`.
TEMPLATEFLOW_HOME_TOKEN = '$TEMPLATEFLOW_HOME'

_ALLOWED_KEYS = {'url', 'clone_from', 'version', 'required'}
_TEMPLATE_DIR = re.compile(r'^tpl-[A-Za-z0-9]+$')


@dataclass(frozen=True)
class TemplateflowConfig:
    """The `templateflow` section of the container config, validated.

    Attributes
    ----------
    url: str
        The templateflow superdataset's public URL, recorded in the project's `.gitmodules`
        so that jobs, and a rerun anywhere, install templateflow from it.
    clone_from: str or None
        A local copy to clone from at `babs init` instead of `url`: a path, or the
        placeholder `$TEMPLATEFLOW_HOME`. None clones from `url`.
    version: str or None
        A commit-ish to check out after cloning; None keeps whatever the clone is at.
    required: list of str
        Patterns, relative to the templateflow root, of the files every job fetches.
        Each starts with a literal `tpl-<name>/` directory.
    """

    url: str
    clone_from: str | None
    version: str | None
    required: list[str]

    @property
    def templates(self):
        """The `tpl-*` subdatasets the `required` patterns reach, sorted."""
        return sorted({pattern.split('/', 1)[0] for pattern in self.required})

    def resolve_clone_from(self):
        """Where `babs init` clones templateflow from: `clone_from`, resolved, or `url`.

        Raises
        ------
        ValueError
            If `clone_from` is `$TEMPLATEFLOW_HOME` and that variable is not set.
        """
        if self.clone_from is None:
            return self.url
        if self.clone_from == TEMPLATEFLOW_HOME_TOKEN:
            home = os.getenv('TEMPLATEFLOW_HOME')
            if not home:
                raise ValueError(
                    '`templateflow.clone_from` is $TEMPLATEFLOW_HOME, which is not set.'
                )
            return home
        return self.clone_from


def templateflow_from_config(config):
    """Read and validate the optional `templateflow` section of a container config.

    Parameters
    ----------
    config: dict
        The whole container config.

    Returns
    -------
    TemplateflowConfig or None
        None when the section is absent.

    Raises
    ------
    TypeError
        If the section is not a mapping.
    ValueError
        If the section is present but malformed.
    """
    section = config.get('templateflow')
    if section is None:
        return None
    if not isinstance(section, dict):
        raise TypeError('`templateflow` must be a mapping with `url` and `required`.')

    unknown = set(section) - _ALLOWED_KEYS
    if unknown:
        raise ValueError(
            f'Unknown key(s) in `templateflow`: {sorted(unknown)}. '
            f'Allowed: {sorted(_ALLOWED_KEYS)}.'
        )

    url = section.get('url')
    if not isinstance(url, str) or not url:
        raise ValueError('`templateflow.url` must be a non-empty string.')

    clone_from = section.get('clone_from')
    if clone_from is not None:
        if not isinstance(clone_from, str) or not clone_from:
            raise ValueError('`templateflow.clone_from`, when given, must be a non-empty string.')
        if '$' in clone_from and clone_from != TEMPLATEFLOW_HOME_TOKEN:
            raise ValueError(
                f'`templateflow.clone_from` recognizes only the placeholder '
                f'{TEMPLATEFLOW_HOME_TOKEN} as a whole value, not other variables: {clone_from!r}'
            )

    version = section.get('version')
    if version is not None and (not isinstance(version, str) or not version):
        raise ValueError('`templateflow.version`, when given, must be a non-empty string.')

    required = section.get('required')
    if not isinstance(required, list) or not required:
        raise ValueError('`templateflow.required` must be a non-empty list of patterns.')
    for pattern in required:
        _validate_required_pattern(pattern)

    return TemplateflowConfig(
        url=url, clone_from=clone_from, version=version, required=list(required)
    )


def _validate_required_pattern(pattern):
    """Refuse a `required` pattern babs cannot map onto one template subdataset."""
    if not isinstance(pattern, str) or not pattern:
        raise ValueError(f'`templateflow.required` entries must be non-empty strings: {pattern!r}')
    if pattern.startswith('/'):
        raise ValueError(f'`templateflow.required` patterns must be relative: {pattern!r}')
    parts = pattern.split('/')
    if '..' in parts:
        raise ValueError(f"`templateflow.required` patterns must not contain '..': {pattern!r}")
    if not _TEMPLATE_DIR.match(parts[0]):
        raise ValueError(
            '`templateflow.required` patterns must start with a literal template '
            f'directory such as `tpl-MNI152NLin2009cAsym/`: {pattern!r}'
        )
