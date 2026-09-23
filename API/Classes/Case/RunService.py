"""Isolated executions and rollback of result publication.

Changes are serialized per model by the desktop API. Each execution builds fresh outputs and chart
files before publishing. The previous run is retained in .run-history.
"""
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import threading
import uuid

from Classes.Base import Config
from Classes.Base.FileClass import File
from Classes.Base.Publication import publish, recover, prune, prune_executions
from Classes.Base.SafePaths import child, component, within
from Classes.Case.HighsSolverClass import HighsSolver
from Classes.Case.MosoxClass import Mosox
from Classes.Case.SolutionConvertersClass import SolutionConverters
from Classes.Case import RunProgressClass as Progress
from Classes.Case.ObjectiveConstant import fixed_cost

logger = logging.getLogger(__name__)
_execution_lock = threading.Lock()
SOLVERS = {'cbc', 'glpk', 'highs', 'highs-exe', 'highs-mosox'}
# Previous copies of the results kept per case run after a successful run.
KEEP_PREVIOUS_RESULTS = 1


def execute(model, solver, caserun, highs_options=None):
    component(caserun)
    if solver not in SOLVERS:
        raise ValueError('Unknown solver: ' + str(solver))
    result = {'status_code': 'error', 'caserun': caserun, 'cbc_message': '',
              'cbc_stdmsg': '', 'glpk_message': '', 'glpk_stdmsg': '', 'highs_message': ''}
    original_view = model.viewFolderPath
    current = child(model.resultsPath, caserun)
    execution = child(model.casePath, '.executions', uuid.uuid4().hex)
    if not _execution_lock.acquire(blocking=False):
        raise ValueError('A model execution is already in progress.')
    try:
        recover(model.casePath)
        Progress.start(model.case, caserun, solver, Progress.STAGE_COLUMNS)
        Progress.stage(model.case, caserun, 'preparing data')
        execution.mkdir(parents=True)
        run = execution / 'run'
        run.mkdir()
        view = execution / 'view'
        shutil.copytree(original_view, view)
        shutil.copy2(current / 'data.txt', run / 'data.txt')
        # The record belongs to the case run, and survives replacement of outputs.
        for record in current.glob('run_summary*'):
            if record.is_file():
                shutil.copy2(record, run / record.name)
        model.resPath = run
        model._execution_base = run
        model.viewFolderPath = view
        model.dataFile = run / 'data.txt'
        model.dataFile_processed = run / 'data_processed.txt'
        model.resFile = run / 'results.txt'
        if solver.startswith('highs'):
            HighsSolver.normaliseOptions(highs_options)
        model.preprocessData(model.dataFile, model.dataFile_processed)
        if not model.dataFile_processed.is_file():
            raise ValueError('Preprocessing did not produce a data file.')

        matrix = run / ('lp.mps' if solver == 'highs-mosox' else 'lp.lp')
        constant_note = ''
        if solver == 'highs-mosox':
            constant, constant_note = fixed_cost(model.osemosysFile, model.dataFile_processed)
            prepared = Mosox.prepare(model.osemosysFile, model.dataFile_processed,
                                     run / 'model_mosox.txt', run / 'data_mosox.txt')
        else:
            glpsol = model.resolveSolver('glpk')
            glp = run / 'model.glp'
            command = [glpsol, '--check', '-m', str(model.osemosysFile.resolve()),
                       '-d', str(model.dataFile_processed), '--wglp', str(glp), '--wlp', str(matrix)]

        Progress.stage(model.case, caserun, 'generating matrix')
        if solver == 'highs-mosox':
            translated = Mosox.translate(model.mosoxFolder, model.osemosysFile,
                                         model.dataFile_processed, matrix, prepared=prepared)
        else:
            translated = subprocess.run(command, capture_output=True, text=True)
        Progress.stage(model.case, caserun, 'checking matrix')
        result.update(glpk_message=translated.stdout, glpk_stdmsg=translated.stderr)
        if translated.returncode != 0 or not matrix.is_file():
            raise ValueError('Model translation failed. See the translation log.')
        if solver != 'highs-mosox':
            constant = model.readObjectiveConstant(glp)
            glp.unlink(missing_ok=True)          # large, and only needed for the constant
            if constant is None:
                raise ValueError('The objective constant could not be recovered; no total cost was published.')
        # If an MPS writer includes an offset, do not add it a second time.
        offset = mps_offset(matrix) if solver == 'highs-mosox' else 0.0
        model.objectiveConstant = None if constant is None else constant - offset
        Progress.setObjectiveConstant(model.case, caserun, model.objectiveConstant)
        rows, cols, nz = Progress.readTranslatorOutput(result['glpk_message'])
        kind, ints = Progress.readMatrixInfo(matrix)
        model.dualsAvailable = kind == 'LP'
        Progress.setModelInfo(model.case, caserun, rows, cols, nz, kind, ints)
        Progress.stage(model.case, caserun, 'solving')

        if solver in ('highs', 'highs-mosox', 'highs-exe'):
            if solver == 'highs-exe':
                flag, message, log = HighsSolver.solveWithExe(model.highsFolder, matrix, model.resFile, highs_options)
            else:
                flag, message, log = HighsSolver.solve(matrix, model.resFile, highs_options)
            result['highs_message'] = log
            detail = log
        elif solver == 'glpk':
            raw, names = run / 'glpk.sol', run / 'solved.glp'
            solved = subprocess.run([glpsol, '--lp', str(matrix), '--write', str(raw),
                                     '--wglp', str(names)], capture_output=True, text=True)
            result['glpk_message'] += '\n' + solved.stdout
            result['glpk_stdmsg'] += '\n' + solved.stderr
            if solved.returncode != 0 or not raw.exists():
                raise ValueError('GLPK failed. See the solver log.')
            detail = (solved.stdout or '') + (solved.stderr or '')
            status, objective = SolutionConverters.fromGlpkRaw(raw, names, model.resFile)
            raw.unlink(missing_ok=True)
            names.unlink(missing_ok=True)
            flag = 'success' if status == 'Optimal' else 'warning'
            message = ('Optimal - objective value {:.10g}'.format(objective) if flag == 'success'
                       else 'GLPK status: ' + status)
        else:
            cbc = model.resolveSolver('cbc')
            solved = subprocess.run([cbc, str(matrix), 'solve', '-printing', 'all',
                                     '-solu', str(model.resFile)], capture_output=True, text=True)
            result.update(cbc_message=solved.stdout, cbc_stdmsg=solved.stderr)
            if solved.returncode != 0 or not model.resFile.exists():
                raise ValueError('CBC failed. See the solver log.')
            detail = solved.stdout or ''
            with model.resFile.open() as handle:
                message = handle.readline().strip()
            flag = 'success' if message.startswith('Optimal - objective value') else 'warning'

        outcome, objective = Progress.readSolveOutcome(message, detail)
        Progress.setSolveOutcome(model.case, caserun, outcome, objective)
        result.update(status_code=flag, timer=message)
        if not model.dualsAvailable:
            result['duals_warning'] = 'Shadow-price exports are unavailable for integer or unclassified models.'
            result['timer'] += ' ' + result['duals_warning']
        if model.objectiveConstant is None:
            result['cost_warning'] = constant_note
            result['timer'] += ' ' + constant_note
        if flag != 'success':
            result['timer'] += ' Previous successful results were retained.'
            return result
        if not model.resFile.exists():
            raise ValueError('The solver reported success without a solution file.')
        Progress.stage(model.case, caserun, 'writing result files')
        model.generateCSVfromCBC(model.dataFile, model.resFile, run)
        Progress.stage(model.case, caserun, 'preparing charts')
        # Remove only this run's old chart values, in the staged view copy.
        for path in view.glob('*.json'):
            if path.name in ('resData.json', 'viewDefinitions.json'):
                continue
            data = File.readFile(path)
            if isinstance(data, dict):
                for values in data.values():
                    if isinstance(values, dict):
                        values.pop(caserun, None)
                File.writeFile(data, path)
        model.generateResultsViewer(caserun)
        entries = [(run, current)]
        entries += [(p, original_view / p.name) for p in view.glob('*.json')
                    if p.name not in ('resData.json', 'viewDefinitions.json')]
        publish(entries, child(model.casePath, '.run-history', execution.name))
        result['published'] = True
        result['timer'] += ' Results published; the previous results are kept as one copy.'
        return result
    except Exception as error:
        logger.exception('Run failed; previous results retained')
        result.update(status_code='error', timer=str(error) + ' Previous successful results were retained.')
        return result
    finally:
        model.viewFolderPath = original_view
        model.__dict__.pop('_execution_base', None)
        Progress.finish(model.case, caserun, result['status_code'], result.get('timer', ''))
        try:
            if current.is_dir():
                Progress.writeSummaryCsv(current, model.case, caserun, solver, highs_options)
            # A published run needs nothing more from its execution folder. An
            # unpublished one is kept for diagnosis, the latest per case run only.
            if execution.is_dir():
                if result.get('published'):
                    shutil.rmtree(execution, ignore_errors=True)
                else:
                    File.writeFile(result, execution / 'run.json')
                    prune_executions(model.casePath, caserun)
            if result.get('published'):
                prune(model.casePath, keep=KEEP_PREVIOUS_RESULTS)
        except Exception:
            logger.exception('Could not record run diagnostics')
        _execution_lock.release()


def mps_offset(path):
    """Read the objective RHS constant in free MPS (objective offset = -RHS)."""
    objective_row = None
    section = None
    with open(path) as handle:
        for line in handle:
            if line.startswith('*'):
                continue
            parts = line.split()
            if not parts:
                continue
            if parts[0] in ('NAME', 'ROWS', 'COLUMNS', 'RHS', 'BOUNDS', 'RANGES', 'ENDATA', 'OBJSENSE') and not line[0].isspace():
                section = parts[0]
                continue
            if section == 'ROWS' and parts[0] == 'N' and objective_row is None:
                objective_row = parts[1]
            if section == 'RHS':
                for i in range(1, len(parts) - 1, 2):
                    if parts[i] == objective_row:
                        return -float(parts[i + 1])
    return 0.0
