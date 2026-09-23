# MUIO 5.6 — Community Edition (HiGHS)

**MUIO** (Modelling User Interface for OSeMOSYS) with additional solver options, including
**HiGHS**, for solving large OSeMOSYS / CLEWs models — plus configurable HiGHS settings, live
progress while a model runs, and a run summary for every run.

This repository contains the **full application source**. The **Windows installer** is published
with each release and includes everything needed to run it.

> **Unofficial community edition** prepared by Nour El Islam DJEDAA (CREAD, Algeria).
> It is not released or endorsed by UN DESA, Climate Compatible Growth or the MUIO maintainers.
> MUIO is their work, licensed under Apache 2.0.

---

## Download

**[Download MUIO-5.6-HiGHS-Setup.exe](../../releases/latest)** (about 72 MB)

The installer bundles everything: **no Python installation, no solver installation, no
configuration.**

### Requirements

* Windows 10 or 11, 64-bit
* Nothing else — no Python, no solvers, no Visual C++ redistributable

### Installation

* Installs for the current user — **no administrator rights needed**
* Default folder: `%LOCALAPPDATA%\Programs\MUIO 5.6 HiGHS`
* The installation contains **no models**; you create or import your own

On first run Windows may show *"Windows protected your PC"* because the file is not
code-signed. Choose **More info → Run anyway**.

---

## Using the application

1. **Create or import a model** — the installation starts empty. Use *Add/configure model*, or
   *Import model* to bring in an existing MUIO model archive. An imported archive is checked before
   the model is created.
2. Open a case run and press **Generate data File**.
3. Choose a solver in the selector next to **RUN MODEL**.
4. Press **RUN MODEL**. While it runs, the progress indicator shows the current stage. When it
   finishes, the *Run summary* tab describes the run, and the *Results* page in the sidebar shows
   the tables and charts.

### The application window

MUIO opens in its own application window and places an icon in the system tray:

* **Open MUIO** — reopens the window
* **Quit MUIO** — stops the application

Closing the window does **not** stop a running calculation; use *Quit MUIO* to stop the
application completely. Solvers run in the background without opening console windows.

### Your models

Models are stored in `WebAPP\DataStorage` inside the installation folder.
**Uninstalling does not delete them.** Use *Backup model* in the application before major
changes.

Each model folder also holds two folders that MUIO manages itself:

* `.run-history` — one copy of the previous results of each case run
* `.executions` — the latest run of each case run that did not produce new results, kept so the
  cause can be examined

*MUIO clean up* removes result files but keeps each case run's input data and its run record.

---

## Solver options

A solver selector appears next to the **RUN MODEL** button:

| option | description |
|---|---|
| **CBC** | the standard MUIO solver (default) |
| **GLPK** | the GLPK simplex solver |
| **HiGHS (standalone)** | HiGHS, run as a separate program |
| **HiGHS (highspy)** | HiGHS, run inside the application |
| **HiGHS (mosox)** | HiGHS combined with the mosox matrix generator |

Every option solves the **same problem** and produces the **same result files and charts** — the
solver output is converted into the format MUIO already reads, so nothing downstream changes.

**Which one to use:** CBC is a good default for small and medium models. HiGHS is the stronger
choice as models grow large, and for mixed-integer models — models that use
`CapacityOfOneTechnologyUnit` to build capacity in whole units. GLPK is provided for comparison
and is not recommended for mixed-integer models.

After a run with any HiGHS option, a **HiGHS solver log** tab shows the solver's own log.

---

## HiGHS settings

The **gear button** next to the solver selector opens the HiGHS settings. They apply only to the
three HiGHS options; every field can be left at its default.

| setting | values | what it does |
|---|---|---|
| **Algorithm** | choose *(default)*, simplex, interior point (ipm), interior point (ipx), active set (qpasm), first order (hipdlp), first order (pdlp) | the method HiGHS uses. *choose* lets HiGHS decide. The two first-order methods reach the optimum to a tolerance rather than exactly. |
| **Presolve** | choose *(default)*, on, off | removes redundant rows and columns before solving. Turn off only to diagnose a model. |
| **Parallel** | on *(default)*, choose, off | allows HiGHS to use several processor cores |
| **Threads** | a number, `0` = automatic | how many threads HiGHS may use |
| **Time limit** | seconds, empty = no limit | stops the solve after this time. Cannot be combined with *pdlp*: MUIO refuses such a run and says so. |
| **PDLP tolerance** | e.g. `1e-7` *(default)*, `1e-8` | used by *pdlp* only: a smaller value gives a more exact objective and takes longer |
| **MIP gap** | e.g. `0.01` for 1 %, empty = exact | mixed-integer models only: accept a solution within this relative gap of the optimum |

A setting that is not valid — an unknown value, or a number out of range — is refused with a
message rather than ignored. The settings actually used are recorded with every run in the run
summary.

---

## Progress while a model runs

While a model runs, the progress indicator shows the **current stage**, its **elapsed time** and
an **estimated percentage** for the whole run. A run passes through six stages:

1. **preparing data** — the case data is prepared for the model
2. **generating matrix** — the model and data are translated into the optimisation problem
3. **checking matrix** — the size and type of the problem are read from the generated matrix
4. **solving** — the chosen solver finds the optimum
5. **writing result files** — the solution is written to the result CSV files
6. **preparing charts** — the data for the *Results* page is prepared

The percentage is an estimate while a stage is running; once a stage finishes, its real time is
used.

### While a model runs

* Only one model runs at a time.
* Your other models stay available: you can open, read and edit them during the run.
* The model being run cannot be changed until its run finishes.

### When a run does not succeed

New results replace the previous ones **only when a run succeeds**. If a run fails, or ends without
an optimal solution — an infeasible model, for example — your previous results stay exactly as they
were, and the Run summary shows what the solver concluded.

---

## Run summary

After every run, the **Run summary** tab shows:

* **Solver**, total run time and **peak memory** used by MUIO and the solver
* **Result** — *Optimal*, *Infeasible*, *Unbounded*, *Time limit*, or the solver's own status —
  and the **objective value** when a solution was found
* **Problem size and type** — *LP* or *MILP*, rows, columns, non-zeros, and for mixed-integer
  models the number of **integer columns**
* **Time and share of each stage**

### The record of runs

Every run is also added as one row to `run_summary.csv`, in the folder of the case run:

```
WebAPP\DataStorage\<model>\res\<case run>\run_summary.csv
```

Download it from the Run summary tab as **.csv**, or as a formatted **.xlsx** workbook. Each row
contains:

| columns | content |
|---|---|
| `timestamp`, `case`, `caserun`, `muio_solver` | when, which model and case run, which solver option |
| `problem`, `rows`, `columns`, `nonzeros`, `integers` | problem type and size |
| `status`, `outcome` | how the run ended and what the solver concluded |
| `objective`, `fixed_cost`, `total_cost` | see *Objective value* below |
| `total_s`, `peak_mb` | total run time in seconds, peak memory in MB |
| `<stage>_s`, `<stage>_pct` | time and share of each of the six stages |
| `highs_<setting>` | the HiGHS settings in force (empty for CBC and GLPK) |

**New record** starts a fresh record. The previous one is not deleted: it is kept in the same
folder as `run_summary_YYYYmmdd_HHMMSS.csv`.

---

## Objective value

The OSeMOSYS objective includes costs that do not depend on any decision the model makes — in
particular the **fixed cost of existing (residual) capacity**. When the model is translated into a
matrix file for the solver, this constant term is not carried in the file, so the value a solver
returns is lower than the model's total cost by exactly that amount.

This edition recovers the constant during matrix generation and **adds it back**:

* `ObjectiveValue.csv` and the *Results* page report the **full total cost**
* the Run summary shows the total and states the part that was added:
  *includes … fixed cost of existing capacity, which the matrix does not carry — the solver
  returned …*
* `run_summary.csv` records the solver's value (`objective`), the constant (`fixed_cost`) and the
  sum (`total_cost`)

The constant does not change **which** solution is optimal: capacities, activities and all other
results are the same with or without it. Only the reported total cost changes.

With **HiGHS (mosox)**, the matrix is generated without GLPK, so the constant is calculated
directly from the model's data — residual capacity, fixed cost and discount rate. This calculation
applies to the OSeMOSYS model file supplied with MUIO. If that file has been modified, MUIO does not
attempt it: the Run summary states that the full cost is unavailable, and no `ObjectiveValue.csv` is
written for that run.

---

## Running from source

The installer is the simplest way to use MUIO. To run it from this repository instead:

1. Install **Python** — this edition is tested with Python 3.14 on Windows.
2. Install the Python packages:

   ```
   pip install -r requirements.txt
   ```

3. Add the **solver programs**. They are not part of this repository (see *Components and
   licences*). Place them as follows:

   ```
   WebAPP\SOLVERs\COIN-OR\cbc.exe
   WebAPP\SOLVERs\GLPK\glpsol.exe      (with glpk_4_65.dll)
   WebAPP\SOLVERs\HIGHS\highs.exe
   WebAPP\SOLVERs\MOSOX\mosox.exe
   ```

   Each solver option needs these programs:

   | option | programs |
   |---|---|
   | CBC | `glpsol.exe`, `cbc.exe` |
   | GLPK | `glpsol.exe` |
   | HiGHS (standalone) | `glpsol.exe`, `highs.exe` |
   | HiGHS (highspy) | `glpsol.exe` — HiGHS itself comes from the `highspy` package |
   | HiGHS (mosox) | `mosox.exe` — HiGHS itself comes from the `highspy` package |

   GLPK generates the matrix for every option except HiGHS (mosox).

   The easiest source for exactly these files is an installed copy of MUIO: copy them from
   `WebAPP\SOLVERs` in the installation folder. CBC and GLPK are also found if they are on your
   `PATH`.

4. Start MUIO — run only one MUIO at a time on the same model folder:

   ```
   python API/app.py
   ```

5. Open **http://127.0.0.1:5002** in a browser.

When run from source, MUIO runs in the terminal and is used through your browser; the
application window and tray icon belong to the installed version. Stop it with **Ctrl+C** in the
terminal.

---

## Troubleshooting

| symptom | what to do |
|---|---|
| *"Windows protected your PC"* | **More info → Run anyway** (the installer is not code-signed) |
| Antivirus blocks the installer | allow the installation folder |
| Setup reports that files are in use | MUIO is running — choose *Automatically close the applications*, or quit it from the tray icon |
| The window opens with an error | another MUIO instance may still be running — quit it from the tray icon |
| Nothing appears when launching | see `WebAPP\console.log` and `WebAPP\app.log` in the installation folder |
| No application window appears | Edge or Chrome was not found; MUIO is still running — open `http://127.0.0.1:5002` in a browser |
| The page stays on *Loading…* with *Error!* | MUIO has stopped — start it again and reload the page |
| *This model is being run or changed* | wait for the run to finish; your other models can be used meanwhile |
| *A model execution is already in progress* | only one model runs at a time — start the next one when the current run finishes |
| A message about *PDLP* and a time limit | choose another algorithm, or remove the time limit |
| From source, a run fails at once | a solver program is missing — place it as described in *Running from source* |

---

## Components and licences

| component | licence | source |
|---|---|---|
| MUIO | Apache 2.0 | https://github.com/OSeMOSYS/MUIO |
| OSeMOSYS | Apache 2.0 | https://github.com/OSeMOSYS/OSeMOSYS |
| HiGHS | MIT | https://github.com/ERGO-Code/HiGHS |
| mosox | MIT | https://github.com/carderne/mosox |
| GLPK | GPL v3 | https://www.gnu.org/software/glpk/ |
| CBC / CLP | EPL 2.0 | https://github.com/coin-or/Cbc |

This edition is distributed under the Apache 2.0 licence of MUIO (see [LICENSE](LICENSE) and
[NOTICE](NOTICE)).

* The **solver programs** are included, unmodified, in the installer only; they are not part of
  this repository.
* The **JavaScript libraries** in `WebAPP/References` are included as in the upstream MUIO
  repository and remain under their respective licences.

### Changes to MUIO

As required by Apache 2.0 §4(b), the changes made to MUIO 5.6 are:

* additional solver options — GLPK, HiGHS (standalone), HiGHS (highspy) and HiGHS (mosox) — with
  converters that write their solutions in the format MUIO reads
* the HiGHS settings panel
* live progress for each stage of a run
* the Run summary and the `run_summary.csv` record, with .csv and .xlsx download
* recovery of the objective's constant term, added to the reported objective value
* results published only when a run succeeds, with one previous copy kept
* changes locked per model while that model is being run
* validated import of model archives, and safe saving of model data
* *MUIO clean up* keeps each case run's input data and run record
* faster writing of the result files
* solver programs run without console windows, and packaging as a desktop application with an
  installer

The OSeMOSYS model file is unchanged.

---

Prepared by **Nour El Islam DJEDAA** — CREAD, Centre de Recherche en Économie Appliquée pour le
Développement, Algeria.
