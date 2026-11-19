"""Runs ON THE BOARD as root, with bam-ioc stopped. Loopback DAC A (gen 1) -> ADC D (readout 0), no trigger cable needed.

1. ACQ:Source soft at 20 Hz, AWG1 CW at 600 MHz: records arrive with nothing on PMOD1_0, at about the set rate.
2. G7: AWG1 'env' (1 us rectangle on a 600 MHz carrier) and 'raw' (the same burst as DAC samples): prints the
   readout-0 envelope in 0.13 us bins, so the onset, length and level of each can be compared.

    python3 board_soft_test.py [adc_fs]      # adc_fs default 3932.16. Imports daq.py from next to this file or ../board
"""
import os, sys, time
import numpy as np
_here = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [_here, os.path.join(_here, '..', 'board')]     # a copy next to it wins over the checkout's
import daq

FS = float(sys.argv[1]) if sys.argv[1:] else 3932.16
d = daq.Daq('/opt/bam/current/fw/qick_4x2.bit', FS)
F, L = 600.0, 2048


def shots(cfg, n, timeout=5.0):
    d.arm(cfg)
    recs, t = [], time.time()
    while len(recs) < n and time.time() - t < timeout:
        recs += d.poll(); time.sleep(0.002)
    dt = time.time() - t
    d.disarm()
    return recs, dt


base = dict(daq.DEFAULTS)
base.update({'ACQ:Source': 'soft', 'ACQ:SoftRate': 20.0, 'CH0:Freq': F, 'CH1:Freq': F, 'CH2:Freq': F})

cfg = dict(base, **{'ACQ:Length': 256, 'ACQ:Delay': 1.0, 'AWG1:Mode': 'cw', 'AWG1:Freq': F, 'AWG1:Gain': 0.5})
recs, dt = shots(cfg, 20)
counts = [r[0] for r in recs]
p = [20 * np.log10(np.abs(r[1][0, 0] + 1j * r[1][0, 1].astype(float)).mean() / 32768 + 1e-12) for r in recs]
print(f"SOFT: {len(recs)} records in {dt:.2f} s ({len(recs) / dt:.1f} Hz, set 20), counts {counts[:3]}..{counts[-1:]},"
      f" missed {d.missed}, readout 0 mean {np.mean(p):.1f} dBFS")
print("SOFT_OK" if len(recs) == 20 and counts == list(range(1, 21)) and np.mean(p) > -70 else "SOFT_FAIL")

g = d.soc['gens'][1]
print(f"gen 1 fs {g['fs']} MS/s, samps_per_clk {g['samps_per_clk']}, maxlen {g['maxlen']}")
n = int(round(1.0 * g['fs']))                              # 1 us; envelope samples run at fs (f_fabric * samps_per_clk)
t = np.arange(n) / g['fs']                                 # us
bins = 64                                                  # readout samples per printed bin
for mode, i in [('env', 0.5 * np.ones(n)), ('raw', 0.5 * np.cos(2 * np.pi * F * t))]:
    cfg = dict(base, **{'ACQ:Length': L, 'ACQ:Delay': 0.0, 'AWG1:Mode': mode, 'AWG1:Freq': F, 'AWG1:Gain': 1.0,
                        'AWG1:Delay': 1.0, 'AWG1:I': i, 'AWG1:Q': np.zeros(0)})
    try:
        recs, dt = shots(cfg, 10)
    except Exception as e:
        print(f"{mode.upper()}: failed to arm: {e!r}"); continue
    a = np.mean([np.abs(r[1][0, 0] + 1j * r[1][0, 1].astype(float)) for r in recs], 0)
    prof = 20 * np.log10(a[:L // bins * bins].reshape(-1, bins).mean(1) / 32768 + 1e-12)
    on = np.flatnonzero(a > a.max() / 2)
    tb = bins / d.fs_dec
    print(f"{mode.upper()}: {len(recs)} records, envelope {len(i)} samples; above half max from "
          f"{on[0] / d.fs_dec if len(on) else float('nan'):.3f} to {on[-1] / d.fs_dec if len(on) else float('nan'):.3f} us "
          f"after window start, peak {20 * np.log10(a.max() / 32768):.1f} dBFS")
    print("   dBFS per %.3f us bin:" % tb, " ".join(f"{x:.0f}" for x in prof))
