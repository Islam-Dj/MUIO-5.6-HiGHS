# Fast solvers for MUIO / OSeMOSYS — HiGHS + mosox drop-in kit

For anyone running big CLEWs / OSeMOSYS models in MUIO who is stuck waiting on the solver.

This adds **HiGHS** (and the **mosox** matrix generator) to an existing MUIO installation
**without touching the OSeMOSYS model file, the CBC path, or any result handling**. Results
come out in exactly the same CSVs and charts as a CBC run — the solver output is converted
into CBC's own solution format, so MUIO cannot tell the difference.

Prepared by Nour El Islam DJEDAA (CREAD) from a working integration in MUIO 5.3 and 5.6.

---

## Why bother — measured numbers

Three real models, same machine, full app runs (translate → solve → 27 result CSVs → pivot
data). Every option reaches the **same optimum**, verified digit for digit.

| model | CBC | **HiGHS (mosox)** | HiGHS (glpsol) | GLPK |
|---|---|---|---|---|
| CLEWs Zone A SSP1 — 2.7 MB data, 153 MB LP | 94 s | **73 s** | 88 s | 788 s |
| CLEWs seasonal aze — 351 587 rows × 307 505 cols (solve only) | 9.4 s | — | 24 s | 473 s |
| small desalination model — 74 705 rows | 12.2 s | 17.2 s | 14.5 s | 30 s |

Reading (not solving) is HiGHS's remaining cost on large models: on Zone A SSP1 it spends
~20 s reading the matrix and only **~7 s solving**. That is why the mosox translator — which
writes MPS about 1.6–2× faster than `glpsol --wlp` — gives the best total.

**Rules of thumb**
- Big seasonal/multi-zone CLEWs models → **HiGHS (mosox)** is fastest end to end.
- Small models → CBC still wins; the crossover point is around 10⁵ rows.
- **Never leave GLPK as your solver** for production runs: 8–50× slower than CBC here.
- **Do not force barrier** (`solver = 'ipm'`). On these very sparse LPs it is ~2–5× slower
  than letting HiGHS choose, which picks dual simplex. This single setting was worth 5× on
  our model (solve 36.9 s → 7.3 s).

---

## What is in this kit

```
classes/      HighsSolverClass.py          HiGHS via highspy + via the standalone exe
              SolutionConvertersClass.py   highs.exe / glpsol report  ->  CBC format
              MosoxClass.py                MathProg -> MPS through mosox
solvers/      highs.exe                    HiGHS 1.15.1 standalone (MIT)
              mosox.exe                    mosox 0.6.2 (MIT, Climate Compatible Growth)
snippets/     dispatch_56.py               code to paste into DataFileClass.run()
              dispatch_53.py               same, for the older 5.3-style run()
              frontend.html.txt            solver dropdown + HiGHS log tab
verify_setup.py                            proves the whole chain works before you run a model
```

## Requirements

- Python environment that runs the MUIO API (Flask + pandas).
- `pip install highspy` — optional. Needed only for the in-process option; the bundled
  `highs.exe` works without it.
- `glpsol` (already in every MUIO install) stays the default translator. Only HiGHS's
  **optimization** step replaces CBC — OSeMOSYS is MathProg, and only glpsol/mosox can read it.

## Install (about 10 minutes)

1. **Binaries** → copy into your MUIO installation:
   `solvers/highs.exe` → `WebAPP/SOLVERs/HIGHS/highs.exe`
   `solvers/mosox.exe` → `WebAPP/SOLVERs/MOSOX/mosox.exe`
2. **Classes** → copy the three files from `classes/` into `API/Classes/Case/`.
3. **Solver folders** → in `API/Classes/Case/OsemosysClass.py`, next to the existing
   `self.glpkFolder` / `self.cbcFolder`, add:
   ```python
   self.mosoxFolder = Path(Config.SOLVERs_FOLDER, 'MOSOX')
   self.highsFolder = Path(Config.SOLVERs_FOLDER, 'HIGHS')
   ```
4. **Dispatch** → in `API/Classes/Case/DataFileClass.py`, add the imports at the top and the
   new branch inside `run()` — copy from `snippets/dispatch_56.py` (MUIO 5.6-style `run()`,
   list-argument subprocess) or `snippets/dispatch_53.py` (older 5.3-style, `shell=True`).
   **Leave the CBC branch untouched.**
5. **Frontend** → apply `snippets/frontend.html.txt`: a solver dropdown next to RUN MODEL,
   a "HiGHS solver log" tab, and reading the dropdown instead of the hardcoded `'cbc'` in
   `WebAPP/App/Controller/DataFile.js`.
6. **Check** → `python verify_setup.py` from your MUIO app root. It must print all PASS.

## How results stay identical

MUIO's `generateCSVfromCBC()` parses exactly one layout, CBC's:

```
Optimal - objective value 608520.56855933
      0 EBb4_EnergyBalanceEachYear4_ICR(RE1,ELC,2024) 10.5 6.0     <- constraints: activity + shadow price
      0 NewCapacity(RE1,PWRSOL,2024) 4.2 0                         <- variables: value + reduced cost
```

The converters write exactly that: constraint rows first (so shadow prices survive), then
variables; no tab characters; one space after the index; `Var[i,j]` names rewritten to
`Var(i,j)`; IEEE `-0.0` normalised to `0`; objective at CBC's 8-decimal precision. Nothing
downstream changes — same CSVs, same pivot JSONs, same charts.

## Known traps (all of these cost us time)

| symptom | cause | fix |
|---|---|---|
| Run fails instantly, "Error during creation of LP file or solution" | MUIO calls `cbc`/`glpsol` by bare name and relies on the working directory | use absolute paths, or put `WebAPP/SOLVERs/COIN-OR` on PATH |
| Solver finishes, then HTTP 500, no CSVs | **pandas 3 removed `DataFrame.applymap`** | replace `df.applymap(` with `df.map(` (same semantics, pandas ≥ 2.1) |
| App shows "Error!" and no models when served on a non-default port | `Base.apiUrl()` hardcodes `127.0.0.1:5002` | use `window.location.origin + "/"` |
| MUIO 5.6 cannot open any model | `WebAPP/DataStorage/Duals.json` and `Indicators.json` missing | they must exist; `Indicators.json` may be `{}` |
| GLPK option produces only `ObjectiveValue.csv` | MUIO's GLPK parser expects `Var(...)`, GLPK writes `Var[...]` | use `SolutionConvertersClass.fromGlpkReport()` |
| mosox run writes 2 extra all-zero CSVs | mosox keeps empty matrix columns that `glpsol --wlp` drops | harmless; ignore or filter |

## Two things to know about the results themselves

1. **Alternative optima are normal.** The LP optimum value is unique, the solution vector
   often is not. On our model `NewCapacity(RE1,LNDBRLI,2026)` has a zero cost coefficient and
   can take **any value between 0 and 998 967** at the same optimal cost — so CBC parks such
   capacities at the 999 999 default while HiGHS returns 0. Both are optimal. If you need
   reproducible capacity numbers, give those technologies a real limit or a small cost.
2. **The LP export drops the objective constant.** `ResidualCapacity × FixedCost` is data ×
   data, so it is a constant that `glpsol --wlp` (and MPS, and mosox) leave out. Every
   LP-based run — **CBC included, always** — therefore reports a total cost short by that
   amount (18 177.84 on one of our models, 0 on another). It never changes the decisions, but
   it shifts reported totals between scenarios with different residual capacity or fixed costs.

## Licenses

HiGHS — MIT (ERGO-Code). mosox — MIT (Climate Compatible Growth,
https://github.com/carderne/mosox). GLPK — GPL, CBC — EPL: both ship with MUIO already and
are unchanged by this kit. The kit's own code is free to use and adapt.
