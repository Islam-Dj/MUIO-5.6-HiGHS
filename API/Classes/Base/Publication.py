"""Recoverable multi-file publication; callers serialize mutations.

The newest committed generation of each case run is kept for manual recovery. An interrupted
transaction is rolled back before the next API request reads or modifies a case.
"""
import os
import shutil
from pathlib import Path
from Classes.Base.FileClass import File
from Classes.Base.SafePaths import within


def _entries(record, root):
    return [(within(root, row['source']), within(root, row['target']),
             within(root, row['backup']), row['had_original']) for row in record['entries']]


def rollback(record, manifest, root):
    for source, target, backup, had_original in reversed(_entries(record, root)):
        if backup.exists() or not had_original:
            if not source.exists() and target.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                os.replace(target, source)
            if backup.exists():
                os.replace(backup, target)
    record['state'] = 'rolled_back'
    File.writeFile(record, manifest)


def recover(root):
    root = Path(root).resolve()
    history = root / '.run-history'
    if not history.is_dir():
        return
    for manifest in history.glob('*/manifest.json'):
        within(root, manifest.relative_to(root))
        record = File.readFile(manifest)
        # Manifests of the older format (a previous_files list only) are left intact.
        if record.get('version') == 2 and record.get('state') == 'publishing':
            rollback(record, manifest, root)


def _case_run(record):
    """The case run a generation belongs to: the target of its entry under 'res'."""
    for entry in record.get('entries', []):
        parts = Path(entry['target']).parts
        if len(parts) >= 2 and parts[0] == 'res':
            return parts[1]
    return None


def prune(root, keep=1):
    """Keep only the newest `keep` committed generations per case run.

    Generations still marked 'publishing' are never removed: recover() needs them.
    Rolled-back generations have nothing left to restore. Manifests of the older
    format are left untouched.
    """
    root = Path(root).resolve()
    history = root / '.run-history'
    if not history.is_dir():
        return
    committed = {}
    for manifest in history.glob('*/manifest.json'):
        try:
            record = File.readFile(manifest)
        except Exception:
            continue
        if record.get('version') != 2:
            continue
        folder = within(root, manifest.parent.relative_to(root))
        if record.get('state') == 'rolled_back':
            shutil.rmtree(folder, ignore_errors=True)
        elif record.get('state') == 'committed':
            run = _case_run(record)
            if run is not None:
                committed.setdefault(run, []).append((manifest.stat().st_mtime, folder))
    for generations in committed.values():
        generations.sort(reverse=True)
        for _, folder in generations[keep:]:
            shutil.rmtree(folder, ignore_errors=True)


def prune_executions(root, caserun, keep_failed=1):
    """Keep only the latest `keep_failed` unpublished executions of one case run."""
    root = Path(root).resolve()
    executions = root / '.executions'
    if not executions.is_dir():
        return
    failed = []
    for record_path in executions.glob('*/run.json'):
        try:
            record = File.readFile(record_path)
        except Exception:
            continue
        if isinstance(record, dict) and record.get('caserun') == caserun:
            failed.append((record_path.stat().st_mtime,
                           within(root, record_path.parent.relative_to(root))))
    failed.sort(reverse=True)
    for _, folder in failed[keep_failed:]:
        shutil.rmtree(folder, ignore_errors=True)


def publish(entries, history):
    history = Path(history).resolve()
    root = Path(os.path.commonpath([str(history)] + [str(p.resolve()) for pair in entries for p in pair]))
    history.mkdir(parents=True, exist_ok=False)
    record = {'version': 2, 'state': 'publishing', 'entries': []}
    for index, (source, target) in enumerate(entries):
        source, target = within(root, source.resolve()), within(root, target.resolve())
        backup = within(root, history / str(index))
        record['entries'].append({'source': str(source.relative_to(root)),
                                  'target': str(target.relative_to(root)),
                                  'backup': str(backup.relative_to(root)),
                                  'had_original': target.exists()})
    manifest = history / 'manifest.json'
    File.writeFile(record, manifest)
    try:
        for source, target, backup, had_original in _entries(record, root):
            if had_original:
                os.replace(target, backup)
            os.replace(source, target)
        record['state'] = 'committed'
        File.writeFile(record, manifest)
    except Exception:
        rollback(record, manifest, root)
        raise
