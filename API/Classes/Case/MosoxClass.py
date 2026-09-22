import re
import subprocess
from pathlib import Path

class Mosox():
    """mosox translation step for the 'HiGHS (mosox)' solver option.

    Replaces only the `glpsol --check --wlp` matrix-generation step:
    mosox compiles model + data directly to a free-MPS file, which the existing
    HighsSolver then reads and solves. glpsol remains the translator for the
    plain 'HiGHS' option; GLPK/CBC paths are untouched.

    MUIO's generated data files contain 'empty' parameter blocks (no non-default
    records) in shapes glpsol accepts but mosox's stricter GMPL parser rejects,
    e.g.:
        param X default V :          param X default V :=       param X default V :=
        :=                           ;                          [RE1,*,*]:
        RE1                                                     2023 2024 ... :=
        ;                                                       ;
    Every value in such blocks is the default, so prepare() drops them
    losslessly and, where the model declaration itself has no default clause,
    injects the harvested default into a DERIVED model copy (model_mosox.txt).
    The original model file is never modified.
    """

    @staticmethod
    def _isStructural(line):
        """True for lines carrying no data: blanks, slice headers '[...]:',
        and column-list lines ending with ':='."""
        s = line.strip()
        if not s:
            return True
        if s.startswith('[') and s.endswith(':'):
            return True
        if s.endswith(':='):
            return True
        return False

    @staticmethod
    def _findEmptyBlocks(lines):
        """Locate empty param blocks. Returns (line-index spans, {name: default})."""
        blocks = []
        defaults = {}
        i, n = 0, len(lines)
        while i < n:
            s = lines[i].strip()
            m = re.match(r'^param\s+(\w+)(?:\s+default\s+(\S+))?\s*(:=?)\s*$', s)
            if m:
                j = i + 1
                while j < n and lines[j].strip() != ';':
                    j += 1
                body = lines[i + 1:j]
                if m.group(3) == ':=':
                    empty = all(Mosox._isStructural(b) for b in body)
                else:
                    # tabular header 'param X ... :' is degenerate iff the
                    # column-list line that follows is a bare ':='
                    empty = len(body) > 0 and body[0].strip() == ':='
                if empty and j < n:
                    blocks.append((i, j))
                    if m.group(2) is not None:
                        defaults[m.group(1)] = m.group(2)
                    i = j + 1
                    continue
            i += 1
        return blocks, defaults

    @staticmethod
    def prepare(model_file, data_file, model_out, data_out):
        """Write mosox-compatible copies of the data file and the model file.
        Returns a short human-readable summary of what was adjusted."""
        with open(data_file, 'r') as f:
            lines = f.readlines()
        blocks, defaults = Mosox._findEmptyBlocks(lines)
        drop = set()
        for a, b in blocks:
            drop.update(range(a, b + 1))
        with open(data_out, 'w') as f:
            f.writelines(l for k, l in enumerate(lines) if k not in drop)

        with open(model_file, 'r') as f:
            model_text = f.read()
        injected = []
        for name, val in defaults.items():
            pat = re.compile(r'(param\s+' + re.escape(name) + r'\b[^;]*?)(\s*;)', re.S)
            m = pat.search(model_text)
            if m and not re.search(r'\bdefault\b', m.group(1)):
                model_text = (model_text[:m.start()] + m.group(1)
                              + ' default ' + val + m.group(2) + model_text[m.end():])
                injected.append(name)
        with open(model_out, 'w') as f:
            f.write(model_text)

        return ('mosox prepare: dropped {} empty param block(s) from data; '
                'injected {} default(s) into derived model copy ({}).'.format(
                    len(blocks), len(injected), ', '.join(injected) if injected else '-'))

    @staticmethod
    def translate(mosox_folder, model_file, data_file, mps_file):
        """prepare + `mosox compile` -> mps_file. Derived copies are written next
        to the data file (model_mosox.txt / data_mosox.txt in the run folder).

        Returns an object shaped like subprocess.run's result (returncode,
        stdout, stderr) so the dispatch can treat it exactly like a glpsol call.
        """
        class _Out():
            returncode = 1
            stdout = ''
            stderr = ''

        out = _Out()
        mosox_exe = Path(mosox_folder, 'mosox.exe')
        if not mosox_exe.exists():
            out.stderr = ('mosox not found: expected {} . Download the Windows binary from '
                          'https://github.com/carderne/mosox/releases and place it there, '
                          'or use the plain HiGHS option (glpsol translator).'.format(mosox_exe))
            return out

        try:
            run_folder = Path(data_file).parent
            model_out = Path(run_folder, 'model_mosox.txt')
            data_out = Path(run_folder, 'data_mosox.txt')
            summary = Mosox.prepare(model_file, data_file, model_out, data_out)
        except Exception as ex:
            out.stderr = 'mosox prepare failed: {}'.format(ex)
            return out

        cmd = '"{}" compile "{}" "{}" -o "{}"'.format(
            mosox_exe.resolve(), Path(model_out).resolve(), Path(data_out).resolve(),
            Path(mps_file).resolve())
        proc = subprocess.run(cmd, cwd=mosox_folder, capture_output=True, text=True, shell=True)
        out.returncode = proc.returncode
        out.stdout = summary + '\n' + proc.stdout
        out.stderr = proc.stderr
        if proc.returncode == 0 and not Path(mps_file).exists():
            out.returncode = 1
            out.stderr = (out.stderr + '\nmosox reported success but no MPS file was written.').strip()
        return out
