# MUIO 5.6 — Community Edition with fast solvers (HiGHS)

A ready-to-install Windows build of **MUIO** (Modelling User Interface for OSeMOSYS) that adds
three additional solver options — including **HiGHS** — so that large CLEWs / OSeMOSYS models
solve in seconds or minutes instead of hours.

Everything is bundled: **no Python installation, no solver installation, no configuration.**
Download, install, run.

> **This is an unofficial community build**, prepared by Nour El Islam DJEDAA (CREAD, Algeria).
> It is not released or endorsed by UN DESA, Climate Compatible Growth, or the MUIO maintainers.
> MUIO itself is their work and is licensed under Apache 2.0; this build adds solver options on
> top of it without modifying the OSeMOSYS model files or the way results are produced.

---

## Download

Get **`MUIO-5.6-HiGHS-Setup.exe`** from the [Releases](../../releases/latest) page (about 69 MB).

* Windows 10 / 11, 64-bit
* Installs per user — **no administrator rights required**
* No Python, no solver installation, no Visual C++ redistributable needed
* The installation contains **no models**; you create or import your own

On first launch Windows may show *"Windows protected your PC"* because the file is not
code-signed. Choose **More info → Run anyway**. Some antivirus products occasionally flag
PyInstaller-packaged applications; if that happens, allow the installation folder.

---

## Why this build exists

MUIO ships with two solvers: **GLPK** and **CBC**. On large CLEWs models — several hundred
thousand constraints, 96 timeslices, multiple zones — GLPK can take 10 minutes or more per run,
which makes scenario work painful.

This build adds **HiGHS**, a modern open-source solver, and **mosox**, a fast matrix generator,
while keeping results identical to a CBC run.

### Measured on real models

Full runs through the application (translation → solve → 27 result CSVs → pivot data):

| model | CBC | **HiGHS (mosox)** | HiGHS (glpsol) | GLPK |
|---|---|---|---|---|
| CLEWs seasonal, 351 587 rows × 307 505 cols | 94 s | **73 s** | 88 s | 788 s |
| CLEWs model, 74 705 rows × 56 078 cols | **12 s** | 17 s | 15 s | 30 s |

Solve step only, on the same 125 MB LP file: CBC 9.4 s · HiGHS 24 s · GLPK 473 s.

**All options reach the same optimum**, verified digit for digit (for example
608520.56855933 on the second model, −32.23122691 on the first).

### Rule of thumb

| your situation | use |
|---|---|
| large seasonal / multi-zone CLEWs model | **HiGHS (mosox)** — fastest end to end |
| small or medium model | **CBC** — hard to beat below ~10⁵ rows |
| you want a second opinion on a result | run it twice with CBC and HiGHS — they must agree |
| — | avoid **GLPK** for production runs; it is 8–50× slower |

---

## What is different from stock MUIO 5.6

### A solver dropdown next to RUN MODEL

| option | matrix generator | optimizer |
|---|---|---|
| **CBC** (default) | glpsol → `lp.lp` | CBC — the original MUIO behaviour, unchanged |
| **GLPK** | glpsol → `lp.lp` | glpsol simplex |
| **HiGHS (standalone)** | glpsol → `lp.lp` | bundled `highs.exe` |
| **HiGHS (highspy)** | glpsol → `lp.lp` | HiGHS in-process |
| **HiGHS (mosox)** | mosox → `lp.mps` | HiGHS in-process |

### A "HiGHS solver log" tab

After a HiGHS run, a new tab shows the full solver log preceded by a permanent run summary:

```
==================== RUN SUMMARY ====================
Case run             : CLEWs
Solver               : HiGHS (highspy)
Translator           : mosox (MathProg -> MPS)
LP/MPS creation time : 16.14 s
Solve time           : 28.82 s
Result               : Optimal - objective value -32.23122691
Full run incl. CSVs  : 72.66 s
=====================================================
```

The message after a run also reports the same timings, so you can compare translators and
solvers on your own models.

### A working GLPK option

In stock MUIO 5.6 the GLPK option fails and produces no results. Here it solves the exported
LP and its solution is converted into the standard format, so it produces the same 27 result
CSVs and the same charts as any other option.

### A desktop-application experience

* No console window
* Opens in its own application window (Edge or Chrome in app mode), not as a browser tab
* A **tray icon** with *Open MUIO* and *Quit MUIO* — closing the window leaves the server
  running so a long solve is never interrupted by accident; use *Quit MUIO* to stop it

---

## Using it

1. **Create or import a model** — the installation starts empty. Use *Add model*, or
   *Upload model* with a MUIO model archive (`.zip`).
2. **Open a case run** and press **Generate data File**.
3. **Choose a solver** in the dropdown next to RUN MODEL.
4. **Press RUN MODEL.** When it finishes, the *Results* tab lists the CSV files and the
   *Results* page in the sidebar shows the pivot tables and charts — identical in structure
   whichever solver you used.

### Where your models are stored

```
<installation folder>\WebAPP\DataStorage\<model name>\
```

Default installation folder: `%LOCALAPPDATA%\Programs\MUIO 5.6 HiGHS`

**Uninstalling does not delete your models** — the uninstaller removes the program files and
leaves `WebAPP` in place. Back up that folder, or use *Backup model* in the application, before
major changes.

---

## How the results are produced

MUIO reads solver output in exactly one format: CBC's. Rather than changing the way MUIO reads
results, each solver's output is converted into that format:

```
MUIO data + OSeMOSYS model (MathProg)
        │
        ├── glpsol --check --wlp  →  lp.lp        (or mosox compile → lp.mps)
        │
        ├── CBC | GLPK | HiGHS solves that file
        │
        ├── converter → results.txt in CBC's format
        │
        └── the standard MUIO pipeline: 27 result CSVs → pivot data → charts
```

The converted file contains the objective value, every constraint with its activity and shadow
price, and every variable with its value and reduced cost — exactly what MUIO expects. This is
why the CSV files, the results viewer and every chart behave the same no matter which solver
you choose, and why the objective value matches CBC's to the last digit.

GLPK remains the translator from MathProg in every option (only `glpsol` and `mosox` can read
the OSeMOSYS model language); HiGHS replaces only the optimization step.

---

## Things worth knowing about results

### Different solvers may report different capacities at the same cost

An LP has a unique optimal **cost**, but not necessarily a unique **solution**. If a technology
has zero cost in the objective, any value within its bounds is equally optimal, and different
solvers legitimately return different ones. In one CLEWs model a land technology could take any
value between 0 and 998 967 at exactly the same total cost: CBC returned the upper end, HiGHS
returned 0.

If you need reproducible capacity numbers, give such technologies a real
`TotalAnnualMaxCapacity` instead of the 999 999 default, or a small cost — that makes the
optimum unique and every solver must then return the same values.

### The reported objective excludes one constant

The OSeMOSYS objective contains `ResidualCapacity × FixedCost` — fixed O&M on capacity that
already exists. It is a constant, and the LP export drops it, so the reported total cost is
short by that amount. **This applies to stock MUIO with CBC as well**, and has nothing to do
with HiGHS. It never changes the optimal decisions (a constant cannot move the optimum), but if
you compare scenarios whose residual capacity or fixed costs differ, be aware the missing amount
differs too.

### HiGHS (mosox) writes two extra CSV files

`InputToNewCapacity.csv` and `InputToTotalCapacity.csv`, containing only zeros. mosox keeps
matrix columns that are empty, which glpsol's LP writer drops. They are harmless.

---

## Troubleshooting

| symptom | what to do |
|---|---|
| *"Windows protected your PC"* | **More info → Run anyway** (the build is not code-signed) |
| Antivirus blocks the installer | allow the installation folder; PyInstaller apps trigger false positives |
| Setup says files are in use | MUIO is running — choose *Automatically close the applications*, or quit it from the tray icon first |
| The window opens but shows an error | another MUIO instance may already be using port 5002 — quit it from the tray icon |
| Nothing appears on launch | check `WebAPP\console.log` and `WebAPP\app.log` in the installation folder |
| A run fails with GLPK but works with CBC | expected — use CBC or HiGHS; GLPK is included for comparison only |
| The application window does not open | Edge and Chrome were not found; MUIO still runs — open `http://127.0.0.1:5002` in any browser |

---

## Adding HiGHS to your own MUIO installation

If you already run MUIO and do not want to replace it, the [`kit/`](kit) folder contains
everything needed to add the solver options to an existing installation:

* three Python classes to copy into `API/Classes/Case/`
* the `highs.exe` and `mosox.exe` binaries
* the exact code to paste into the solver dispatch, for both MUIO 5.3-style and 5.6-style
  applications, plus the interface changes
* `verify_setup.py`, which checks every piece and solves a small test problem to prove the
  installation works before you run a real model

See [`kit/README.md`](kit/README.md) for step-by-step instructions and the known pitfalls.

---

## Components and licences

| component | licence | source |
|---|---|---|
| MUIO | Apache 2.0 | https://github.com/OSeMOSYS/MUIO |
| OSeMOSYS model | Apache 2.0 | https://github.com/OSeMOSYS/OSeMOSYS |
| HiGHS 1.15.1 | MIT | https://github.com/ERGO-Code/HiGHS |
| mosox 0.6.2 | MIT | https://github.com/carderne/mosox |
| GLPK 4.65 (`glpsol`) | GPL v3 | https://www.gnu.org/software/glpk/ |
| CBC / CLP | EPL 2.0 | https://github.com/coin-or/Cbc |

This build is distributed under the Apache 2.0 licence of MUIO (see [LICENSE](LICENSE)).
The solver binaries are redistributed unmodified under their own licences, listed above with
links to their official sources.

**Changes made to MUIO 5.6 in this build** (as required by Apache 2.0 §4b): addition of the
HiGHS, HiGHS (standalone), HiGHS (mosox) and repaired GLPK solver options with their solution
converters; a solver selector and HiGHS log tab in the interface; desktop-application packaging
(windowed launch, application window, tray icon). The OSeMOSYS model files, the CBC solver path
and the result-processing pipeline are unchanged.

---

## Credits

MUIO is developed by the MUIO / OSeMOSYS community (UN DESA, Climate Compatible Growth, KTH and
contributors). This community build was prepared by **Nour El Islam DJEDAA**, CREAD — Centre de
Recherche en Économie Appliquée pour le Développement, Algeria.
