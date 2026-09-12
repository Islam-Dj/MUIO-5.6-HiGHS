# =============================================================================
#  Paste into API/Classes/Case/DataFileClass.py of a MUIO 5.3-style app
#  (a run() that builds command STRINGS and uses shell=True with cwd=<solver folder>)
# =============================================================================

# --- 1. imports at the top ----------------------------------------------------
from Classes.Case.HighsSolverClass import HighsSolver
from Classes.Case.MosoxClass import Mosox
from Classes.Case.SolutionConvertersClass import SolutionConverters


# --- 2. one extra path, where run() defines self.lpFile -----------------------
#     self.mpsFile = Path(Config.DATA_STORAGE, self.case, 'res', caserunname, 'lp.mps')
#     and in OsemosysClass.__init__:
#     self.mosoxFolder = Path(Config.SOLVERs_FOLDER, 'MOSOX')
#     self.highsFolder = Path(Config.SOLVERs_FOLDER, 'HIGHS')


# --- 3. new branches inside run(), after the `if solver == 'glpk':` block ------
#     The CBC `else:` block stays untouched. In 5.3 the file paths are already
#     quoted strings (modelfile, datafile_processed, lpfile).

            elif solver in ('highs', 'highs-exe', 'highs-mosox'):
                self.preprocessData(self.dataFile, self.dataFile_processed)

                translate_start = time.time()
                if solver == 'highs-mosox':
                    matrixFile = self.mpsFile
                    translator = 'mosox (MathProg -> MPS)'
                    glpk_out = Mosox.translate(self.mosoxFolder, self.osemosysFile,
                                               self.dataFile_processed, self.mpsFile)
                else:
                    matrixFile = self.lpFile
                    translator = 'glpsol (MathProg -> LP)'
                    glpk_out = subprocess.run(
                        'glpsol --check -m ' + modelfile + ' -d ' + datafile_processed +
                        ' --wlp ' + lpfile,
                        cwd=glpfolder, capture_output=True, text=True, shell=True)
                translate_time = time.time() - translate_start

                if glpk_out.returncode != 0:
                    highs_flag, highs_msg, highs_log = 'error', 'Translation failed.', ''
                elif solver == 'highs-exe':
                    highs_flag, highs_msg, highs_log = HighsSolver.solveWithExe(
                        self.highsFolder, matrixFile, self.resFile)
                else:
                    highs_flag, highs_msg, highs_log = HighsSolver.solve(matrixFile, self.resFile)


# --- 4. the matching response block, next to the CBC/GLPK response blocks -----

            elif solver in ('highs', 'highs-exe', 'highs-mosox'):
                if highs_flag == 'success':
                    self.generateCSVfromCBC(self.dataFile, self.resFile, self.resPath)
                    self.generateResultsViewer(caserunname)
                total_time = time.time() - start_time
                run_summary = (
                    '==================== RUN SUMMARY ====================\n'
                    + 'Case run             : {}\n'.format(caserunname)
                    + 'Translator           : {}\n'.format(translator)
                    + 'LP/MPS creation time : {:0.2f} s\n'.format(translate_time)
                    + 'Result               : {}\n'.format(highs_msg.strip())
                    + 'Full run incl. CSVs  : {:0.2f} s\n'.format(total_time)
                    + '=====================================================\n\n')
                response = {
                    'cbc_message': '', 'cbc_stdmsg': '',
                    'glpk_message': glpk_out.stdout, 'glpk_stdmsg': glpk_out.stderr,
                    'highs_message': run_summary + highs_log,
                    'timer': highs_msg + ' - Translation ({}): {:0.2f}s - Full run incl. CSVs: {:0.2f}s'.format(
                        'mosox' if solver == 'highs-mosox' else 'glpsol', translate_time, total_time),
                    'status_code': highs_flag,
                    'caserun': caserunname,
                }


# --- 5. to give the GLPK option working CSVs too (optional) -------------------
#     Solve the exported LP with glpsol and convert its report, instead of
#     solving the MathProg model directly:
#
#     glpsol --lp <lp.lp> -o <glpk_report.txt>
#     status, objective, nrows, ncols = SolutionConverters.fromGlpkReport(report, self.resFile)
#     then call generateCSVfromCBC + generateResultsViewer as above.
