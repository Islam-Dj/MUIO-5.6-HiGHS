"""Filesystem boundaries for user-selected case names and files."""
from pathlib import Path
import re


def component(value):
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError('A non-empty name without surrounding spaces is required.')
    if (value in ('.', '..') or re.search(r'[<>:"/\\|?*\x00-\x1f]', value)
            or value.endswith('.') or re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', value, re.I)):
        raise ValueError('Names cannot contain path separators, reserved characters or device names.')
    return value


def within(root, *parts):
    root = Path(root).resolve()
    target = root.joinpath(*parts).resolve()
    if target == root or not target.is_relative_to(root):
        raise ValueError('The requested path is outside its allowed folder.')
    return target


def child(root, *names):
    return within(root, *(component(name) for name in names))
