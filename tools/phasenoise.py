"""Phase noise of one digitized tone (SPEC R1, PLAN B6).

    python tools/phasenoise.py capture.npy --fs 4046e6 --frf 2856e6 [--band 1e3 10e6]
    python tools/phasenoise.py            # self-check only

capture.npy holds either raw real samples or complex DDC I/Q. For I/Q, --fs is the I/Q rate.
--frf is the TRUE input frequency, not the alias: clock jitter scales with it.
The DDC is one full-length FFT, so it needs ~50 bytes per input sample (100 ms of QICK I/Q ~ 3 GB):
copy the capture to the PC rather than running this on the board.

The script prints the jitter integrated over the band, plus the AM noise over the same band.
Additive noise (ADC thermal) shows up equally in AM and PM, but clock jitter only shows up in PM.
So PM well above AM means the number is clock jitter. PM close to AM means it is only the additive floor.
"""
import argparse
import numpy as np
from scipy.signal import welch, detrend


def baseband(x, fs, bw):
    """FFT-domain DDC: keep +-bw around the strongest positive-frequency line. Returns (z, rate)."""
    n = len(x)
    X = np.fft.fft(x)
    if not np.iscomplexobj(x):
        X[n // 2:] = 0                   # analytic signal: drop negative frequencies
    k0 = np.argmax(np.abs(X))
    m = int(bw * n / fs)
    z = np.fft.ifft(np.fft.ifftshift(X[(k0 + np.arange(-m, m)) % n]))
    return z, 2 * m * fs / n


def measure(x, fs, frf, band):
    """Integrated (PM rad, jitter s, AM rel) over band, and (f, S_phi one-sided rad^2/Hz)."""
    z, fz = baseband(x, fs, min(4 * band[1], fs / 4))
    phi = detrend(np.unwrap(np.angle(z)))          # the linear term is the residual frequency offset
    am = np.abs(z) / np.abs(z).mean() - 1
    nper = 1 << int(np.ceil(np.log2(4 * fz / band[0])))   # 4 bins below the lowest offset
    if nper > len(z):
        raise SystemExit(f"record too short for {band[0]:g} Hz: need {nper * fs / fz:.3g} samples")
    f, Sp = welch(phi, fz, nperseg=nper)
    _, Sa = welch(am, fz, nperseg=nper)
    sel = (f >= band[0]) & (f <= band[1])
    df = f[1] - f[0]
    pm = np.sqrt(Sp[sel].sum() * df)
    return pm, pm / (2 * np.pi * frf), np.sqrt(Sa[sel].sum() * df), (f, Sp)


def demo():
    rng = np.random.default_rng(1)
    fs, frf, n, band = 4046e6, 2856e6, 1 << 21, (1e5, 2e7)
    t = np.arange(n) / fs
    # 100 fs of jitter, white up to fc. Jitter that is white all the way to fs/2 folds back partly as
    # AM-like noise (a real effect: PM reads 1.5x in variance). The clock's jitter sits at low offsets.
    fc = 1e8
    d = np.fft.irfft(np.where(np.fft.rfftfreq(n, 1 / fs) < fc, rng.standard_normal(n // 2 + 1)
                              + 1j * rng.standard_normal(n // 2 + 1), 0), n)
    d *= 100e-15 / d.std()
    expect = 2 * np.pi * frf * 100e-15 * np.sqrt((band[1] - band[0]) / fc)
    x = np.cos(2 * np.pi * frf * (t + d)) + 1e-4 * rng.standard_normal(n)
    pm, sj, am, _ = measure(x, fs, frf, band)
    assert abs(pm / expect - 1) < 0.1, (pm, expect)
    assert am < pm / 5, (am, pm)
    x = np.cos(2 * np.pi * frf * t) + 1e-3 * rng.standard_normal(n)              # additive noise only
    pm, _, am, _ = measure(x, fs, frf, band)
    assert abs(pm / am - 1) < 0.25, (pm, am)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("capture", nargs="?")
    ap.add_argument("--fs", type=float, default=4046e6)
    ap.add_argument("--frf", type=float, default=2856e6)
    ap.add_argument("--band", type=float, nargs=2, default=(1e3, 10e6))
    a = ap.parse_args()
    if not a.capture:
        demo()
        print("self-check OK")
        raise SystemExit
    pm, sj, am, (f, Sp) = measure(np.load(a.capture), a.fs, a.frf, a.band)
    print(f"band {a.band[0]:g}-{a.band[1]:g} Hz: PM {pm * 1e3:.4f} mrad = {sj * 1e15:.1f} fs at "
          f"{a.frf / 1e6:g} MHz; AM {am * 1e3:.4f} mrad-equiv (additive floor)")
    for fo in 10.0 ** np.arange(3, 8):
        if a.band[0] <= fo <= a.band[1]:
            print(f"  L({fo:.0e} Hz) = {10 * np.log10(np.interp(fo, f, Sp) / 2):.1f} dBc/Hz")
