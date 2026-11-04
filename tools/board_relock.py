"""Runs ON THE BOARD (base overlay, as root, LMX2594_491.52_stock.txt alongside). Loopback DAC A -> ADC A at 600 MHz.

    python3 board_relock.py none:12 lmx:40      # action:count; actions none, dac, adc, lmx, lmx0, lmx1

Each step re-locks (a tile PLL, or rewrites one/both LMX), then prints level dBFS / close-in score dB, where the
score is the 0.3-2 MHz noise over the 5-9 MHz noise. PLAN "Bench results": the score follows a 4-state DAC/ADC
clock phase that every LMX write re-rolls.
"""
import re, sys, time, numpy as np, xrfdc
from xrfclk import xrfclk as xc
from pynq.overlays.base import BaseOverlay
words = lambda p: [int(m[0], 16) for m in (re.search(r"0x[0-9A-Fa-f]+", l) for l in open(p)) if m]
base = BaseOverlay("base.bit"); base.init_rf_clks(); radio = base.radio
tx, rx = radio.transmitter.channel[1], radio.receiver.channel[3]
for c, f in ((tx, 600.0), (rx, -590.0)):
    blk = c.dac_block if c is tx else c.adc_block; t = c.dac_tile if c is tx else c.adc_tile
    ms = dict(blk.MixerSettings); ms.update(Freq=f, EventSource=xrfdc.EVNT_SRC_IMMEDIATE if c is tx else xrfdc.EVNT_SRC_TILE)
    blk.MixerSettings = ms; blk.UpdateEvent(xrfdc.EVENT_MIXER); t.SetupFIFO(True)
tx.control.gain, tx.control.enable = 0.25, True
fs, n = 2457.6e6, 30720; w = np.blackman(n); f = np.fft.fftfreq(n, 1 / fs)
def score():
    xs = [rx.transfer(n) for _ in range(8)]; lv = 20 * np.log10(np.mean([np.abs(x).mean() for x in xs]))
    S = np.mean([np.abs(np.fft.fft(x * w))**2 for x in xs], 0)
    off = np.abs(f - f[S.argmax()])
    return lv, 10 * np.log10(np.median(S[(off > .3e6) & (off < 2e6)]) / np.median(S[(off > 5e6) & (off < 9e6)]))
def relock(t): t.DynamicPLLConfig(1, 491.52, 4915.2)
lmx = words("LMX2594_491.52_stock.txt")
acts = {"none": lambda: None, "dac": lambda: relock(tx.dac_tile), "adc": lambda: relock(rx.adc_tile),
        "lmx": lambda: [xc._write_LMX_regs(lmx, d) for d in xc.lmx_devices],
        "lmx0": lambda: xc._write_LMX_regs(lmx, xc.lmx_devices[0]), "lmx1": lambda: xc._write_LMX_regs(lmx, xc.lmx_devices[1])}
t0 = time.time()
for arg in sys.argv[1:]:
    name, k = (arg.split(":") + ["6"])[:2]; r = []
    for _ in range(int(k)):
        acts[name](); time.sleep(0.5); tx.dac_tile.SetupFIFO(True); rx.adc_tile.SetupFIFO(True); r.append(score())
    print(f"{name} t={time.time()-t0:4.0f}s", " ".join(f"{l:.2f}/{v:.1f}" for l, v in r), flush=True)
