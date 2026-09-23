"""Validate every ZIP member before extracting a single case to staging."""
from pathlib import Path, PurePosixPath
import os
import shutil
import stat
from zipfile import ZipFile
from Classes.Base.SafePaths import component, within

MAX_MEMBERS = 50000
MAX_BYTES = 8 * 1024 ** 3


def extract_case(archive, staging):
    with ZipFile(archive) as zipped:
        infos = zipped.infolist()
        if len(infos) > MAX_MEMBERS or sum(i.file_size for i in infos) > MAX_BYTES:
            raise ValueError('Archive exceeds the case import limit (50,000 files / 8 GiB expanded).')
        members = []
        seen = set()
        for info in infos:
            raw = info.filename
            if '\\' in raw or raw.startswith('/'):
                raise ValueError('Archive contains an unsafe path.')
            parts = PurePosixPath(raw).parts
            for name in parts:
                component(name)
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ValueError('Archive links are not supported.')
            key = '/'.join(parts).casefold()
            if key in seen:
                raise ValueError('Archive contains duplicate paths.')
            seen.add(key)
            members.append((info, parts))
        roots = [parts[:-1] for info, parts in members if parts and parts[-1] == 'genData.json' and not info.is_dir()]
        if len(roots) != 1 or not roots[0]:
            raise ValueError('Import one case containing one genData.json file.')
        prefix = roots[0]
        case = component(prefix[-1])
        destination = within(staging, case)
        for info, parts in members:
            if info.is_dir() and prefix[:len(parts)] == parts:
                continue
            if parts[:len(prefix)] != prefix:
                raise ValueError('Archive contains files outside the selected case.')
            relative = parts[len(prefix):]
            if not relative:
                continue
            if relative[0] in ('.executions', '.run-history'):
                raise ValueError('Internal execution and recovery folders cannot be imported.')
            target = within(destination, *relative)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zipped.open(info) as source, target.open('xb') as output:
                shutil.copyfileobj(source, output, 1024 * 1024)
        return case, destination
