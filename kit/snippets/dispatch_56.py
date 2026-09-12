# =============================================================================
#  Paste into API/Classes/Case/DataFileClass.py of a MUIO 5.6-style app
#  (a run() that uses list-argument subprocess and self.glpsol_path / self.cbc_path)
# =============================================================================

# --- 1. imports, next to the other "from Classes.Case..." lines at the top -----
from Classes.Case.HighsSolverClass import HighsSolver
from Classes.Case.MosoxClass import Mosox
from Classes.Case.SolutionConvertersClass import SolutionConverters


# --- 2. one extra path, where run() defines self.lpFile ------------------------
#     self.mpsFile = base / "lp.mps"


# --- 3. the new branch, placed BEFORE the existing CBC branch ------------------
#     Replace the original `if solver == "glpk":` block with this one; the CBC
#     `else:` block stays exactly as it is.

            if solver in ("glpk", "highs", "highs-exe", "highs-mosox"):
                # Same pipeline as the CBC option: translate the MathProg model into a
                # matrix file, solve THAT file, convert the solution into CBC's format.
                # Every option therefore solves the same problem and the timings compare.
                self.preprocessData(self.dataFile, self.dataFile_processed)

                # ---------------- translate ----------------
                translate_start = time.time()
                if solver == "highs-mosox":
                    matrixFile = self.mpsFile
                    translator = "mosox (MathProg -> MPS)"
                    trans_out = Mosox.translate(self.mosoxFolder, self.osemosysFile,
                                                self.dataFile_processed, self.mpsFile)
                else:
                    matrixFile = self.lpFile
                    translator = "glpsol (MathProg -> LP)"
                    trans_out = subprocess.run(
                        [self.glpsol_path, "--check", "-m", modelfile,
                         "-d", dataFile_processed, "--wlp", lpFile],
                        cwd=glpk_cwd, text=True, capture_output=True)
                translate_time = time.time() - translate_start

                if trans_out.returncode != 0:
                    return {
                        "cbc_message": None, "cbc_stdmsg": None,
                        "glpk_message": trans_out.stdout, "glpk_stdmsg": trans_out.stderr,
                        "highs_message": "",
                        "timer": "Error during creation of the LP/MPS file - check the LP file log.",
                        "status_code": "error", "caserun": caserun,
                    }

                # ---------------- solve + convert ----------------
                solve_start = time.time()
                solver_log = ""
                if solver == "glpk":
                    solverName = "GLPK (glpsol simplex)"
                    reportFile = str(Path(self.resPath, "glpk_report.txt").resolve())
                    solve_out = subprocess.run(
                        [self.glpsol_path, "--lp", str(Path(matrixFile).resolve()), "-o", reportFile],
                        cwd=glpk_cwd, text=True, capture_output=True)
                    solver_log = (solve_out.stdout or "") + (solve_out.stderr or "")
                    if solve_out.returncode != 0 or not Path(reportFile).exists():
                        solve_flag, solve_msg = "error", "GLPK failed to solve the LP file."
                    else:
                        status, objective, nrows, ncols = SolutionConverters.fromGlpkReport(
                            reportFile, self.resFile)
                        solve_flag = "success" if status.upper().startswith("OPTIMAL") else "warning"
                        solve_msg = "   {} - objective value {:.8f}".format(
                            "Optimal" if solve_flag == "success" else status, objective)

                elif solver == "highs-exe":
                    solverName = "HiGHS standalone exe"
                    solve_flag, solve_msg, solver_log = HighsSolver.solveWithExe(
                        self.highsFolder, matrixFile, self.resFile)

                else:
                    solverName = "HiGHS (highspy)"
                    solve_flag, solve_msg, solver_log = HighsSolver.solve(matrixFile, self.resFile)

                solve_time = time.time() - solve_start

                # ---------------- results, CSVs, pivot data ----------------
                if solve_flag == "success":
                    self.generateCSVfromCBC(self.dataFile, self.resFile, self.resPath)
                    self.generateResultsViewer(caserun)

                total_time = time.time() - start_time
                timer_msg = solve_msg + ' - Solve: {:0.2f}s - Translation ({}): {:0.2f}s - Full run incl. CSVs: {:0.2f}s'.format(
                    solve_time, 'mosox' if solver == 'highs-mosox' else 'glpsol',
                    translate_time, total_time)
                run_summary = (
                    '==================== RUN SUMMARY ====================\n'
                    + 'Case run             : {}\n'.format(caserun)
                    + 'Solver               : {}\n'.format(solverName)
                    + 'Translator           : {}\n'.format(translator)
                    + 'LP/MPS creation time : {:0.2f} s\n'.format(translate_time)
                    + 'Solve time           : {:0.2f} s\n'.format(solve_time)
                    + 'Result               : {}\n'.format(solve_msg.strip())
                    + 'Full run incl. CSVs  : {:0.2f} s\n'.format(total_time)
                    + '=====================================================\n\n')
                return {
                    "cbc_message": None, "cbc_stdmsg": None,
                    "glpk_message": trans_out.stdout, "glpk_stdmsg": trans_out.stderr,
                    "highs_message": run_summary + solver_log,
                    "timer": timer_msg, "status_code": solve_flag, "caserun": caserun,
                }
