# ADC frequency plan, revised for the beam's prompt band (2026-11-17)

**Status: proposal.** [SPEC.md](SPEC.md) §5 stays as written until this is accepted. The scores come from
lbnl-cavity `characterization/direct/gain_split/freq_plan.py`, which needs that repo's beam data. The evidence is in that
folder's README ("Why the board scatters on beam and the scope doesn't").

**Revised the same day (review):** the first draft's QICK rate, 3686.4 MS/s, can't be set on this bitstream. The tile
PLL's reference divider is fixed at 1 in the bitstream, so QICK can only reach 491.52 × FBDIV / M with a VCO of
8.5–13.2 GHz (qick 0.2.442 `RFDC.valid_sample_rates`). 3686.4 needs a divider of 2. Stage 1 now uses **3932.16 MS/s**
(24 × 491.52 / 3), which matches or beats 3686.4 on every readout-band column. The open questions are answered
[below](#open-questions-answered-2026-11-17), followed by the [execution plan](#execution-plan).

## Recommendation

1. **Now, still on QICK: run the ADC tiles at 3932.16 MS/s instead of 4423.68.** QICK supports this with no new
   firmware: `QickSoc(bit, adc_sample_rates={0: 3932.16, 2: 3932.16})`. In the model, the edge error in the readout band
   drops from 20% to 0.2%, which removes the beam-day shot-to-shot scatter. On the board, a CW tone at 4100 MHz folds
   into today's 4758.4 readout with no rejection (below), and at 3932.16 it should land 658 MHz away from the cavity.
   Running QICK at a rate other than its build rate is untested on this board (E2). Its one new risk is the linac
   2856 MHz pickup, which lands at the decimated band edge (E2 measures how much gets through).
2. **For the custom overlay and the master lock: 3689 MS/s (31 × 119 MHz), raw samples, instead of SPEC §5's
   4046 MS/s.** One Nyquist zone (3689–5533.5 MHz) then holds the filter's whole passband and both skirts, so
   raw records are scope-like across the full band (0.5% edge error, against 3.3% at 4046) (Stage 2).
3. **Keep 4046 MS/s only if the EO arm's exact fs/frep = 51 matters more than the full band.** The cavity band
   (±200 MHz) is equally clean at both rates. The choice comes down to the full band against one ADC phase per
   laser pulse. It is the user's call (Q5 below), and Stage 1 doesn't depend on it.

## Why this differs from SPEC §5

SPEC §5 chose 4046 MS/s on two premises that the beam data from 11-06 contradict.

| | SPEC §5 premise | What the beam data show |
|---|---|---|
| The cavity signal | A ≈ 20 MHz ringdown line. Everything else reaching the ADC is noise, which the ZX75BP-4700 rejects by 33–52 dB at the alias images (3334, 7380, 8804 MHz), adding ≪ 0.1 dB. | The pulse also has a **broadband prompt component across the whole filter passband and its skirts**: 3.62–5.25 GHz above −40 dB, flat at ≈ −22 dB from 3.9 to 4.6 GHz. It is signal, not noise. Folded content adds coherently, with a phase set by the arrival time against the ADC clock, so it shows up as shot-to-shot scatter. |
| The filter | A 4400–5000 MHz passband. | Its typical loss (`docs/zx75bp-4700-s_filter.pdf`, via `pdftotext`) is 43.9 dB at 3000, 20.5 at 3680, 10.3 at 3900, 3.3 at 4060, 1.4 at 4400, 3.1 at 5155, 11.8 at 5400, 20.0 at 5650 and 30.7 dB at 6000 MHz. The beam spectrum's low side follows it to within 1–3 dB from 3.68 to 4.4 GHz, so the prompt reaches the ADC from ≈ 3.7 to ≈ 5.3 GHz. |
| How rates are scored | `tools/freqplan.py`: spacing of discrete tone aliases (2856, f0, harmonics) from each other and from DC, fs/4, fs/2. | Tone spacing can't see a band folding onto itself. `freq_plan.py` puts the measured beam waveform through a sampler model at random arrivals and scores what folds into the analysis band. |

What follows for each rate:

- **4423.68 (QICK, SPEC §8):** fs falls inside the passband (1.4 dB at 4400). The mirror of the readout band,
  3.81–4.37 GHz, passes at 1–14 dB and folds onto the cavity line. The model gives 20% at the edge, 7% in the
  full matched filter and 3% in the ringdown fit. That is the scatter the board showed on beam and the scope
  didn't. §8's custom-overlay triggers don't cover this, and Stage 1 doesn't need the overlay.
- **4046 (SPEC §5):** the readout band is clean (0.5%), so SPEC's rate is right for a ±200 MHz analysis. But
  R3(a) and R5 ask for raw, scope-like records. Zone 3 starts at 4046 MHz, where the filter is down only
  3.3 dB, so 3.7–4.05 GHz folds onto 4.05–4.4 GHz (3.3% edge error over the full band).
- **3932.16 (QICK, Stage 1):** the readout band's images are at 2.93–3.29 GHz (zone 2, ≈ 34–44 dB down) and
  6.86–7.22 GHz (zone 4, ≈ 50 dB down), both outside the prompt band. Raw, zone 3 starts at 3932 MHz, so 3.7–3.93 GHz
  folds onto the band's low edge (1.9%). That doesn't matter while records are decimated.
- **3689:** the zone edges sit at 3689 MHz (filter −20 dB) and 5533.5 MHz (≈ −16 dB, interpolated).
  The whole band is in one zone, and the residual is 0.5%.

### Measured on the board (2026-11-17, loopback, stock 4423.68 MS/s)

DAC A CW at gain 0.5 → splitter → ADC D (no filter), readout 0 at 4758.4 MHz, 10 shots of 256 samples through the
IOC (`AWG1` setpoints, since restored):

| DAC tone | Expected in the readout | Peak bin (2.16 MHz bins, Hann) | Line power (peak bins summed) |
|---|---|---|---|
| 4100 MHz (mirror band) | 2 fs − 4100 − 4758.4 = −11.04 MHz | −10.8 MHz, 54 dB over the floor | ≈ 62 dB |
| 4770 MHz (in band, reference) | +11.6 MHz | +10.8 MHz, 51 dB over the floor | ≈ 59 dB |

The mirror-band tone arrives ≈ 3 dB *stronger* than the in-band one at the same DAC setting (the DAC's own roll-off is
≈ 1 dB of that). So the board's front end gives no mirror rejection at all; only the external filter does. That is
what the model assumes.

### Measured at 3932.16 MS/s (E2, 2026-11-17, same loopback)

`tools/board_fs_test.py 3932.16 4770 4100 2856`, run by the user with the IOC stopped. QICK accepted the rate. Both ADC
tile PLLs and both DAC tiles locked, and all three readouts report fs 3932.16, f_output 491.52. The valid-rate list
matches the desk calculation, and the soccfg is saved as `fw/soccfg_3932.json` (DAC and tProc clocks unchanged).
Peak bins over 10 shots, 1.92 MHz bins, floor ≈ 6.4 dB:

| DAC tone | Strongest lines (offset from the 4758.4 NCO) | Against the 4770 peak | Verdict |
|---|---|---|---|
| 4770 MHz (reference) | +11.52 MHz, 56.9 dB (50.5 over the floor; stock 51) | — | Same level as stock |
| 4100 MHz (mirror band) | −11.52 MHz, 13.9 dB; +157.44 MHz, 17.0 dB | **−43 dB** (stock: +3 dB) | **Fold gone: ≥ 46 dB less.** −43 dB also bounds DAC A's image of the tone, which lands on the same bin. |
| 2856 MHz (pickup stand-in) | +63.36 MHz, 46.1 dB; the −241.6 MHz line isn't among the top four (< 18.9 dB) | −241.6 line: **≤ −38 dB** | Decimation filter rejects it: the linac pickup comes out ≤ 0.4 codes, ≈ 0.1% of the beam peak |

- The +63.36 MHz line in the 2856 run is where the pickup's interleave spur was predicted (63.7 MHz). DAC A's image of
  the tone (9830.4 − 2856 = 6974.4 MHz) lands on the same frequency, because the DAC rate is 2.5 × the ADC rate. So this
  test can't separate the two. On beam the pickup isn't a DAC tone, and its interleave spur was −38 dBc on 11-16
  (≈ 0.5 code at 39 codes).
- The +157.44 MHz line in the 4100 run sits at fs/4 (983.04 MHz in ADC terms, 156.8 MHz from the cavity alias). It is
  probably the ADC's offset interleaving spur, which doesn't depend on the input. The E4 dark scan checks that. It is
  outside the 19.8 MHz fit kernel.

## Candidate rates

Two tables: what QICK can reach now (Stage 1), and the 119 MHz grid for the custom overlay (Stage 2).

On the Run 4 beam waveform (scope, ≈ 490 shots aligned and averaged), with the machine lines notched (they are CW
and handled separately), over 48 random arrivals. Error is the complex difference between the sampled band and the
same band of the continuous signal, as whole-record energy (dB) and rms within ±3 ns of the peak (% of peak). This is
stricter than the beam pipeline's 12% / 8% edge figure, which measures |IQ| only. DDC band: ±fs/20 around 4758.4 MHz.
Raw band: 3.55–5.40 GHz cut to the zone with a 2% guard. HD: MHz from the cavity alias to its HD2/HD3 aliases.
Spur: to its nearest interleave spur (±alias + k·fs/8). Tones: SPEC §5's machine-tone margin (`tools/freqplan.py`).

**QICK-reachable** (f_ref 491.52, R = 1, FBDIV 13–160, VCO 8.5–13.2 GHz, M ∈ {2, 3, 4, 6, …}; fabric clock
fs/16 inside the MMCM's 188–376 MHz; QICK also refuses to *raise* fs above the build rate, which rules out 4669.44).
Rates 3072 and 3113 put the cavity in zone 4 and score 16–22%; 3195 scores 32%.

| fs (MS/s) | PLL | zone, alias (MHz) | HD / spur / tones (MHz) | DDC: dB / edge % | raw band (GHz) | raw: dB / edge % |
|---|---|---|---|---|---|---|
| **3932.16** | 24 / 3, VCO 11796 | 3, 826.2 | **627 / 178 / 93** | **−41.5 / 0.2** | 4.01–5.40 | −30.6 / 1.9 |
| 3604.48 | 22 / 3, VCO 10813 | 3, 1153.9 | 143 / 55 / 62 | −34.0 / 0.3 | 3.68–5.33 | −35.7 / 0.3 |
| 3768.32 | 23 / 3, VCO 11305 | 3, 990.1 | 192 / 96 / 30 | −29.6 / 0.5 | 3.84–5.40 | −35.0 / 0.6 |
| 3440.64 | 21 / 3, VCO 10322 | 3, 1317.8 | 513 / 55 / 34 | −37.8 / 0.3 | 3.55–5.09 | −35.5 / 0.4 |
| 4096.00 | 25 / 3, VCO 12288 | 3, 662.4 | 662 / 211 / 85 | −31.3 / 0.7 | 4.18–5.40 | −23.8 / 4.8 |
| 4259.84 | 26 / 3, VCO 12780 | 3, 498.6 | 499 / 68 / 48 | −26.3 / 4.1 | 4.35–5.40 | −17.0 / 12.9 |
| 4423.68 (QICK now) | 18 / 2, VCO 8847 | 3, 334.7 | 335 / 117 / 55 | −14.1 / 20.3 | 4.51–5.40 | −13.7 / 21.0 |
| 3686.4 (first draft) | needs R = 2: **not reachable** | 3, 1072.0 | 470 / 160 / 91 | −40.3 / 0.2 | 3.76–5.40 | −35.4 / 0.5 |

- **Why 3932.16 over 3604.48:** Stage 1 records are decimated, so the DDC columns decide. The model has no
  interleave images, and the board's measured interleave spur is −38 dBc on ADC D/C (11-16), well above the model's
  0.2–0.3% fold floor. So the spur distance (178 against 55 MHz) separates them, and the fold error doesn't. 3932.16's
  HD2/HD3 aliases (627 MHz away) also fall outside its ±197 MHz readout band; 3604.48's (143 MHz) fall inside.
- **3932.16's risk: the linac 2856 MHz pickup.** It aliases 249.9 MHz above the cavity alias. That is only 4 MHz past
  the decimated Nyquist (245.76 MHz), so it folds to −241.6 MHz in the readout, in the decimation filter's transition
  band, with little attenuation. The pickup lasts until 3.7–3.9 µs after the trigger, so it overlaps the beam window
  (peak at 3.42 µs). On 11-05 it was 39 codes rms on readout 0 (PLAN), against a beam peak of ≈ 424 codes (Run 4
  median |IQ|, `recs/Run4`). Unattenuated, that is ≈ 9% of the peak in the edge samples. The matched filters reject
  a line 240 MHz away by ≈ 25 dB, so they are less exposed. Today it sits 1233 MHz away, deep in the stopband.
  - **E2 measures the attenuation without beam:** a 2856 MHz DAC tone into the 4758.4 readout. It has to come out
    ≥ 25 dB below the in-band reference to keep the pickup under ≈ 0.5% of the beam peak. **Result: ≥ 38 dB below
    (≈ 0.1%), passed.** E5's beam-on dark scan confirms it with the real pickup.
  - If it doesn't: stop the pickup where it enters (downstream of the splitter input, PLAN 11-05), or fall back to
    3604.48. There 2856 lands 405 MHz away (0.9 × fs_dec, deep stopband), but 8568 MHz sits at the band edge (+205 MHz)
    and the cavity's interleave spur is 55 MHz away.
- **Other lines at 3932.16:** the pickup's nearest interleave spur lands 63.7 MHz from the line (+127 MHz today),
  outside the 19.8 MHz fit kernel. 8568 MHz, today's −55.4 MHz beam-on line, moves to −122.6 MHz.
- **Bench side effect, partial:** the DAC's 4758.4 MHz image (5072 MHz) stays 313.6 MHz from the tone at any ADC rate,
  but against the decimated rate it moves from 0.57 to 0.64 × fs_dec, deeper into the decimation filter's stopband.
  The DAC's 2f0 product (313.6 MHz at the DAC output) lands 21 MHz from the cavity alias today and 513 MHz away at
  3932.16. So the DAC ringdown bench (gain_split README) may get cleaner, but it is still not the beam's path.
- At 3932.16 the decimated rate is 491.52 MS/s (2.035 ns, ≈ ±197 MHz usable) and the fabric clock is 491.52 MHz.

**On the 119 MHz grid** (custom overlay, Stage 2):

| fs (MS/s) | grid | zone, alias (MHz) | HD / spur / tones (MHz) | fs/frep | DDC: dB / edge % | raw band (GHz) | raw: dB / edge % |
|---|---|---|---|---|---|---|---|
| **3689** | 31 × 119 | 3, 1069.4 | 481 / 167 / 89 | 46.5 | −31.2 / 0.4 | 3.76–5.40 | −35.5 / 0.5 |
| 4046 (SPEC) | 34 × 119 | 3, 712.4 | 712 / 92.5 / 178 | 51 | −34.1 / 0.5 | 4.13–5.40 | −26.5 / 3.3 |
| 3570 | 30 × 119 | 3, 1188.4 | **5** / 146 / 0 | 45 | −32.7 / 0.4 | 3.64–5.28 | −35.8 / 0.3 |
| 3808 | 32 × 119 | 3, 950.4 | **6** / **3** / 0 | 48 | −33.9 / 0.3 | 3.88–5.40 | −34.5 / 0.8 |
| 3451 | 29 × 119 | 3, 1307.4 | 471 / **27** / 27 | 43.5 | −41.1 / 0.2 | 3.55–5.11 | −35.6 / 0.4 |
| 4998 | 42 × 119 | 2, 239.6 | 240 / 146 / 178 | 63 | −28.7 / 1.7 | 3.55–4.90 | −30.9 / 1.3 |

- 3570 is the cleanest fold-wise, but its alias is at fs/3, so the ADC's own HD2 folds 4.8 MHz from the line.
- 3808 puts the cavity on fs/4: the interleave spurs land on it (SPEC §5).
- 3451's interleave spur is 27 MHz away. 4998 is at the converter's 5 GS/s limit, with the cavity 240 MHz from
  the zone edge.
- An integer fs/frep needs fs = k × 238 MHz (the lcm of 119 and 79.33). Of those, 3570 and 3808 fail as above,
  4284 starts zone 3 at 4284 MHz (filter ≈ −2 dB), and 3332 puts the cavity 240 MHz below the zone edge. So no
  rate gives both fs/frep integer and the full band, and Q5 is a real trade.

The model's null test (an input already inside the band) reads −67 dB in zone 3 and −53 dB in zone 2 (leakage at
the brickwall edges), so the scores above are well clear of the method's floor. The QICK rows were scored on 2026-11-17
with the same functions and seed. They reproduce the first draft's rows for 3686.4, 3689, 4046 and 4423.68 exactly.

## What 3689 gives up against 4046

| | 4046 (SPEC) | 3689 (this plan) |
|---|---|---|
| fs/frep (frep = 2856/36 = 79.33 MHz) | 51: every laser pulse on the same ADC samples (§2 "Laser sample lock") | 46.5: pulses alternate between two phases half a sample apart. The EO fit needs two weight sets, and the §7 n0 bookkeeping has a 93-sample two-pulse period. For the cavity, half a sample is exactly one fold cycle (1/(2fs)), so its residual fold is the same in both phases. |
| 238 MHz grid | yes (17 × 238) | no (31 × 119). SYSREF 7.4375 MHz still divides it (496), and the fabric clock (fs/16 = 230.5625 MHz, 31 × SYSREF). |
| ADC LMX2594 | VCO 8092 = 34 × 238, ÷2 | VCO 14756 = 62 × 238, ÷4 (integer-N, PFD 238 MHz, VCO ≤ 15 GHz). 7378 MHz direct is below the 7.5 GHz VCO floor, so ÷4 is required. |
| DAC | 8092 MS/s, on its own LMX (Q4) | Unchanged: the DAC LMX stays at 8092. |
| Interleave spurs ±f0 + k·fs/8 (PG269) | 92.5 MHz from the cavity alias | 166.8 MHz |
| HD2/HD3 aliases from the cavity alias | 712 MHz | 481 MHz |
| Tone margin (`tools/freqplan.py`) | 178 MHz | 89 MHz |

## Stage 1: QICK at 3932.16 MS/s (free-running, no new clock files)

- **Clock:** the stock LMK/LMX and QICK's 491.52 MHz tile reference. Tile PLL FBDIV 24, M 3, VCO 11796.48 MHz, inside
  the 8.5–13.2 GHz range and QICK's MMCM limits (f_out 245.76 MHz against 188–376). Both ADC tiles share one clock
  group in `fw/soccfg.json`, so both move together. The tProc and DACs are in the other group and don't change.
- **How:** `QickSoc(bit, adc_sample_rates={0: 3932.16, 2: 3932.16})` (qick 0.2.442 `configure_sample_rates`). It
  calls `DynamicPLLConfig` and re-reads the rates, so `soc['readouts'][n]['f_output']`, which `board/daq.py` already
  uses for `fs_dec` and the `REC` header, becomes 491.52. `tools/record.py` takes fs from that header.
- **Readout:** QICK sets the NCO to f mod fs itself (alias 826.2 MHz, zone 3, not inverted). The decimated rate
  becomes 491.52 MS/s (2.035 ns), with ≈ ±197 MHz usable. A 256-sample record covers 521 ns instead of 463 ns.
- **Raw, "don't decimate" inside QICK:** the MR buffer holds 8192 samples (2.1 µs at this rate). What it taps
  (before or after the mixer) and how it is triggered are untested. Raw here folds 3.7–3.93 GHz in (1.9%).
- **Things that scale with the fabric clock:** the readout-config latency (185 ns ≈ 102 clocks at 552.96 MHz, PLAN
  11-16) becomes ≈ 208 ns if it is counted in readout clocks, so keep `ACQ:Delay` ≥ 0.3 µs. Beam (3.3 µs) is unaffected.
- **Analysis side:** the lbnl-cavity scripts assume 1.808 ns samples (`DTF`); they become 2.035 ns. Better: read
  fs_dec from the `REC` header, as `record.py` does. `INFO:FsDec` reads 491.52, which pegasus archives as a slow PV.

## Stage 2: custom overlay at 3689 MS/s, locked to the master

Gated by SPEC §8's overlay triggers: a master-derived reference on CLK IN, which doesn't exist yet. Not scheduled.

| Item | Setting |
|---|---|
| CLK IN | 119 MHz = master/24 (SPEC §4). Until it exists, the onboard 10 MHz on CLKin1 (`clocks/lmk_2380_clkin1_10M.txt`, locked in PLAN C4) |
| LMK04828 | PLL2 VCO 2380 MHz, ÷10 → 238 MHz LMX reference, ÷320 → SYSREF 7.4375 MHz (unchanged from SPEC §4) |
| ADC LMX2594 | VCO 14756 MHz (N = 62), output ÷4 → **3689 MHz**, tile PLLs bypassed. The DAC LMX gets its own file (8092 MHz); `xrfclk` writes one LMX file to both devices, so this needs per-device writes. |
| Capture | Raw real samples at full rate (R3a), a PMOD-triggered BRAM window. For example 4096 samples (1.11 µs) per channel, ≈ 20 kB/s per channel at 2.5 Hz. The RFDC's coarse fs/4 mixer with ÷2 decimation keeps the same zone at half the data, with no NCO. |
| Fabric | fs/16 = 230.5625 MHz at 16 samples per clock |
| Aliases | 2856 → 833.0 MHz (inverted; 236 MHz below the cavity), 5712 → 1666.0, 8568 → 1190.0 (+120.6), 2f0 → 1550.2, 3f0 → 480.8 |
| Interleave spurs of the cavity (±f + k·fs/8) | nearest 166.8 MHz away |

Once the board is locked, the beam lands at a fixed ADC phase, provided the photoinjector laser's period is a
multiple of 12 RF buckets (Q2). The residual fold, the interleave images and HD2 are then the same every shot and go
into the template, and arrival time becomes measurable.

## Bench checks

At the Stage 1 rate (3932.16), unless marked:

1. A CW tone at 4758.4 MHz into the cavity input: HD2/HD3 (aliases 627 MHz away, outside the readout) and the
   interleave spurs at ±826.2 + k·491.52 MHz. Use a clean source, not the DAC, whose own harmonics confound HD.
2. CW at 3.85 GHz and 5.95 GHz, just outside zone 3 (3932–5898 MHz), through the filter: their folded levels give the
   real front-end rejection (filter plus balun, `docs/maba-011118_balun.pdf`).
3. Dark scan: the spur list at the new rate, beam off and beam on (the 2856 pickup and its spurs).
4. Beam, scope and board on one splitter: the spread of the first edge samples, the full-MF / tail-MF ratio, and
   the fold-phase test from lbnl-cavity `alias_model.py`. That test should then explain nothing.

## Open questions, answered 2026-11-17

1. **Was the ZX75BP-4700 before the scope/board splitter on 11-06?** **Yes (user, 2026-11-17):** the filter sits right
   on the cavity, with an isolator on the BAM signal against reflections. So everything downstream, scope and board,
   sees the filtered signal. That matches the data: the scope spectrum's low skirt tracks the filter within 1–3 dB from
   3.68 to 4.4 GHz, and the model, fed the scope arm, overestimates the board's fold by ≈ 1.5× rather than under.
   It also means the 2856 MHz line in the scope record (filter ≈ 49 dB down there) enters after the filter, as pickup.
   **Does the board see it?** Yes. The 11-05 beam-on dark scans (PLAN) show linac 2856 MHz pickup on ADC D/C with the
   inputs capped, entering downstream of the splitter input, ≈ −55 dBc against a −3 dBFS signal. At 3932.16 it folds
   to −241.6 MHz, at the decimation filter's band edge. E2 measured ≥ 38 dB of rejection there (≈ 0.1% of the beam
   peak), and E5 checks it on beam.
2. **Does the photoinjector laser run at master/36?** **Yes (user, 2026-11-17),** to within a few hundred fs of timing
   error. Under QICK the board free-runs, so this doesn't touch Stage 1. Once the board is locked (Stage 2), the fold
   phase depends on the bucket the beam lands in, as 2π·(2fs/f_master)·k: 2π·31k/12 at 3689, 2π·17k/6 at 4046. With
   laser pulses N = 36 buckets apart, 12 | 36 and 6 | 36, so every pulse sees the same main-fold phase (2fs − f) at
   either rate. The fold at the zone's upper edge and the interleave images have their own periods; check them when
   Stage 2 is designed. A few hundred fs of laser timing error is ≈ 0.01 rad of fold phase at 2fs = 7.4 GHz
   (2π × 7.4 GHz × 300 fs), on a residual fold that is already ≈ 0.5%, so it doesn't matter.
3. **Real HD2/HD3 and interleave-spur levels at 3.7–5.5 GHz?** *Measure as needed (user): bench check 1 in E4.* The
   interleave spur is measured: −38 dBc on ADC D/C and −54 dBc on B at 2856 MHz (PLAN, 11-16), far above the data
   sheet. That is why spur distance picks the Stage 1 rate. HD2/HD3 near 4.76 GHz aren't measured. At 3932.16 they
   alias 627 MHz from the line, outside the readout band, so their level doesn't matter for Stage 1. For Stage 2 raw
   records they land in-band but fixed, and go into the template.
4. **One LMX or two?** *Two (agreed).* The reference manual's clock diagram (rev A6, p. 8) shows two LMX2594s: PLL2 drives
   DAC tiles 228/230 and PLL1 drives ADC tiles 224/226, each with its own LMK output as reference. The BOM lists IC37
   and IC39. So the DAC stays at 8092 MS/s under 3689, and SPEC §4's "DAC = LMX VCO direct, ADC = ÷2" table should
   read as two LMXs programmed separately. The catch is in software: `xrfclk.set_ref_clks` loads the same LMX file
   into every device in `lmx_devices`. Stage 2 has to call `_write_LMX_regs(regs, lmx)` per device (checked on the
   board's PYNQ v3.0.1 install).
5. **Is the full band worth fs/frep = 46.5 on the EO arm?** **Deferred to E5's beam data (agreed 2026-11-17).** It
   reopens the fs/frep = 51 directive in NOTES, so it stays the user's call. The trade, for when Stage 2 opens:
   - The cost of 3689 is software only: two fixed weight sets instead of one, and a 93-sample period in the n0
     bookkeeping. Pulses still land on a fixed grid of two phases. Tone margin halves (178 → 89 MHz).
   - The gain is raw records that are clean from 3.76 to 5.40 GHz. 4046 is clean only from 4.13 GHz, and the cavity
     readout band is clean at both.
   - It matters only if the analysis uses content beyond ±200 MHz of the cavity (the prompt edge as a timing signal).
     Today's pipeline (edge samples, full MF, tail MF) uses the decimated band only.
   - A third option keeps 51: 4046 plus a sharper high-pass with ≳ 25 dB below 4.0 GHz. It removes 3.7–4.05 GHz
     instead of folding it. The raw band then stops at 4.13 GHz, but cleanly.
   - Stage 1's beam data (E5) say whether anything outside ±200 MHz is worth recording. Decide then.

## Execution plan

| # | Step | Who | Done when |
|---|---|---|---|
| E1 | **Decide:** accept 3932.16 for Stage 1. Q1 (filter position) can be answered alongside. | User | **Accepted 2026-11-17** (with Q1–Q5 answered). |
| E2 | **First board test, as wired now** (DAC A → splitter → ADC D + scope CH1). Stop the IOC, run `tools/board_fs_test.py` as root, restart the IOC (commands below). **Done 2026-11-17, passed** (results above). The IOC came back 27 s after the stop with `INFO:FsDec` 552.96, armed, 2.50 Hz, 0 missed: the bitstream reload restores the build rate. | User runs it (sudo needs the password); Claude reads the output | Tile PLLs locked; `f_output` 491.52. 4770 MHz (reference) at ≈ +11.6 MHz, its peak bin within a few dB of stock (51 dB over the floor). 4100 MHz: its −11 MHz line ≥ 40 dB below the 4770 peak (at stock it was 3 dB above). At 3932.16 the 4100 tone itself lands 658 MHz away; DAC A's image of it (5730.4 MHz) lands 972 MHz = 2 fs_dec − 11.04 away, so any decimator leakage shows at exactly −11 MHz too. 2856 MHz: the line at −241.6 MHz ≥ 25 dB below the 4770 peak, or see the 3932.16 risk above. Then the IOC is back with `INFO:FsDec` 552.96, armed, `Rate` 2.50. |
| E3 | **Make the rate a knob.** `--adc-fs` in `ioc.py`, defaulting to `$BAM_ADC_FS` (the unit's `EnvironmentFile` already exports it, so the unit is unchanged) → `Daq(bitfile, adc_fs)` → `QickSoc(..., adc_sample_rates={0: fs, 2: fs})`. `Daq` refuses a rate QICK would round. `FakeDaq.fs_dec` = fs/8. `bam-ioc.env.example` sets `BAM_ADC_FS=3932.16`. E2's soccfg is in `fw/soccfg_3932.json`. **Code done 2026-11-17:** `daq.py`, `ioc.py --check` and `bundle.py --check` pass, and `--fake` with `BAM_ADC_FS=3932.16` serves `INFO:FsDec` 491.52 with a matching `REC` header. **Deploy:** commit, tag v0.2.0, `tools/bundle.py`, `install.sh` on the board. Then add `BAM_ADC_FS=3932.16` to `/etc/bam-ioc.env` by hand (installs never overwrite it) and restart. Without that line the board stays at 4423.68. | Claude (code), user (sudo steps) | After deploy: `Version` v0.2.0, `INFO:FsDec` 491.52, armed, 2.50 Hz |
| E4 | **Bench at 3932.16** on the deployed bundle: dark scans (bench check 3, beam off); the readout-config latency and the `ACQ:Delay` floor; bench checks 1 and 2 (they need a clean 4758.4 source and 3.85/5.95 GHz tones); the DAC ringdown pad scan (`recs/dac_ringdown`), whose edge scatter may drop (the DAC's 2f0 product moves away; its 5072 MHz image only moves deeper into the stopband). | Bench | Spur list (expect the 2856-tone line at −241.6 MHz) and latency recorded in PLAN; ringdown scatter compared with 11-16 |
| E5 | **Beam day at 3932.16:** scope and board on one splitter, filter position written down (Q1); dark scan with beam on (bench check 3), which gives the 2856 pickup's real level at −241.6 MHz in the beam window; bench check 4. Pass: board edge #1/#2 scatter and sd ln(full/tail) at the scope's level (model 0.2%, plus noise), and the fold-phase test explains nothing. | Beam time | lbnl-cavity analysis shows scope-like scatter |
| E6 | **Adopt:** SPEC §5/§8 (QICK rate 3932.16, decimated 491.52, cavity alias 826.2), NOTES decision log, README key numbers. In lbnl-cavity: `DTF` from the `REC` header, and `freq_plan.py`'s `'QICK 3686'` candidate replaced with the reachable list. | Claude, after E5 | Docs agree; Sims/lbnl scripts run on 2.035 ns records |
| E7 | **Stage 2**, only when a master-derived reference reaches CLK IN (SPEC §8): decide Q5 (3689 or 4046, with E5's evidence), answer Q2, write separate ADC/DAC LMX files and per-device loading, then the custom overlay. | User decides; later | Not scheduled |

E2, from a terminal on the PC (the test takes about a minute; `bam-ioc` keeps its setpoints in `state.json`):

```bash
scp -i ~/.ssh/claude_bench tools/board_fs_test.py xilinx@10.0.0.27:fs_test/
```

```bash
ssh -t -i ~/.ssh/claude_bench xilinx@10.0.0.27 "sudo systemctl stop bam-ioc && sudo bash -c 'source /etc/profile.d/boardname.sh && source /etc/profile.d/pynq_venv.sh && source /etc/profile.d/xrt_setup.sh && python3 ~xilinx/fs_test/board_fs_test.py 3932.16 4770 4100 2856' ; sudo systemctl start bam-ioc"
```

The IOC takes ≈ 30 s to come back on CA, and it reloads the bitstream, which restores the build rate (checked 2026-11-17).
