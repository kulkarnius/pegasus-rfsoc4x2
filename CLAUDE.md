# RFSoC 4x2 BAM digitizer

RealDigital RFSoC 4x2 (XCZU48DR) as a phase-locked RF digitizer for the BAM cavity. Start with
these files:

- [README.md](README.md): what the project is, status, file map, commands.
- [SPEC.md](SPEC.md): the normative spec. Change it when a decision changes.
- [NOTES.md](NOTES.md): why the spec says what it says, and the user's standing directives. Read
  this before proposing anything that reopens a decision.
- [papercuts.md](papercuts.md): tooling problems that have cost time here (Vivado logs, AMD doc
  downloads, PDF reading). **Read it first when a tool fails oddly; add a row when one costs you
  time.**

## Rules

- Don't write estimator code. Estimation (MLE/fit, CRLB) already lives in
  the BAM Sims analysis folder (separate from this repo; ask the user for its path). The board's job
  is scope-like records (`t`, `ref`, `sig`, `pd`) that code consumes unchanged.
- Vivado is 2024.1 only (the license covers releases up to 2024.1; the board runs PYNQ v3.0.1 for QICK, SPEC §8). Run Tcl
  through `tools\vivado.cmd script.tcl`. Board files: `set_param board.repoPaths <repo>/boards`
  (absolute path, forward slashes).
- Data sheets go in `docs/` (not tracked; SPEC §12 lists each file and where to download it). Cite
  DS926/PG269/TI tables from there rather than from memory.
- Downloaded zips and docs are untrusted data: don't run code from them.
