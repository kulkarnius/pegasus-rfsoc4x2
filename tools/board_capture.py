"""Runs ON THE BOARD (PYNQ base overlay; written on 3.1.1, board now on 3.0.1, as root). DAC tone -> ADC capture for PLAN C2-C4.

    sudo bash -lc "source /etc/profile.d/pynq_venv.sh; source /etc/profile.d/xrt_setup.sh;
                   python3 board_capture.py --tx 1 --ftx 2000 --rx 0 1 2 3 --reps 20 --out stock"
    ... --lmk lmk_2380_clkin1_10M.txt --lmx LMX2594_491.52_stock.txt --out v2380

Saves <out>.npz: x[rx, rep, n] complex64 I/Q, fs_iq, f_tx, nco, fs, plus each tile's PLL lock.
With --lmk, the LMK file is written after the overlay's own clock setup, then the LMX file again (its
VCO recalibrates at the new reference), then every tile PLL is relocked at fref = 476 MHz.
"""
import argparse
import re
import time
import numpy as np
from xrfclk import xrfclk as xc                       # the package re-exports only the public calls
import xrfdc
from pynq.overlays.base import BaseOverlay


def words(path):
    return [int(m[0], 16) for m in (re.search(r"0x[0-9A-Fa-f]+", l) for l in open(path)) if m]


ap = argparse.ArgumentParser()
ap.add_argument("--lmk"); ap.add_argument("--lmx")
ap.add_argument("--tx", type=int, default=1)                 # 0 = tile 228 (DAC B), 1 = tile 230 (DAC A)
ap.add_argument("--ftx", type=float, default=2000.0)         # MHz, true frequency
ap.add_argument("--gain", type=float, default=0.25)
ap.add_argument("--rx", type=int, nargs="+", default=[0, 1, 2, 3])
ap.add_argument("--off", type=float, default=10.0)           # MHz: receive NCO sits this far below the tone
ap.add_argument("--n", type=int, default=30720)          # 32000+ hangs the DMA (papercuts)
ap.add_argument("--reps", type=int, default=20)
ap.add_argument("--out", default="cap")
a = ap.parse_args()

base = BaseOverlay("base.bit")
base.init_rf_clks()                                          # stock: LMK 245.76, LMX 491.52
fref, fs = 491.52, 4915.2
if a.lmk:
    for d in xc.lmk_devices:
        xc._write_LMK_regs(words(a.lmk), d)
    time.sleep(0.5)
    for d in xc.lmx_devices:
        xc._write_LMX_regs(words(a.lmx), d)
    time.sleep(0.5)
    fref, fs = 476.0, 4760.0                                 # x 2380/2457.6

radio = base.radio
tiles = {id(c.dac_tile): c.dac_tile for c in radio.transmitter.channel}
tiles.update({id(c.adc_tile): c.adc_tile for c in radio.receiver.channel})
for t in tiles.values():
    t.DynamicPLLConfig(1, fref, fs)                          # relock (a no-op change at stock)
time.sleep(1)
lock = [t.PLLLockStatus for t in tiles.values()]

for i, c in enumerate(radio.transmitter.channel):
    blk = c.dac_block
    ms = dict(blk.MixerSettings)
    ms.update(Freq=a.ftx, EventSource=xrfdc.EVNT_SRC_IMMEDIATE)
    blk.MixerSettings = ms
    blk.UpdateEvent(xrfdc.EVENT_MIXER)
    c.dac_tile.SetupFIFO(True)
    c.control.gain = a.gain if i == a.tx else 0.0
    c.control.enable = i == a.tx
nco = a.ftx - a.off
for c in radio.receiver.channel:
    blk = c.adc_block
    ms = dict(blk.MixerSettings)
    ms.update(Freq=-nco, EventSource=xrfdc.EVNT_SRC_TILE)    # negative, as rfsystem does for zone 1
    blk.MixerSettings = ms
    blk.UpdateEvent(xrfdc.EVENT_MIXER)
    c.adc_tile.SetupFIFO(True)
time.sleep(0.5)

x = np.zeros((len(a.rx), a.reps, a.n), np.complex64)
for r in range(a.reps):
    for k, ch in enumerate(a.rx):
        x[k, r] = radio.receiver.channel[ch].transfer(a.n)
np.savez(a.out + ".npz", x=x, rx=a.rx, fs_iq=fs / 2 * 1e6, fs=fs * 1e6, f_tx=a.ftx * 1e6,
         nco=nco * 1e6, lock=lock, lmk=str(a.lmk))
p = 20 * np.log10(np.abs(x).mean(axis=(1, 2)) + 1e-12)
print("PLL lock:", lock, "| rx", a.rx, "mean |x| dBFS:", np.round(p, 1))
