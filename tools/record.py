"""Host side: board records (decimated I/Q, PLAN wave 2) -> scope-like real samples for the BAM Sims scripts.

    python tools/record.py                        # self-check
    python tools/record.py grab 20 out/ [--prefix BAM:RFSOC:]   # 20 records from the IOC -> out/rec_<count>.csv
    python tools/record.py grab 300 s_band/ --split 0,1          # readouts 0, 1 as [t, ch1, ch2] (PLAN S)
    python tools/record.py grab 300 s_band/ --split 0,1 --iq-only   # only s_band/iq/, for long records
    python tools/record.py log recs/scan1 [--prefix P]  # every record, raw + timestamps, until Ctrl-C (load())

A record is the int32 `REC` waveform from board/ioc.py, one shot, all channels:
    [count, L, n_ch, delay_ns, fs_dec_kHz, f_kHz * n_ch, then I[L], Q[L] per channel]
Sample k of every channel is at t_k = delay + k/fs_dec, in program time after the readout NCOs' phase reset.

Each readout NCO runs at the channel's true RF frequency f (mod fs), so the DDC output of the sampled
cos(2*pi*f*t + phi) is (A/2)*exp(j*phi) in any Nyquist zone, and x(t) = 2*Re{IQ(t)*exp(j*2*pi*f*t)}
rebuilds it with no conjugation for even zones (f = 0: x = Re{IQ}). The sign convention is checked
on the bench (PLAN G7). Amplitudes are in ADC codes; volts need the per-channel calibration.
"""
import sys
import numpy as np

HDR = 5
ROLES = {'ref': 0, 'sig': 1, 'pd': 2}       # readout per column; SPEC §8 cabling, confirm in PLAN G2
PRE = 40e-9                                  # s of window before the scope-convention t = 0 (to_scope)
EDGE = 16                                    # decimated samples split_csv trims per end (the _check guard)


def parse(rec):
    rec = np.asarray(rec, dtype=np.int64)
    count, L, n, delay_ns, fs_khz = rec[:HDR]
    f = rec[HDR:HDR + n] * 1e3
    iq = rec[HDR + n:HDR + n + 2 * n * L].reshape(n, 2, L)
    return dict(count=int(count), delay=delay_ns * 1e-9, fs=fs_khz * 1e3, f=f, iq=iq[:, 0] + 1j * iq[:, 1])


def to_real(iq, fs, f, delay, up):
    """Band-limited upsample of one channel's I/Q by `up` (FFT zero-pad, so it treats the window as
    periodic: expect edge ringing in the first and last few samples), then mix up to f (Hz)."""
    L = len(iq)
    X = np.fft.fft(iq)
    Y = np.zeros(L * up, complex)
    h = L // 2
    Y[:h], Y[-h:] = X[:h], X[-h:]
    t = delay + np.arange(L * up) / (fs * up)
    y = np.fft.ifft(Y) * up
    return t, (y.real if f == 0 else 2 * (y * np.exp(2j * np.pi * f * t)).real)


def to_scope(r, fs_out=20e9, pre=PRE):
    """Record -> [t, ref, sig, pd] columns at >= fs_out (the TDS6804B ran at 20 GS/s). t is shifted to
    the scope's convention, t = 0 at `pre` after the window opens, so the Sims scripts' baseline
    (t < -20 ns) and fit segment (t >= 0) work unchanged when ACQ:Delay opens the window `pre`
    before the beam. The shift only relabels t; the samples are rebuilt at true program time."""
    up = int(np.ceil(fs_out / r['fs']))
    cols = [to_real(r['iq'][ch], r['fs'], r['f'][ch], r['delay'], up) for ch in ROLES.values()]
    return np.column_stack([cols[0][0] - r['delay'] - pre] + [x for _, x in cols])


def split_csv(r, a, b):
    """Readouts a, b as [t, ch1, ch2] at ~8 GS/s, the Noise Characterization CW format (PLAN S). EDGE
    decimated samples go from each end, where the periodic upsample rings on a CW tone."""
    up = int(np.ceil(8e9 / r['fs']))
    cols = [to_real(r['iq'][ch], r['fs'], r['f'][ch], r['delay'], up) for ch in (a, b)]
    e = EDGE * up
    return np.column_stack([cols[0][0]] + [x for _, x in cols])[e:-e]


def split_iq(r, a, b):
    """The same shot's decimated I/Q, trimmed like split_csv: [t, Ia, Qa, Ib, Qb] at fs_dec."""
    z = r['iq'][[a, b], EDGE:-EDGE]
    t = r['delay'] + np.arange(EDGE, EDGE + z.shape[1]) / r['fs']
    return np.column_stack([t, z[0].real, z[0].imag, z[1].real, z[1].imag])


def grab(n, out, prefix='BAM:RFSOC:', split=None, iq_only=False):
    """Save the next n records from the IOC as headerless CSV, the Sims scripts' scope format, or with
    split=(a, b) two readouts in Noise Characterization's [t, ch1, ch2] format, plus the same shot's
    decimated I/Q in out/iq/ (a subfolder, so the scripts' *.csv listing doesn't pick it up).
    iq_only skips the upsampled CSV (~4 MB a record at ACQ:Length 8192)."""
    import pathlib
    import queue
    from caproto.threading.client import Context
    pv, = Context().get_pvs(prefix + 'REC')
    out = pathlib.Path(out)
    (out / 'iq' if split else out).mkdir(parents=True, exist_ok=True)
    q = queue.Queue()                   # a subscription, so slow CSV writing queues records instead of skipping them
    put = lambda sub, resp: q.put(resp.data)                    # caproto holds callbacks weakly: keep this name
    sub = pv.subscribe(data_type='native')
    sub.add_callback(put)
    q.get()                             # a monitor opens with the current value, which may predate a setpoint change
    while n:
        rec = q.get()
        if len(rec) > HDR:              # the IOC starts with a 1-element placeholder
            r = parse(rec)
            if not (split and iq_only):
                x = to_scope(r) if split is None else split_csv(r, *split)
                np.savetxt(out / f"rec_{r['count']}.csv", x, delimiter=',', fmt='%.10g')
            if split:
                np.savetxt(out / 'iq' / f"rec_{r['count']}.csv", split_iq(r, *split), delimiter=',', fmt='%.10g')
            n -= 1


def log(out, prefix='PEG:DIAG:BAM1:'):
    """Save every REC until Ctrl-C, raw, for a run whose other data lives elsewhere (LabVIEW) and is
    resynced later. Each record goes to out/<seq>.npy as it arrives. One line per record goes to
    out/index.csv (seq, count, board_ts, pc_ts). board_ts is the IOC's stamp (board clock, synced to
    10.0.0.1), and pc_ts is this PC's receive time. out/meta.txt holds this PC's offset from 10.0.0.1.
    seq is monotonic. count restarts on every arm (any setpoint write), so a gap in count within one
    arm is a missed shot."""
    import os, pathlib, queue, subprocess, time
    for k, v in [('EPICS_CA_ADDR_LIST', '10.0.0.27'), ('EPICS_CA_AUTO_ADDR_LIST', 'NO'),
                 ('EPICS_CA_MAX_ARRAY_BYTES', '1000000')]:
        os.environ.setdefault(k, v)                             # before caproto reads them
    from caproto.threading.client import Context
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=False)                     # never append to an old run
    try:
        ntp = subprocess.run(['w32tm', '/stripchart', '/computer:10.0.0.1', '/samples:1', '/dataonly'],
                             capture_output=True, text=True, timeout=10).stdout
    except Exception as e:
        ntp = repr(e)
    (out / 'meta.txt').write_text(f"prefix {prefix}\nstart_pc {time.time():.6f}\n"
                                  f"w32tm offset of 10.0.0.1 from this PC (+ = PC behind):\n{ntp}")
    pv, = Context().get_pvs(prefix + 'REC', timeout=5)
    q = queue.Queue()
    put = lambda sub, resp: q.put((resp.metadata.timestamp, time.time(), resp.data.copy()))  # held weakly: keep the name
    sub = pv.subscribe(data_type='time')
    sub.add_callback(put)
    q.get(timeout=10)                   # the monitor opens with the current value, already saved or stale
    seq, last, t_print = 0, None, 0
    print(f"logging {prefix}REC -> {out}   Ctrl-C to stop")
    with open(out / 'index.csv', 'w') as idx:
        idx.write('seq,count,board_ts,pc_ts\n')
        try:
            while True:
                try:
                    ts, pc, rec = q.get(timeout=0.5)            # a timeout so Ctrl-C gets through on Windows
                except queue.Empty:
                    continue
                if len(rec) <= HDR:                             # the IOC's 1-element placeholder
                    continue
                count = int(rec[0])
                if last is not None and count != last + 1:
                    print(f"  count {last} -> {count}: " + ('re-armed' if count < last else f'{count - last - 1} missed'))
                np.save(out / f'{seq:06d}.npy', rec)
                idx.write(f'{seq},{count},{ts:.6f},{pc:.6f}\n')
                idx.flush()
                seq, last = seq + 1, count
                if pc - t_print > 10:
                    print(f"  {seq} records, count {count}, L {rec[1]}")
                    t_print = pc
        except KeyboardInterrupt:
            pass
    sub.clear()
    print(f"stopped: {seq} records in {out}")


def load(run):
    """A log() run -> (index rows as a structured array, list of parsed records), in seq order."""
    import pathlib
    run = pathlib.Path(run)
    idx = np.genfromtxt(run / 'index.csv', delimiter=',', names=True, dtype=None)
    idx = np.atleast_1d(idx)
    return idx, [parse(np.load(run / f'{s:06d}.npy')) for s in idx['seq']]


def _check():
    """A Gaussian-envelope tone at the cavity frequency, as an ideal DDC would deliver it, rebuilds to
    the true RF waveform in zone 3 of the QICK ADC rate, and a pd-like baseband pulse at f = 0."""
    fs, L, delay = 552.96e6, 256, 1e-6
    t = delay + np.arange(L) / fs
    for f, phi in [(4758.4e6, 0.7), (2856e6, -1.2), (0.0, 0.0)]:
        env = 1000 * np.exp(-((t - t.mean()) / 40e-9) ** 2)
        iq = env / 2 * np.exp(1j * phi) if f else env.astype(complex)
        rec = np.concatenate([[7, L, 1, 1000, 552960, f / 1e3], np.round(iq.real), np.round(iq.imag)])
        r = parse(rec)
        tt, x = to_real(r['iq'][0], r['fs'], r['f'][0], r['delay'], 37)
        truth = 1000 * np.exp(-((tt - t.mean()) / 40e-9) ** 2) * np.cos(2 * np.pi * f * tt + phi)
        inner = slice(37 * EDGE, -37 * EDGE)                   # skip the periodic-edge ringing
        err = np.abs(x - truth)[inner].max()
        assert err < 2, (f, err)                               # < 2 codes of 1000 (int16 rounding)
        assert split_csv(r, 0, 0).shape == ((L - 2 * EDGE) * 15, 3)
        s, z = split_csv(r, 0, 0), split_iq(r, 0, 0)
        assert np.isclose(s[0, 0], z[0, 0]) and np.isclose(s[15, 0], z[1, 0])    # same time grid, every 15th row
    import pathlib, tempfile                                    # load() reads what log() writes
    with tempfile.TemporaryDirectory() as d:
        np.save(pathlib.Path(d) / '000000.npy', rec.astype(np.int32))
        (pathlib.Path(d) / 'index.csv').write_text('seq,count,board_ts,pc_ts\n0,7,1.5,1.25\n')
        idx, rs = load(d)
        assert idx['count'][0] == 7 and idx['board_ts'][0] == 1.5 and np.array_equal(rs[0]['iq'], r['iq'])
    print("record.py self-check OK")


if __name__ == "__main__":
    if sys.argv[1:2] == ['log']:
        a = sys.argv[2:]
        log(a[0], *a[a.index('--prefix') + 1:][:1] if '--prefix' in a else [])
    elif sys.argv[1:2] == ['grab']:
        a = sys.argv[2:]
        opt = lambda k: a[a.index(k) + 1] if k in a else None
        split = opt('--split')
        grab(int(a[0]), a[1], opt('--prefix') or 'BAM:RFSOC:', split and tuple(map(int, split.split(','))),
             '--iq-only' in a)
    else:
        _check()
