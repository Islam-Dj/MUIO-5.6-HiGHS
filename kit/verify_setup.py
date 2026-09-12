"""Check that the HiGHS/mosox kit is correctly installed in a MUIO application.

Run it from the MUIO app root (the folder that contains API/ and WebAPP/):

    python verify_setup.py

It checks the pieces, then solves a tiny OSeMOSYS-shaped LP end to end and
verifies that the converted solution is readable exactly the way MUIO reads a
CBC solution. No model of yours is touched.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

OK, WARN, BAD = "PASS", "WARN", "FAIL"
results = []


def report(level, what, detail=""):
    results.append(level)
    print(f"[{level}] {what}" + (f"  -  {detail}" if detail else ""))


root = Path.cwd()
print(f"MUIO app root: {root}\n")

# ---------------------------------------------------------------- structure
api_case = root / "API" / "Classes" / "Case"
web_solvers = root / "WebAPP" / "SOLVERs"
if api_case.is_dir() and web_solvers.is_dir():
    report(OK, "MUIO layout found", "API/Classes/Case and WebAPP/SOLVERs exist")
else:
    report(BAD, "MUIO layout NOT found",
           "run this from the folder that contains API/ and WebAPP/")
    print("\nCannot continue.")
    sys.exit(1)

for f in ("HighsSolverClass.py", "SolutionConvertersClass.py", "MosoxClass.py"):
    report(OK if (api_case / f).exists() else BAD, f"class {f}",
           "" if (api_case / f).exists() else f"copy it into {api_case}")

# ---------------------------------------------------------------- binaries
exe_name = "highs.exe" if os.name == "nt" else "highs"
mosox_name = "mosox.exe" if os.name == "nt" else "mosox"
highs_exe = web_solvers / "HIGHS" / exe_name
mosox_exe = web_solvers / "MOSOX" / mosox_name
report(OK if highs_exe.exists() else WARN, f"standalone {exe_name}",
       str(highs_exe) if highs_exe.exists() else "optional - needed for the HiGHS (standalone) option")
report(OK if mosox_exe.exists() else WARN, f"{mosox_name}",
       str(mosox_exe) if mosox_exe.exists() else "optional - needed for the HiGHS (mosox) option")

# MUIO prefers its bundled solver, so look there first
glpsol = next(iter(web_solvers.glob("GLPK/**/glpsol*")), None) or shutil.which("glpsol")
report(OK if glpsol else BAD, "glpsol (MathProg translator)",
       str(glpsol) if glpsol else "required: only glpsol/mosox can read the OSeMOSYS model")

# ---------------------------------------------------------------- python deps
try:
    import highspy  # noqa: F401
    report(OK, "highspy", "in-process HiGHS available")
except ImportError:
    report(WARN, "highspy not installed", "pip install highspy (only needed for the in-process option)")

try:
    import pandas as pd
    ver = tuple(int(x) for x in pd.__version__.split(".")[:2])
    if ver >= (3, 0):
        src = (api_case / "DataFileClass.py").read_text(encoding="utf-8", errors="replace") \
            if (api_case / "DataFileClass.py").exists() else ""
        # only real code counts - commented-out calls are harmless
        live_applymap = [ln for ln in src.splitlines()
                         if ".applymap(" in ln and not ln.strip().startswith("#")]
        if live_applymap:
            report(BAD, f"pandas {pd.__version__} + DataFileClass uses applymap",
                   "pandas 3 removed DataFrame.applymap - replace '.applymap(' with '.map(' or CSVs will fail")
        else:
            report(OK, f"pandas {pd.__version__}", "no applymap left in DataFileClass")
    else:
        report(OK, f"pandas {pd.__version__}")
except ImportError:
    report(BAD, "pandas missing", "MUIO needs pandas")

# ---------------------------------------------------------------- end-to-end
sys.path.insert(0, str(root / "API"))
tiny_lp = """\\* Problem: verify *\\

Minimize
 cost: + 2 RateOfActivity(RE1,S11,PWRSOL,1,2024) + 3 NewCapacity(RE1,PWRGAS,2024)

Subject To
 EBb4_EnergyBalanceEachYear4_ICR(RE1,ELC,2024): + RateOfActivity(RE1,S11,PWRSOL,1,2024)
 + NewCapacity(RE1,PWRGAS,2024) >= 10
 CAa4_Constraint_Capacity(RE1,S11,PWRSOL,2024): + RateOfActivity(RE1,S11,PWRSOL,1,2024) <= 8

Bounds

End
"""

def check_cbc_format(path):
    """Parse the file the way MUIO's generateCSVfromCBC does."""
    with open(path) as f:
        header = f.readline().strip()
        if "Optimal - objective value" not in header:
            return False, "first line is not 'Optimal - objective value ...'"
        names = []
        for line in f:
            if "\t" in line:
                return False, "file contains a TAB character (MUIO reads it with sep='\\t')"
            line = line.lstrip(" *\n\t")
            if not line.strip():
                continue
            if ")" not in line or "(" not in line:
                return False, f"entry without parentheses: {line[:60]}"
            left, _, right = line.partition(")")
            parts = right.split()
            if len(parts) != 2:
                return False, f"expected 'value dual' after ')': {line[:60]}"
            names.append(left.split("(")[0].split(" ")[1])
        return True, f"header + {len(names)} entries, parameters seen: {sorted(set(names))}"

tmp = Path(tempfile.mkdtemp(prefix="muio_highs_verify_"))
lp_path, res_path = tmp / "verify.lp", tmp / "results.txt"
lp_path.write_text(tiny_lp)

try:
    from Classes.Case.HighsSolverClass import HighsSolver
    flag, msg, _ = HighsSolver.solve(lp_path, res_path)
    if flag == "success" and res_path.exists():
        good, detail = check_cbc_format(res_path)
        report(OK if good else BAD, "end-to-end: highspy -> CBC-format solution", detail)
    else:
        report(WARN, "end-to-end (highspy) skipped", msg[:90])
except Exception as e:
    report(WARN, "end-to-end (highspy) skipped", f"{type(e).__name__}: {e}")

if highs_exe.exists():
    try:
        from Classes.Case.HighsSolverClass import HighsSolver
        res2 = tmp / "results_exe.txt"
        flag, msg, _ = HighsSolver.solveWithExe(highs_exe.parent, lp_path, res2)
        if flag == "success" and res2.exists():
            good, detail = check_cbc_format(res2)
            report(OK if good else BAD, "end-to-end: highs.exe -> CBC-format solution", detail)
        else:
            report(BAD, "end-to-end (highs.exe) failed", msg[:90])
    except Exception as e:
        report(BAD, "end-to-end (highs.exe) failed", f"{type(e).__name__}: {e}")

if mosox_exe.exists():
    out = subprocess.run([str(mosox_exe), "--version"], capture_output=True, text=True)
    report(OK if out.returncode == 0 else BAD, "mosox runs", (out.stdout or out.stderr).strip()[:60])

shutil.rmtree(tmp, ignore_errors=True)

# ---------------------------------------------------------------- verdict
print()
if BAD in results:
    print("RESULT: something is missing - fix the FAIL lines above, then run this again.")
    sys.exit(1)
print("RESULT: ready. Start MUIO, open a case run and pick HiGHS in the solver dropdown.")
