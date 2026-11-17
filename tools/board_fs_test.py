"""Runs ON THE BOARD as root, with bam-ioc stopped (FREQ_PLAN.md, execution plan E2).

Loads the QICK tProc-v2 bitstream with both ADC tiles at fs (argv[1], MS/s; one clock group, so both move),
prints the tile-PLL lock state and the new readout rates, saves the soccfg to /tmp/soccfg_<fs>.json, then
for each tone in argv[2:] (MHz) plays DAC A CW at gain 0.5 and lists the strongest lines in readout 0 (ADC D,
NCO 4758.4) over 10 shots on the external trigger. Usage: python3 board_fs_test.py 3932.16 4770 4100 2856
"""
import sys, time, numpy as np
sys.path.insert(0, '/opt/bam/current/board')
import daq
FS = float(sys.argv[1])
d = daq.Daq('/opt/bam/current/fw/qick_4x2.bit', FS)     # needs daq.py >= v0.2 (adc_fs); v0.1.x: patch qick.QickSoc
soc = d.soc
print('valid ADC rates', [round(x, 2) for x in soc.valid_sample_rates('adc', 0)])
print('locked', soc.rf.clocks_locked())
print('readout fs / f_output', [(r['fs'], r['f_output']) for r in soc['readouts']], 'fs_dec', d.fs_dec)
open('/tmp/soccfg_%g.json' % FS, 'w').write(soc.dump_cfg())
for f in map(float, sys.argv[2:]):
    cfg = dict(daq.DEFAULTS)
    cfg.update({'ACQ:Delay': 3.3, 'ACQ:Length': 256, 'CH0:Freq': 4758.4, 'CH1:Freq': 4758.4, 'CH2:Freq': 4758.4,
                'AWG1:Mode': 'cw', 'AWG1:Freq': f, 'AWG1:Gain': 0.5})
    d.arm(cfg)
    recs, t = [], time.time()
    while len(recs) < 10 and time.time() - t < 20:
        recs += d.poll(); time.sleep(0.1)
    d.disarm()
    X = [r[1][0, 0] + 1j * r[1][0, 1].astype(float) for r in recs]
    L = 256; w = np.hanning(L)
    P = np.mean([np.abs(np.fft.fft(x * w))**2 for x in X], 0) / (w**2).sum()
    fr = np.fft.fftfreq(L, 1 / d.fs_dec); o = np.argsort(fr); fr, P = fr[o], 10 * np.log10(P[o])
    tot = 10 * np.log10(sum(10**(P / 10)) - L * 10**(np.median(P) / 10))
    print(f'tone {f} MHz, {len(X)} shots, floor {np.median(P):.1f} dB, total minus floor {tot:.1f} dB')
    for i in np.argsort(P)[::-1][:4]:
        print(f'   {fr[i]:+8.2f} MHz {P[i]:6.1f} dB')
