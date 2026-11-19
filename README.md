# RFSoC 4x2 BAM digitizer

A RealDigital RFSoC 4x2 (XCZU48DR, Gen3) set up as a phase-locked, triggerable RF I/O box for the
linac. Its first job is to replace the 20 GS/s scope that digitizes the BAM cavity ringdown
(4758.4 MHz, τ = 16.1 ns), delivering scope-like records to the existing BAM Sims analysis
(a separate folder, not in this repo).

## Getting started

- **PC side** (fake IOC, record tools, frequency/clock scripts): Python 3 with `pip install numpy caproto` (`scipy` too for `tools/phasenoise.py`).
  See [Commands](#commands).
- **Board side**: the RFSoC 4x2 PYNQ v3.0.1 image, the QICK tProc-v2 4x2 bitstream (`fw/qick_4x2.bit`)
  and the wheels in `fw/wheels/` are not in git. Their sources are in SPEC §8 and PLAN wave 2 T;
  check them with `sha256sum -c SHA256SUMS`, then deploy with `tools/bundle.py` (Commands).
- **Data sheets**: `docs/` is not in git either. SPEC §12 lists each file and where to download it.
- **Vivado** 2024.1 with an Enterprise license, only for a custom overlay (SPEC §3).

## Status (2026-11-19)

- **Running in production** as `PEG:DIAG:BAM1:` (v0.3.0, deployed 2026-11-19; v0.2.0 before): stock QICK tProc-v2
  firmware on PYNQ v3.0.1, ADC at **3932.16 MS/s** ([FREQ_PLAN.md](FREQ_PLAN.md) Stage 1), caproto
  EPICS IOC under systemd, triggered by the beamline DG645 at 2.5 Hz. An overnight run (2026-11-05, 143,692 shots) missed none.
- **Soft trigger** (`ACQ:Source soft`, in v0.3.0): verified on the bench 2026-11-19
  (20 Hz, no trigger cable, counts contiguous, `Missed` 0). After the v0.3.0 install the board re-armed on
  `external` at 2.50 Hz with `Missed` 0.
- **File playback** (`env`/`raw`): burst timing and length verified on the bench 2026-11-19 (PLAN G7,
  partial). The DDC frequency/phase sign across Nyquist zones and the fine step response are still open.
- **Open:** the custom overlay rate (4046 vs 3689 MS/s, FREQ_PLAN Q5), locking to the linac master
  (the lab has no 10 MHz; the board free-runs), S2 relock repeats, the ADC D/C floor's source.
  History and bench results are in [PLAN.md](PLAN.md); the hand-off to `pegasus_epics_upgrade` in
  [PEGASUS_HANDOFF.md](PEGASUS_HANDOFF.md).
- **Toolchain:** Vivado 2024.1 only (the license covers releases up to 2024.1; don't upgrade). Needed
  only for a custom overlay.

## Files

| Path | What it is |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Instructions for Claude Code sessions in this repo: which files to read first, and project rules. |
| [SPEC.md](SPEC.md) | The spec: requirements, channel plan, board facts, clock and frequency plan, trigger, record format, framework, phases, open questions. **Normative.** |
| [FREQ_PLAN.md](FREQ_PLAN.md) | ADC rate revision (2026-11-17) for the beam's prompt band: 3932.16 MS/s on QICK (deployed in v0.2.0), 3689 MS/s raw for a later overlay (still a proposal), why it differs from SPEC §5, the open questions answered, and the execution plan. |
| [tools/board_fs_test.py](tools/board_fs_test.py) | Runs on the board as root: QICK at another ADC rate, loopback tones into readout 0 (FREQ_PLAN E2). |
| [tools/board_soft_test.py](tools/board_soft_test.py) | Runs on the board as root, `bam-ioc` stopped: soft trigger at 20 Hz with a CW 600 MHz loopback DAC A → ADC D (prints `SOFT_OK`), then `env` vs `raw` 1 µs bursts (PLAN G7). Uses `board/daq.py` from the same checkout (or a copy next to it), not the installed one. |
| [tools/board_probe.sh](tools/board_probe.sh) | Read-only board probe over ssh (no root): what `install.sh` and `bam-ioc.service` assume. |
| [LICENSE](LICENSE), [LICENSES/](LICENSES/) | MIT for this repo; the QICK (MIT), RFSoC-PYNQ (BSD-3) and Apache-2.0 (boards/) texts for the third-party files below. |
| [NOTES.md](NOTES.md) | Decision log: the questions behind the spec, the reasoning, and the user's standing directives. Read this to know *why*. |
| [PLAN.md](PLAN.md) | Wave 1 (phase-noise bring-up) and wave 2 (QICK acquisition, AWG, EPICS) work plans: tasks, bench checks, exit criteria, open decisions. |
| [PEGASUS_HANDOFF.md](PEGASUS_HANDOFF.md) | Handoff to `pegasus_epics_upgrade`: the contract, PV semantics, host facts and tasks P1–P6. |
| [papercuts.md](papercuts.md) | Tooling problems that cost time (Vivado logs, AMD downloads, PDF reading). **Check it first when a tool fails oddly.** |
| [tools/freqplan.py](tools/freqplan.py) | Ranks ADC/DAC sample rates on the 119 MHz grid by alias spacing. |
| [tools/clocks.py](tools/clocks.py) | Decodes and checks LMK04828/LMX2594 register files, and derives the 2380 MHz LMK variants. |
| [tools/phasenoise.py](tools/phasenoise.py) | Phase noise and integrated jitter of a captured tone (raw or I/Q), with an AM floor. |
| [tools/board_capture.py](tools/board_capture.py) | Runs on the board: DAC tone → ADC I/Q captures (`.npz`), optionally after loading a clock variant. |
| [tools/board_relock.py](tools/board_relock.py) | Runs on the board: re-locks the LMX or tile PLLs repeatedly and scores the loopback's close-in noise. |
| [board/daq.py](board/daq.py) | Runs on the board: the one-shot QICK tProc-v2 program per trigger, arm, and ring-buffer readout; `FakeDaq` for the PC. |
| [board/ioc.py](board/ioc.py) | The caproto EPICS IOC over `daq.py` (PV list in PLAN wave 2 §H, identity PVs in wave 3 B5). `--fake` runs it on the PC; `--state` keeps setpoints across restarts; `--adc-fs` (default `$BAM_ADC_FS`) sets the ADC rate (FREQ_PLAN.md); `--list-pvs` / `--check`. |
| [board/pvs.json](board/pvs.json) | The served PVs (name, type, access, count), generated by `ioc.py --list-pvs`. The contract file the pegasus registry copies. |
| [board/bam-ioc.service](board/bam-ioc.service) | systemd unit: runs `/opt/bam/current` with the site values from `/etc/bam-ioc.env`, after time sync. |
| [board/install.sh](board/install.sh) | Runs on the board from an unpacked bundle: installs to `/opt/bam/<version>`, repoints `current`, sets up NTP and the unit. `--rollback`. |
| [board/bam-ioc.env.example](board/bam-ioc.env.example), [board/timesyncd-pegasus.conf](board/timesyncd-pegasus.conf) | The site file template (prefix, ADC rate, IP, EPICS server variables) and the NTP drop-in (10.0.0.1). |
| [tools/bundle.py](tools/bundle.py) | PC: builds the versioned `peg-bam-ioc` bundle (git version, `SHA256SUMS` check, `MANIFEST.sha256`, zip) into `artifacts/`. |
| [SHA256SUMS](SHA256SUMS) | Hashes of the untracked binaries in `fw/` (PYNQ image, `.bit`, wheels). Their sources are in SPEC §8 and PLAN wave 2 T. |
| `fw/` | Board-side files. Not in git: the QICK bitstream `qick_4x2.bit`, the PYNQ image and `wheels/` (qick, caproto, tqdm for the offline board), pinned in `SHA256SUMS`. In git: `qick_4x2.hwh`/`.ltx`, `soccfg.json` (4423.68 MS/s build rate) and `soccfg_3932.json` (3932.16, deployed), and the G1 log. |
| [tools/record.py](tools/record.py) | Host: a `REC` record → `[t, ref, sig, pd]` real samples / CSV; `grab N dir` saves records from the IOC. |
| [clocks/](clocks/) | Stock 4x2 clock register files (RFSoC-PYNQ) and the derived wave-1 LMK variants. |
| [tools/vivado.cmd](tools/vivado.cmd) | One-line Vivado 2024.1 batch runner. |
| [tools/vivado_check.tcl](tools/vivado_check.tcl) | Toolchain smoke test: board files, version, parts, trivial synth. |
| `docs/` | Local copies of the data sheets, manuals and board files. Not tracked (vendor copyright); SPEC §12 lists each file and its download source. |
| [boards/](boards/) | RealDigital Vivado board files extracted from `rfsoc4x2_board_files.zip` (Apache-2.0, see its `LICENSE`). |

## License

This repo's own code and docs are MIT ([LICENSE](LICENSE)). The third-party files below keep their
own licenses; the texts are in [LICENSES/](LICENSES/) and `boards/`.

## Third-party files

- `boards/`: RealDigital/Xilinx Vivado board files, Apache-2.0 (notice in `boards/rfsoc4x2/1.0/LICENSE`, full text in [LICENSES/apache-2.0.txt](LICENSES/apache-2.0.txt)).
- `clocks/LMK04828_245.76_stock.txt`, `clocks/LMX2594_491.52_stock.txt`: stock RFSoC 4x2 clock
  register files from Xilinx RFSoC-PYNQ (`xrfclk`), BSD-3-Clause ([LICENSES/rfsoc-pynq.txt](LICENSES/rfsoc-pynq.txt)). The `lmk_2380_*` files are derived
  from them.
- `fw/qick_4x2.hwh`, `fw/qick_4x2.ltx`: from the prebuilt QICK tProc-v2 4x2 firmware (QICK, MIT
  License, Copyright (c) Open Quantum Hardware, [LICENSES/qick.txt](LICENSES/qick.txt)). `fw/soccfg*.json` and `fw/g1.log` were generated by
  the QICK library on this board.

## Commands

Frequency plan for the custom overlay's 119 MHz grid (SPEC §5; the top row is SPEC's design rate. The
deployed QICK rate, 3932.16 MS/s, comes from [FREQ_PLAN.md](FREQ_PLAN.md) instead):

```bash
python tools/freqplan.py adc
```

```text
 fs (MHz)   n  margin  2856:z/alias  4760:z/alias
     4046  34     178  z2/  1190     z3/   712
```

`python tools/freqplan.py dac` tops out at 8092 MS/s with a 357 MHz margin. The script runs its own
self-check first.

IOC without a board (needs `pip install numpy caproto`), then save 10 records as CSV from a second
shell. Both clients need `EPICS_CA_ADDR_LIST=127.0.0.1` and `EPICS_CA_AUTO_ADDR_LIST=NO`:

```bash
python board/ioc.py --fake --interfaces 127.0.0.1
```

```bash
python -m caproto.commandline.put BAM:RFSOC:ACQ:Arm On
```

```bash
python tools/record.py grab 10 recs/ --prefix BAM:RFSOC:
```

`grab` and `log` default to the production prefix `PEG:DIAG:BAM1:` (with `EPICS_CA_ADDR_LIST=10.0.0.27` for the
real board), so the fake IOC needs `--prefix BAM:RFSOC:`. A prefix nobody serves fails after 5 s.

On the board by hand: `sudo python3 board/ioc.py --bit <qick tProc-v2 4x2 .bit> --adc-fs 3932.16` (PLAN F1
for the file). In production `bam-ioc.service` runs it with the values in `/etc/bam-ioc.env`.

### Loopback without a trigger cable (soft trigger)

`ACQ:Source soft` makes the board fire its own shots at `ACQ:SoftRate` Hz (default 10, max 100), at a
random time against anything outside the board. The default, `external`, waits for the TTL on PMOD1_0,
so production is unchanged. `soft` is never saved in the state file: an IOC restart is always back on `external`. Cable DAC A → ADC D (≲ 600 MHz, see papercuts), then:

```bash
python -m caproto.commandline.put BAM:RFSOC:AWG1:Freq 600
python -m caproto.commandline.put BAM:RFSOC:AWG1:Mode cw
python -m caproto.commandline.put BAM:RFSOC:CH0:Freq 600
python -m caproto.commandline.put BAM:RFSOC:ACQ:Source soft
python -m caproto.commandline.put BAM:RFSOC:ACQ:Arm On
```

Readout 0 then shows the tone at ≈ −30 dBFS (AWG gain 0.5). Put `ACQ:Source external` back before
returning the board to the beam. `BAM:RFSOC:` is the fake/dev prefix; production is `PEG:DIAG:BAM1:`.
Verified on the bench 2026-11-19 (`tools/board_soft_test.py`: 20 Hz, 20 records in 0.99 s, `Missed` 0).

### Play a waveform from a file

`AWG<m>:I` and `AWG<m>:Q` take float arrays with values in ±1, up to 65536 samples at the DAC rate
(9830.4 MS/s, so ≤ 6.67 µs; `fw/soccfg_3932.json` gens). `Q` may stay empty (zeros). The burst starts
`AWG<m>:Delay` µs after time zero, every shot. `AWG<m>:Mode`:

- `env`: the arrays are the complex envelope × `AWG<m>:Gain`, on an NCO carrier at `AWG<m>:Freq` MHz.
  QICK's product path plays at **half** the amplitude of `raw`/`cw` for the same `I` × `Gain`
  (measured −5.8 dB), so `env` tops out at −6 dBFS (I = 1, Gain = 1).
- `raw`: `I` × `AWG<m>:Gain` is the DAC sample stream itself (put the carrier in yourself); full scale
  at I = ±1, Gain = 1. `Gain` defaults to 0.5 in every mode.

Write the arrays first, then the mode (`env`/`raw` refuse an empty `I`). Clients need
`EPICS_CA_MAX_ARRAY_BYTES=1000000` or more:

```bash
python -c "import numpy as np; from caproto.threading.client import Context; pv, = Context().get_pvs('BAM:RFSOC:AWG1:I'); pv.write(np.load('burst.npy').tolist(), wait=True)"
python -m caproto.commandline.put BAM:RFSOC:AWG1:Mode raw
```

`Q` must be empty or as long as `I`. To change the length, clear `Q` first (writing a lone `0` to an
array clears it), then write `I`, then `Q`. Readouts return DDC'd I/Q decimated by 8 (491.52 MS/s at
3932.16, 2.035 ns per sample), `ACQ:Length` a power of 2 up to 8192 samples. Bench 2026-11-19
(PLAN G7, partial): a 1 µs burst comes back 1 µs long to one readout sample, `env` and `raw` land on
the same sample, and the DAC → ADC path adds ≈ 0.32 µs. **Not yet verified:** the DDC frequency and
phase sign across Nyquist zones, and the fine step response.

Deploy (PLAN wave 3): on the PC, from a clean tagged tree, `python tools/bundle.py`. Copy the zip
to the board, unzip it, `cd` into the folder, and run `sudo bash board/install.sh`. The first run
creates `/etc/bam-ioc.env` and stops so you can fill in the prefix and IP.

Self-checks: `python board/daq.py`, `python board/ioc.py --check`, `python tools/bundle.py --check`.
After any PV change, regenerate the contract file with `python board/ioc.py --list-pvs > board/pvs.json`.

Vivado smoke test, from cmd or PowerShell in this folder (takes about a minute):

```bash
tools\vivado.cmd tools\vivado_check.tcl
```

Expect `BOARDS: realdigital.org:rfsoc4x2:part0:1.0`, `VERSION: 2024.1` and `SYNTH_OK`. Vivado
echoes every Tcl line as `# <line>`, so when grepping a log, anchor the marker: `^SYNTH_OK`. From
Git Bash, use `cmd //c "tools\\vivado.cmd tools\\vivado_check.tcl"`. Runs leave a `.Xil/` folder,
which is safe to delete.

Any other script: `tools\vivado.cmd script.tcl [-tclargs ...]`. For interactive queries, run
`C:\Xilinx\Vivado\2024.1\bin\vivado.bat -mode tcl` in a terminal. To use the board files in your own
script, add `set_param board.repoPaths <repo>/boards` (absolute path, forward slashes).

## Key numbers

As deployed (v0.3.0, stock QICK tProc-v2; SPEC §8). SPEC §4/§5 hold the custom-overlay design
(119 MHz reference into CLK IN, 4046/8092 MS/s), which is not built.

| | |
|---|---|
| Reference | None from the lab (no 10 MHz): the board free-runs on its onboard clocks, tile PLLs from 491.52 MHz |
| ADC / DAC sample rate | 3932.16 MS/s (`--adc-fs`, `BAM_ADC_FS`; the bitstream's own rate is 4423.68) / 9830.4 MS/s |
| Readouts | 3, DDC'd I/Q decimated by 8: 491.52 MS/s (2.035 ns), `ACQ:Length` 16–8192 samples |
| AWGs | 2, `off`/`cw`/`env`/`raw`, ≤ 65536 samples (6.67 µs) per waveform |
| SMA map | readout 0/1/2 = ADC D/C/B; gen 0/1 = DAC B/A; ADC A has no readout |
| Cavity alias | 4758.4 MHz in zone 3 at 826.2 MHz ([FREQ_PLAN.md](FREQ_PLAN.md)) |
| Trigger | TTL into PMOD1_0 (J1 pin 10) through a TTL → 3.3 V divider; or `ACQ:Source soft` |
| Control | caproto EPICS IOC, CA only (PLAN W1); production prefix `PEG:DIAG:BAM1:` |
