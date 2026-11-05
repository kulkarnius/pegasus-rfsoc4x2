# Wave 1 plan

Drafted 2026-10-28. Wave 1 has one goal: **a credible phase-0 number for board-added phase noise**, the
R1 gate in SPEC §4. It also covers the desk work that needs no board. Plan wave 2 (the phase-1
overlay and the IOC) once the exit criteria below are met.

## Exit criteria

- [ ] **The gate:** the A↔B differential phase residual (C5) is measured at stock clocks and at 2380.
      It is what bounds the BAM phase, and it needs no reference. The number goes into SPEC R1 / §4.
- [ ] Board-added absolute jitter, 1 kHz–10 MHz, at stock and at 2380 (C3/C4). This one informs
      the rework and DAC-side use. It doesn't block the readout.
- [ ] A rework decision (952 MHz into the LMX) is recorded and marked **provisional**. Phase 0 tests
      only PLL2 at a 20 MHz phase detector. The tile-PLL bypass and 4046 MS/s can't be tested until
      the phase-1 overlay exists (SPEC §9).
- [x] Lab questions Q1, Q3 and Q5 are answered and folded into SPEC.
- [x] Decisions D1–D3 below are made, and SPEC §7 is amended where they change it.
- [ ] ~~The RFDC IP accepts the §4/§5 rates (B5).~~ Deferred 2026-10-30: needed only if a custom overlay is built (SPEC §8 decision).

## A. Lab questions (answered 2026-10-28, folded into SPEC §2/§4/§6/§10)

- **Q1:** nothing is distributed. master/36 (79.33 MHz) may be scrounged later, and it works on CLK IN.
  Deferred: wave 1 runs free on the onboard 10 MHz. **The lab has no 10 MHz** (2026-10-30), so no step below
  may assume a shared reference.
- **Q3:** ADC B uses a ~20 dB pad until a coupler is found. The coupler only has to cover ~20 MHz
  around 4758 MHz.
- **Q5:** 50 Ω, synchronous with the comb at a fixed delay, with ~100 ps jitter. The level and rep rate
  are still open.

## B. Desk work (no board needed)

| # | Task | Owner | Done when |
|---|---|---|---|
| B1 | `git init` and a first commit. | Claude | The repo is under version control. |
| B2 | **Superseded 2026-11-02 by v3.0.1** (QICK refuses ≥ 3.1; wave 2). Was: use the 4x2 image **v3.1.1** (Vivado 2024.1). v4.0.0 needs 2025.2, which the license doesn't cover (SPEC §8). | Claude | ✓ |
| B3 | **Done:** `clocks/` holds the stock files plus four LMK variants at VCO 2380 MHz: `lmk_2380_clkin1_10M` (onboard 10 MHz, the C4 file), `_clkin0_10M`, `_clkin0_119M` and `_clkin0_79M33`. Each differs from stock only in PLL2 R/P/N and, for CLKin0, the input select and PLL1 R/N. [tools/clocks.py](tools/clocks.py) decodes and checks any of them; all pass. The stock LMX file stays valid (VCO 7616 MHz). The stock VCO was 2457.6 MHz, not 2949.12, so the step is ×0.9684 (NOTES "Clock files"). | Claude | ✓ |
| B4 | **Done:** the base overlay gives DDC I/Q only, ≤ 32768 samples (13.3 µs), which limits it to offsets ≳ 300 kHz. QICK's 4x2 build streams decimated I/Q (÷8) into DDR4 for up to 1.94 s, which covers the full 1 kHz–10 MHz band. Its MR buffer has 8192 raw samples. Source: QICK READMEs, not yet tried on the board (SPEC §8). | Claude | ✓ |
| B5 | **RFDC IP check.** A Tcl script that configures the RFDC only: ADC at 4046 MS/s, external clock, tile PLL bypassed, 16 S/clk at 252.875 MHz; DAC at 8092 MS/s in modes 3 and 4, 32 S/clk. Then `validate_bd_design`, with no synthesis. | Claude | It validates, or the rejected parameter is written into SPEC §5. |
| B6 | **Done 2026-10-28:** [tools/phasenoise.py](tools/phasenoise.py) turns a raw or I/Q capture into L(f), integrated PM jitter, and the AM floor (PM ≫ AM means clock jitter; PM ≈ AM means additive noise). Its self-check recovers 100 fs of injected jitter to within 10%. For a band starting at 1 kHz it asks for ~6 ms of continuous capture; 100 kHz needs ~65 µs. | Claude | ✓ |
| B7 | **R5 dry run in Sims, via MATLAB, with no new estimator code.** Synthesize a 4046 MS/s record of the sims' ringdown model and run `estimate_phase_mf` on it. The cavity is undersampled in zone 3; the matched filter should be fine at exact sample times, but nobody has checked it at this rate. Also do the two Sims actions SPEC lists: add `4.046e9` to `snr_vs_charge.m` `fs_list` (§5), and rerun `eo_comb_readout_validation.m` rows D/F with `readNoise ≈ 5e-4` (§10 Q10). | User, or Claude on request (these are Sims files) | Phase is recovered at 4046 MS/s at the expected CRLB, and both SPEC TBDs are updated. |

## C. Bench (user, with the board)

| # | Step | Needs |
|---|---|---|
| C1 | Read the speed grade off the chip (-1 or -2) and record it in SPEC §3. | — |
| C2 | Flash v3.1.1 and run the stock base overlay. Check that every ADC and DAC is alive. Then install QICK (`pip install` from the repo, copied over from the PC) and load the **tProc-v2** bitstream from `firmware/projects/qick_tprocv2_4x2_standard/out/`. The `qick_4x2.bit` that pip ships is tProc v1, which has only 2 readouts (SPEC §8). Check that `print(soc)` lists 3 readouts, find which SMA reaches which readout, and run the loopback demo. Hardening waits for wave 2. | SD card, network |
| C3 | **Baseline** at stock clocks. <ul><li>**PLL2 leg:** an external generator (any you have; it runs free, and `phasenoise.py` detrends the offset) goes into ADC A through a band-pass filter. Capture ≥ 100 ms of QICK DDR4 I/Q and save it as `.npy`, then run `python tools/phasenoise.py cap.npy --fs <I/Q rate> --frf 2856e6`. The result is source + board, so record the generator's model and its phase-noise spec.</li><li>**Absolute number, if the lab has a spectrum or phase-noise analyzer:** put a DAC tone on the analyzer. Its reference is clean, so the source doesn't enter.</li><li>**A DAC tone looped into an ADC is not a PLL2 test.** Both LMXs take the same LMK reference, so PLL2 and VCXO noise cancel in the loop. It only sees LMX, tile and additive noise.</li><li>Also measure noise/SFDR at 2856 and 4760 MHz and DAC output power (SPEC §9).</li></ul> | a generator, a BPF at its frequency, QICK; analyzer if available |
| C4 | **Clock-risk test.** Load `clocks/lmk_2380_clkin1_10M.txt` (procedure below). VCO 2380 MHz is only 10 MHz above VCO0's minimum, so confirm PLL2 lock (the LMK LD LEDs, LD13/LD14) both cold and after 30 min warm. Then repeat C3 exactly with the same source. The C3 − C4 difference on the PLL2 leg is valid whatever the source contributes. Compare the L(f) curves below ~300 kHz, where PLL2 sets the noise. Measure 4760 MHz only at stock clocks: at 2380 MHz the base overlay's fs is 4760 MS/s, which puts 4760 MHz at DC. | — |
| C5 | **Split test (the gate).** Feed one generator through a 2-way splitter into ADC C and ADC D (both tile 224, the only tile where QICK v2 has two readouts), capture both at the same instants, and take phase(B) − phase(A) per ~200-sample window. Source noise and common clock noise cancel, so the generator can run free and no reference is needed. What's left (aperture, thermal, per-channel clock paths) is what the BAM phase sees. Use 4758 MHz through the ZX75BP-4700 at stock clocks; at 2380, 4758 aliases to 2 MHz, so pick another tone. Run it at stock clocks and at 2380, and across ~10 LMX writes. The base overlay's `transfer()` captures one channel at a time, so use QICK **tProc v2** (`qick_tprocv2_4x2_standard`). Its readouts are on ADC streams m00, m02 (tile 224) and m20 (tile 226). m22 (tile 226) feeds only the time tagger, and that is probably ADC A/J19 (PLAN bench notes: tile 226, block 1). Confirm the SMA ↔ stream map on the board. | a generator, a 2-way splitter, ZX75BP-4700, QICK |

### Bench results (2026-10-28: base overlay, loopback cable DAC A → ADC A, no external source)

- **C2 is done, except QICK.** The board has no internet, so QICK has to be copied over from the PC.
  - The overlay loads in about 8 s.
  - All four tiles lock at stock clocks (491.52 → 4915.2 MS/s) and at 2380 (476 → 4760 MS/s).
  - The board gets its IP from DHCP. It moved from 10.0.0.146 to 10.0.0.200 after a reboot.
- **Channel map:** ADC A (J19) is `radio.receiver.channel[3]` (tile 226, block 1), and DAC A is `transmitter.channel[1]` (tile 230). Unconnected inputs read about −66 dBFS (mean |I/Q|).
- **Level:** DAC gain 0.25 reads about −21 dBFS at ADC A at 600 MHz; gain 1 reads about −11 dBFS.
- **Additive floor:** with a −21 dBFS tone, L ≈ −141 dBc/Hz from 1 to 20 MHz offset. PM equals AM there, so this is additive noise, not clock noise. Integrated over 1–20 MHz it is 0.54 mrad.
- **Stock vs 2380:** no visible difference in loopback. That shows the LMX and tile PLLs are happy at a 476 MHz reference. It says nothing about PLL2, because PLL2 noise cancels in loopback.
- **Loopback noise depends on a four-state clock phase.**
  - Every LMX write lands the DAC↔ADC sample-clock phase in one of four states. They show up as four tone levels at 600 MHz (−20.68 / −20.85 / −21.04 / −21.31 dBFS), via the DAC image at fs − f folding back onto f.
  - In two of the four states a 0.3–2 MHz hump appears, 6 dB above the floor: PM 0.95 vs AM 0.63 mrad over 1–20 MHz.
  - Over 40 rewrites, the hump correlates with level at −0.93 ([tools/board_relock.py](tools/board_relock.py)).
  - A state persists until the next LMX write. TI's recommended VCO-calibration start values (VCO_SEL 7, DACISET 300, CAPCTRL 183) give the same spread.
- **What that means:**
  - Loopback jitter numbers are state-dependent, so don't quote them.
  - C3 has to settle whether the hump is a loopback artifact or a real ADC-chain state. Repeat the external-source capture over about 10 LMX writes and check that the hump never appears.
  - A and B share tile 226, so the BAM phase doesn't see this. Coherent DAC↔ADC use (playback) would need MTS.
- **Don't loop back near fs/2 at equal DAC and ADC rates.** At 2000 MHz the image lands on the tone at nearly equal amplitude, and the level swings by 11 dB between relocks. Use ≲ 600 MHz.
- **C4 lock: passed.** The tiles and LMX lock at 2380. Both LMK lock LEDs (LD13 PLL2, LD14 PLL1) were lit with the board 2.4 h after boot and warm, so this is the warm check. A cold check (2380 loaded within minutes of power-on) is still to do.

**Loading a clock variant (C4).** Do this after the overlay or `QickSoc()` is up, because both reprogram the stock clocks when they start.

```python
import re, xrfclk          # PYNQ's clock driver; check that the 4x2 image uses xrfclk and not a 'tics' package
words = lambda f: [int(m[0], 16) for m in (re.search(r"0x[0-9A-Fa-f]+", l) for l in open(f)) if m]
for d in xrfclk.lmk_devices: xrfclk._write_LMK_regs(words("lmk_2380_clkin1_10M.txt"), d)
for d in xrfclk.lmx_devices: xrfclk._write_LMX_regs(words("LMX2594_491.52_stock.txt"), d)  # re-run the LMX VCO cal at the new 238 MHz ref
# then re-lock every RFDC tile PLL at the new reference:
# tile.DynamicPLLConfig(1, 476.0, fs_new)   fs_new = 4760 (base), 4283.9 ADC / 9519.6 DAC (QICK)
```

After the swap, every frequency is ×0.9684. QICK's own frequency arguments assume the stock fs, so a
true 2856 MHz needs `2856 / 0.9684` in QICK units. QICK's ADC tile VCO lands at 8568 MHz, which is
0.8% above its 8.5 GHz minimum. If that tile won't lock, use the base overlay for C4, which covers
offsets above ~300 kHz only.

**Parts to have on hand:** a 2-way splitter for C5 (with the ZX75BP-4700 it needs nothing else). For
C3/C4, a band-pass filter at whatever frequency the generator runs: every zone folds in (SPEC §3).
The ZX75BP-4700 works if the generator does 4758 MHz. Also: 3–6 dB SMA pads, cables, and an SD
card. The ADC B coupler waits for Q3.

## D. Decisions (made 2026-10-28)

- **D1.** A record is the window from trigger + delay, for a set length: `[t, ref, sig, pd]` plus
  metadata, with t built from fs and delay (SPEC §7). Also kept: n0, the absolute sample index,
  which costs one int64. Without it, the window start can shift by 0–15 samples relative to the beam,
  depending on which comb pulse fired, and each sample is 63° at f0 (SPEC §7).
- **D2.** Reference subtraction happens downstream in software. For now, phase is measured relative
  to the window start.
- **D3.** The phase-noise script lives here: [tools/phasenoise.py](tools/phasenoise.py).

## Not in wave 1

The coherence/follow test (a fixed tone phase over minutes, then drift on unlock). It needs a shared
reference, and the only candidate is master/36 on CLK IN (Q1). The overlay build (beyond the B5 IP check), EPICS/IOC and its aarch64 wheels, PYNQ hardening, and the
prescaler build (unless Q1 shows that nothing suitable is distributed).

---

# Wave 2 plan: v1 board software on QICK

Drafted 2026-11-02, with no board access. Goal: **triggered acquisition and a triggered AWG on the stock
QICK tProc-v2 4x2 firmware, with an EPICS interface** (SPEC R2–R5 under the §8 QICK decision). No
Vivado and no HDL. The firmware facts in E come from reading the QICK source at commit `80753a9`
(qick_lib 0.2.442, 2026-10-30). None of it has run on the board yet. Wave 1's gate (C5) still decides
whether the phase numbers are any good; wave 2 builds the box around it.

## Exit criteria

- [ ] One TTL edge gives one record per channel (master, cavity, photodiode) and plays both AWG
      outputs, each at its PV-set delay.
- [ ] A CA client on the PC (`caget`/`caput`, pyepics, MATLAB) sets every PV in H and reads the
      records. A setpoint change takes effect within one re-arm.
- [ ] No missed records for 1 h at the machine rep rate (R5), shown by a gap-free shot counter.
- [ ] `tools/record.py` turns a record into `[t, ref, sig, pd]` CSV that the Sims scripts read
      unchanged (R5).
- [ ] The IOC runs as a systemd service and comes back after a power cycle.

## E. What stock QICK v2 gives (from source; verify in G)

| Fact | Source | Consequence |
|---|---|---|
| External start is PMOD1_0 → `proc_start_i`: rising edge, 3-FF sync on the core clock, gated by `TPROC_CFG[10]`. It resets time and core, so **every edge reruns the program from the top**, even mid-program. | `qproc_ctrl.sv:102-116`, `axis_qick_processor.sv:367-390`, BD l.1867 | One shot = one program run. There is no in-program wait for a trigger (`EXT_FLAG 0`). |
| A restart clears every tProc register, including the AXI-readable counters `s_core_w1/w2`. Data memory isn't in the clear path. | `qcore_reg_bank.sv:116`, `qcore_cpu.sv:497` | The shot counter lives in dmem: `read_dmem` → +1 → `write_dmem`, then copy to `s_core_w1` for the host. |
| Decimated buffers **append** per trigger (`WAIT_TRIGGER → TRIGGER`, no address reload) and wrap at 2^N_BUF: **16384 I/Q on all three readouts** (N_BUF 14 in the 2025-12-09 build's `.hwh`, including the weighted buffer; an earlier guess here was 4096 for readout 2). | `buffer.sv:107-130`, `fw/qick_4x2.hwh` | A free ring buffer, 16384/L shots deep for record length L (64 shots at L = 256 ≈ 463 ns, 63 usable). The host reads behind the writer by counter. |
| 3 readouts (`axis_dyn_readout_v1`, configured by the tProc) at 4423.68 MS/s, decimated to 552.96 MS/s I/Q: tile 224 m00 and m02, tile 226 m20. | BD | NCO frequency and phase reset are per shot, in the program. |
| 2 generators (`axis_signal_gen_v6`) at 9830.4 MS/s: 65536 complex envelope samples (6.67 µs) at full rate, 32-bit DDS, oneshot or periodic. | BD, QICK demo printout | R2 (a) CW = periodic const pulse; (b) raw = arb envelope at f = 0; (c) envelope × DDS. 4758 MHz is in zone 1 (fs/2 = 4915 MHz); its image sits at 5072 MHz. |
| PMOD0_0..7 are tProc trigger outputs 4–11 (1.8 V). | BD l.1882-1894 | Gate/marker outputs. |

"Source" paths are under `firmware/ip/qick_processor/src/` and `firmware/ip/axis_avg_buffer/src/`;
"BD" is `firmware/projects/qick_tprocv2_4x2_standard/bd_2023-1.tcl`.

What stock QICK does **not** cover (each has a task or check below):

1. **No bitstream in the repo.** `firmware/projects/qick_tprocv2_4x2_standard/out/qick_4x2.bit` is a
   38-byte path pointer to a local build. → F1.
2. **QICK's `acquire*` assumes one start → N reps.** Restart-per-trigger means v1 has its own
   arm/poll loop. → F3.
3. **The trigger is PMOD1_0** (J1 pin 10), not the PPS SMA: 3.3 V logic at the connector, through a translator with a 3.3 V pull-up (SPEC §3). 5 V needs a divider. → F2.
4. **The 9830.4 MS/s DAC rate needs a -2 part** (SPEC §3: -1 tops out at 8.92 GS/s). → C1.
5. **R4's "fixed latency" holds only to a few fabric clocks.** The board free-runs against the trigger,
   so the window start moves by about one decimated sample (1.8 ns) and the generation start by about
   one tProc clock. There is no n0 (SPEC §7): the time counter resets on every shot. The reference
   channel is the only cross-shot phase anchor (SPEC §7 already allows this). → G6.

## F. Work

| # | Task | Who | Board? | Done when |
|---|---|---|---|---|
| F1 | Get the tProc-v2 4x2 `.bit` + `.hwh` prebuilt from QICK's `s3df.slac.stanford.edu/people/meeg/qick/fw/` (open it in your own browser; papercuts), plus `qick_lib` from the same date. Fallback: build `bd_2023-1.tcl`, which needs Vivado 2023.1 (licensed, not installed) or an unproven port to 2024.1. | User | No | Files in `fw/`, with the build date and QICK commit noted in SPEC §8. |
| F2 | Trigger front end: 50 Ω termination, then a divider to 0/3.3 V into PMOD1_0 (J1 pin 10). Size it for the machine trigger's level (Q5, still open). | User | No | A scope shows 0/1.8 V at the pin with the real trigger. |
| F3 | `board/daq.py`: `QickSoc` + a config dict → one-shot `QickProgramV2` (`add_readoutconfig`/`send_readoutconfig`, `add_envelope`/`add_pulse`/`pulse` on both gens, `trigger(ros, pins)` at the acquisition delay, dmem shot counter, `end`). `arm()` loads it with `start_src="external"`. `poll()` reads the counter, `transfer_buf`s the new ring slots, and counts gaps and overruns. Reuse the envelope pattern in `Desktop/FPGA/flat_top_pulse_qick.py`. | Claude | Write: no. Run: yes | Compiles against the G1 `soccfg` JSON; passes G3–G5. |
| F4 | `board/ioc.py`: the PVs in H → config dict → `daq.arm()` on change. Each shot's PVs post with one timestamp. `--fake` swaps in a stub daq so the IOC runs on the PC now. | Claude | No | `caget`/`caput` from the PC work against `--fake`, then against the board. |
| F5 | `tools/record.py` (host): x(t) = 2·Re{IQ(t)·e^{j2πft}} on any time grid, with f the true RF frequency. No conjugation is needed in even zones, because QICK runs the NCO at f mod fs. Writes `[t, ref, sig, pd]` CSV. Self-check: synthetic ringdown → decimate → rebuild matches in band. | Claude | No | Self-check passes; B7's MATLAB run reads the CSV. |
| F6 | The board has no internet: collect `qick` and the EPICS server's wheels on the PC, `scp` them over, pin versions. | Claude | No | `pip install --no-index` works on the board. |
| F7 | Hardening (SPEC §8): Jupyter off, password changed, static IP, `overlayroot`, a `bam-ioc.service` unit. | Claude writes, user applies | Yes | The IOC is back after a power cycle. |

**Status 2026-11-02:** F3–F5 are written: [board/daq.py](board/daq.py), [board/ioc.py](board/ioc.py),
[tools/record.py](tools/record.py). Tested on the PC with `ioc.py --fake` over CA:
- arm and disarm work;
- bad setpoints come back as `ECA_PUTFAIL` with the reason;
- re-arming applies new values;
- `record.py grab` saves consecutive records as `[t, ref, sig, pd]` CSV at 20.5 GS/s;
- `record.py`'s self-check passes, and it fails if the reconstruction is conjugated;
- `python board/daq.py` checks `poll()`'s ring arithmetic against a stub soc: per-channel wrap
  (16384 vs 4096), overruns, and the rule that a slot one ring-length behind counts as lost, so the
  usable depth is one less than the ring.

`daq.build()` compiles against a QICK testbench tProc-v2 soccfg (ZCU216) stretched to the 4x2's
shape: 2 gens, 3 readouts, 4x2 rates. That check found one bug: pulse names are global, not per
channel. The ASM came out as intended. It has not run, and the real ports are unchecked until G1;
`python board/daq.py fw/soccfg.json` compiles against the real one. QICK wraps the readout frequency
register mod 2^32, so the NCO runs at true RF mod fs, as `record.py` assumes.

F6 is done: `fw/wheels/` holds `qick-0.2.442`, `caproto-1.3.0` and `tqdm`, all pure Python. F7's unit
is [board/bam-ioc.service](board/bam-ioc.service).

**R5 desk check (B7 for the QICK path), 2026-11-02:**
- Setup: a synthetic ringdown (f0 4758.4 MHz, τ 16.1 ns, A 3000 codes), turned into int16 decimated
  I/Q at 552.96 MS/s with a ±221 MHz brickwall standing in for QICK's decimation filter, rebuilt by
  `record.py`, and fitted by the unchanged `fit_shot.m`.
- Result: phase is within 0.2°.
- With the default `Seg` [0 60 ns], τ comes out 17.2 ns, A is 7% low, and the residual is 10× the
  noise. The fit's instant turn-on can't match the band-limited onset.
- With `'Seg', [6e-9 60e-9]`, τ is within 0.6% and A·e^{t0/τ} within 1%. f0 is 20–70 kHz high,
  which is ≈ 0.1–0.3° through the f0/φ coupling.
- So decimated records need the fit segment to start ≈ 6 ns after turn-on. Measure the real filter's
  step response (G7) before trusting τ/A.
- `to_scope()` puts t = 0 at 40 ns into the window (`PRE`), so the scripts' `t < −20 ns` baseline works
  unchanged when ACQ:Delay opens the window 40 ns before the beam.

**PYNQ image: v3.0.1, not v3.1.1 (found 2026-11-02).**
- `import qick` raises on PYNQ ≥ 3.1 (`qick/__init__.py`), and the QICK README and quick-start say
  so. The quick-start recommends **v3.0.1** for the 4x2.
- QICK's pip metadata also pins `pynq<3.1`.
- v3.1.1 was chosen only to match Vivado 2024.1 for a custom overlay, which the QICK decision
  dropped. **The user dropped v3.1.1 (2026-11-02):** one v3.0.1 card for everything. The wave-1
  scripts (`board_capture.py`, `board_relock.py`) were run on v3.1.1, so re-check the
  `xrfclk` import (papercuts) the first time they run on v3.0.1.

## T. Bench session runbook (2026-11-03)

**Before (user):**
1. **Done 2026-11-02:** `fw/qick_4x2.{bit,hwh,ltx}` are
   `s3df.slac.stanford.edu/people/meeg/qick/tprocv2/2025-12-09_4x2_tprocv2r27_standard/` (Vivado
   2023.1). The `.hwh` confirms `qick_processor` 2.0 with `proc_start_i` ← PMOD1_0, `EXT_FLAG 0`, 3
   `axis_dyn_readout_v1`, the weighted buffer, and N_BUF 14 on all three. Was: download the QICK
   tProc-v2 4x2 `.bit` + `.hwh` from the s3df `fw/` listing into `fw/`, renamed
   `qick_4x2.bit` / `qick_4x2.hwh`. Pick the newest `4x2` `tprocv2` standard build; its tProc revision
   must be 21–27 (QICK 0.2.442's `ASM_REVISIONS`). Note its date in SPEC §8. The real `.bit` for a
   ZU48DR is tens of MB, and the `.hwh` is hundreds of kB of XML. The 38–50-byte files from GitHub's
   `out/` folder are path pointers (tried 2026-11-02).
2. Flash `fw/rfsoc4x2_v3.0.1.zip` (2.26 GB, downloaded 2026-11-02 from `download.amd.com/opendownload/xlnx/`,
   zip CRC OK, 9.9 GB `.img` inside) over the v3.1.1 card.
3. Have on hand: a pulse generator for PMOD1_0 (J1 pin 10) at 0/3.3 V (a function generator in
   high-Z mode works; the pin has a 1.15 kΩ pull-up to 3.3 V, SPEC §3), an SMA loopback cable, and the 2-way splitter for C5.

**On the board** (it gets its IP from DHCP: papercuts). Copy `board/` and `fw/` to `/home/xilinx/bam`.

```bash
scp -r board fw xilinx@<ip>:/home/xilinx/bam/
```

```bash
sudo bash -c 'source /etc/profile.d/pynq_venv.sh && pip install --no-index --find-links /home/xilinx/bam/fw/wheels qick==0.2.442 caproto==1.3.0'
```

| Step | Do | Pass |
|---|---|---|
| G1 | `sudo bash -c 'source /etc/profile.d/boardname.sh && source /etc/profile.d/pynq_venv.sh && source /etc/profile.d/xrt_setup.sh && cd /home/xilinx/bam && python3 -c "from qick import QickSoc; s=QickSoc(\"fw/qick_4x2.bit\"); print(s); open(\"fw/soccfg.json\",\"w\").write(s.dump_cfg())"'`, then copy `fw/soccfg.json` back and run `python board/daq.py fw/soccfg.json` on the PC. | 2 gens, 3 readouts, PMOD1_0 listed as the start pin; the program compiles |
| IOC | Same environment: `cd /home/xilinx/bam/board && python3 ioc.py --bit ../fw/qick_4x2.bit`. On the PC set `EPICS_CA_ADDR_LIST=<ip>` and `EPICS_CA_AUTO_ADDR_LIST=NO`, then `python -m caproto.commandline.put BAM:RFSOC:ACQ:Arm On`. | PVs answer |
| G3/G4 | 10 Hz into PMOD1_0. Watch `ACQ:Count`, `ACQ:Rate`, `ACQ:Missed`. | Rate 10, Missed 0, Count = edges sent |
| G2 | Loopback DAC A → each ADC SMA in turn: `AWG1:Mode cw`, `AWG1:Freq 600`, all `CH<n>:Freq 600`; see which `CH<n>:I` lights up. Repeat for DAC B / `AWG0`. | SMA ↔ readout/gen table into SPEC §3 |
| G7 | Same loopback with `AWG<m>:Mode env` and a short rectangular `:I`. `record.py grab`: the tone rebuilds at 600 MHz, and the onset shows the filter's step response. | Frequency and phase sign right; step response noted |
| G5 | Raise the trigger rate until `ACQ:Missed` > 0. | Highest gap-free rate recorded |
| G6 | Env pulse in loopback, 10⁴ records: spread of the onset sample. | Spread recorded in R4 |
| F7 | `sudo cp board/bam-ioc.service /etc/systemd/system/ && sudo systemctl enable --now bam-ioc`, then power-cycle. | IOC back unattended |

## S. Two-stage bench plan (2026-11-03)

The v3.0.1 card is being flashed now. **Stage 1** brings the QICK box up and ends with the analysis
pipeline proven on a loopback tone. **Stage 2** is C5 done properly: the clean S-band clock, split into
two readouts, with an attenuator ladder. It is analysed by the Noise Characterization scripts
(`LBNL Cavity\BAM\Noise Characterization`) exactly as the TDS6804B's `s-band-cw-data` was, so board and
scope sit on one Δφ-vs-σ/A plot against the CRLB.

### Stage 1: bring-up (runbook T, in this order)

| # | Step | Hands to stage 2 |
|---|---|---|
| 1.1 | **Done 2026-11-03** (board at 10.0.0.151; `sudo` needs the password, so the user runs root steps). T "Before" 2, then find the IP (papercuts: DHCP), `scp` `board/` `fw/`, install the wheels. `python3 -c "import qick"` must now succeed (it raised on v3.1.1). | — |
| 1.2 | C1: read the speed grade off the chip into SPEC §3. It decides G8 (9830 MS/s DAC) and nothing in stage 2. | — |
| 1.3 | **Done 2026-11-03** (SPEC §8, `fw/g1.log`). G1: `print(soc)`, save `fw/soccfg.json`, compile `daq.py` against it on the PC. | 3 readouts confirmed |
| 1.4 | **G3 passed 2026-11-03:** the IOC answers over CA from the PC; at 10 Hz on J1 pin 10, `Rate` 9.98, `Missed` 0, and records reach `record.py grab` (4-column and `--split`) with consecutive counts. Unconnected inputs: ~1.5 codes rms on readouts 0/1. Found and fixed: `Daq` lacked `missed` before the first arm, which killed the IOC's poll task silently. Arm only after the IOC has finished loading (~10 s), or the put times out. **G4 passed:** `Count` ran to 11012 with no reset; 10205 shots in 1020 s (10.005/s against the 10 Hz generator), `Missed` 0. IOC up, then G3/G4 with a function generator at 10 Hz into PMOD1_0 = J1 pin 10 (0/3.3 V, high-Z mode, ground on J1 pin 14). | One edge = one record |
| 1.5 | **Mostly done 2026-11-03:** DAC A → splitter → ADC D + ADC C with `AWG1` CW at 600 MHz lights readouts 0 and 1 (−42.4 dBFS each at gain 0.5) and leaves readout 2 dark (−92 dBFS). So gen 1 = DAC A, and readouts 0/1 are the D/C pair. Which of the two is D isn't separated yet (unplug one). G2: SMA ↔ readout map. QICK's printout says readout 0 = **ADC D**, 1 = **ADC C**, 2 = ADC B, gen 0 = DAC B, gen 1 = DAC A (SPEC §8). Confirm with a loopback tone on each SMA. | Cabling for S1: D and C |
| 1.6 | **Done 2026-11-03.** 20 records in `s-band-cw-data/rfsoc_dry` run through an unmodified copy of `phase_folder_report.m` (config lines only; its figures and cache write into the Noise Characterization folder, so the copy pointed them at a scratch dir). f0 = 600.000 MHz, 3360 samples at 8.2944 GS/s, 4/4 self-checks pass; RMS Δφ 0.031° at σ/A 0.0053 = **2.98× its white CRLB**. The same tone over 200 gap-free shots, done in the I/Q domain (224 independent samples, Δφ = arg of the mean cross-phasor): 0.0330° rms against a 0.0285° I/Q CRLB, **1.16 ± 0.06×**. So ≈2.6× of the CSV ratio is the correlated-sample artifact (the stage-2 trap below, predicted 2.7×), not excess noise. Mean Δφ moved −3.47° → −3.55° over a few minutes. **Pipeline dry run.** DAC → 2-way splitter → readouts 0 and 1, both `CH<n>:Freq` = the DAC tone (≲ 600 MHz, papercuts), `ACQ:Length 256`. On the PC: `python tools/record.py grab 20 "<Noise Characterization>/s-band-cw-data/rfsoc_dry" --split 0,1`, then `phase_folder_report.m` with `CFG.folders = {'rfsoc_dry'}` and `CFG.noise_folder = ''`. `find_data_dir` only takes bare names from a fixed list of subfolders, not full paths. | The MATLAB side reads board CSVs |
| 1.7 | G7 (step response, phase sign). G5, G6 and F7 hardening are off the stage-2 path; do them when convenient. | — |

The 2380 MHz clock variant (C4) is optional and comes after stage 2 at stock clocks. It needs
`from xrfclk import xrfclk as xc` to work on v3.0.1 (papercuts).

### Stage 2: two-channel jitter with the S-band clock

**Setup.** S-band clock (2856 MHz) → pad → 2-way splitter → pad ladder → readouts 0 and 1, with
matched cables. Set **both** `CH0:Freq` and `CH1:Freq` to 2856: `daq.py` defaults CH1 to 4758.4.
`ACQ:Length 256`; `--split` trims 16 samples per end, so each record is 224 decimated samples
(405 ns, 3360 rows at 8.29 GS/s; the scope's were 200 ns). The 10 Hz trigger stays: it is
asynchronous to the source, which Δφ doesn't care about. Every folder: 300 records,
`python tools/record.py grab 300 "<Noise Characterization>/s-band-cw-data/<folder>" --split 0,1`.
That directory is one `find_data_dir` already searches, so the scripts need no path edit.

- **Level.** ADC full scale is ≈ 0.35 V peak ≈ +1 dBm at the SMA (SPEC §2). Size the fixed pad so the
  top rung reads about −3 dBFS on both channels (`CH<n>:I` on the IOC). Check DS926's absolute maximum
  input before the first connection. The clock's output level isn't recorded here yet.
- **Aliases at 4423.68 MS/s** (QICK's ADC rate, not SPEC's 4046). 2856 MHz lands at 1567.68 MHz in
  zone 2, and the decimated band is ±276 MHz around it. Harmonics fold to 1288.32 (2f), 279.36 (3f),
  1847.04 (4f) and 1008.96 MHz (5f), so the nearest are 279 MHz away, just outside the band (and far outside
  the fit kernel if the filter's roll-off lets them fold in): no 2856 BPF is needed. One interleave spur (−2856 + 10·fs/8) lands at 1750.08 MHz, 182 MHz from the tone.
  It is inside the band but far outside the 1/T ≈ 2.5 MHz fit kernel, so it inflates the residual σ,
  not Δφ.

| # | Run | Folders | What it gives |
|---|---|---|---|
| S1 | **Ladder, tile 224** (the BAM pair: master and cavity both go on tile 224, SPEC §8) | `rfsoc_s_band`, `_6dB_att` … `_18dB_att` (0/6/9/12/15/18 dB, as the scope ladder), plus `rfsoc_s_band_only_noise`: source off, splitter input terminated, all cabling kept | Δφ rms vs σ/A against the CRLB; `fit_noise_model.m` splits it into CRLB + σ_floor² + (k·A)². **σ_floor is the headline.** Mean Δφ vs rung is the *differential* AM→PM: the pads sit before the splitter, so their insertion phase is common. Before quoting σ, check the Δφ pdf (diagnostics figure) and robust/plain rms for discrete modes: a per-shot one-clock skew in the readouts' NCO resets would show as modes, which is a firmware effect, not jitter. |
| S2 | **Relock states.** Top rung, 10 IOC restarts (each `QickSoc()` rewrites the LMX), 100 records each | `rfsoc_relock_01` … `_10` | σ must not depend on the restart; the mean Δφ may step (four-state issue, bench results above). |
| S3 | **Window length.** Top rung at `ACQ:Length` 64, 128, 512, 2048, 8192 | `rfsoc_L64` … | Δφ vs T: ∝ 1/√T is noise, flat is a floor, rising is differential close-in phase noise. L = 64 leaves 32 samples (58 ns) after the trim, which is the BAM fit segment (6–60 ns, PLAN wave 2 R5 check). |
| S4 | **Per-channel AM→PM** (the phase-vs-level calibration NOTES calls for). Pads can't be swapped on one arm: each pad's own insertion phase (tens of degrees at 2856 MHz) is a constant offset, the same as an AM→PM shift. Either step the clock's output level with the pads fixed, or VNA each pad's insertion phase at 2856 MHz and subtract it. | `rfsoc_ampm_<level>` | Mean Δφ vs ch2 level. Only if the clock has a level control or a VNA is free; S1 already gives the differential part. |
| S5 | **Cross-tile.** Move arm 2 to readout 2 (tile 226), top rung and noise-only, `--split 0,2` | `rfsoc_xtile`, `_noise` | Adds the two tile PLLs' differential noise. Matters for anything referenced across tiles, not for the BAM pair. |
| S6 | **Side result: absolute phase noise.** `ACQ:Length 8192` (14.8 µs). Save one record's I/Q from the PC: `python -c "import sys, numpy as np; sys.path.insert(0, 'tools'); import record; from caproto.threading.client import Context; pv, = Context().get_pvs('BAM:RFSOC:REC'); z = record.parse(pv.read(data_type='native').data)['iq']; np.save('cap.npy', z[0]); np.save('diff.npy', np.conj(z[0]) * z[1])"`. Then `python tools/phasenoise.py cap.npy --fs 552.96e6 --frf 2856e6 --band 100e3 200e6`; `diff.npy` through the same command gives the *differential* spectrum. | — | Board-added L(f) above ~100 kHz, since the source is clean. 8192 samples can't reach 1 kHz (that needs DDR4 streaming, not in wave 2), so this is not the R1 number. |

**What Δφ includes.** It cancels source noise, the common clock chain (LMK, LMX, the shared tile PLL)
and trigger and window jitter. It keeps aperture jitter, each channel's own clock path and front end,
the NCO phase-reset skew between readouts, and any decimation-filter mismatch. This is the noise the BAM
phase sees after reference subtraction. One caveat: the master and cavity are at different frequencies,
so the common timing jitter cancels only after the reference deviation is scaled by f0/fm (NOTES).
A same-frequency split can't test that scaling.

**Analysis (Noise Characterization, user or Claude on request).**
- `phase_folder_report.m` with `CFG.folders` = the S1 list and `CFG.noise_folder = 'rfsoc_s_band_only_noise'`.
  `fit_noise_model.m` and `plot_all_freqs.m` need an entry in `lib/cw_datasets.m`, and then the board
  ladder plots next to the scope's S-band ladder.
- **Trap: the white-noise σ in the CW path is wrong for these records.** Each CSV is upsampled from
  552.96 MS/s I/Q, so its noise fills only ±276 MHz around the tone and neighbouring rows are
  correlated. The white CRLB with N = 3360 rows comes out too low by about √(8.29 GS/s ÷ 2·553 MHz)
  ≈ 2.7× (more, given the decimation filter's roll-off), and both σ markers land in the wrong place.
  The fix is already in the folder: project the noise-only records through the fit's own `Mpin` and
  use that scatter as σ (the tinted marker, `analyze_pulsed_folder.m`). The README says the CW path
  was never given it. Do that before reading any board point against the bound. σ_floor from
  `fit_noise_model.m` is less sensitive to this, but only once its CRLB term is right.
- **Done 2026-11-03, on the loopback: `Noise Characterization/rfsoc_bound_check.m`.** It runs both
  routes on the same shots: the CSV sine fit and the decimated-I/Q phasor mean (`record.py --split`
  now also writes `<folder>/iq/`). The bound for each is the scatter of signal-free records pushed
  through that estimator. Data: DAC A at 600 MHz → splitter → ADC D/C, DAC gain 0.5 → 1/64 in 6 dB
  steps, 200 shots each, plus noise-only (`rfsoc-loopback-data/`).
  - Measured/projected was 1.00–1.17 on both paths at every level (σ/|m| 0.007–0.23), each ±0.07; 15/15 checks pass.
  - CSV and I/Q Δφ agree to 0.6% on the same shots.
  - The I/Q white bound is 0.89–0.96 of the projected one: the in-band noise is nearly white.
  - The CSV white CRLB is 2.9–3.1× too low (2.74 predicted from the rates alone).
  - No slow drift within a folder (successive-difference rms / rms = 0.97–1.04).
  - **Use this script for S1–S5**, with the noise-only folder taken with every AWG off and the IOC re-armed (papercuts).
  - This loopback shares the board clock between DAC and ADC, so it validates the analysis, not the jitter.
- **S1 done 2026-11-03** (`rfsoc-sband-data/`, `rfsoc_bound_check.m` with `CFG.campaign = 'sband'`, figure `rfsoc_bound_check_sband.png`).
  - Setup: +10 dBm clock → 10 dB fixed → ladder (+3/6/9/12/15 dB, measured 3.16/6.26/9.35/12.42/15.52) → splitter → ADC D/C, both readouts at 2856 MHz.
  - 300 shots per rung, L = 256 (224 samples kept, 405 ns), none missed.
  - Top rung: 539/508 codes, and the step from 16 dB to 10 dB was linear (+6.15 dB).
  - The tone sits +16–27 kHz from the NCO (free-running references; the estimate is biased by the spur below).
  - **Floor: 11.7 ± 1.2 fs at 2856 MHz (0.0120°), at 4.7σ**, from var(meas) = c·var(proj) + floor². Fit χ² 4.3/4; c 0.945 ± 0.048; CSV and I/Q agree (11.6 / 11.7 fs).
  - Meas/proj runs 1.26 (top rung) → 1.13 → 1.05 → 0.97 → 0.96 → 1.06, each ±0.06.
  - At the top rung, Δφ is Gaussian: MAD/rms 1.02, excess kurtosis 0.18 ± 0.28, no modes. It's uncorrelated with either amplitude (|r| < 0.06), with no drift (diff-rms/rms 0.96, lag-1 0.08 ± 0.06). So the floor is shot-to-shot Gaussian jitter, not AM→PM.
  - Mean Δφ −23.0° … −23.7°, not monotonic in level (a 0.7° jump at +3 dB, back by +6 dB): cable handling, not AM→PM.
  - **Too big for white aperture jitter:** over a 405 ns kernel at 4.42 GS/s, 11.7 fs needs ~250 fs rms per ADC sample, against tens of fs (DS926). More likely close-in differential noise or a per-shot effect. S3's window scan decides: white noise falls as 1/√T, close-in noise does not.
  - **Comparison:** the scope's CW floor was 30–70 fs (Noise Characterization README), over 200 ns windows.
  - **S3 done 2026-11-03** (`rfsoc_window_scan.m`, `rfsoc_window_scan.png`): 300 top-rung shots at `ACQ:Length` 8192 (14.76 µs, `--iq-only`), windows of 16–8160 samples cut from the same shots, and 300 noise-only shots of the same length.
    - The tone sits **+33.3 kHz** from the NCO. The S1 +16–27 kHz figures were biased by the spur.
    - Bound: white, with the local noise σ² beside the tone. The long noise-only records carry a −85 dBc oscillator-leak line at the tone, which would inflate the projected bound.
    - **The floor is a per-shot offset: 11.2–11.8 fs, flat from 116 ns to 14.8 µs** (mid-record windows). In-record differential noise explains ≤ 3.7 fs of it at 405 ns, and none at 14.8 µs.
    - Across shots it isn't white: autocorrelation +0.25 at lag 1, −0.2 at lags 2–4. 73% of the variance sits at 1–3.5 Hz alias frequency (50% if white). No single line: the best sinusoid takes out 0.4 fs. Either slow, or a faster disturbance aliased by the 10 Hz trigger; repeating at another trigger rate decides.
    - **Short windows:** the ADC interleave spur (−36.5 dBc at −182.5 MHz) leaks through a T-sample mean as 1/T. It gave 50 fs at 29 ns and 34 fs at 58 ns (the BAM fit length) until LS-removed with three weaker lines.
    - With the lines removed, mid-record short windows are 17 / 15 / 12 fs at 29 / 58 / 116 ns, near the flat floor. Record-start windows stay higher (25 / 20 / 16 fs): the first ~100 ns after the readout restart carry extra, probably the decimation filter settling (G7).
    - For BAM: model or remove the interleave spurs in the fit, and start the fit window ≳ 100 ns after the window opens.
  - **Two things that cost time:**
    - The oscillator sitting on the board leaked into ADC C at −72 dBc. That looks like in-band noise in the noise-only folder; move it off the board.
    - The ADC interleave spur at −36.5 dBc, 182.7 MHz from the tone, inflates the residual σ. So only the projected bound counts.

**Exit.** σ_floor (degrees, and fs at 2856 MHz) for S1 at L = 256 and L = 64. It goes into SPEC R1/§4 as
the wave-1 gate (C5), next to the scope's S-band floor and DS926's 8–11 fs prediction (NOTES "Board vs
scope"). The board beats the scope for the BAM if its floor sits well under the scope's.

## G. Bench checks (when the board is back, after C2)

| # | Check | Pass |
|---|---|---|
| G1 | Load F1's bitstream on PYNQ v3.0.1 (QICK refuses ≥ 3.1). `print(soc)` lists 2 gens and 3 readouts. Save `soc.dump_cfg()` to `fw/soccfg.json`, so programs compile offline from then on. | 3 readouts, JSON saved |
| G2 | SMA ↔ readout and DAC ↔ gen map (merges with PLAN C5). | Table in SPEC §3 |
| G3 | A pulse generator into PMOD1_0: each edge gives exactly one record. Note what an edge does mid-program. | 1 record per edge |
| G4 | The dmem counter tracks 10⁴ edges with no reset. | Counter = edges sent |
| G5 | Ring: at depth K, send 3K shots at a rising rate; the host reads all of them. Record the highest gap-free rate. | ≥ machine rep rate |
| G6 | Trigger → window and trigger → DAC spread over 10⁴ triggers (DAC → ADC loopback at ≲ 600 MHz, papercuts). | Number recorded in R4 |
| G7 | DDC conventions: a known tone in zones 1–3; `record.py` rebuilds the right frequency and phase sign. | Matches |
| G8 | AWG modes (CW, raw, envelope) at 2856 and 4758 MHz on an analyzer or an ADC. | R2 |

## H. PVs (v1)

The prefix `BAM:RFSOC:` is a placeholder (W2). `<n>` = readout 0–2, `<m>` = DAC 0–1, `<k>` = PMOD0
pin 0–7.

| PV | Type | Meaning |
|---|---|---|
| `ACQ:Arm` | enum Off/On | Arm / disarm. While armed, every setpoint write re-arms at once. |
| `ACQ:Delay` | double, us | Trigger → window start, after the fixed `INFO:T0` |
| `ACQ:Length` | long | Record length, 16–8192 decimated samples (half the 16384 buffer), power of 2 |
| `ACQ:Count`, `ACQ:Missed` | long | Shot counter (restarts at 1 on arm); gaps + ring overruns |
| `ACQ:Rate` | double, Hz | Measured trigger rate |
| `CH<n>:Freq` | double, MHz | Readout NCO, as the true RF frequency |
| `CH<n>:I`, `CH<n>:Q` | long waveform | Latest record, for display |
| `REC` | long waveform | One whole shot, all channels plus header (`tools/record.py`). Consumers read this one. |
| `AWG<m>:Mode` | enum | off / cw / env / raw |
| `AWG<m>:Freq`, `:Phase`, `:Gain`, `:Delay`, `:Nqz` | double / long | DDS, timing, Nyquist zone |
| `AWG<m>:I`, `AWG<m>:Q` | double waveform, ≤ 65536, in ±1 | Uploaded envelope. Writing a single 0 clears it. |
| `MRK<k>:Delay`, `MRK<k>:Width` | double, us | Gate on PMOD0_k (width 0 = off) |
| `INFO:FsDec`, `INFO:T0` | double | Decimated rate (MHz) and trigger → time-zero slack (us) |

Clients need `EPICS_CA_MAX_ARRAY_BYTES` ≥ 1000000 for the waveforms.

## W. Decisions for the user

- **W1. EPICS server. Decided 2026-11-02: caproto** (pure Python, CA only) for v1. pythonSoftIOC
  (CA + PVA) only if SPEC Q7 turns up a PVA client; switching changes only `ioc.py`.
- **W2.** PV prefix and naming convention, if the facility has one.
- **W3.** Record length and rep rate (Q5/Q6) set the ring depth. At L = 256 the ring holds 64
  shots and 63 are usable, which is 630 ms at 100 Hz.

## Not in wave 2

PVA structures, DDR4 streaming, the MR raw buffer, the time tagger, multi-board sync, on-board
estimation (CLAUDE.md), and a custom overlay (SPEC §8 lists what would reopen it).

# Wave 3 plan: production trigger and Pegasus EPICS integration

Drafted 2026-11-04. Goal: **the board runs unattended on the beamline trigger, and the Pegasus
aggregator records one BAM record per shot next to every other device.** Wave 2's box works at 10 Hz
on a function generator. Wave 3 changes the trigger to the beamline DG645, makes the board a host on
the lab network, and wires it into the `pegasus_epics_upgrade` repo.

## Exit criteria

- [ ] The DG645 drives J1 pin 10. 1 h gap-free at 2.5 Hz, then 1 h at 10 Hz (`ACQ:Missed` 0).
- [ ] After a power cycle, the board comes back unattended: static IP, clock synced to 10.0.0.1, IOC
      up and armed with the last setpoints.
- [ ] The BAM PVs have a registered `PEG:` name, and the pegasus registry and pegasus-opi accept them.
- [ ] A 1 h aggregator run on PegasusControl with the shot counter as shot id: every shot has a
      `REC`, the board's `ACQ:Count` steps match `PulseId_RBV` steps, and every `REC` timestamp is
      within `guard_ms` of its shot's counter stamp.

## Where the work lives

One plan, here, in two parts. **Code and config land in the repo that owns them:**

- **This repo (part B):** `board/`, the board's OS configuration, and the bench checks. The IOC stays
  here. It's a QICK driver with a CA face, it can only run on the board, and the pegasus bundle,
  install and test machinery assumes Windows hosts.
- **pegasus_epics_upgrade (part P):** the PV names (registry), how clients reach the board
  (network config, `epics_env`), what gets recorded (aggregator configs), and the decision record.
  That repo keeps decisions in ADRs and issues, so P1 opens an issue and an ADR there that point back
  to this section rather than copying it. Work there in a worktree, per its `CLAUDE.md`.
- **The contract between them** is the PV table (wave 2 H, plus B5 below). Once P2 lands, the pegasus
  registry is the authority for names, and `ioc.py` follows it.

### The contract (decided 2026-11-04)

| What | Owner | Artifact | How the other side checks it |
|---|---|---|---|
| PV leaf names, types, access | This repo (`board/ioc.py`) | `board/pvs.json`, generated by `ioc.py --list-pvs` from the dict the server serves. `ioc.py --check` fails if the committed file is stale. | Pegasus copies `pvs.json` from a tagged version here, and its registry generator reads that copy as the IOC's source. Its T1 tests then require `pv_registry.md` to document every served name, as for its own IOCs. |
| PV prefix | Pegasus (registry allocation) | `PEG:DIAG:BAM1:`, set on the board in `/etc/bam-ioc.env` (`BAM_PREFIX`); commissioning uses `PEGTEST:DIAG:BAM1:`. `ioc.py` defaults to `BAM:RFSOC:`, and `--fake` refuses a `PEG:` prefix, so a PC can't shadow the board. | The registry entry, and `caget` of the served prefix. |
| Version | This repo | A git tag here. `tools/bundle.py` stamps it into the bundle's `VERSION` file, and the IOC serves it as `Version` (and `BuildDate`). | Pegasus records the pinned version next to its copy of `pvs.json`; preflight compares it with `caget …:Version`. The aggregator records it as identity. |
| `REC` layout | This repo | `INFO:RecFormat` (1 = today's header + int16 I/Q, `tools/record.py`). Any layout change bumps it. | Recorded as identity, and readers check it. |
| Deployment | This repo | `peg-bam-ioc/<version>/` bundle with `MANIFEST.sha256`, installed by `board/install.sh` to `/opt/bam/<version>` with a `current` symlink; systemd `bam-ioc`; `install.sh --rollback`. Setpoints persist in `/var/lib/bam-ioc/state.json`. | Pegasus doesn't install it. It records the host facts (IP, port 5064, prefix, version) where it keeps them for every host (ADR 0017, P1). |
| Host facts | Pegasus | Site file and/or `docs/network_config.md` | — |

## B. Board work (this repo)

| # | Task | Who | Done when |
|---|---|---|---|
| B1 | **Measured 2026-11-05 at the production location:** the trigger cable gives 0/3.0 V into a 1 MΩ scope, and half that with a 50 Ω terminator, so it's a 50 Ω source set for a high-Z load. The edge is clean with no ringing, positive polarity, at 2.5 Hz. **So: no terminator. Cable straight to J1 pin 10 (shield to pin 14).** The pin's 1.15 kΩ pull-up keeps the low near 0.1 V, and the high stays ≈ 3.0 V (≤ 3.3 V). The text below was the pre-measurement plan; its "terminator + 3.0 V into 50 Ω" is superseded. **Trigger from the DG645** (replaces F2). Give the board its own DG645 output, driven from the same T0 as the shot counter's fan-out, so one DG645 cycle gives one record and one `PulseId`. Use its delay to place the window, with `ACQ:Delay` as the fine adjustment. Open the window ≥ 100 ns before the ringdown (S3: the record start carries extra noise). Electrically: J1 pin 10 is 3.3 V logic with a 1.15 kΩ pull-up to 3.3 V (SPEC §3). Put a 50 Ω feedthrough terminator at the board end and set the output to 0 → 3.0 V into 50 Ω, positive polarity, with no divider. The pull-up then lifts the low level to ≈ 0.14 V. **Hazard:** a level set for 50 Ω doubles into high-Z, so a missing terminator gives 6 V at a 3.3 V pin. The DG645 manual isn't in `docs/` yet; download it and check the output range and load setting (from memory, 0.5–5 V into 50 Ω). | User | A high-Z scope probe at the pin shows 0/3.0 V with clean edges *before* the board is connected. Then `ACQ:Rate` reads 2.50. |
| B2 | **Done 2026-11-04: 10.0.0.27, a DHCP reservation on the router (10.0.0.1) for MAC `fc:c2:3d:6f:3e:27`; the board stays on DHCP, so a reflash keeps it.** Was: **Static IP.** Pick a free address on 10.0.0.0/24 with a ping/ARP sweep first, as for the counter board at .60. Set it in PYNQ's network config (check which mechanism v3.0.1 uses) and give the board a hostname. | User (root) | The board answers at that address after a power cycle. The DHCP papercut rows are marked fixed. |
| B3 | **Clock sync.** `systemd-timesyncd` with `NTP=10.0.0.1`, the source both pegasus hosts use (`deploy/configure_time_sync.ps1`; not ntp.ucla.edu, which answered ~2 h wrong). The aggregator matches on `REC`'s timestamp with a 50 ms guard. (On 10.0.0.27 the board does reach `ntp.ubuntu.com`, but it sat 11 ms off 10.0.0.1, so it needs the pegasus hosts' source.) Enable `systemd-time-wait-sync` and order `bam-ioc.service` after `time-sync.target`, so no record goes out with a boot-time clock. | Claude writes, user applies | `timedatectl timesync-status` shows 10.0.0.1 with an offset < 1 ms. P6 measures the per-shot offset against the counter. |
| B4 | **Hardening** (finishes F7). Change the `xilinx` password and turn off Jupyter. Add the EPICS server environment to `bam-ioc.service`: `EPICS_CAS_INTF_ADDR_LIST=<static ip>`, `EPICS_CAS_AUTO_BEACON_ADDR_LIST=NO`, `EPICS_CAS_BEACON_ADDR_LIST=10.0.0.255`, `EPICS_CA_SERVER_PORT=5064`, and `--interfaces <static ip>` (caproto 1.3.0 reads all four variables, `caproto/_utils.py`). The board is its own host, so the production port needs no ladder rung. Leave `overlayroot` until B5e is settled, because a read-only root would lose the saved setpoints. | Claude writes, user applies | The IOC is back after a power cycle with nobody logged in. |
| B5 | **IOC changes** (`board/ioc.py`, `board/daq.py`). (a) Prefix: default to the P2 name. Commissioning passes `--prefix PEGTEST:...`, which is the pegasus `PEG:=PEGTEST:` convention, so no code is needed. (b) Identity and health PVs in the registry's Python-IOC spelling: `Version`, `BuildDate`, `Heartbeat` (~1 Hz). `Version` is read from a `VERSION` file stamped into the shipped folder at tag time, as pegasus's `deploy/stamp_version.py` does, not from `git describe`: the board gets a copied folder, not a clone. Also `INFO:Firmware` (bitstream name and sha256) and `INFO:Qick` (qick_lib version). The aggregator snapshots identity at run start. (c) Count records that arrive more than one per poll (`ACQ:Batched`). They share one timestamp, so the aggregator would bin them into the wrong shots. If the 1 h run shows any, move the re-arm off the server loop (the `ponytail:` note in `ioc.py`). (d) Keep `REC`'s timestamp at the poll that first sees the count advance (as now). (e) Setpoints survive a restart: write the config to a JSON file on every accepted write, load it at start, and re-arm if it was armed. | Claude | `--fake` serves the new PVs. A restart keeps the setpoints and the armed state. `python board/daq.py` self-check still passes. |
| B6 | **Bench validation with the DG645** (no beam). G5: raise the rate until `ACQ:Missed` > 0 and record the ceiling. Then the 1 h runs at 2.5 and 10 Hz. G2: tell D from C by unplugging one. C1: read the speed grade off the chip (the gens already run at 9830.4 MS/s, which needs a -2 part). G7: step response and phase sign. **Retake the S-band top rung plus noise-only at 2.5 Hz** (300 shots each, `rfsoc_bound_check.m`): S3 left the floor's source open, and a different trigger rate decides whether it is an aliased disturbance. Power-cycle the board twice, which also gives two S2 relock samples. | User at the bench, Claude analyses | The items in this row are recorded in this plan and in SPEC §3/§4. |
| B7 | **First beam records** (beam time). Cable per G2: master → readout 0, cavity → readout 1 through the 20 dB pad (Q3), and the photodiode → readout 2 once the EO arm exists. Set `CH1:Freq` 4758.4 (zone 3). Set the DG645 delay and `ACQ:Delay` so the window opens ≥ 100 ns before the ringdown, with L = 256 (463 ns). `record.py grab`, then the Sims `fit_shot.m` with the segment starting ≳ 6 ns after onset. G6 (trigger → window spread) is meaningful here for the first time. | User, Claude analyses | Fitted τ, A and phase on real shots, next to the scope's if it's still connected. |

**Status 2026-11-04 (desk work done, not on the board yet):**
- **B5 is written.** `board/ioc.py` now serves `Version`/`BuildDate` (from `VERSION`), `Heartbeat`, `INFO:Firmware`/`INFO:Qick`/`INFO:RecFormat` and `ACQ:Batched`. It takes `--state`, refuses a `PEG:` prefix under `--fake`, makes every readback read-only to clients, and writes `--list-pvs` to `board/pvs.json` (57 PVs).
- **The B3/B4 files are written:** `bam-ioc.service` (env file, after `time-sync.target`), `bam-ioc.env.example`, `timesyncd-pegasus.conf`, `install.sh` (with `--rollback`), and `tools/bundle.py` (the bundle).
- **Checked on the PC:**
  - The `daq.py`, `ioc.py --check` and `bundle.py --check` self-checks pass, and `bash -n install.sh` passes.
  - A fake IOC over CA served the identity PVs, refused writes to readbacks, and kept its setpoints and armed state across a restart.
  - A `--allow-dirty` bundle passes `sha256sum -c MANIFEST.sha256`, both unpacked and unzipped.
- **On the board, 2026-11-04 (10.0.0.27, DHCP; no root used):**
  - `tools/board_probe.sh` shows:
    - PynqLinux 3.0 (Ubuntu 22.04), Python 3.10.4, with numpy 1.21.5, qick 0.2.442 and caproto 1.3.0 already in the venv.
    - The network is ifupdown: `/etc/network/interfaces.d/eth0` has `eth0` on DHCP plus the PYNQ default `eth0:1` at 192.168.2.99. B2 is an edit there, or a DHCP reservation.
    - Jupyter is enabled. `systemd-time-wait-sync` is present but disabled. An RTC is present. `sudo` needs a password.
    - timesyncd is synced to `ntp.ubuntu.com`, so the board does reach the internet. 10.0.0.1 answers NTP from the board: 0.5 ms round trip, board 11 ms off it. B3 still points it at 10.0.0.1, so it shares the pegasus hosts' reference.
  - The `ef21a46` bundle passes its manifest on the board, and `daq.py`, `ioc.py --check` and `pvs.json` regeneration all pass under Python 3.10.
  - A fake IOC served from the board's address (the `bam-ioc.env` variables, prefix `BAMTEST:`) answered CA from the PC: `Version` `ef21a46`, `BuildDate`, `RecFormat` 1. Arm worked, `Count` advanced at 9.98 Hz with `Missed`/`Batched` 0, and a write to `ACQ:Count` was refused. `REC` came across as 1544 elements at L = 256.
  - `REC`'s timestamp read 0.34 s *ahead* of this workstation's clock. The workstation (10.0.0.17) isn't disciplined to 10.0.0.1, which matters only if it ever records shots.
- **Installed on the board, 2026-11-04** (`ef21a46`, `sudo bash board/install.sh`, prefix `PEGTEST:DIAG:BAM1:` on 10.0.0.27):
  - `bam-ioc` is active and enabled, `/opt/bam/current` points to `ef21a46`, and `systemd-time-wait-sync` is enabled.
  - timesyncd now uses 10.0.0.1 and is synchronized.
  - `ps` shows `ExecStart` expanded as intended (`--prefix PEGTEST:DIAG:BAM1: --interfaces 10.0.0.27 --state …`), and the IOC listens on 10.0.0.27:5064.
  - From the PC over CA: `Version` `ef21a46`, `INFO:Qick` 0.2.442, and `INFO:Firmware` sha256 `dc3799…6e08`, which equals SHA256SUMS.
  - `ACQ:Arm` On compiled and loaded on the real hardware with no trigger connected (`Count` 0), and `state.json` was written. Then `ACQ:Arm` Off, to leave it as found.
  - The install left `/opt/bam/ef21a46` owned by `xilinx` (`cp -a`), so root runs code that user can edit. `install.sh` now chowns to root; on this install, run `sudo chown -R root:root /opt/bam/ef21a46`.
  - **B4 done 2026-11-04:** the `xilinx` password is changed. `jupyter.service` was disabled and stopped, which also stops the port-80 redirect, so 80 and 9090 were closed, **but it came back on reboot** (see the reboot test below); `/opt/bam/ef21a46` is chowned to root. `overlayroot` is still open (B5e state file).
- **v0.1.0 installed and reboot-tested, 2026-11-04:**
  - `/opt/bam/current` points to `v0.1.0` (owned by root), and `previous` to `ef21a46`.
  - After `sudo reboot`, the clock synced to 10.0.0.1 at 56 s uptime: its first offset was +263 ms, from drift while it was off. `systemd-time-wait-sync` then finished and `bam-ioc` started on its own.
  - Over CA: `Version` `v0.1.0`, the firmware sha256 matches, and the setpoints came back from `state.json` (left disarmed, as saved). Arming works after the reboot.
  - **Jupyter was running again** on 80/9090 although disabled: PYNQ's `clear_pl_statefile.service` (`WantedBy=basic.target`) has `Requires=jupyter.service`. That unit only does `PL.reset()`, and it was failing on this boot anyway. `install.sh` now disables it and masks `jupyter`. On this install, run `sudo systemctl disable clear_pl_statefile && sudo systemctl mask --now jupyter`.
- **Moved to the production location, 2026-11-05** (clean `shutdown -h`, then power-up there):
  - It's back at 10.0.0.27 (the DHCP reservation holds on this LAN) and synced to 10.0.0.1 (latest offset +10 ms).
  - `bam-ioc` came up on its own 41 s after boot: `v0.1.0`, disarmed, default setpoints from `state.json`.
  - Jupyter stays masked, and ports 80/9090 are closed.
  - `dmesg` repeats `usb usb2-port1: Cannot enable. Maybe the USB cable is bad?` every ~4 s. It's in every boot's journal at the bench too (USB 3 root hub port, nothing plugged in), so it's noise, not the move.
- **Production trigger on J1 pin 10, 2026-11-05** (DG645, no terminator, IOC armed via CA):
  - 50 consecutive `REC` records in 20 s, every count step 1, intervals 400.0 ± 0.7 ms (min 398.5, max 401.1), so exactly 2.5 Hz. `Missed` 0.
  - `ACQ:Batched` read 16 and didn't grow afterwards. That's most likely contact bounce while plugging in, so `Count` includes those edges.
  - **Bug found and fixed in `ioc.py` (not yet deployed):** `ACQ:Rate` read 2.99. It counted records per ~1 s tick, and at 2.5 Hz a tick holds 2 or 3. It now divides the count change by the time between the ticks' newest record stamps (`rate()`, checked in `--check`).
  - Clocks: `REC` stamps were 180 ms ahead of the PC, and the PC is 200 ms behind 10.0.0.1 (SNTP), so the board reads ≈ 20 ms behind 10.0.0.1. timesyncd showed +23 ms six packets after boot. That's under the 50 ms guard but thin; recheck once timesyncd has settled, and before P6.
- **v0.1.1 installed, 2026-11-05** (rate fix plus `PollIntervalMaxSec=64`):
  - `current` points to `v0.1.1` and `previous` to `v0.1.0`. The IOC came back armed from `state.json`.
  - `ACQ:Rate` reads 2.498–2.499. 31 consecutive records at 400.1 ± 0.8 ms; `Missed` and `Batched` 0. Ports 80/9090 are still closed.
  - Clock, by SNTP to 10.0.0.1 every 30 s: +28 ms behind at the first packet, then 7.8 ms ahead, settling to < 1 ms within 5 min (0.3 ms at 300 s; timesyncd −0.77 ms, frequency +112 ppm). The 64 s cap fixed the 21 ms that had stood for 27 min under the default 34 min cap.
- **Not yet run on the board:** a trigger on J1 pin 10 through the installed service, a reboot that re-arms from an armed `state.json`, and `--rollback`.
  - `--rollback` with no previous install fails without a clear message.
  - If `pip` fails after the copy, delete `/opt/bam/<version>` before rerunning.
  - `bam-ioc` waits for `time-sync.target`, and `systemd-time-wait-sync` has no timeout. So off the
    lab subnet (no route to 10.0.0.1) the IOC never starts at boot. On such a bench, run
    `sudo systemctl stop systemd-time-wait-sync` (or start `bam-ioc` by hand).
  - `tools/bundle.py` ships only git-tracked `board/` files, so the new files go into a bundle only
    once they're committed.

## P. Pegasus work (pegasus_epics_upgrade)

| # | Task | Done when |
|---|---|---|
| P1 | **Issue + ADR 0017: an IOC that runs on its instrument.** Record that the BAM IOC lives in `rfsoc4x2` and runs on the board under systemd, outside the bundle, install and supervisor system. Pegasus owns its name, its network entry and its recording. Pegasus tests cover the config and registry, not the IOC. Contrast with the counter board (ADR 0010), whose IOC runs on PegasusControl: this is the first non-Windows IOC host. Add the RFSoC and the DG645 to `03_DEVICE_INVENTORY.md`, where the trigger source is still `UNKNOWN`. Say in the triage doc whether the BAM is in v1.0. | ADR merged, inventory rows in. |
| P2 | **Registry.** Allocate `PEG:DIAG:BAM1:`. `DIAG` covers cameras, screens and charge monitors, and the BAM is a beam diagnostic like `PEG:DIAG:ICT1:`. Leave `PEG:RF:` for the LLRF IOC (triage §4). The generator reads IOC definitions from that repo, and this IOC isn't there, so first find how the registry carries PVs whose source is elsewhere (the reserved-allocation route), then add the wave 2 H table plus B5's PVs. Regenerate `pv_registry.json`. | `python -m common.pv_registry` passes. A pegasus-opi screen naming a BAM PV validates. |
| P3 | **Network and client env.** Add a host row in `docs/network_config.md` and a host box in the README diagram. Add `<board ip>:5064` to `EPICS_CA_ADDR_LIST` for PegasusControl's aggregator and the workstation. Add `EPICS_CA_MAX_ARRAY_BYTES=1000000` to `config/epics_env.ps1` and `epics_env_test.ps1`: the default 16 kB holds `REC` at L = 256 (≈ 6 kB) but not at L ≥ 1024. | `caget` of `PEG:DIAG:BAM1:REC` works from both hosts using only the repo's env scripts. |
| P4 | **Aggregator channels.** In the production configs (the `aggregator_hybrid_*.yaml` in use and `aggregator_pulse_id.yaml`): `REC` as `ca`, `class: fast`, with `Version`/`BuildDate`/`INFO:Firmware` as identity; `ACQ:Count` as fast (a cross-check against `PulseId_RBV`, never the key); `ACQ:Missed`, `ACQ:Delay`, `ACQ:Length`, `CH<n>:Freq` as slow. Under ADR 0016, `REC` is an array channel with its own `Save:` enable once that lands. **Rule: `ACQ:Length` is fixed for a run.** A change alters `REC`'s shape, which `hdf5_writer._validate_channel_value` rejects. Trace whether that ends the run or drops the shot, and say which in the config comment. Add a T1 test that loads the configs (pattern: `tests/unit/test_aggregator_pulse_id_config.py`). | T1/T2 green locally, per that repo's hooks. |
| P5 | **T3 coverage.** Check whether the simulated stack has a CA integer-array channel. If not, add a fake `REC` there. Don't make T3 depend on this repo. | T3 exercises a fast CA array end to end. |
| P6 | **T4 acceptance** on PegasusControl: board, Arduino shot counter (triage §5a item 1), DG645 at 2.5 Hz, 1 h, `shot_id_source: external_pulse_id`. Checks: no BAM1 INCOMPLETE shots; `ACQ:Count` steps equal `PulseId_RBV` steps over the run, so a dropped edge on either side shows; and the distribution of `REC` stamp minus counter stamp, recorded with its maximum below `guard_ms`. Repeat at 10 Hz when #54 opens. | Verdict in `docs/qualification/`. |

An operator screen (pegasus-opi) is not in wave 3.

## Order

- **Now, at the desk:** B5, P1–P5.
- **Next bench session:** B1 → B2 → B3 → B4, then B6.
- **P6** needs B3, B4, B5b, P2–P4 and the shot counter on PegasusControl.
- **B7** needs beam time only and can run before P6, with `record.py grab` standing alone.

## Open

- Which DG645 output feeds the board, how long the cable is, and whether anything else shares that
  output (a second load on it changes the level B1 sets).
- Whether the BAM goes into pegasus v1.0 (triage §2) or comes after it.
- `overlayroot` against B5e's saved setpoints: put the file on a writable partition, or drop
  overlayroot.
