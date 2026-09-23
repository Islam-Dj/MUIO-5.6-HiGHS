from pathlib import Path
import time
import math

class HighsSolver():
    """HiGHS optimization step for the MUIO solver pipeline.

    Pipeline (mirrors the CBC path): glpsol translates MathProg -> lp.lp (unchanged),
    HiGHS solves the LP, and the solution is written as a CBC-style results.txt so
    MUIO's existing parser (generateCSVfromCBC) works untouched.

    The CBC-style contract (see DISCOVERY.md Â§3):
      line 1:  'Optimal - objective value <float>'
      then one line per constraint row:  '<idx> <name>(<indices>) <activity> <dual>'
      then one line per variable column: '<idx> <name>(<indices>) <value> <reducedCost>'
    Exactly one space between index and name; no tab characters anywhere.
    Constraint rows must be included: MUIO reads duals for the names in Config.DUALS.
    """

    # HiGHS model status string -> MUIO status flag
    STATUS_MAP = {
        'Optimal': 'success',
        'Infeasible': 'warning',
        'Primal infeasible or unbounded': 'warning',
        'Unbounded': 'warning',
    }

    # Options the interface may set, with the values HiGHS 1.15 accepts. Anything
    # not listed here is rejected rather than passed through, so a malformed or
    # unexpected field cannot reach the solver.
    # The defaults reproduce exactly what was hard-coded before this was
    # configurable, so a run with no options behaves as it always did.
    OPTIONS = {
        # Every algorithm this build can run. The first-order methods (pdlp,
        # hipdlp) reach the optimum to a tolerance rather than exactly, and the
        # interface says so where they are offered. 'hipo' is not listed because
        # this build is compiled without the libraries it requires.
        'solver':        {'type': 'choice',
                          'values': ('choose', 'simplex', 'ipm', 'ipx', 'qpasm',
                                     'hipdlp', 'pdlp'),
                          'default': 'choose'},
        'pdlp_optimality_tolerance': {'type': 'float', 'min': 1e-10, 'default': None},
        'presolve':      {'type': 'choice', 'values': ('choose', 'on', 'off'), 'default': 'choose'},
        'parallel':      {'type': 'choice', 'values': ('choose', 'on', 'off'), 'default': 'on'},
        'run_crossover': {'type': 'choice', 'values': ('choose', 'on', 'off'), 'default': 'on'},
        'threads':       {'type': 'int', 'min': 0, 'max': 256, 'default': 0},
        'time_limit':    {'type': 'float', 'min': 0.0, 'default': None},
        'mip_rel_gap':   {'type': 'float', 'min': 0.0, 'max': 1.0, 'default': None},
    }

    @staticmethod
    def normaliseOptions(options):
        """Return (clean dict, list of notes) from whatever the interface sent.

        Blank values use defaults. Unknown keys, invalid numbers and unsupported
        combinations fail explicitly rather than silently changing the request.
        """
        if options is not None and not isinstance(options, dict):
            raise ValueError('HiGHS options must be an object.')
        clean, notes = {}, []
        for key, spec in HighsSolver.OPTIONS.items():
            raw = (options or {}).get(key, None)
            if raw is None or str(raw).strip() == '':
                if spec['default'] is not None:
                    clean[key] = spec['default']
                continue
            raw = str(raw).strip()
            if spec['type'] == 'choice':
                if raw in spec['values']:
                    clean[key] = raw
                else:
                    notes.append("invalid {}='{}' (expected one of {})".format(
                        key, raw, ', '.join(spec['values'])))
            else:
                try:
                    value = int(raw) if spec['type'] == 'int' else float(raw)
                except ValueError:
                    notes.append("invalid {}='{}' (not a number)".format(key, raw))
                    continue
                if not math.isfinite(value) or value < spec.get('min', float('-inf')) or value > spec.get('max', float('inf')):
                    notes.append("invalid {}={} (out of range)".format(key, raw))
                    continue
                clean[key] = value

        for key in (options or {}):
            if key not in HighsSolver.OPTIONS:
                notes.append("unknown option '{}'".format(key))

        if notes:
            raise ValueError('Invalid HiGHS options: ' + '; '.join(notes))
        if clean.get('solver') == 'pdlp' and 'time_limit' in clean:
            raise ValueError('This build does not reliably support PDLP with a time limit. Choose another algorithm or explicitly remove the limit.')

        return clean, notes

    @staticmethod
    def _describe(clean):
        """One readable line naming the settings actually in force."""
        return ', '.join('{}={}'.format(k, v) for k, v in sorted(clean.items())) or 'defaults'

    @staticmethod
    def solve(lp_path, results_path, options=None):
        """Solve lp_path with HiGHS with validated options and write a CBC-style solution
        file to results_path.

        Returns (status_flag, custom_msg, log_text):
          status_flag: 'success' | 'warning' | 'error'  (same semantics as the CBC branch)
          custom_msg:  one-line summary for the UI message box
          log_text:    full HiGHS log for the solver-log panel
        """
        try:
            import highspy
        except ImportError:
            msg = "HiGHS not installed: run 'pip install highspy' in the Python environment used by the MUIO API."
            return 'error', msg, msg

        lp_path = Path(lp_path)
        results_path = Path(results_path)
        log_path = results_path.parent / 'highs.log'

        if not lp_path.exists():
            msg = 'HiGHS error: LP file not found ({}). GLPK translation may have failed.'.format(lp_path)
            return 'error', msg, msg

        try:
            start_time = time.time()
            h = highspy.Highs()
            h.setOptionValue('log_file', str(log_path))
            h.setOptionValue('log_to_console', False)

            read_status = h.readModel(str(lp_path))
            if read_status != highspy.HighsStatus.kOk:
                log = HighsSolver._readLog(log_path)
                msg = 'HiGHS error: could not read LP file {}'.format(lp_path)
                return 'error', msg, log

            read_time = time.time() - start_time

            # By default HiGHS picks the algorithm itself, which suits these
            # models: they are sparse and simplex-friendly, so forcing the barrier
            # method is usually slower. The interface can override it.
            clean, notes = HighsSolver.normaliseOptions(options)
            for key, value in clean.items():
                if h.setOptionValue(key, value) != highspy.HighsStatus.kOk:
                    raise ValueError('HiGHS rejected option {}={}'.format(key, value))

            run_status = h.run()
            if run_status == highspy.HighsStatus.kError:
                raise ValueError('HiGHS failed during optimization.')

            solve_time = time.time() - start_time - read_time
            model_status = h.getModelStatus()
            status_str = h.modelStatusToString(model_status)
            status_flag = HighsSolver.STATUS_MAP.get(status_str, 'error')

            if status_flag == 'success':
                objective = h.getObjectiveValue()
                lp = h.getLp()
                sol = h.getSolution()
                HighsSolver._writeCbcStyleSolution(results_path, objective, lp, sol)
                write_time = time.time() - start_time - read_time - solve_time
                custom_msg = '   Optimal - objective value {:.8f} - Total time (HiGHS): {:0.2f}s (read {:0.2f}s, solve {:0.2f}s, write {:0.2f}s)'.format(
                    objective, time.time() - start_time, read_time, solve_time, write_time)
            else:
                # No solution file for non-optimal outcomes; surface the status readably.
                custom_msg = '   HiGHS finished with status: {} (no results generated)'.format(status_str)

            log = HighsSolver._readLog(log_path)
            log += '\nHiGHS model status: {}\n'.format(status_str)
            log += 'HiGHS options in force: {}\n'.format(HighsSolver._describe(clean))
            for note in notes:
                log += 'HiGHS options: {}\n'.format(note)
            return status_flag, custom_msg, log

        except Exception as ex:
            log = HighsSolver._readLog(log_path)
            msg = 'HiGHS error: {}'.format(ex)
            return 'error', msg, log + '\n' + msg

    @staticmethod
    def solveWithExe(highs_folder, matrix_path, results_path, options=None):
        """Solve with the STANDALONE HiGHS executable (WebAPP/SOLVERs/HIGHS/highs.exe),
        exactly the way CBC is called - no Python binding involved. The solution file
        HiGHS writes is converted into CBC's solution format.

        Returns (status_flag, custom_msg, log_text).
        """
        import platform
        import subprocess
        import time as _time
        from Classes.Case.SolutionConvertersClass import SolutionConverters

        exe_name = 'highs.exe' if platform.system() == 'Windows' else 'highs'
        exe = Path(highs_folder, exe_name)
        if not exe.exists():
            msg = ('HiGHS executable not found: expected {} . Download it from '
                   'https://github.com/ERGO-Code/HiGHS/releases and place it there, '
                   'or use the HiGHS (highspy) option.'.format(exe))
            return 'error', msg, msg

        matrix_path = Path(matrix_path)
        results_path = Path(results_path)
        if not matrix_path.exists():
            msg = 'HiGHS error: matrix file not found ({}). Translation may have failed.'.format(matrix_path)
            return 'error', msg, msg

        sol_file = results_path.parent / 'highs_exe.sol'

        # Every option goes through an options file rather than command-line flags.
        # The flags cover only part of the option set - mip_rel_gap, for one, has no
        # flag at all - whereas the options file accepts any HiGHS option as
        # 'key = value', so both solver paths support exactly the same settings.
        clean, notes = HighsSolver.normaliseOptions(options)
        opt_file = results_path.parent / 'highs_options.txt'
        with open(opt_file, 'w', newline='\n') as f:
            for key, value in sorted(clean.items()):
                f.write('{} = {}\n'.format(key, value))

        sol_file.unlink(missing_ok=True)
        start_time = _time.time()
        proc = subprocess.run(
            # no algorithm is forced by default: HiGHS makes its own choice
            [str(exe.resolve()), str(matrix_path.resolve()),
             '--solution_file', str(sol_file.resolve()),
             '--options_file', str(opt_file.resolve())],
            cwd=str(Path(highs_folder).resolve()), text=True, capture_output=True)
        solve_time = _time.time() - start_time
        log = (proc.stdout or '') + (proc.stderr or '')
        log += '\nHiGHS options in force: {}\n'.format(HighsSolver._describe(clean))
        for note in notes:
            log += 'HiGHS options: {}\n'.format(note)

        if proc.returncode != 0 or not sol_file.exists():
            return 'error', 'HiGHS (exe) failed: {}'.format((proc.stderr or proc.stdout or '')[-300:]), log

        convert_start = _time.time()
        status, objective, nrows, ncols = SolutionConverters.fromHighsExe(sol_file, results_path)
        convert_time = _time.time() - convert_start

        status_flag = HighsSolver.STATUS_MAP.get(status, 'error')
        if status_flag == 'success':
            custom_msg = '   Optimal - objective value {:.8f} - Total time (HiGHS exe): {:0.2f}s (solve {:0.2f}s, convert {:0.2f}s)'.format(
                objective, solve_time + convert_time, solve_time, convert_time)
        else:
            custom_msg = '   HiGHS (exe) finished with status: {}'.format(status)
        log += '\nHiGHS model status: {}\nconverted {} rows and {} columns to CBC format in {:0.2f}s\n'.format(
            status, nrows, ncols, convert_time)
        return status_flag, custom_msg, log

    @staticmethod
    def _writeCbcStyleSolution(results_path, objective, lp, sol):
        """Write all constraint rows (activity, dual) then all variable columns
        (value, reduced cost) in CBC '-printing all' solution format."""
        row_names = lp.row_names_
        col_names = lp.col_names_
        row_value = sol.row_value
        row_dual = sol.row_dual if sol.dual_valid else [float('nan')] * lp.num_row_
        col_value = sol.col_value
        col_dual = sol.col_dual if sol.dual_valid else [float('nan')] * lp.num_col_

        # mosox-generated MPS files index names with brackets (Var[i,j]); MUIO's
        # parser expects glpsol/CBC-style parentheses (Var(i,j)). Translating is a
        # no-op for glpsol-produced LPs, whose names already use parentheses.
        bra = str.maketrans('[]', '()')

        with open(results_path, 'w', newline='\n') as f:
            # 8 decimals = exactly CBC's own header precision, so ObjectiveValue.csv
            # matches a CBC run digit for digit
            f.write('Optimal - objective value {:.8f}\n'.format(objective))
            lines = []
            # '+ 0.0' normalizes IEEE negative zero so files show '0' like CBC does
            for i in range(lp.num_row_):
                lines.append('{:7d} {} {:.9g} {:.9g}\n'.format(i, row_names[i].translate(bra), row_value[i] + 0.0, row_dual[i] + 0.0))
            for j in range(lp.num_col_):
                lines.append('{:7d} {} {:.9g} {:.9g}\n'.format(j, col_names[j].translate(bra), col_value[j] + 0.0, col_dual[j] + 0.0))
            f.writelines(lines)

    @staticmethod
    def _readLog(log_path):
        try:
            with open(log_path, 'r') as f:
                return f.read()
        except (IOError, OSError):
            return ''
