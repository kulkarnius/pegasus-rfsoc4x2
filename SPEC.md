# RFSoC 4x2 RF front-end: project spec

Status: draft, 2026-10-27; lab answers folded in 2026-10-28. Values marked **TBD** need an answer from the lab; **verify** means checked
against a secondary source only.

This file is the normative spec. The reasoning behind each decision is in [NOTES.md](NOTES.md); the
file map and commands are in [README.md](README.md).

## 1. Goal

Make a RealDigital RFSoC 4x2 (XCZU48DR, Gen3) a phase-locked, triggerable RF I/O box for the linac:
two arbitrary-waveform RF outputs, four RF inputs (direct-sampled or digitally downconverted), and a
control/data interface that fits the accelerator control system.

Key frequencies:

- Master oscillator: **2856 MHz**.
- BAM cavity ringdown:
  - **f0 = 4758.4 MHz** and **τ = 16.1 ns** (amplitude decay time). That gives Q ≈ 240 and a
    matched-filter width of 1/πτ = 19.8 MHz.
  - These are fitted values. The single source is `bam_constants.m` in the BAM Sims folder (below).
  - The nominal design frequency is 4760 MHz = 5/3 × 2856. The fitted f0 sits 1.6 MHz below it.
- 2856 and 4760 MHz are both integer multiples of **119 MHz** (24× and 40×). 119 MHz is therefore the
  common grid for every clock in this spec.
- **The master may sit a few hundred kHz off 2856 MHz.**
  - Every board clock, and the comb if it runs at master/36, is derived from the actual master. So
    every ratio in this spec holds exactly, and all absolute numbers scale by about 1 ± 1e-4.
  - The cavity f0 is independent of the master. Its alias therefore moves by under 1 MHz, which is
    small against the 178 MHz margin in §5.
  - Any f0/master ratio must use the measured values of both.

**Prior work.** The estimator, its CRLB, and the scope-based jitter analysis (TDS6804B at 20 GS/s)
already exist in the BAM Sims analysis folder (separate from this repo).

- Key files: `bam_constants.m`, `crlb_derivation.md`, `crlb_decaying_sinusoid.md`,
  `tds6804b_phase_limit.md`, `snr_vs_charge.m`, `estimate_phase_mf2.m` / `mf2_design.m` (the
  estimator), `eo_comb_readout_validation.m` (EO readout), and `FPGA tradeoffs/mixing_math.md`.
- This board replaces the scope as the digitizer.
- It must deliver records the existing analysis can consume unchanged (R5).

## 2. Requirements

Each one is written so it can be tested. Numbers marked TBD are open questions in §10.

| ID | Requirement | Acceptance test |
|----|-------------|-----------------|
| R1 | All ADC/DAC sample clocks are phase-locked to the 2856 MHz master through a prescaled reference on the CLK IN SMA. | With CLK IN derived from the master, changing the master by ±1 kHz leaves the captured 2856 alias at the same fraction of fs (no drift in its phase). Board-added phase noise, measured by digitizing the master itself, is below **TBD fs rms (1 kHz–10 MHz)**. *(2026-10-30: nothing master-derived exists and the lab has no 10 MHz, so the follow test is blocked on Q1. Wave 1 gates on the A↔B differential residual instead: §4, PLAN C5.)* *(2026-11-03, PLAN S1: the same-tile differential floor (ADC D/C, QICK readouts 0/1) is **11.7 ± 1.2 fs at 2856 MHz over a 405 ns window**, Gaussian and amplitude-independent. Provisional until S2 (relock) is done. S3: it is a per-shot offset, flat from 116 ns to 14.8 µs; short windows also need the ADC interleave spur removed and ≳ 100 ns clear of the readout restart, PLAN S3.)* |
| R2 | Each of the 2 DACs can play (a) a CW sine at any frequency with set amplitude and phase, (b) an uploaded sample buffer at full rate, and (c) an uploaded baseband I/Q envelope upconverted by the NCO, which gives arbitrary AM/PM. | A spectrum or scope check of each mode at 2856 and 4760 MHz. |
| R3 | Each of the 4 ADCs can capture (a) raw samples at full rate (direct RF sampling) or (b) I/Q after the on-chip DDC, with NCO frequency and decimation set independently per channel. | A 4758 MHz ringdown (τ ≈ 16 ns) is captured raw and as I/Q, and the measured amplitude/phase matches a known injection. |
| R4 | Capture and/or playback starts on an external TTL edge, with a programmable delay after the trigger and a programmable record length. | Trigger-to-output latency is fixed across 10⁴ triggers and across power cycles. Its jitter is ≤ **TBD**. |
| R5 | The host can upload waveforms. It reads **scope-like records**: per trigger, a time array `t`, the reference ("clock") array, and the signal array(s), plus a trigger counter (format in §7). Setpoints and readbacks are exposed through the control system (**EPICS PVs** or **Rogue**, decided in §8). | A record per trigger at the machine rep rate (**TBD Hz**) with none dropped over 1 h. The existing BAM analysis runs on the records unchanged. |

### Channel plan (ADCs)

| ADC | Tile | Input | Band | Purpose |
|---|---|---|---|---|
| A | 226 | **Master, 2856 MHz** | zone 2 → 1190 MHz alias | Phase reference for the direct-RF arm. |
| B | 226 | **Direct cavity signal**, tapped off the MZM drive line by a directional coupler | zone 3 → 712 MHz alias | Coarse arrival time, which keeps the EO reading inside its ±40 ps unambiguous range. Amplitude for charge normalization. |
| C | 224 | **Photodiode** after the MZM: one port, intensity-modulated laser pulses | zone 1, baseband | Fine arrival time from the pulse amplitude at the zero crossing. |
| D | 224 | Spare | — | Reserved for the complementary MZM port. M = (a − b)/(a + b) cancels laser RIN per pulse: ~45 → ~29 fs in `eo_comb_readout_validation.m` rows F/G. |

- **ADC B's level has to be budgeted with the MZM drive.**
  - The MZM line carries 32–38 dB of RF gain, sized for Vπ = 2.5 V. That is ≈ 0.6 V peak at the sims'
    reference charge, and more at higher charge.
  - ADC full scale is ≈ 0.35 V peak at the SMA. A 3 dB splitter would halve the MZM drive and still
    put ADC B at or above full scale.
  - Use a **−10 to −20 dB directional coupler**, plus a fixed pad or the ADC's built-in attenuator.
    Size the attenuation for the maximum charge: ≤ −1 dBFS at the largest expected pulse.
  - The MZM gain and the ADC B attenuation are set together.
  - The coupler only has to cover the ringdown, ~20 MHz around 4758 MHz, so it doesn't need to be broadband.
  - **Interim, until a coupler is found (2026-10-28):** feed ADC B through a ~20 dB pad. After the
    MZM-drive gain that puts the reference charge at ≈ 0.06 V peak (≈ −15 dBFS), with ~5× headroom
    in charge. Trim with the ADC's 0–27 dB attenuator.
- **A and B share a tile.** That way the clock jitter they share cancels when B's phase is referenced to A's (§4).
- **C is insensitive to the board clock.** It measures pulse amplitude, not phase. Clock jitter up to
  ~30 ps costs nothing (row G1).
- **The photodiode channel needs pulse shaping.** Shape the photodiode pulse to **~1–2 ns** before
  ADC C (`adcFWHM` in the sims), because a ~200 ps pulse falls between 247 ps samples.
  - The shaping low-pass also serves as the anti-alias filter.
  - The balun's AC coupling (above 10 MHz) only removes the DC baseline, so fit a baseline with the
    template.
- **With one MZM port, laser amplitude noise is normalized by the unmodulated pulses that arrive
  before the bunch** (the sims' `'prior'` reference).
- **Laser sample lock (confirmed).** The comb's own PLL locks it to frep = master/36 (≈ 79.33 MHz), so
  fs/frep = 4046/79.33 = **51 exactly**.
  - Every laser pulse lands on the same ADC sample positions, so the amplitude fit is a fixed-weight
    dot product per pulse.
  - The sub-sample offset is fixed only while both PLLs stay locked. Re-derive the weights after a
    relock of either PLL.
- **The RF path to the MZM stays analog.** A manual phase shifter sets the laser pulse on the zero
  crossing. The ringdown is only ~20 MHz wide, so true time delay is not needed. An automatic
  zero-crossing tracking loop is deferred (§11).
- **The DACs can do the delay-scan calibration without beam.**
  - Drive the MZM with a synthetic 4758 MHz ringdown and step its NCO phase digitally. A 0.01° step
    at f0 is ≈ 6 fs.
  - This needs an RF switch or combiner into the MZM drive.

## 3. Board facts

Taken from the RealDigital *RFSoC 4x2 Reference Manual* rev A6 unless marked otherwise.

- **Converters**: 4× 14-bit RF-ADC up to 5 GS/s and 2× 14-bit RF-DAC up to 9.85 GS/s. Every ADC and DAC
  has its own DDC or DUC with a 48-bit NCO.
  - **SMA-to-tile mapping (checked on schematic p. 27):**

    | SMA | Tile | Channel pins |
    |---|---|---|
    | ADC A (J19) | 226 | `I23` |
    | ADC B (J18) | 226 | `I01` |
    | ADC C (J17) | 224 | `I23` |
    | ADC D (J16) | 224 | `I01` |
    | DAC A | 230 | — |
    | DAC B | 228 | — |

    Each ADC tile has its own clock input (`ADC_224/226_REFCLK`) driven from the ADC LMX.
  - **Speed grade**: the board files give `xczu48dr-ffvg1517-2-e`. The schematic title block (a
    "Prototype" variant) says `-1`. Check the marking on the chip. The plan fits either grade: the
    DAC limit is 9.85 GS/s at -2 and 8.92 GS/s at -1.
    **2026-11-04:** the BOM (`docs/rfsoc4x2_bom.xlsx`) also lists `XCZU48DR-1FFVG1517E`, so two
    RealDigital documents say -1 against the board files' -2. The heatsink hides the marking, and
    JTAG can't settle it (the IDCODE names the device, not the speed bin). **Treat the chip as -1.**
    The ADCs (4423.68 MS/s, under 5 GS/s) are unaffected. QICK's DACs at 9830.4 MS/s are then above
    the -1 limit, so the AWG is out of spec until the marking is read (G8).
- **ADC (DS926 Table 117 / 127, ZU4xDR dual tile)**:
  - 1–5 GS/s, 14 bits.
  - Full scale 1 Vpp differential ≈ **+1 dBm**.
  - Built-in digital step attenuator, 0–27 dB in 1 dB steps. With 15 dB of attenuation the maximum
    input is +14.6 dBm.
  - Full-power bandwidth **6 GHz**.
  - Noise floor **−154 dBFS/Hz**.
  - At 4.9 GHz and −1 dBFS the noise density is −149 dBFS/Hz with an external clock and −147 dBFS/Hz
    with the internal PLL. Attributing the whole rise to jitter gives **≈ 53 fs and ≈ 73 fs rms** total
    sampling jitter in AMD's test setups. Part of the rise is distortion, so these are upper bounds.
- **DAC (DS926 Table 132, PG269 Table 63)**:
  - The maximum rate depends on the datapath mode. Mode 1 (full-Nyquist DUC) is limited to
    **7.0 GS/s**. Modes 2–4 reach the grade limit.
  - Maximum output is ≈ +6.5 dBm at low frequency, and the bandwidth is 6 GHz.
- **Analog front end**: each SMA connects to a converter through a MABA-011118 1:2 transmission-line
  balun (**10–10,000 MHz**, confirmed on its data sheet) and 100 nF DC-blocking capacitors. There are
  no filters and no amplifiers.
  - Nothing is band-limited, so every Nyquist zone folds in. Direct sampling needs an external
    band-pass filter per channel.
  - Nothing below ~10 MHz gets through. A "square wave" from a DAC is a band-limited RF waveform, not a
    logic level. For logic-level pulses, use digital outputs instead (§6).
- **Clock chain**:
  - Si5395, factory-programmed, supplies a 10 MHz clock to the LMK04828 CLKin1.
  - **CLK IN SMA → LMK04828 CLKin0**, the PLL1 reference input.
  - A 160 MHz VCXO feeds the LMK OSCin and is the PLL2 reference.
  - The LMK drives two LMX2594 synthesizers (one for the ADC tiles, one for the DAC tiles), the PL
    reference clock (122.88 MHz by default) and SYSREF (7.68 MHz by default).
  - **SYNC IN SMA → LMK**, used to align the LMX dividers across boards. This requires enabling LMK OUT1/OUT5.
  - PYNQ's `xrfclk` programs all of this at boot from TICS Pro register files.
- **Digital I/O**: the Pmod+ header (J1, 2×15) has 22 FPGA pins. They are LVCMOS18 at the FPGA, but
  each goes through an NVT2008 translator (VREFA 1.8 V, VREFB 3.3 V) and has a 1.15 kΩ pull-up to
  3.3 V on the connector side (schematic p. 5). So the connector is **3.3 V logic and idles high**.
  Keep inputs within 0–3.3 V; 5 V TTL needs a divider. PMOD1_0 (FPGA AW13, the QICK start pin) is
  **J1 pin 10** (PMODy_1, Pmod pin 1 of the "PmodB" 12-pin subset, pins 10–21). Its ground is pin 14
  (also 5, 17, 26); **pin 15 next to it is 3.3 V** (also 6, 16, 25).
- **PPS SMA (J7, schematic p. 10)**: this is the natural TTL trigger input.
  - **Input stage**: a 49.9 Ω termination to ground, then 100 Ω in series, then a 10 nF AC-coupling
    capacitor. The coupled node is biased to 1.65 V (10k/10k from 3.3 V) and clamped to 0–3.3 V by
    a BAT54S.
  - **Comparator**: an LMV7235 with its threshold at the same 1.65 V and ~0.2 V of hysteresis (100k
    feedback). Its output goes through an NVT2008 translator to fabric pin `IRIG_COMP_OUT` (AJ13).
    The node also feeds an 8-bit SPI ADC (ADS7885).
  - **Behaviour**: it trips on an edge step of ≳ 0.2 V. AC coupling (τ ≈ 50 µs) plus the hysteresis
    hold the state for any pulse width, so a TTL source into 50 Ω (≈ 2.5 V) works.
  - **Limits**: keep the average power low, because 5 V continuous into the 49.9 Ω resistor is 0.5 W.
    The LMV7235 adds tens of ns of latency, which a fixed trigger delay absorbs.
- **CLK IN SMA (J14, schematic p. 16)**:
  - The path is: 49.9 Ω to ground, then 100 nF, then the "3 dB attenuator", then **another 49.9 Ω** to
    ground, then 100 nF into LMK **CLKin0_P**. CLKin0_N is AC-grounded.
  - The attenuator footprint is fitted with a 0 Ω through link and no shunt resistors, so it does not
    attenuate.
  - Net load is **≈ 25 Ω**, so the pin sees 2/3 of the voltage a matched 50 Ω load would. Add a 3–6 dB
    pad at the source if reflections matter.
  - **SYNC IN (J13) is unterminated** (R131 not fitted), so it presents a high-impedance load.
- **Memory and I/O**: 4 GB DDR4 on the PS and 4 GB DDR4 on the PL (64-bit, 2400 MT/s ≈ 19 GB/s peak);
  1 GbE through the PS; 100G QSFP28; SYZYGY connector.
- **On-chip RAM (DS889)**: 1,080 BRAM (38.0 Mb) and 80 URAM (22.5 Mb), about 7.5 MB in total. 4,272 DSP
  slices.
- **Toolchain**: the XCZU48DR needs a Vivado **Enterprise** license. ML Standard does not list the part.
  As checked on 2026-10-27:
  - **Vivado 2024.1** is installed at `C:\Xilinx\Vivado\2024.1`. It matches PYNQ 3.1, not the
    v3.0.1 image the board now runs (§8); it's needed only for a custom overlay.
  - The license is ML Enterprise, version 2024.07, valid to 2027-10-27. It covers releases up to
    2024.1, not 2024.2 or later.
  - A test synthesis for `xczu48dr-ffvg1517-2-e` passes.
  - The RealDigital board files are extracted to `boards/` and found with
    `set_param board.repoPaths <repo>/boards` (absolute path, forward slashes; `realdigital.org:rfsoc4x2:part0:1.0`).
  - Batch-mode startup takes ≈ 11 s. `tools\vivado.cmd tools\vivado_check.tcl` reruns these checks.

## 4. Clock plan

**Recommended plan** (all on the 119 MHz grid):

| Signal | Frequency | How it is made |
|---|---|---|
| CLK IN (from the timing system) | **119 MHz** (476 MHz also works) | Prescaled 2856 MHz master, ÷24. LMK04828 CLKin max is **750 MHz**, so an external prescaler is needed. Single-ended AC-coupled input: 0.25–2.4 Vpp at the pin and a minimum slew rate of 0.15 V/ns. Through the ≈ 25 Ω board load that means roughly **0 to +15 dBm** at 119 MHz from a 50 Ω source. Use about +6 dBm. Nothing on the 119 MHz grid is distributed yet (2026-10-28). A likely alternative is **master/36 = 79.33 MHz**, the comb's reference: PLL1 then compares at 83.3 kHz (R = 952, N = 1920), and the 0.15 V/ns slew limit needs ≳ +3 dBm, so use about +8 dBm. Interim (2026-10-30): none. The lab has no 10 MHz reference, so the board runs on its onboard 10 MHz (CLKin1), free-running relative to the master. The digitized master on ADC A carries the offset. |
| LMK PLL1 | phase detector 100 kHz (R 1190, N 1600) | Locks the 160 MHz VCXO to the master. It must divide gcd(119, 160) = 1 MHz. It stays near the stock 80 kHz (R 125, N 2000 from 10 MHz) because the PLL1 loop filter is fixed and its gain goes as 1/N. |
| LMK PLL2 VCO | **2380 MHz** (20×119) | Its phase detector runs at gcd(2380, 160) = **20 MHz** (R 8, P 7, N 17). Stock is 2457.6 MHz at 6.4 MHz (R 25, P 2, N 192). |
| LMX reference (from the LMK) | 238 MHz | 2380 ÷ 10 |
| LMX VCO | **8092 MHz** (34×238, integer-N) | |
| DAC sample rate | 8092 MS/s | LMX VCO direct |
| ADC sample rate | 4046 MS/s | LMX VCO ÷ 2 |
| PL / AXI-stream clock | 252.875 MHz | ADC rate ÷ 16, DAC rate ÷ 32 |
| SYSREF | 7.4375 MHz | 2380 ÷ 320. It divides every clock above, which is what multi-tile sync and a phase that repeats on every boot both require. |

All limits were checked against the TI data sheets:

- LMK04828: PLL1 phase detector ≤ 40 MHz, PLL2 phase detector ≤ 155 MHz.
- LMX2594: reference input 5–1400 MHz, integer-mode phase detector ≤ 400 MHz, VCO 7.5–15 GHz.

So the 952 MHz rework option fits as well. The LMK PLL2 VCO must be a multiple of 119 MHz inside one
of the LMK04828 VCO bands (2370–2630 or 2920–3080 MHz). The candidates are 2380, 2499, 2618 and 2975 MHz. The PLL2 phase-detector frequency
is gcd(VCO, 160 MHz), so the candidates give 20, 1, 2 and 5 MHz respectively. 2380 MHz is the clear
choice.

**Main risk.** Beyond the PLL1 loop bandwidth (Hz to hundreds of Hz), the board's phase noise comes
from the VCXO, LMK PLL2 and the LMX, not from the master. Nobody has measured it in this
configuration.

- **PLL2 at 20 MHz is not the weak point it was assumed to be (checked 2026-10-28).** The stock 4x2
  file runs PLL2 at only 6.4 MHz.
  - Higher compare frequency and lower N put the in-band floor ≈ 5 dB *below* stock: PN1Hz −227 +
    10 log fPD + 20 log N gives −112.5 vs −107.2 dBc/Hz at the VCO.
  - With the board's PLL2 loop filter (schematic p. 16: 22 pF, 2.2 nF, 2.7 kΩ) and Kvco 17–27 MHz/V,
    `tools/clocks.py` gives a 200–310 kHz bandwidth and 78–79° phase margin. Stock gives 65–100 kHz
    and 66–73°.

- "Locked" therefore means frequency- and phase-locked with the board's own short-term jitter.
- The **R1 phase-noise measurement is the acceptance gate.** It has to pass before any phase-sensitive
  feature is built.
- (2026-10-30) For the BAM ADC readout, the number that matters is the **A↔B differential residual**,
  not the absolute board jitter. A and B share the clock and C is clock-insensitive (§2), so common
  clock noise cancels (below). That residual needs no reference to measure: one free-running generator
  split into A and B (PLAN C5). The absolute number still decides DAC-side use and the rework.
- If it fails, the fix is hardware and out of scope for v1: feed 952 MHz (master ÷ 3) straight into the
  LMX OSCin, which is a board rework. Its phase-detector arithmetic already works: 952 ÷ 4 = 238 MHz.
- **Mitigation that needs no hardware**: digitize the 2856 MHz master on one ADC channel and measure
  every phase *relative* to it. Clock drift and common clock jitter cancel.
  - At the cavity frequency they cancel too, provided the reference phase *deviation* is scaled by
    f0/f_master ≈ 1.66611, computed from the measured f0 and f_master. Use the deviation, not the
    absolute phase, to avoid the 3-fold ambiguity.
  - What doesn't cancel is noise that isn't shared between channels (ADC thermal noise, per-tile clock
    paths). It is amplified by the same factor of 1.666.
  - Put the reference and the signal **in the same tile** (e.g. ADC A = master, ADC B = pickup).
  - Clock the tiles directly from the LMX with the tile PLLs bypassed (the §4 plan already does
    this), so the tile's internal PLL adds no independent jitter.
    - DS926 Table 144 (ZU4xDR) allows a tile clock input up to **10 GHz**. With the PLL bypassed,
      only the converter's sample-rate range applies.
    - On the 4x2, the LMX feeds each ADC tile's `ADC_22x_REFCLK` through 100 nF caps only, with no
      filtering.
    - AMD's ADC noise data were taken this way (external clock forwarded from tile 226).
  - Estimate the reference phase over the **same samples** as the pulse. Aperture jitter is
    uncorrelated and broadband, so it averages down over the pulse
    (~1/√N). The low-offset clock phase noise doesn't average, but it is common to both channels, so it
    is what this subtraction removes.
  - **Jitter floor versus the scope.** This uses the per-sample (i.i.d.) jitter result from
    `tds6804b_phase_limit.md`: σφ = √(3/2)·ω0·σt·√(Δt/τ).

    | Digitizer | Δt | √(Δt/τ) | Floor |
    |---|---|---|---|
    | Scope | 50 ps | 0.056 | 0.152° at σt = 1.3 ps |
    | This board | 247 ps | 0.124 | **0.014–0.019° (≈ 8–11 fs)** at σt = 53–73 fs, the jitter implied by DS926 (§3) |

    - The board breaks even with the scope at σt ≈ 585 fs.
    - The DS926 figure comes from AMD's test clocks. This board's LMX clock adds its own jitter,
      which the R1 measurement settles.
    - The formula covers only white jitter. Low-offset clock phase noise is correlated across the
      ringdown and doesn't average down. It is the common-mode term that the two-window Δφ, or this
      reference subtraction, removes.
  - Additive noise sets a phase error ∝ 1/amplitude. Run the pickup channel near full scale, but
    **calibrate phase versus input level** (AM-to-PM conversion in the balun/ADC near full scale).
    Otherwise charge jitter shows up as phase jitter.

## 5. Frequency plan

> **Revision (2026-11-17):** [FREQ_PLAN.md](FREQ_PLAN.md). Its Stage 1 rate, 3932.16 MS/s under QICK, is deployed (v0.2.0, PLAN B); the overlay rate below is still open. Beam data show a broadband prompt band (≈ 3.7–5.3 GHz through the ZX75BP-4700's skirts) that folds onto the cavity line at QICK's 4423.68 MS/s and, in raw records, below 4.4 GHz at 4046 MS/s. It proposes 3932.16 MS/s under QICK now (a QICK runtime setting, no new firmware) and 3689 MS/s for the custom overlay.

`python tools/freqplan.py adc|dac` ranks the sample rates on the 119 MHz grid. Its score is the
worst-case spacing between the aliases of 2856, the cavity f0 and their low harmonics, and between those
aliases and DC, fs/2 and **fs/4**. The fs/4 keep-out is deliberate: interleaving spurs and DDC images
collect there.

- **ADC at 4046 MS/s** (34×119):
  - 2856 MHz falls in zone 2 and aliases to 1190 MHz.
  - The cavity (4758.4 MHz) falls in zone 3 and aliases to 712.4 MHz.
  - Worst-case margin is 178 MHz, against a 19.8 MHz matched-filter width.
  - **Image rejection of the chain's last ZX75BP-4700** (4400–5000 MHz passband), from its typical
    data:

    | Image of the 712.4 MHz alias | Rejection |
    |---|---|
    | 3334 MHz (zone 2) | ≈ 33 dB |
    | 7380 MHz (zone 4) | ≈ 52 dB |
    | 8804 MHz (zone 5) | ≈ 40 dB, interpolated |

    - The filter re-enters to 28 dB at 9.2 GHz. The ADC's 6 GHz bandwidth adds more rejection up there.
    - Only the final filter counts against the LNAs' noise. Folded noise therefore adds ≪ 0.1 dB.
    - `snr_vs_charge.m` can confirm this: add 4.046e9 to its `fs_list`.
- **DAC at 8092 MS/s** (68×119):
  - 2856 MHz is in zone 1 (normal mode).
  - The cavity frequency is in zone 2, so it needs the DAC's **mix-mode** output. Its zone-1 image at
    3334 MHz must be filtered.
  - **Datapath modes (PG269 Table 63).** Mode 1 is capped at 7.0 GS/s, so this rate needs one of:
    - **Mode 3** (IMR high-pass) for NCO/DUC generation. It covers 0.30–0.45 fs in normal mode
      (2856 MHz = 0.353 fs) and 0.55–0.70 fs in mix-mode (4758 MHz = 0.588 fs). It inverts the spectrum.
    - **Mode 4** (DUC bypass) for raw AWG playback, at 32 samples per 252.875 MHz clock.
  - Both modes can run at the same time: DAC A at 2856 MHz, DAC B at 4760 MHz.
- **Spectral inversion**: at an ADC rate of 4046 MS/s, 2856 MHz is in an even Nyquist zone (2), so its
  alias is **inverted**. The phase measured at 1190 MHz is −φ. The cavity (4758 MHz) is in zone 3, which is not
  inverted. Conjugate the reference before taking any difference. Convert phase to time with the
  *true* frequency, not the alias frequency.
- **Conflict with `FPGA tradeoffs/mixing_math.md` §3.** That study chooses fs so the carrier lands at
  fs/4, which makes the digital mixer multiplier-free and exact. This spec avoids fs/4 instead.
  - **Confirmed in PG269 ("Sub-ADC and Interleaving Factors", calibration blocks).** Each Dual-tile ADC
    is 8 interleaved sub-ADCs.
    - Residual gain and time-skew mismatch puts spurs at ±fin + k·fs/8. At f_alias = fs/4, the term
      −fs/4 + 4·fs/8 = fs/4 lands *on* the signal, coherently, as a phase-dependent bias.
    - The gain calibration also ignores signal bins at k·fs/16, and fs/4 is one of them.
  - **This plan's aliases are clear.** At 4046 MS/s the nearest such spur is 92 MHz from 712.4 MHz
    and 149 MHz from 1190 MHz, against a 19.8 MHz matched-filter width.
  - **Background calibration needs an input at or above −40 dBFS.** PG269 says to freeze it when the
    input stays below that.
    - Freeze it on ADC B, whose ringdown is silent between shots.
    - Run the foreground calibration at startup with the inputs muted.
    - Measure whether background time-skew updates on ADC A step its phase. If they do, freeze it
      after warm-up.
  - The ~200× interleave rejection in `tds6804b_phase_limit.md` §5 relies on those spurs landing far
    from f0, which fails here.
  - On this board the multiplier-free benefit is moot: the NCO is a dedicated hardware block, or the
    mixing happens in software.
- **Rejected options**:
  - 5000 MS/s, used in `snr_vs_charge.m`, is not on the 119 MHz grid, so it is not commensurate with
    the master. On the grid, 4998 MS/s puts the cavity in zone 2, 240 MHz from the fs edge.
  - 3808 MS/s folds *both* tones onto fs/4.

## 6. Trigger

- **Input**: TTL goes into the PPS SMA (comparator + Schmitt). A Pmod input would need a 5 V → 1.8 V
  translator with 50 Ω termination.
- **The machine trigger (2026-10-28)** drives 50 Ω. It is synchronous with the laser comb (and so with
  the master), at a fixed delay with ~100 ps of jitter, and it arrives **before** the beam. Its level
  and rep rate are still open.
- **Timestamp resolution** is the open decision:
  - Sampling in the fabric gives 1 PL clock of granularity (**3.95 ns**).
  - Sample period is 0.25 ns (ADC) and 0.12 ns (DAC).
- **The machine trigger jitters by ~100 ps**, which is ~171° at 4758 MHz and ~103° at 2856 MHz. Trigger
  timing therefore carries no phase information. Pulse phase is always measured against the reference
  channel (§4), over the samples where the pulse envelope is located.
- **Acquisition doesn't care about trigger jitter.** Capture starts a programmable delay after the
  trigger sample and runs for a programmable length. The trigger comes before the beam, so no
  pre-trigger ring buffer is needed. Set the delay so the window opens a little before the pulse,
  which leaves room for a baseline. The beam signal in the record carries its own timing.
- **Generation start inherits trigger jitter.** Two ways to deal with it:
  - The machine trigger is synchronous with the master, so latency is deterministic and the jitter is
    the trigger's own. No extra logic is needed.
  - (An asynchronous trigger would need ISERDES oversampling (~0.5 ns), or would have to accept ±1 PL clock.)
- **Outputs**: Pmod pins as triggered gate/marker outputs, through a 1.8 V → TTL buffer.
- **Soft source (bench only):** `ACQ:Source soft` makes the host restart the program every 1/`ACQ:SoftRate` s
  (≤ 100 Hz), with no trigger input. It is not kept across an IOC restart. Shots are then unrelated to the machine; the default, `external`,
  is the production setting (PLAN wave 2 H).

## 7. Data path and memory budget

| Mode | Rate | Fits in |
|---|---|---|
| Raw, all 4 ADCs | 4 × 4.046 GS/s × 2 B = **32.4 GB/s** | Exceeds PL DDR4 peak (~19 GB/s), so it goes **on-chip** only: ~7.5 MB ≈ **230 µs** across all 4 channels, ~57 µs each. |
| Raw, 1 ADC | 8.1 GB/s | PL DDR4: 4 GB ≈ 0.5 s |
| DDC I/Q, decimation 8, 4 ch | 4 × 506 MS/s × 4 B ≈ 8.1 GB/s | PL DDR4 ≈ 0.5 s |
| Host readout | 1 GbE ≈ 100 MB/s | A 4 ch × 16 k-sample record (128 kB) takes ~1.3 ms, so 100+ Hz rep rates work. |

v1 design:

- Capture: per-channel buffers in URAM/BRAM, filled from the trigger sample + delay for a set length
  (§6), read out by AXI DMA into PS DDR, then sent over 1 GbE. That covers a 3τ ≈ 50 ns ringdown, or both pulses of the two-window Δφ (45.9 ns apart),
  with 1000× headroom.
- Playback: DAC waveform memory in URAM (~50 µs raw), plus long I/Q envelopes at a low rate through the
  DUC.
- PL DDR4 and the QSFP28 are **out of scope until a requirement needs them**.

### Record format (scope-like)

Per trigger, the board returns what the scope did, so the existing analysis consumes it unchanged:

| Field | Content |
|---|---|
| `t` | Time array, s, from the trigger sample: t[k] = (delay + k)/fs. The window opens at t = delay/fs. |
| `ref` | ADC A: the 2856 MHz master, raw samples. Its alias is spectrally inverted (§5). |
| `sig` | ADC B: direct cavity signal, raw samples. |
| `pd` | ADC C: photodiode (EO), raw samples. ADC D is added as a column when it is in use. |
| `meta` | fs, delay and length (samples), trigger counter, n0, and volts per code for each channel (from calibration). |

- **The record is the window and its metadata (decided 2026-10-28).** The host builds `t` from fs and
  delay. For now, phase is measured relative to the window start. Reference subtraction (§4) happens
  downstream in software.
- **n0 is the absolute index of the first sample.** It is counted on the RF-locked sample clock from a
  SYSREF-aligned reset. It costs one int64 per record, and it is what keeps per-shot phase
  comparable:
  - The trigger is detected on the PL clock (16 samples).
  - The comb period is 51/16 PL clocks. So depending on which comb pulse fired, the window start
    lands 0–15 samples differently relative to the beam, and every sample of shift moves the cavity
    phase by 63°.
  - Within a shot (Δφ, amplitude) this cancels. Across shots, n0 or the reference channel removes it.
- **On the wire** the board sends the metadata and int16 codes. The host expands them to `t` and volts.
- **The existing scripts read headerless CSV `[time, ch1, ch2]` and take the ringdown from column 3.**
  So `[t, ref, sig, pd]` keeps that column. Their baseline uses `t < −20 ns`, which has to become
  "the first N samples of the window" (a one-line change on the Sims side).
- **Raw samples, not DDC output, for v1.** The DDC would lose no information. But each NCO's phase
  would then have to be reset in sync or calibrated after every reconfiguration.

**Estimation stays in the existing BAM code** (MLE / least-squares fit; see the prior work in §1),
running on the host. It moves to the ARM only for live PVs, and into the FPGA only if a feedback loop
needs latency ≪ 1 ms.

## 8. Firmware and control framework

Pick one. My recommendation is **A**, with **B** chosen instead if the control system already runs
Rogue.

| | A: PYNQ (+ QICK as reference / phase 0) + EPICS IOC on the PS | B: SLAC Rogue/SURF/ruckus (`axi-soc-ultra-plus-core`) |
|---|---|---|
| Board OS | Stock PYNQ image for the 4x2 | Custom Yocto/PetaLinux image |
| RF config | `xrfdc`/`xrfclk` in Python | Rogue device tree, plus clock-chip register files |
| Control system | `pythonSoftIOC` (real EPICS base, CA + PVA) in the same process as the overlay. PyPI has no aarch64 wheels for Python 3.10, so build the wheels once (on the board or in an aarch64 container) and pin them. `caproto` (pure Python, CA only) works with `pip install` as a phase-0 fallback. **Chosen for v1: caproto (PLAN W1).** | Rogue's built-in EPICS bridge. Every register in the Rogue tree becomes a PV automatically. |
| Build host | Vivado on Windows works | Linux expected (ruckus Makefiles), so WSL2 or a Linux box |
| Existing 4x2 support | PYNQ image, and prebuilt QICK bitstreams for the 4x2 | No 4x2 target found in public repos; a port is needed |
| Fit | Fastest to a working box | Best fit if the facility is Rogue/SLAC-standard |

**Board OS for option A**: the stock PYNQ image, hardened.

- Turn off Jupyter and the default `xilinx` password.
- Give the board a static IP.
- Run the IOC as a systemd service.
- Make the root filesystem read-only (`overlayroot`) so it survives power cuts.
- Build overlays with the Vivado version that matches the PYNQ release. The `xrfdc` driver has to
  match the RF Data Converter IP version.
  - **Use the 4x2 image v3.0.1** (`rfsoc4x2_v3.0.1.zip`, decided 2026-11-02, v3.1.1 dropped). QICK
    refuses to import on PYNQ ≥ 3.1 and recommends v3.0.1 for the 4x2. QICK's own bitstreams are
    built with Vivado 2023.1 and load on it.
  - Earlier choice (2026-10-28): v3.1.1, built with Vivado 2024.1, to match the installed Vivado for
    a custom overlay. Reopen it only if a custom overlay is built (see the end of this section).
    v4.0.0 needs Vivado 2025.2, which the license doesn't cover.
- Build a custom image only if the PS configuration, kernel drivers, network boot or IT policy
  requires one.

**What QICK already does on the 4x2**: DDS + envelope generators, DDC readouts, an external start input
(PMOD1_0 in recent builds), time-tagged sequencing, and 10 MHz locking on CLK IN. Its "newstandard"
build samples at 4.42368 GS/s, where 4.76 GHz is in zone 3 (alias 336 MHz). Its MR buffer holds 8192
raw samples (1.85 µs). Its decimated readout (÷8, 552.96 MS/s) streams up to ~1.07 G I/Q samples
(1.94 s) into DDR4, which makes it the phase-0 tool for low-offset phase noise. (These are from the
QICK firmware READMEs; not yet tried on the board.)

**What it does not do**:

- The 119 MHz clock plan. Its sample rates sit on the 245.76 MHz family.
- Capture at the §5 rates.
- EPICS.

So QICK is the phase-0 measurement tool and the design reference, not the final firmware.

**Firmware in use (2026-11-02):** `fw/qick_4x2.bit`/`.hwh`, from QICK's
`s3df.slac.stanford.edu/people/meeg/qick/tprocv2/2025-12-09_4x2_tprocv2r27_standard/` (Vivado 2023.1, tProc v2 r27),
with qick_lib 0.2.442 (`fw/wheels/`). All three decimated buffers are 16384 deep.

**Decision (2026-10-30): QICK tProc v2 is the firmware for now. No custom overlay until a trigger below
fires.** Use `firmware/projects/qick_tprocv2_4x2_standard/out/qick_4x2.bit` from the QICK repo, not the
pip default, which is the tProc-v1 build with 2 readouts. The board free-runs on its onboard 10 MHz, so
the 119 MHz grid buys nothing yet. What the decision changes, pending bench confirmation:

| Area | Spec as written | Under QICK v2 |
|---|---|---|
| Channel plan (§2) | A = master, B = cavity (tile 226), C = photodiode | Master and cavity on the two **tile-224** SMAs (now labelled C/D), so they still share a tile. Photodiode on tile 226 m20. Tile 226 m22 (probably J19, "ADC A") has no readout, only the time tagger. A cable change only. |
| Samples (§7) | Raw | Decimated I/Q, fs/8 (552.96 MS/s at the build rate, 491.52 at 3932.16). The host rebuilds band-limited real samples so records stay scope-like (R5). |
| fs (§5) | 4046 MS/s | 4423.68 MS/s, tile PLL on (cavity in zone 3 at a 336 MHz alias). **3932.16 MS/s since v0.2.0** (FREQ_PLAN Stage 1, a QICK runtime setting; cavity alias 826.2 MHz). |
| Trigger (§6) | PPS SMA | PMOD1_0 (J1 pin 10), 0–3.3 V logic (§3), behind a TTL → 3.3 V divider. Each edge restarts the tProc program, so one shot = one program run (PLAN wave 2, E). `ACQ:Source soft` (§6) for the bench. |
| Board OS (§8) | PYNQ v3.1.1 | **PYNQ v3.0.1**: `import qick` raises on PYNQ ≥ 3.1, and QICK's quick-start recommends v3.0.1 for the 4x2. v3.1.1 matters only for a custom overlay built with Vivado 2024.1. |
| Record meta (§7) | n0, the absolute sample index | No n0: the tProc time counter resets every shot. A shot counter in tProc data memory instead; the reference channel is the cross-shot phase anchor. |

**Verified on the board (2026-11-03, PLAN G1, log in `fw/g1.log`):** the bitstream loads on PYNQ
v3.0.1 under qick 0.2.442. `print(soc)` shows 2 gens at 9830.4 MS/s, 3 readouts at 4423.68 MS/s
(decimated 552.96 MHz, 16384 deep), tProc v2 rev 27, and external start on PMOD1_0. `fw/soccfg.json`
is saved, and `daq.build()` compiles against it. QICK's own map, consistent with the schematic table
in §3 (QICK ADC tile 0/2 = 224/226, DAC tile 0/2 = 228/230):

| QICK channel | Tile, block | SMA |
|---|---|---|
| readout 0 | ADC 224, blk 0 | ADC D (J16) |
| readout 1 | ADC 224, blk 2 | ADC C (J17) |
| readout 2 | ADC 226, blk 0 | ADC B (J18) |
| time tagger only | ADC 226, blk 2 | ADC A (J19) |
| gen 0 | DAC 228 | DAC B |
| gen 1 | DAC 230 | DAC A |

So the BAM pair (master, cavity) goes on D and C, and the photodiode on B.

Not yet verified:
- The SMA map above with a signal on each SMA (PLAN G2). Loopback so far (2026-11-03): gen 1 drives
  DAC A, and a tone split into ADC D + C reaches readouts 0 and 1 but not 2. **D confirmed
  2026-11-06:** the beam cavity signal cabled to ADC D alone appears on readout 0 only (both at
  4758.4 MHz; readout 1 stays at the noise floor). **C and B confirmed the same day:** two BPM
  electrodes cabled to ADC C and ADC B appear on readouts 1 and 2, all three readouts at 4758.4 MHz.
- Readout 2 goes through `axis_weighted_buffer`, which has a triggered I/Q buffer. Per-shot dumps from it are untried.
- The shaped photodiode pulse fits the readout passband (check with `eo_comb_readout_validation.m`).

**Write a custom overlay if** a master-derived reference reaches CLK IN and fs/frep = 51 has to be exact
(QICK's rates are on the 245.76 MHz family), or if the I/Q passband turns out too narrow for the
photodiode.

## 9. Phases

| Phase | Work | Needs Vivado? |
|---|---|---|
| **0** | **Bring-up and measurement**, with no new bitstream. <ul><li>Flash PYNQ and run the prebuilt PYNQ/QICK bitstreams.</li><li>Run on the onboard 10 MHz. No lab or master-derived reference exists.</li><li>Measure ADC noise/SFDR at 2856 and 4760 MHz, DAC output power, and baseline phase noise.</li><li>**Clock risk test**: reprogram only the LMK, moving its VCO from the stock 2457.6 to **2380 MHz** (×0.9684), with every output divider unchanged. The stock ÷10, ÷20 and ÷320 then give exactly the §4 LMK outputs: 238, 119 and 7.4375 MHz. The stock LMX file stays usable (VCO 7864 → 7616 MHz, still ≥ 7.5 GHz; output 476 MHz). The base overlay's tile PLLs stay in range (VCO 9830 → 9520 MHz). So ADC and DAC run at 4760 MS/s instead of 4915.2. Files: `clocks/`.</li></ul> The full §4 plan changes the fs : PL clock : SYSREF ratios and bypasses the tile PLLs, so it can only be tested once the phase-1 overlay exists. | **No** |
| 1 | Minimal firmware: RFDC at the §4/§5 rates, 4 capture buffers + 2 playback memories, trigger on the PPS input, AXI-Lite registers, DMA. **Under the §8 QICK decision: the stock QICK tProc-v2 bitstream instead.** | Yes (No under QICK) |
| 2 | Control-system layer (IOC or Rogue tree), record format, host GUI. Under QICK: PLAN wave 2. | Board-side only |
| 3 | Only if required: deep capture in PL DDR4, sub-ns trigger timestamps, multi-board SYNC, QSFP streaming. | Yes |

## 10. Open questions

1. Which sub-harmonics of 2856 MHz does the timing system provide, and at what level? 119 MHz is ideal;
   476, 952 MHz and 10 MHz are all usable. Is there a 10 MHz that is *derived from* the master?
   **Answer (2026-10-28):** nothing at the moment. The comb's master/36 (79.33 MHz) may be
   obtainable, and it works on CLK IN (§4). Deferred: wave 1 runs free on the onboard 10 MHz (the lab has no 10 MHz). Raise it again only
   if a measurement needs the master's own phase.
2. What phase-noise or jitter target defines "locked" (R1)? What phase stability do the 2856 and 4760
   measurements need?
3. Where does the ADC B coupler go, and at what ratio? This blocks the phase-0 wiring.
   - The cavity gives 40 mV/pC peak at the chain input (`snr_vs_charge.m`), followed by the MZM-drive
     gain.
   - ADC full scale is ≈ +1 dBm (≈ 0.35 V peak into 50 Ω).
   - Set the coupler ratio and attenuation for the maximum charge (§2).
   - **Partly answered (2026-10-28):** the user is looking for a coupler. In the meantime ADC B uses a
     ~20 dB pad (§2).
4. What DAC output power is needed at 2856 and 4760 MHz (external amplifiers)?
5. Trigger: TTL level, impedance, rep rate, and is it synchronous with the master? What
   generation-start jitter is tolerable? **Partly answered (2026-10-28):** 50 Ω, synchronous with
   the comb at a fixed delay, ~100 ps jitter (§6). The level and rep rate are still open.
6. How long are the capture and playback windows? How many records per trigger?
7. Does the control system run **EPICS (CA or PVA)**, Rogue, or both? Who are the clients (archiver,
   PyDM/CS-Studio, MATLAB)?
8. Must the phase relative to the master repeat **across power cycles** (needs SYSREF from the master
   via SYNC IN), or is "after a calibration step" acceptable?
9. Is the board rework in §4 acceptable if phase noise falls short?
10. **ADC C readout noise.** From DS926: −154 dBFS/Hz over 2.02 GHz gives σ ≈ 6.4e-4 of full-scale
    peak per sample.
    - With the unmodulated pulse at half full scale (the sims' convention), that is ≈ 0.13% per
      sample.
    - A template fit over a 2 ns FWHM pulse (≈ 6 effective samples) brings it to **≈ 0.05% per pulse**.
      That sits between rows D (0.04%) and F (0.02%) of `eo_comb_readout_validation.m`.
    - Rerun those rows with `readNoise ≈ 5e-4` and the photodiode/TIA noise added, to see whether
      readout or RF noise is the floor.

## 11. Out of scope for v1

Continuous streaming, QSFP28, PL DDR4 capture, multi-board sync, on-board analysis beyond the DDC,
an automatic zero-crossing tracking loop for the MZM phase shifter, and a custom analog front end
(filters and attenuators are external, off-the-shelf parts).

## 12. Reference documents

The files under `docs/` are vendor documents with no redistribution grant, so git ignores them. To
get the same set, download each one into `docs/` under the name below. The originals were
downloaded on 2026-10-27:

| Local file (`docs/`) | Document | Source |
|---|---|---|
| `ds926_rfsoc_datasheet.pdf` | AMD DS926 v1.14, RFSoC data sheet | <https://docs.amd.com/r/en-US/ds926-zynq-ultrascale-plus-rfsoc> |
| `pg269_rf_data_converter.pdf` | AMD PG269 v2.6, RF Data Converter product guide | <https://docs.amd.com/r/en-US/pg269-rf-data-converter> |
| `ds889_rfsoc_overview.pdf` | AMD DS889 v1.14, RFSoC product overview | search docs.amd.com for "DS889" |
| `lmk04828_datasheet.pdf` | TI LMK04828 data sheet | <https://www.ti.com/product/LMK04828> |
| `lmx2594_datasheet.pdf` | TI LMX2594 data sheet | <https://www.ti.com/product/LMX2594> |
| `rfsoc4x2_reference_manual_A6.pdf` | RealDigital RFSoC 4x2 reference manual, rev A6 | <https://www.realdigital.org/downloads/d6a7543b5033e5dadde272a48bcb5090.pdf> |
| `rfsoc4x2_schematic.pdf`, `rfsoc4x2_xdc.zip`, `rfsoc4x2_board_files.zip`, `rfsoc4x2_bom.xlsx`, `rfsoc4x2_mechanical.pdf`, `rfsoc4x2_reference_designators.pdf`, `rfsoc4x2_gerbers.zip` | RealDigital RFSoC 4x2 schematic, XDC, Vivado board files, BOM, mechanical drawing, reference designators, gerbers | RealDigital's RFSoC 4x2 product page (downloads) |
| `maba-011118_balun.pdf` | MACOM MABA-011118 balun data sheet | search macom.com for "MABA-011118" |
| `zx75bp-4700-s_filter.pdf` | Mini-Circuits ZX75BP-4700-S+ filter data sheet | search minicircuits.com for "ZX75BP-4700-S+" |
| `zx60-83ln-s_amp.pdf` | Mini-Circuits ZX60-83LN-S+ amplifier data sheet | search minicircuits.com for "ZX60-83LN-S+" |

The board files from `rfsoc4x2_board_files.zip` are tracked, extracted, in [`boards/`](boards/)
(Apache-2.0, `boards/rfsoc4x2/1.0/LICENSE`). AMD's docs site returns HTML to plain downloads;
[papercuts.md](papercuts.md) has the API route that fetches the PDFs.

What the main documents are used for:

| Doc | What it's for | Where |
|---|---|---|
| **DS926**: Zynq UltraScale+ RFSoC data sheet, DC and AC switching characteristics | RF-ADC/DAC noise density, SNR, full scale, input bandwidth, sample-rate limits | <https://docs.amd.com/r/en-US/ds926-zynq-ultrascale-plus-rfsoc> |
| **PG269**: RF Data Converter LogiCORE IP product guide | Tile/PLL/clocking modes, DDC/DUC and NCO, multi-tile sync, calibration and interleaving behaviour, mix mode | <https://docs.amd.com/r/en-US/pg269-rf-data-converter> |
| **DS889**: Zynq UltraScale+ RFSoC product overview | Device resource table (BRAM/URAM/DSP for the ZU48DR) | docs.amd.com, search "DS889" |
| RFSoC 4x2 reference manual (rev A6) | Board clocking, pinout, front end | <https://www.realdigital.org/downloads/d6a7543b5033e5dadde272a48bcb5090.pdf> |
| RFSoC 4x2 schematic | PPS input threshold, CLK IN termination, ADC tile mapping | RealDigital's RFSoC 4x2 product page (downloads) |
| LMK04828 / LMX2594 data sheets | CLKin limits, VCO bands, PLL phase-detector limits | <https://www.ti.com/product/LMK04828>, <https://www.ti.com/product/LMX2594> |
