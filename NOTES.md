# Design notes and decision log

Why the spec says what it says. [SPEC.md](SPEC.md) is the normative document; this file records the
questions asked along the way, the answers, and where each one landed. It is grouped by topic.

All of this was worked out on 2026-10-27, before any hardware test. Numbers marked *illustrative*
were examples in the discussion, not board measurements.

## Standing directives from the user

These came from the user and override anything that seems to suggest otherwise.

| Directive | Consequence |
|---|---|
| Estimation is done: "these calculations have been done". The estimator, CRLB and jitter analysis live in the BAM Sims analysis folder (separate from this repo). | Don't write estimator code. The board's job is to deliver records that code consumes unchanged (SPEC R5, §7). |
| Records should look like a scope's: a time array, a clock (reference) array, a signal array. | SPEC §7 record format: `t`, `ref`, `sig`, `pd`, `trig`, `scale`. |
| Estimation is an MLE / least-squares fit, which sidesteps the t0 image-correction issue. "Don't worry about it for now." | t0 / image correction is not in the spec. |
| Hold the slow zero-crossing tracking loop: "not immediately important". | Listed as out of scope (SPEC §11). |
| "Calibration we can run." | DAC delay-scan calibration stays as an option (SPEC §2). |
| The comb is locked by its own PLL to master/36. | fs/frep = 51 exactly, so fixed-weight pulse fits (SPEC §2). |
| The master is nominally 2856 MHz but may be a few hundred kHz off. | All ratios stay exact; absolute numbers scale by ~1e-4 (SPEC §1). |
| Channel plan: master, EO photodiode (one port), direct cavity signal split from the EO line. | ADC A / C / B, with D spare (SPEC §2). |
| (2026-10-28) A record is the window from trigger + delay, for a set length: the three channel arrays plus metadata to rebuild `t`. Phase is measured relative to the window start for now, and reference subtraction happens downstream in software. | SPEC §6/§7: delayed capture, no pre-trigger ring buffer. `meta` carries fs, delay, length and n0, and n0 keeps per-shot phase comparable (SPEC §7). |
| (2026-10-28) No 2856 sub-harmonic is distributed; master/36 might be scrounged. "Defer, and say if it's really needed." | Wave 1 runs on the onboard 10 MHz. 79.33 MHz is checked as a CLK IN option (SPEC §4). |
| (2026-10-30, repeated several times) **There is no 10 MHz reference in the lab**, house or otherwise. | The board runs free on its onboard 10 MHz. No bench step may assume a shared reference: the wave-1 gate is the A↔B split test (PLAN C5), and the coherence/follow test waits for master/36 (Q1). |
| (2026-10-28) ADC B uses a ~20 dB pad until a coupler is found. The trigger is 50 Ω, synchronous with the comb at a fixed delay, with ~100 ps jitter. | SPEC §2, §6, §10 Q3/Q5. |

## Application

- **What the board is for.** It replaces a TDS6804B scope (20 GS/s) as the digitizer for the BAM
  (beam arrival monitor) cavity ringdown: f0 = 4758.4 MHz, τ = 16.1 ns. The fitted values come from
  `bam_constants.m`. The nominal 4760 MHz is 5/3 × 2856.
- **Two measurement arms.**
  - *Direct RF*: the cavity signal (ADC B) is phase-referenced to the digitized master (ADC A). This
    gives coarse arrival time and charge.
  - *EO*: the cavity RF drives an MZM that modulates a comb locked to master/36. The photodiode
    (ADC C) reads pulse amplitude at the RF zero crossing, which gives fine arrival time inside a
    ±40 ps range. The direct arm keeps the EO reading inside that range.

## Framework and software

**Rogue vs PYNQ.** Rogue/SURF maps every register to a PV automatically, but it needs a custom
Yocto image, Linux build hosts, and a port to the 4x2 (none exists publicly). PYNQ already runs on
the 4x2, has the RF drivers (`xrfdc`, `xrfclk`), and QICK has prebuilt bitstreams for it.
→ Option A (PYNQ + EPICS IOC) recommended; switch to B only if the facility is Rogue-standard
(SPEC §8).

**Which EPICS server: a soft IOC.** `pythonSoftIOC` is real EPICS base (CA + PVA) and runs in the
same Python process as the overlay, so a PV write goes straight to a register. A loop over a
register-map dict gives most of Rogue's auto-PV feature.
- Catch: PyPI has no aarch64 wheels for Python 3.10 (PYNQ's Python) for `softioc`,
  `epicscorelibs`, `p4p` or `pvxslibs`. Build the wheels once (on the board or in an aarch64
  container) and pin them.
- Fallback for bring-up: `caproto`, pure Python, CA only, installs with pip. Fast enough for
  ~128 kB records at tens of Hz.

**QICK v2 instead of a custom overlay (2026-10-30, user agreed).** The overlay existed mainly for
the 119 MHz grid (fs/frep = 51 exact), raw samples, and tile-PLL bypass. Once it was clear the lab has
no 10 MHz and nothing master-derived, the board free-runs and the grid buys nothing. Tile-PLL jitter is
shared by both inputs of a tile, so it cancels in the reference subtraction. Raw samples were chosen to
avoid unsynchronized NCO phases, and QICK's readouts reset phase under tProc control. QICK v2's
block design (checked on GitHub) has 3 simultaneous DDC readouts: tile 224 m00/m02 and tile 226 m20.
That covers master, cavity and photodiode if the master and cavity move to the tile-224 SMAs. Details
and reopen triggers are in SPEC §8.

**PYNQ v3.0.1 for QICK (2026-11-02).** `import qick` raises on PYNQ ≥ 3.1, and QICK's quick-start
recommends v3.0.1 for the 4x2. v3.1.1 was picked only to match Vivado 2024.1 for our own overlay,
which the QICK decision dropped. The user dropped v3.1.1 altogether: one card, v3.0.1, for
everything, including the wave-1 base-overlay scripts. A second card can come later if needed.

**Decimated records need the fit to start after the turn-on (2026-11-02).** In a desk test,
`fit_shot.m` on a QICK-path record (decimated I/Q, band-limited to about ±220 MHz) recovers phase
to 0.2°. Its instant turn-on model biases τ and A, though, unless `Seg` starts about 6 ns after
t0. The phase is what matters, so this is a usage note for the Sims side, not a reason to leave
QICK (PLAN wave 2 status).

**No custom board image.** PYNQ already provides Linux, runtime bitstream loading, the RF drivers,
DMA buffers and pip. A custom image would mostly rebuild PYNQ. Harden the stock image instead:
Jupyter off, default password changed, static IP, IOC as a systemd service, read-only root
(`overlayroot`). Revisit only for PS configuration changes, extra kernel drivers, network boot, or
a move to Rogue (SPEC §8).

**Where the work is.** Four pieces, and the overlay is not the riskiest:
1. Clock register files for the LMK04828 and two LMX2594s, loaded by `xrfclk`. No Vivado. The
   biggest risk (next section).
2. The overlay: mostly AMD IP (RF Data Converter, DMA, Zynq PS). Custom HDL is a few hundred lines:
   trigger sync/timestamp, pre-trigger ring buffers, playback controller, register block. The hard
   part is timing closure at 252.875 MHz on wide buses.
3. Python on the board: a driver class plus the IOC.
4. Analog hardware, bought or built: the ÷24 prescaler (the user will build it), band-pass filters, couplers/attenuators, trigger cabling, DAC
   amplifiers.

**Matched filter on the host, not the FPGA.** A ringdown record is a few hundred samples; the fit
takes microseconds in numpy. Move it into fabric only if a feedback loop needs the answer in
≪ 1 ms (it would be ~64 DSP slices out of 4,272). v1 FPGA work: converter setup, trigger, ring
buffers, DMA, playback (SPEC §7).

**Raw samples, not DDC output.** The DDC loses no information, but each NCO starts at an arbitrary
phase, which would need synchronized resets or recalibration after every reconfiguration. With raw
samples the "NCO" is software with exactly known sample times (SPEC §7).

**Tooling: plain Tcl, no MCP server.** An MCP server would only wrap
`vivado -mode batch -source x.tcl`, which already works and starts in ~11 s. Keep the build as Tcl
in the repo, the block design as `write_bd_tcl` output (readable diffs), and a one-line runner. For
interactive queries use `vivado -mode tcl` in a terminal. Revisit only if a session needs dozens of
interactive queries. See [README.md](README.md) for the commands.

## Clocking

**Why the clock configuration is the biggest risk.** Not because the board is known to be bad:
because nobody knows its jitter in this configuration, and it is the one thing firmware cannot fix.
- The chain is: master ÷24 → 119 MHz → LMK PLL1 → 160 MHz VCXO → LMK PLL2 (2380 MHz) → ÷10 →
  238 MHz → LMX2594 → 8092 MHz (DAC) and ÷2 → 4046 MHz (ADC).
- PLL1 is a jitter cleaner with a narrow loop (Hz to hundreds of Hz). Above that offset the board
  substitutes the VCXO's phase noise for the master's, even though the master is probably cleaner.
- The VCXO (160 MHz) is off the 119 MHz grid, so PLL2 compares at gcd(2380, 160) = 20 MHz. That
  was first read as a weakness. **Corrected 2026-10-28:** the stock 4x2 file compares at only 6.4 MHz
  (VCO 2457.6 MHz, not the 2949.12 assumed earlier). So 20 MHz with N = 119 is ≈ 5 dB *better*
  in-band than stock. The board's fixed PLL2 loop filter keeps it stable: 200–310 kHz, 78–79° phase
  margin (`tools/clocks.py`). The open risk is the VCXO and LMX noise, which only R1 measures.
- Loop filters are fixed components; software can retune charge pumps but not move bandwidths much.
- "Locked" therefore means exact frequency and fixed average phase, with the board's own
  short-term jitter. If that fails the R1 test, the fix is hardware (952 MHz into the LMX OSCin, a
  rework) (SPEC §4).

**No prescaler yet: not blocked.** Above PLL1's bandwidth the board's phase noise is the same
whether PLL1 locks to the master or to the on-board 10 MHz. So:
- Measure the board's added phase noise now: load the clock plan, digitize the 2856 MHz master on
  one ADC, remove the small frequency offset, compute the spectrum.
- Interim reference: none. The lab has no 10 MHz (corrected 2026-10-30; an earlier draft assumed
  one). The board runs free on its onboard 10 MHz. ADC A sees the master at a small offset,
  `phasenoise.py` detrends it, and B referenced to A doesn't care.
- Before building a prescaler, ask the timing group whether 476 or 119 MHz is already distributed.
  A home-built one is ÷3 then ÷8; the divider's noise floor usually sets the limit.

**Why digitizing the master helps even though aperture jitter does not cancel.** Split the sampling
error into a shared part (synthesizer chain, low offsets, does not average over a pulse) and a
per-channel part (aperture jitter, broadband, averages as ~1/√N over the pulse).
- *Illustrative*: 50 fs aperture jitter averages to ~0.006° over 200 samples at 4.76 GHz; 100 fs of
  close-in clock jitter is ~0.17° and does not average. The shared part dominates.
- Subtracting the reference phase removes the shared part. Conditions: reference and signal in the
  same tile (A and B, tile 226), tile PLLs bypassed, reference phase estimated over the same
  samples as the pulse.
- At the cavity frequency, scale the reference phase *deviation* by f0/f_master ≈ 1.66611 using
  measured values. Scaling the absolute phase is 3-fold ambiguous.
- DAC outputs get none of this benefit: generation is where the R1 measurement still decides.

**The 100 ps trigger jitter carries no phase.** It is ~171° at 4758 MHz. The trigger only has to put
the pulse inside the capture window; both channels are sampled at the same instants, so trigger
jitter drops out of the phase difference (SPEC §6).

**Amplitude and jitter.** Timing error gives a voltage error that grows with amplitude (slew rate ×
δt), but the phase error is that divided by the amplitude, so the jitter floor is amplitude-
independent. Thermal and quantization noise give phase error ∝ 1/A. So run the pickup near full
scale, and calibrate phase versus input level, because AM-to-PM near full scale turns charge
jitter into phase jitter (SPEC §4).

**Board vs scope jitter floor.** Using the formula from `tds6804b_phase_limit.md`,
σφ = √(3/2)·ω0·σt·√(Δt/τ): the scope gives 0.152°; the board gives 0.014–0.019° (8–11 fs) at the
53–73 fs implied by DS926, an upper bound from AMD's test clocks. The board breaks even with the
scope at σt ≈ 585 fs (SPEC §4).

## Frequency plan

- Every clock sits on the 119 MHz grid (2856 = 24×119, 4760 = 40×119), so everything is
  commensurate with the master.
- `tools/freqplan.py` picked ADC 4046 MS/s (cavity → zone 3 at 712.4 MHz, master → zone 2 at
  1190 MHz, spectrally inverted) and DAC 8092 MS/s, both from one LMX VCO.
- **fs/4 is avoided on purpose, contrary to `FPGA tradeoffs/mixing_math.md`.** That study puts the
  carrier at fs/4 for a multiplier-free mixer. PG269 confirms each ADC is 8 interleaved sub-ADCs:
  mismatch spurs at ±fin + k·fs/8 land *on* an fs/4 signal, and gain calibration skips k·fs/16 bins.
  On the RFSoC the NCO is hardware (or the mix is in software), so the multiplier-free benefit is
  moot (SPEC §5).
- **No peak tracking for the direct arm.** It is a real technique for one-sample-per-bunch
  electronics, but here a full-waveform fit has ~200 samples stepping ~63° through the carrier per
  sample, and the clock and beam are both RF-locked, so the grid does not move relative to the
  carrier.
- The real cost of 247 ps sampling is noise from other zones folding in; the ZX75BP-4700 rejects
  the images by 33–52 dB, adding ≪ 0.1 dB (SPEC §5).

## EO readout

- **Keep the RF path to the MZM analog.** Routing it ADC → fabric → DAC would put the board's
  jitter, quantization and drifting pipeline latency onto the very zero crossing being measured,
  and 4.76 GHz output needs DAC mix-mode. The optical pulse already samples with essentially no
  aperture jitter.
- **A phase shifter is enough; true time delay is not needed.** The ringdown is ~20 MHz wide. Half a
  carrier period (~105 ps) of phase shift against τ = 16 ns barely moves the envelope.
- **Bit depth helps only until readout noise drops below the RF-noise floor.** The sims' row G
  (both ports, ADC readout) already equals the RF-only floor (row H) at ~29 fs. On this board the
  readout noise is set by the analog noise floor, not the 14 bits: ≈ 0.13% per sample,
  ≈ 0.05% per pulse after the fit (SPEC §10 Q10).
- **ADC B is tapped with a −10 to −20 dB directional coupler, not a 3 dB splitter.** The MZM drive is
  ~0.6 V peak; ADC full scale is ~0.35 V peak. A splitter would halve the MZM drive and still
  overload ADC B (advisor review; SPEC §2).

## Board inputs (from the schematic)

- **Trigger → PPS SMA.** 49.9 Ω terminated, AC-coupled, comparator at 1.65 V with ~0.2 V hysteresis.
  TTL into 50 Ω works for any pulse width. Pmod pins are 1.8 V at the FPGA but 3.3 V at the connector, through NVT2008 translators with 1.15 kΩ pull-ups (corrected 2026-11-03 from the schematic; SPEC §3).
- **CLK IN** is double-terminated (≈ 25 Ω). Drive about +6 dBm at 119 MHz (SPEC §3, §4).

## Advisor reviews (2026-10-27), applied to the spec

1. ADC B level budget → directional coupler and attenuation sized for maximum charge; Q3 rewritten.
2. Phase 0 can only move the LMK VCO (2457.6 → 2380 MHz; first written as 2949.12) under the stock bitstream; the full clock
   plan needs the phase-1 overlay.
3. Tile-PLL bypass confirmed (DS926 Table 144: tile clock input up to 10 GHz). The 53–73 fs figure
   is an upper bound.
4. Capture goes on-chip: 4 raw channels at 32.4 GB/s exceed PL DDR4's ~19 GB/s.

## Clock files (2026-10-28)

- Stock files: `clocks/LMK04828_245.76_stock.txt` and `clocks/LMX2594_491.52_stock.txt`, from
  Xilinx/RFSoC-PYNQ `boards/RFSoC4x2/packages/tics/tics/register_txts/`. They select CLKin1 (the
  onboard 10 MHz) in manual mode, with PLL1 at 80 kHz.
- **The stock LMK output dividers already produce the §4 plan.** At VCO 2380 MHz, ÷10, ÷20 and ÷320
  give 238 MHz (LMX ref), 119 MHz (PL refclk) and 7.4375 MHz (SYSREF). The phase-0 LMK file is
  therefore the final LMK file, apart from CLKin selection.
- PLL1 stays near the stock 80 kHz phase detector in every variant, because its loop filter (R156
  39k, C207 0.68 µF, C208 100 nF) is fixed and its gain goes as 1/N1.
- Stock 0x146 = 0x1B sets CLKin0 to MOS type. Per datasheet §9.7.4.1, that suits the board's
  single-ended, AC-coupled CLK IN with CLKin0_N AC-grounded. QICK's `external_clk` changes only 0x147.
- PYNQ image: v3.1.1 for the 4x2 (Vivado 2024.1). v4.0.0 needs 2025.2, which the license doesn't cover.
  *Superseded 2026-11-02: v3.0.1, because QICK refuses ≥ 3.1 (above).*

## Still open

See SPEC §10 for the lab questions. Unverified items on the board/tooling side:
- QICK raw zone-3 capture at these rates.
- The chip's speed grade marking (-1 or -2).
- The R1 phase-noise measurement itself.
