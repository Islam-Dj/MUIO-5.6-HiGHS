"""Live progress of a model run.

/run is one blocking request that only answers when everything is finished, which
is why the interface looks frozen on a long model. This keeps the current stage and
its timings in memory while the run proceeds, so a second request (/progress) can
report them. Waitress serves requests on several threads, so the poll is answered
while /run is still working.

Nothing is written to disk: the record lives only for the duration of the run plus
a short grace period, and the finished record carries the exact per-stage times that
the interface shows when the run ends.
"""
import csv
import os
import threading
import time
from datetime import datetime
from pathlib import Path

# Typical share of a run taken by each stage. Used only to estimate progress
# while the run is under way; once a stage finishes its real time is reported.
DEFAULT_WEIGHTS = {
    'preparing data': 0.02,
    'generating matrix': 0.38,
    'checking matrix': 0.01,
    'solving': 0.33,
    'writing result files': 0.18,
    'preparing charts': 0.09,
}

_lock = threading.Lock()
_runs = {}
_KEEP_FINISHED_SECONDS = 600


def _key(case, caserun):
    return '{}|{}'.format(case, caserun)


def _prune(now):
    """Drop finished records once nobody is likely to ask for them."""
    for key, rec in list(_runs.items()):
        if rec['finished_at'] and now - rec['finished_at'] > _KEEP_FINISHED_SECONDS:
            _runs.pop(key, None)


def _sampleMemory(key, stop):
    """Follow MUIO and every child process, keeping the largest total seen."""
    try:
        import psutil
    except ImportError:
        return
    try:
        me = psutil.Process()
    except Exception:
        return
    while not stop.is_set():
        try:
            total = me.memory_info().rss
            for child in me.children(recursive=True):
                try:
                    total += child.memory_info().rss
                except Exception:
                    pass
            with _lock:
                rec = _runs.get(key)
                if rec and total > rec.get('peak_bytes', 0):
                    rec['peak_bytes'] = total
        except Exception:
            pass
        stop.wait(0.25)


def start(case, caserun, solver, stages):
    """Begin a run. 'stages' is the ordered list of stage names this run will pass."""
    now = time.time()
    key = _key(case, caserun)
    with _lock:
        _prune(now)
        old = _runs.get(key)
        if old and old.get('stop'):
            old['stop'].set()                  # never leave a sampler from a previous run
        stop = threading.Event()
        _runs[key] = {
            'case': case, 'caserun': caserun, 'solver': solver,
            'stages': list(stages), 'done': [], 'current': None,
            'started_at': now, 'stage_started_at': now,
            'finished_at': None, 'status': 'running', 'message': '',
            'peak_bytes': 0, 'stop': stop,
        }
    threading.Thread(target=_sampleMemory, args=(key, stop), daemon=True).start()


def stage(case, caserun, name):
    """Move to 'name', recording how long the stage that just ended took."""
    now = time.time()
    with _lock:
        rec = _runs.get(_key(case, caserun))
        if not rec:
            return
        if rec['current']:
            rec['done'].append({'name': rec['current'],
                                'seconds': round(now - rec['stage_started_at'], 2)})
        rec['current'] = name
        rec['stage_started_at'] = now


def finish(case, caserun, status='done', message=''):
    now = time.time()
    with _lock:
        rec = _runs.get(_key(case, caserun))
        if not rec:
            return
        if rec['current']:
            rec['done'].append({'name': rec['current'],
                                'seconds': round(now - rec['stage_started_at'], 2)})
        rec['current'] = None
        rec['finished_at'] = now
        rec['status'] = status
        rec['message'] = message
        if rec.get('stop'):
            rec['stop'].set()


def get(case, caserun):
    """Snapshot for the interface: the stage running now, its elapsed time, the
    stages already done with their real times, and an estimated overall percent."""
    now = time.time()
    with _lock:
        rec = _runs.get(_key(case, caserun))
        if not rec:
            return {'status': 'unknown'}

        done = list(rec['done'])
        elapsed = (rec['finished_at'] or now) - rec['started_at']
        stage_elapsed = now - rec['stage_started_at'] if rec['current'] else 0.0

        if rec['status'] != 'running':
            total = sum(d['seconds'] for d in done) or 1.0
            for d in done:
                d['percent'] = round(100.0 * d['seconds'] / total, 1)
            return {'status': rec['status'], 'current': None, 'percent': 100,
                    'elapsed': round(elapsed, 1), 'stage_elapsed': 0,
                    'done': done, 'total_seconds': round(total, 2),
                    'stage_index': len(rec['stages']), 'stage_count': len(rec['stages']),
                    'solver': rec['solver'], 'message': rec['message'],
                    'peak_mb': round(rec.get('peak_bytes', 0) / 1e6, 1) or '',
                    'rows': rec.get('rows', ''), 'cols': rec.get('cols', ''),
                    'nonzeros': rec.get('nonzeros', ''), 'kind': rec.get('kind', ''),
                    'integers': rec.get('integers', ''),
                    'constant': rec.get('constant', None),
                    'outcome': rec.get('outcome', ''),
                    'objective': rec.get('objective', '')}

        # still running: weight the stages already finished, plus part of this one
        weights = {name: DEFAULT_WEIGHTS.get(name, 1.0 / max(len(rec['stages']), 1))
                   for name in rec['stages']}
        scale = sum(weights.values()) or 1.0
        completed = sum(weights.get(d['name'], 0.0) for d in done)
        current_weight = weights.get(rec['current'], 0.0)
        # inside the current stage, ease toward its full weight without ever passing it
        within = current_weight * min(0.95, stage_elapsed / 30.0) if current_weight else 0.0
        percent = round(100.0 * min(0.99, (completed + within) / scale))

        index = len(done) + 1
        return {'status': 'running', 'current': rec['current'], 'percent': percent,
                'elapsed': round(elapsed, 1), 'stage_elapsed': round(stage_elapsed, 1),
                'done': done, 'stage_index': index, 'stage_count': len(rec['stages']),
                'solver': rec['solver'], 'message': '',
                'peak_mb': round(rec.get('peak_bytes', 0) / 1e6, 1) or '',
                'rows': rec.get('rows', ''), 'cols': rec.get('cols', ''),
                'nonzeros': rec.get('nonzeros', ''), 'kind': rec.get('kind', ''),
                'integers': rec.get('integers', ''),
                'constant': rec.get('constant', None),
                'outcome': rec.get('outcome', ''),
                'objective': rec.get('objective', '')}


# Stage names in run order, so every row of the CSV has its columns in the same
# places no matter which branch the run took.
STAGE_COLUMNS = ['preparing data', 'generating matrix', 'checking matrix', 'solving',
                 'writing result files', 'preparing charts']

# The HiGHS settings worth recording alongside the timings. Blank for CBC and GLPK,
# which do not take them.
OPTION_COLUMNS = ['solver', 'presolve', 'parallel', 'run_crossover', 'threads',
                  'time_limit', 'mip_rel_gap', 'pdlp_optimality_tolerance']


def _totalCost(snapshot):
    """Objective plus the constant the matrix does not carry, when both are known."""
    objective, constant = snapshot.get('objective'), snapshot.get('constant')
    if objective in ('', None) or constant is None:
        return ''
    try:
        return round(float(objective) + float(constant), 6)
    except (TypeError, ValueError):
        return ''


def writeSummaryCsv(folder, case, caserun, muio_solver, highs_options=None):
    """Append this run to run_summary.csv in the case run folder.

    One row per run, so successive runs of the same case can be compared: which
    solver, which HiGHS settings, how long each stage took. The options recorded
    are the ones actually in force after validation, not the raw request, so the
    file says what the solver really did.
    """
    snapshot = get(case, caserun)
    if snapshot.get('status') in (None, 'unknown') or not snapshot.get('done'):
        return None

    effective = {}
    if (muio_solver or '').startswith('highs'):
        try:
            from Classes.Case.HighsSolverClass import HighsSolver
            effective, _ = HighsSolver.normaliseOptions(highs_options)
        except Exception:
            effective = {}

    by_stage = {d['name']: d for d in snapshot['done']}
    row = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'case': case,
        'caserun': caserun,
        'muio_solver': muio_solver,
        'problem': snapshot.get('kind', ''),
        'rows': snapshot.get('rows', ''),
        'columns': snapshot.get('cols', ''),
        'nonzeros': snapshot.get('nonzeros', ''),
        'integers': snapshot.get('integers', ''),
        'status': snapshot.get('status', ''),
        'outcome': snapshot.get('outcome', ''),
        'objective': snapshot.get('objective', ''),
        'fixed_cost': '' if snapshot.get('constant') is None
                      else snapshot.get('constant'),
        'total_cost': _totalCost(snapshot),
        'total_s': snapshot.get('total_seconds', ''),
        'peak_mb': snapshot.get('peak_mb', ''),
    }
    for name in STAGE_COLUMNS:
        entry = by_stage.get(name)
        row[name.replace(' ', '_') + '_s'] = entry['seconds'] if entry else ''
        row[name.replace(' ', '_') + '_pct'] = entry.get('percent', '') if entry else ''
    for key in OPTION_COLUMNS:
        row['highs_' + key] = effective.get(key, '')

    path = os.path.join(str(folder), 'run_summary.csv')
    exists = os.path.isfile(path)
    if exists:
        # A record written with a different set of columns cannot be appended to
        # without misaligning it, so it is archived instead of being overwritten.
        try:
            with open(path, newline='') as f:
                header = next(csv.reader(f), [])
        except OSError:
            header = list(row)
        if header and header != list(row):
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            try:
                os.rename(path, os.path.join(
                    str(folder), 'run_summary_{}.csv'.format(stamp)))
                exists = False
            except OSError:
                return None
    try:
        with open(path, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(row))
            if not exists:
                writer.writeheader()
            writer.writerow(row)
    except OSError:
        return None                 # a locked or unwritable file must not fail the run
    return path

def setModelInfo(case, caserun, rows=None, cols=None, nonzeros=None, kind=None,
                 integers=None):
    """Attach the problem size and kind to the run record."""
    with _lock:
        rec = _runs.get(_key(case, caserun))
        if not rec:
            return
        if rows is not None:
            rec['rows'] = rows
        if cols is not None:
            rec['cols'] = cols
        if nonzeros is not None:
            rec['nonzeros'] = nonzeros
        if kind is not None:
            rec['kind'] = kind
        if integers is not None:
            rec['integers'] = integers


def setSolveOutcome(case, caserun, outcome=None, objective=None):
    """Attach what the solver concluded, and the objective when it reached one."""
    with _lock:
        rec = _runs.get(_key(case, caserun))
        if not rec:
            return
        if outcome is not None:
            rec['outcome'] = outcome
        if objective is not None:
            rec['objective'] = objective


def setObjectiveConstant(case, caserun, value):
    """The part of the objective the exported matrix does not carry.

    Recorded separately from the solver's own figure so the record shows both what
    the solver returned and what the model actually costs. None means the run took
    a path where it could not be recovered, which must not read as zero.
    """
    with _lock:
        rec = _runs.get(_key(case, caserun))
        if rec is not None:
            rec['constant'] = value


def readSolveOutcome(text, detail=None):
    """(outcome, objective) from the solver's own words.

    'text' is the result line of the run; 'detail' is the solver's log, read when
    the result line names no specific outcome. GLPK reports an infeasible LP only in
    its log ('LP HAS NO PRIMAL FEASIBLE SOLUTION'), and CBC prints a MIP objective
    on its own line.

    When the outcome carries no solution, no objective is returned, even if a
    figure appears in the line.
    """
    import re
    text = text or ''
    number = r'(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)'

    def objective_in(blob):
        if not blob:
            return None
        found = re.findall(r'objective\s+value\s*[:=]?\s*' + number, blob, re.I)
        try:
            return float(found[-1]) if found else None   # the last one is the final one
        except ValueError:
            return None

    objective = objective_in(text)
    if objective is None:
        objective = objective_in(detail)

    # (what to look for, what to call it, whether an objective still means anything)
    specific = (('no integer feasible', 'Infeasible', False),
                ('no primal feasible', 'Infeasible', False),
                ('no dual feasible', 'Unbounded', False),
                ('infeasible', 'Infeasible', False),
                ('unbounded', 'Unbounded', False),
                ('time limit', 'Time limit', True),
                ('stopped on time', 'Time limit', True),
                ('iteration limit', 'Iteration limit', True),
                ('interrupt', 'Interrupted', True),
                ('failed', 'Error', False),
                ('error', 'Error', False))
    not_optimal = re.compile(r'\bno(?:n|t)[\s-]+optimal\b', re.I)
    optimal = re.compile(r'(?<![\w-])optimal\b', re.I)

    def scan(blob):
        low = (blob or '').lower()
        for needle, word, keep in specific:
            if needle in low:
                return word, keep
        return None, True

    word, keep = scan(text)
    if word:
        return word, (objective if keep else None)
    if optimal.search(text) and not not_optimal.search(text):
        return 'Optimal', objective
    # The result line names no specific outcome; the solver's log may.
    word, keep = scan(detail)
    if word:
        return word, (objective if keep else None)
    if not_optimal.search(text):
        return 'Not optimal', None
    found = re.search(r'status:\s*([^(\n]+)', text)
    if found:
        return found.group(1).strip(), None
    found = re.match(r'\s*([A-Za-z][\w \-]*?)\s*-\s*objective value', text)
    return (found.group(1).strip(), None) if found else (None, objective)


def readTranslatorOutput(text):
    """rows, columns and non-zeros as the translator reported them.

    glpsol prints a 'Problem Characteristics' block; mosox prints one line of the
    form 'Matrix: R rows, C cols, N nonzero'.
    """
    import re
    if not text:
        return None, None, None
    rows = re.search(r'Number of rows\s*=\s*(\d+)', text)
    cols = re.search(r'Number of columns\s*=\s*(\d+)', text)
    nz = re.search(r'Number of non-zeros \(matrix\)\s*=\s*(\d+)', text)
    if rows and cols and nz:
        return int(rows.group(1)), int(cols.group(1)), int(nz.group(1))
    m = re.search(r'Matrix:\s*(\d+)\s*rows?,\s*(\d+)\s*cols?,\s*(\d+)\s*nonzero', text)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return None, None, None


def _countLpIntegers(text):
    """Columns declared in an LP file's Generals / Binaries sections."""
    total, inside = 0, False
    for line in text.splitlines():
        word = line.strip()
        low = word.lower()
        if low in ('generals', 'general', 'gen', 'integers', 'integer',
                   'binaries', 'binary', 'bin'):
            inside = True
            continue
        if low in ('end', 'bounds', 'sos', 'semi-continuous', 'semis'):
            inside = False
            continue
        if inside and word:
            total += len(word.split())
    return total


def readMatrixInfo(matrix_path, tail_bytes=16 * 1024 * 1024):
    """('MILP', integer columns) or ('LP', 0) for the matrix just generated.

    The kind is taken from the matrix rather than from a solver message, so every
    solver reports the same thing about the same model. The integer count is the
    figure that says how hard the problem is: rows and columns describe only the
    relaxation, while the branch-and-bound search grows with the integer columns.

    Reading a large matrix in full would cost seconds, so an .lp is read from the
    end, where its Generals section lives, and an .mps is scanned in blocks that
    are only split into lines around its integer markers.
    """
    try:
        path = Path(matrix_path)
        if not path.is_file():
            return None, None
        size = path.stat().st_size

        if path.suffix.lower() == '.lp':
            with open(path, 'rb') as f:
                if size > tail_bytes:
                    f.seek(size - tail_bytes)
                tail = f.read().decode('latin-1', 'replace')
            count = _countLpIntegers(tail)
            if count:
                return 'MILP', count
            #no integer section, but only trustworthy if the end of the file was seen
            if size <= tail_bytes or '\nEnd' in tail or '\nend' in tail:
                return 'LP', 0
            return None, None

        integers, counting, seen, carry = set(), False, False, b''
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(4 * 1024 * 1024)
                if chunk:
                    data = carry + chunk
                    cut = data.rfind(b'\n') + 1
                    body, carry = data[:cut], data[cut:]
                else:
                    body, carry = carry, b''
                if body and (counting or b'MARKER' in body):
                    for raw in body.splitlines():
                        if b'MARKER' in raw:
                            if b'INTORG' in raw:
                                counting = seen = True
                            elif b'INTEND' in raw:
                                counting = False
                        elif counting:
                            parts = raw.split()
                            if parts:
                                integers.add(parts[0])
                if not chunk:
                    break
        return ('MILP', len(integers)) if seen else ('LP', 0)
    except OSError:
        return None, None
