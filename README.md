# MUIO 5.6 — Community Edition (HiGHS)

A ready-to-install Windows build of **MUIO** (Modelling User Interface for OSeMOSYS) with
additional solver options, including **HiGHS**, for faster solving of large OSeMOSYS / CLEWs
models.

Everything is bundled: **no Python installation, no solver installation, no configuration.**

> **Unofficial community build** prepared by Nour El Islam DJEDAA (CREAD, Algeria).
> It is not released or endorsed by UN DESA, Climate Compatible Growth or the MUIO maintainers.
> MUIO is their work, licensed under Apache 2.0.

---

## Download

**[Download MUIO-5.6-HiGHS-Setup.exe](../../releases/latest)** (about 69 MB)

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

## Solver options

A solver selector appears next to the **RUN MODEL** button:

| option | description |
|---|---|
| **CBC** | the standard MUIO solver (default) |
| **GLPK** | the GLPK simplex solver |
| **HiGHS (standalone)** | HiGHS, run as a bundled executable |
| **HiGHS (highspy)** | HiGHS, run inside the application |
| **HiGHS (mosox)** | HiGHS combined with the mosox matrix generator |

All options produce the **same optimal value** and the **same result files and charts** — the
solver output is converted into the format MUIO already reads, so nothing downstream changes.

**Which one to use:** CBC is a good default for small and medium models. On large models —
many timeslices, several zones, hundreds of thousands of constraints — **HiGHS (mosox)** is
normally the fastest from start to finish. GLPK is the slowest and is provided for comparison.

After a run with any HiGHS option, a **HiGHS solver log** tab shows the solver log and a summary
with the time spent generating the matrix, solving, and producing the result files, so you can
compare options on your own models.

---

## Using the application

1. **Create or import a model** — the installation starts empty. Use *Add model*, or upload an
   existing MUIO model archive.
2. Open a case run and press **Generate data File**.
3. Choose a solver in the selector next to **RUN MODEL**.
4. Press **RUN MODEL**. When it finishes, the *Results* tab lists the result files, and the
   *Results* page in the sidebar shows the tables and charts.

### The application window

MUIO opens in its own application window and places an icon in the system tray:

* **Open MUIO** — reopens the window
* **Quit MUIO** — stops the application

Closing the window does **not** stop a running calculation; use *Quit MUIO* to stop the
application completely.

### Your models

Models are stored in `WebAPP\DataStorage` inside the installation folder.
**Uninstalling does not delete them.** Use *Backup model* in the application before major
changes.

---

## Troubleshooting

| symptom | what to do |
|---|---|
| *"Windows protected your PC"* | **More info → Run anyway** (the build is not code-signed) |
| Antivirus blocks the installer | allow the installation folder |
| Setup reports that files are in use | MUIO is running — choose *Automatically close the applications*, or quit it from the tray icon |
| The window opens with an error | another MUIO instance may still be running — quit it from the tray icon |
| Nothing appears when launching | see `WebAPP\console.log` and `WebAPP\app.log` in the installation folder |
| No application window appears | Edge or Chrome was not found; MUIO is still running — open `http://127.0.0.1:5002` in a browser |

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

Distributed under the Apache 2.0 licence of MUIO (see [LICENSE](LICENSE)). Solver binaries are
redistributed unmodified under their own licences.

**Changes made to MUIO 5.6** (as required by Apache 2.0 §4b): additional solver options with
their solution converters, a solver selector and solver log tab in the interface, and desktop
application packaging. The OSeMOSYS model files, the CBC solver path and the result processing
are unchanged.

---

Prepared by **Nour El Islam DJEDAA** — CREAD, Centre de Recherche en Économie Appliquée pour le
Développement, Algeria.
