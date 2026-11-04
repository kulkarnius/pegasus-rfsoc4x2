"""Runs ON THE BOARD (PYNQ 3.0.1 + the QICK tProc-v2 4x2 bitstream, as root). PLAN wave 2 F3.

Every rising edge on PMOD1_0 restarts the tProc program from the top (qproc_ctrl.sv), so the program
is one shot: reset the readout NCOs, play the AWG pulses, trigger the readouts and markers, wait for
the readouts to finish, then bump a shot counter. Restarts clear the tProc registers, so the counter
lives in data memory and is copied to s_core_w1 for the host. The decimated buffers append one
record per trigger and wrap (buffer.sv), so they form a ring that poll() reads behind the writer.

The config is a flat dict keyed by PV name (board/ioc.py serves exactly these keys). Times are in us
after T0; frequencies are true RF in MHz.
"""
import sys
import time
import numpy as np

T0 = 0.5    # us from restart to time zero. ponytail: fixed slack for the tProc after a restart; PLAN G6 measures the real latency
MODES = ['off', 'cw', 'env', 'raw']
N_RO, N_GEN, N_PIN = 3, 2, 8

DEFAULTS = {'ACQ:Delay': 1.0, 'ACQ:Length': 256}
for _n, _f in enumerate([2856.0, 4758.4, 0.0]):     # SPEC §8: master + cavity on tile 224, photodiode at baseband
    DEFAULTS[f'CH{_n}:Freq'] = _f
for _m in range(N_GEN):
    DEFAULTS.update({f'AWG{_m}:Mode': 'off', f'AWG{_m}:Freq': 2856.0, f'AWG{_m}:Phase': 0.0,
                     f'AWG{_m}:Gain': 0.5, f'AWG{_m}:Delay': 0.0, f'AWG{_m}:Nqz': 1,
                     f'AWG{_m}:I': np.zeros(0), f'AWG{_m}:Q': np.zeros(0)})
for _k in range(N_PIN):
    DEFAULTS.update({f'MRK{_k}:Delay': 0.0, f'MRK{_k}:Width': 0.0})      # width 0 = off


def check(cfg, buf_len, env_len):
    """Raise ValueError for a config the firmware can't run (the IOC rejects the PV write)."""
    L = cfg['ACQ:Length']
    if L < 16 or L & (L - 1) or 2 * L > buf_len:
        raise ValueError(f"ACQ:Length must be a power of 2 in 16..{buf_len // 2}")
    for m in range(N_GEN):
        i, q = cfg[f'AWG{m}:I'], cfg[f'AWG{m}:Q']
        if cfg[f'AWG{m}:Mode'] in ('env', 'raw') and not 0 < len(i) <= env_len:
            raise ValueError(f"AWG{m}:I needs 1..{env_len} samples in env/raw mode")
        if len(q) not in (0, len(i)) or np.abs(np.r_[i, q, 0]).max() > 1:
            raise ValueError(f"AWG{m}:Q must be empty or match I, and |I|,|Q| <= 1")
        if not -1 <= cfg[f'AWG{m}:Gain'] <= 1 or cfg[f'AWG{m}:Nqz'] not in (1, 2):
            raise ValueError(f"AWG{m}: Gain in -1..1, Nqz 1 or 2")


def build(soccfg, cfg):
    """The one-shot program for cfg."""
    from qick.asm_v2 import QickProgramV2

    class Shot(QickProgramV2):
        def compile_datamem(self):
            return np.zeros(1, dtype=np.int32)      # dmem[0] = shot counter, zeroed on every load

    p = Shot(soccfg)
    L = cfg['ACQ:Length']
    for n in range(N_RO):
        p.declare_readout(ch=n, length=L / soccfg['readouts'][n]['f_output'])
        assert p.ro_chs[n]['length'] == L, p.ro_chs[n]['length']
        p.add_readoutconfig(ch=n, name=f"ro{n}", freq=cfg[f'CH{n}:Freq'], phrst=1)
    gens = []
    for m in range(N_GEN):
        mode = cfg[f'AWG{m}:Mode']
        if mode == 'off':
            continue
        gens.append(m)
        g = soccfg['gens'][m]
        p.declare_gen(ch=m, nqz=cfg[f'AWG{m}:Nqz'])
        par = dict(freq=cfg[f'AWG{m}:Freq'], phase=cfg[f'AWG{m}:Phase'], gain=cfg[f'AWG{m}:Gain'])
        if mode == 'cw':        # no phrst: a periodic pulse with phase reset would glitch every period
            p.add_pulse(ch=m, name=f"awg{m}", style='const', length=0.1, mode='periodic', **par)
            continue
        i = np.asarray(cfg[f'AWG{m}:I'], float)
        q = np.asarray(cfg[f'AWG{m}:Q'], float) if len(cfg[f'AWG{m}:Q']) else np.zeros_like(i)
        spc = g['samps_per_clk']
        pad = -len(i) % spc + (3 * spc if len(i) < 3 * spc else 0)     # whole fabric clocks, >= 3 of them
        i, q = (np.round(np.r_[x, np.zeros(pad)] * g['maxv']).astype(np.int16) for x in (i, q))
        p.add_envelope(ch=m, name=f"env{m}", idata=i, qdata=q)
        if mode == 'raw':       # envelope straight to the DAC: I is the sample stream
            par.update(freq=0, phase=0, outsel='input')
        p.add_pulse(ch=m, name=f"awg{m}", style='arb', envelope=f"env{m}", phrst=1, **par)

    p.delay(T0)
    for n in range(N_RO):
        p.send_readoutconfig(ch=n, name=f"ro{n}", t=0)
    for m in gens:
        p.pulse(ch=m, name=f"awg{m}", t=cfg[f'AWG{m}:Delay'])
    p.trigger(ros=list(range(N_RO)), t=cfg['ACQ:Delay'])
    for k in range(N_PIN):
        if cfg[f'MRK{k}:Width'] > 0:
            p.trigger(pins=[k], t=cfg[f'MRK{k}:Delay'], width=cfg[f'MRK{k}:Width'])
    p.wait_auto()                                   # readouts done before the count says so
    p.add_reg(name="shots")
    p.read_dmem(dst="shots", addr=0)
    p.inc_reg(dst="shots", src=1)
    p.write_dmem(addr=0, src="shots")
    p.write_reg(dst='s_core_w1', src="shots")
    p.end()
    return p


class Daq:
    def __init__(self, bitfile):
        from qick import QickSoc
        self.soc = QickSoc(bitfile)         # the tProc-v2 build; QickSoc()'s default is the 2-readout v1 one
        ro = self.soc['readouts'][:N_RO]
        self.fs_dec = ro[0]['f_output']                 # MHz
        self.buf_len = min(r['buf_maxlen'] for r in ro)
        self.env_len = min(g['maxlen'] for g in self.soc['gens'][:N_GEN])
        self.armed, self.missed, self.n = False, 0, 0  # the IOC reads missed before the first arm, as with FakeDaq

    def arm(self, cfg):
        """Load cfg's program and wait for triggers. Same order as QICK's own acquire()."""
        check(cfg, self.buf_len, self.env_len)
        prog = build(self.soc, cfg)
        self.disarm()                                   # a periodic CW outlives its program: stop it before loading the next
        prog.config_all(self.soc)                       # switches to internal start and stops first
        prog.config_bufs(self.soc, enable_avg=False, enable_buf=True)
        self.soc.clear_tproc_counter(1)                 # drop the last program's s_core_w1
        self.L, self.depth, self.n, self.missed = cfg['ACQ:Length'], self.buf_len // cfg['ACQ:Length'], 0, 0
        self.soc.start_src('external')
        self.armed = True

    def disarm(self):
        self.soc.start_src('internal')
        self.soc.reset_gens()                           # stops a CW (periodic) output
        self.armed = False

    def poll(self):
        """New complete records since the last call: [(count, int16 iq[N_RO, 2, L])]."""
        if not self.armed:
            return []
        n = self.soc.get_tproc_counter(1)               # 0 while a shot runs (restart clears it); skip
        if n <= self.n:
            return []
        first = max(self.n, n - self.depth)
        self.missed += first - self.n
        L, ro = self.L, self.soc['readouts']
        # each buffer wraps at its own size, so shot s sits at a different address per channel
        recs = [(s + 1, np.stack([self.soc.get_decimated(c, s * L % ro[c]['buf_maxlen'], L).T for c in range(N_RO)]))
                for s in range(first, n)]
        # the smallest buffer rewrites shot s first, with shot s+depth, which may have started (index <= counter)
        n2 = max(n, self.soc.get_tproc_counter(1))
        keep = [r for r in recs if r[0] - 1 > n2 - self.depth]
        self.missed += len(recs) - len(keep)
        self.n = n
        return keep


class FakeDaq:
    """PC stand-in with the stock firmware's limits: a 10 Hz shot of noisy ringdowns."""
    fs_dec, buf_len, env_len = 552.96, 16384, 65536

    def __init__(self, bitfile=None):
        self.armed, self.missed, self.n, self.t = False, 0, 0, time.time()

    def arm(self, cfg):
        check(cfg, self.buf_len, self.env_len)
        self.L, self.armed, self.missed, self.n = cfg['ACQ:Length'], True, 0, 0

    def disarm(self):
        self.armed = False

    def poll(self):
        if not self.armed or time.time() - self.t < 0.1:
            return []
        self.t, self.n = time.time(), self.n + 1
        k = np.arange(self.L)
        ring = 3000 * np.exp(-k / (16.1e-3 * self.fs_dec)) * np.exp(2j * np.pi * np.random.rand())
        iq = np.stack([ring * (c + 1) / 3 + 20 * (np.random.randn(self.L) + 1j * np.random.randn(self.L))
                       for c in range(N_RO)])
        return [(self.n, np.stack([iq.real, iq.imag], 1).astype(np.int16))]


def _check():
    """poll()'s ring arithmetic against a stub soc with the stock buffer sizes (runs on the PC)."""
    class Soc:
        def __init__(self, counts):
            self.counts, self.reads = iter(counts), []

        def __getitem__(self, k):
            # the real build has 16384 on all three; a smaller one exercises the per-channel wrap
            return [{'buf_maxlen': b} for b in (16384, 16384, 4096)]

        def get_tproc_counter(self, addr):
            return next(self.counts)

        def get_decimated(self, ch, address, length):
            self.reads.append((ch, address))
            return np.zeros((length, 2), np.int16)

    d = Daq.__new__(Daq)
    d.armed, d.L, d.depth, d.n, d.missed = True, 256, 4096 // 256, 0, 0
    d.soc = Soc([0, 16, 16, 17, 17, 36, 36])                # each poll reads the counter twice
    assert d.poll() == []                                   # 0 while a shot runs
    # 16 done: shot 17 may already be rewriting shot 1's slot, so shot 1 is dropped (usable depth = depth-1)
    assert [r[0] for r in d.poll()] == list(range(2, 17)) and d.missed == 1
    d.soc.reads.clear()
    assert [r[0] for r in d.poll()] == [17]
    assert d.soc.reads == [(0, 4096), (1, 4096), (2, 0)]   # s=16: ch0/1 at 4096, ch2 wrapped to 0
    assert [r[0] for r in d.poll()] == list(range(22, 37)) and d.missed == 5   # 19 new: 3 overrun + 1 at risk
    print("daq.py self-check OK")


if __name__ == "__main__":
    _check()
    if sys.argv[1:]:        # a soccfg JSON from soc.dump_cfg() (PLAN G1): compile the default program offline
        import json
        from qick import QickConfig
        p = build(QickConfig(json.load(open(sys.argv[1]))), DEFAULTS)
        p.compile()
        print(p)
