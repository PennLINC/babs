"""Tests for BABS command-line entry points."""

from importlib.metadata import distribution


def test_console_script_entry_points_load():
    """Ensure every installed BABS console script resolves to a callable."""
    console_scripts = [
        entry_point
        for entry_point in distribution('babs').entry_points
        if entry_point.group == 'console_scripts'
    ]

    assert console_scripts

    for entry_point in console_scripts:
        assert callable(entry_point.load()), f'{entry_point.name} does not resolve to a callable'
