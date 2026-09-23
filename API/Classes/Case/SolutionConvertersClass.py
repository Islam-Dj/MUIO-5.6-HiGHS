from pathlib import Path
import re


class SolutionConverters():
    """Convert solver output into the CBC solution format MUIO's parser reads.

    MUIO's generateCSVfromCBC expects:
        line 1: 'Optimal - objective value <float>'
        then:   '<idx> <name>(<indices>) <value> <dual>'   (one space after the index,
                no tab characters), constraint rows first (activity + shadow price),
                then variable columns (value + reduced cost).

    Two converters live here:
      * fromHighsExe    - the solution file written by the standalone highs.exe
      * fromGlpkReport  - the printable report written by 'glpsol -o'
    The in-process highspy path writes the same format directly (HighsSolverClass).
    """

    # names of MathProg origin use brackets, MUIO's parser expects parentheses
    _BRACKETS = str.maketrans('[]', '()')

    @staticmethod
    def _write(results_path, objective, rows, cols):
        """rows/cols: iterables of (name, value, dual)."""
        with open(results_path, 'w', newline='\n') as f:
            # 8 decimals = CBC's own header precision
            f.write('Optimal - objective value {:.8f}\n'.format(objective))
            out = []
            for i, (name, value, dual) in enumerate(rows):
                out.append('{:7d} {} {:.9g} {:.9g}\n'.format(
                    i, name.translate(SolutionConverters._BRACKETS), value + 0.0, dual + 0.0))
            for j, (name, value, dual) in enumerate(cols):
                out.append('{:7d} {} {:.9g} {:.9g}\n'.format(
                    j, name.translate(SolutionConverters._BRACKETS), value + 0.0, dual + 0.0))
            f.writelines(out)

    # ------------------------------------------------------------------ HiGHS exe
    @staticmethod
    def fromHighsExe(solution_file, results_path):
        """Parse highs.exe's --solution_file output and write a CBC-style file.

        That file looks like:
            Model status
            Optimal

            # Primal solution values
            Feasible
            Objective 608520.56855933
            # Columns 56078
            <name> <value>
            # Rows 74705
            <name> <activity>

            # Dual solution values
            Feasible
            # Columns 56078
            <name> <reduced cost>
            # Rows 74705
            <name> <dual>
        """
        status = None
        objective = 0.0
        primal_cols, primal_rows, dual_cols, dual_rows = [], [], [], []
        section = None          # ('primal'|'dual', 'cols'|'rows')

        with open(solution_file, 'r') as f:
            lines = f.read().splitlines()

        block = None
        for k, raw in enumerate(lines):
            line = raw.strip()
            if not line:
                continue
            if line == 'Model status':
                block = 'status'
                continue
            if block == 'status' and status is None:
                status = line
                block = None
                continue
            if line.startswith('# Primal solution values'):
                block, section = 'primal', None
                continue
            if line.startswith('# Dual solution values'):
                block, section = 'dual', None
                continue
            if line.startswith('# Basis'):
                block, section = 'basis', None
                continue
            if line.startswith('Objective '):
                objective = float(line.split()[1])
                continue
            if line.startswith('# Columns'):
                section = 'cols'
                continue
            if line.startswith('# Rows'):
                section = 'rows'
                continue
            if block in ('primal', 'dual') and section and line not in ('Feasible', 'Infeasible', 'Unknown'):
                # '<name> <number>' - the name never contains a space
                name, _, value = line.rpartition(' ')
                if not name:
                    continue
                try:
                    val = float(value)
                except ValueError:
                    continue
                target = {('primal', 'cols'): primal_cols, ('primal', 'rows'): primal_rows,
                          ('dual', 'cols'): dual_cols, ('dual', 'rows'): dual_rows}[(block, section)]
                target.append((name, val))

        dual_row_by_name = dict(dual_rows)
        dual_col_by_name = dict(dual_cols)
        rows = [(n, v, dual_row_by_name.get(n, float('nan'))) for n, v in primal_rows]
        cols = [(n, v, dual_col_by_name.get(n, float('nan'))) for n, v in primal_cols]
        if status == 'Optimal':
            if not cols:
                raise ValueError('Optimal HiGHS solution contains no columns.')
            SolutionConverters._write(results_path, objective, rows, cols)
        return status or 'Unknown', objective, len(rows), len(cols)

    # ----------------------------------------------------------------- GLPK report
    @staticmethod
    def fromGlpkReport(report_file, results_path):
        """Parse the printable report written by 'glpsol -o' and write a CBC-style file.

        The report is fixed-width, with a dashed ruler that defines the columns:
            ------ ------------ -- ------------- ------------- ------------- -------------
             No.    Row name    St    Activity     Lower bound   Upper bound    Marginal
        Long names are printed on their own line, with the numbers on the next one, and
        a negligible marginal is printed as '< eps' - both are handled here.
        """
        status, objective = None, 0.0
        rows, cols = [], []
        target = None                  # list currently being filled
        fields = None                  # (name_start, st_start, act, low, upp, marg) offsets
        pending_name = None

        def _num(text):
            text = text.strip()
            if not text or text in ('=', '<', 'eps', '< eps'):
                return 0.0
            try:
                return float(text)
            except ValueError:
                return 0.0

        with open(report_file, 'r') as f:
            for raw in f:
                line = raw.rstrip('\n')
                stripped = line.strip()

                if stripped.startswith('Status:'):
                    status = stripped.split(':', 1)[1].strip()
                    continue
                if stripped.startswith('Objective:'):
                    # 'Objective:  cost = 608520.5686 (MINimum)'
                    m = re.search(r'=\s*([-\d.eE+]+)', stripped)
                    if m:
                        objective = float(m.group(1))
                    continue
                if 'Row name' in line:
                    target, pending_name = rows, None
                    continue
                if 'Column name' in line:
                    target, pending_name = cols, None
                    continue
                if stripped and set(stripped) <= {'-', ' '} and '-' in stripped:
                    # the ruler: derive the exact field offsets from it
                    spans, pos = [], 0
                    for chunk in line.split(' '):
                        if chunk:
                            spans.append((pos, pos + len(chunk)))
                        pos += len(chunk) + 1
                    if len(spans) >= 7:
                        fields = spans
                    continue
                if target is None or fields is None or not stripped:
                    continue
                if stripped.startswith('Karush') or stripped.startswith('End of'):
                    target = None
                    continue

                (no_s, no_e), (nm_s, nm_e), (st_s, st_e), (ac_s, ac_e) = fields[0], fields[1], fields[2], fields[3]
                mg_s, mg_e = fields[6]
                # A data line carries a GLPK status code in the status column AND a number
                # in the activity column. A long name printed on its own line also reaches
                # into the status column, hence both tests.
                st_text = line[st_s:st_e].strip() if len(line) > st_s else ''
                act_text = line[ac_s:ac_e].strip() if len(line) > ac_s else ''
                try:
                    act_is_num = act_text != '' and float(act_text) is not None
                except ValueError:
                    act_is_num = False
                if not (st_text in ('B', 'NL', 'NU', 'NF', 'NS') and act_is_num):
                    # a long name printed on its own line
                    pending_name = line[no_e:].strip() or pending_name
                    continue

                name = line[nm_s:nm_e].strip() or pending_name
                pending_name = None
                if not name:
                    continue
                value = _num(line[ac_s:ac_e])
                marginal = _num(line[mg_s:mg_e]) if len(line) > mg_s else 0.0
                target.append((name, value, marginal))

        if status == 'OPTIMAL':
            if not cols:
                raise ValueError('Optimal GLPK report contains no columns.')
            SolutionConverters._write(results_path, objective, rows, cols)
        return status or 'UNKNOWN', objective, len(rows), len(cols)

    @staticmethod
    def fromGlpkRaw(solution_file, names_file, results_path):
        """Use GLPK's full-precision machine format, including integer solutions."""
        names = {'i': {}, 'j': {}}
        with open(names_file) as handle:
            for line in handle:
                parts = line.split()
                if len(parts) >= 4 and parts[0] == 'n' and parts[1] in names:
                    names[parts[1]][int(parts[2])] = parts[3]
        status, objective, kind = 'Unknown', None, None
        values = {'i': [], 'j': []}
        with open(solution_file) as handle:
            for line in handle:
                p = line.split()
                if not p:
                    continue
                if p[0] == 's':
                    kind = p[1]
                    if kind == 'bas':
                        status = 'Optimal' if p[4:6] == ['f', 'f'] else 'Non-optimal'
                    elif kind in ('mip', 'ipt'):
                        status = 'Optimal' if p[4] == 'o' else 'Non-optimal'
                    else:
                        raise ValueError('Unsupported GLPK solution type.')
                    objective = float(p[-1])
                elif p[0] in values:
                    name = names[p[0]][int(p[1])]
                    if kind == 'bas':
                        primal, dual = float(p[3]), float(p[4])
                    elif kind == 'mip':
                        primal, dual = float(p[2]), float('nan')
                    else:
                        primal, dual = float(p[2]), float(p[3])
                    values[p[0]].append((name, primal, dual))
        if status == 'Optimal':
            if objective is None or not values['j']:
                raise ValueError('Incomplete GLPK solution.')
            SolutionConverters._write(results_path, objective, values['i'], values['j'])
        return status, objective
