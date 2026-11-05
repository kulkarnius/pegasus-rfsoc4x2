"""The EPICS (Channel Access, caproto) face of daq.py. PLAN wave 2 F4.

    sudo python3 ioc.py --bit /home/xilinx/fw/qick_4x2.bit      # on the board
    python board/ioc.py --fake                                   # on the PC, no board

Every key of daq.DEFAULTS is a setpoint PV of the same name under --prefix. A write is checked and,
while armed, re-arms at once, so the next trigger uses it. A value the firmware can't run is
rejected back to the client. ACQ:Arm (Off/On) starts and stops triggered acquisition.
Readbacks (read-only to clients): ACQ:Count/Missed/Rate, CH<n>:I/Q (latest record), and REC, one whole
shot in one int32 array (layout in tools/record.py; consumers should read REC, not CH<n>:I/Q, so
channels can't come from different shots). Clients need EPICS_CA_MAX_ARRAY_BYTES >= 1000000 for the
waveforms.

Also served, read-only: Version and BuildDate (line 1 and 2 of the VERSION file one directory above
this one, which the deploy tool writes; "dev" and "" in a git tree), Heartbeat (+1 per second),
INFO:Firmware (bitstream name + sha256, or "fake"), INFO:Qick (qick version, "none" for --fake),
INFO:RecFormat (REC layout number), and ACQ:Batched: records that arrived more than one per poll
(they share a timestamp), cumulative since IOC start (not reset by arm, unlike Missed).

    --state PATH   save the setpoints and the armed flag there (JSON, atomic) on every accepted
                   write and reload them at start, re-arming if it was armed. A bad file means defaults.
    --list-pvs     print the served PVs as JSON (board/pvs.json) and exit; needs no --bit/--fake.
    --check        self-check. --fake refuses a PEG: prefix (production names); PEGTEST: is fine.

ponytail: a re-arm (compile + envelope DMA) runs inside the server loop, so every client stalls for
it. Fine at v1 setpoint rates; move it to an executor if that ever shows.
"""
import argparse
import asyncio
import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path
import numpy as np
from caproto import (AccessRights, CaprotoValueError, ChannelChar, ChannelDouble, ChannelEnum, ChannelInteger,
                     ChannelString)
from caproto.asyncio.server import run
import daq

REC_FORMAT = 1      # layout of REC (header, then int16 I/Q, see Ioc.poll): any change to it must bump this
PVS_JSON = Path(__file__).resolve().parent / 'pvs.json'
UNITS = {'Delay': 'us', 'Width': 'us', 'Freq': 'MHz', 'Phase': 'deg'}


class Setpoint:
    """Mixin: a client write goes through Ioc.write, which re-arms or raises to reject it."""
    async def verify_value(self, data):
        data = await super().verify_value(data)
        await self.ioc.write(self.key, data)
        return data


class SetDouble(Setpoint, ChannelDouble): pass
class SetInteger(Setpoint, ChannelInteger): pass
class SetEnum(Setpoint, ChannelEnum): pass


class ReadOnly:
    """Mixin: clients may read and monitor but not write (the server's own .write() still works)."""
    def check_access(self, hostname, username):
        return AccessRights.READ


class RoDouble(ReadOnly, ChannelDouble): pass
class RoInteger(ReadOnly, ChannelInteger): pass
class RoString(ReadOnly, ChannelString): pass
class RoChar(ReadOnly, ChannelChar): pass


def load_state(path, d):
    """(cfg, armed) from a state file; defaults (with a warning) if it can't be parsed or fails daq.check."""
    try:
        s = json.loads(Path(path).read_text())
        cfg = dict(daq.DEFAULTS)
        for k, v in s['cfg'].items():
            if k not in cfg:
                continue
            if isinstance(cfg[k], np.ndarray):
                v = np.asarray(v, float).ravel()
            elif isinstance(cfg[k], str):
                v = str(v)
                if v not in daq.MODES:
                    raise ValueError(f"{k}: {v!r}")
            else:
                v = type(cfg[k])(v)
            cfg[k] = v
        daq.check(cfg, d.buf_len, d.env_len)
        return cfg, bool(s['armed'])
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"warning: ignoring state file {path}: {e!r}; using defaults", file=sys.stderr)
    return dict(daq.DEFAULTS), False


class Ioc:
    def __init__(self, d, prefix, info, state=None):
        """info: the Version, BuildDate, INFO:Firmware and INFO:Qick strings. state: path or None."""
        self.d, self.prefix, self.state, self.batched = d, prefix, state, 0
        self.cfg, self.armed0 = load_state(state, d) if state else (dict(daq.DEFAULTS), False)
        self.pv = {}
        for key, v in self.cfg.items():
            if isinstance(v, str):
                ch = SetEnum(value=v, enum_strings=daq.MODES)
            elif isinstance(v, np.ndarray):
                ch = SetDouble(value=v.tolist() or [0.0], max_length=d.env_len)      # caproto wants >= 1 element
            elif isinstance(v, int):
                ch = SetInteger(value=v)
            else:
                ch = SetDouble(value=v, precision=4, units=UNITS.get(key.split(':')[1], ''))
            ch.ioc, ch.key = self, key
            self.pv[key] = ch
        self.pv['ACQ:Arm'] = SetEnum(value='On' if self.armed0 else 'Off', enum_strings=['Off', 'On'])
        self.pv['ACQ:Arm'].ioc, self.pv['ACQ:Arm'].key = self, 'ACQ:Arm'
        for key in ['ACQ:Count', 'ACQ:Missed', 'ACQ:Batched', 'Heartbeat']:
            self.pv[key] = RoInteger(value=0)
        self.pv['INFO:RecFormat'] = RoInteger(value=REC_FORMAT)
        self.pv['ACQ:Rate'] = RoDouble(value=0.0, precision=2, units='Hz')
        self.pv['INFO:FsDec'] = RoDouble(value=d.fs_dec, precision=3, units='MHz')
        self.pv['INFO:T0'] = RoDouble(value=daq.T0, precision=3, units='us')
        for key in ['Version', 'BuildDate', 'INFO:Qick']:           # short: plain strings, so a bare caget reads them
            self.pv[key] = RoString(value=info[key])
        self.pv['INFO:Firmware'] = RoChar(value=info['INFO:Firmware'], max_length=128)    # > 39 characters
        Lmax = d.buf_len // 2
        for n in range(daq.N_RO):
            for c in 'IQ':
                self.pv[f'CH{n}:{c}'] = RoInteger(value=[0], max_length=Lmax)
        self.pv['REC'] = RoInteger(value=[0], max_length=5 + daq.N_RO + 2 * daq.N_RO * Lmax)

    def save(self):
        """Setpoints + armed flag to the state file, atomically. A failure is logged, never raised."""
        if not self.state:
            return
        s = {'cfg': {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in self.cfg.items()},
             'armed': self.d.armed}
        try:
            p = Path(self.state)
            p.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=p.name, suffix='.tmp')
            with os.fdopen(fd, 'w') as f:
                json.dump(s, f)
            os.replace(tmp, p)
        except OSError as e:
            print(f"warning: can't save state to {self.state}: {e!r}", file=sys.stderr)

    async def write(self, key, value):
        """Apply one client write; raising rejects it and leaves the running config alone."""
        try:
            if key == 'ACQ:Arm':
                self.d.arm(self.cfg) if value == 'On' else self.d.disarm()
                self.save()
                return
            if isinstance(self.cfg[key], np.ndarray):
                value = np.atleast_1d(np.asarray(value, float))
                if len(value) == 1 and value[0] == 0:
                    value = np.zeros(0)                     # writing a lone 0 clears the envelope
            else:
                value = type(self.cfg[key])(value)
            new = dict(self.cfg)
            new[key] = value
            if self.d.armed:
                self.d.arm(new)
            else:
                daq.check(new, self.d.buf_len, self.d.env_len)
            self.cfg = new
            self.save()
        except ValueError as e:
            raise CaprotoValueError(str(e)) from e

    async def poll(self):
        t_tick, prev, last = time.time(), None, None        # (count, stamp) of the newest record, now and a tick ago
        while True:
            recs = self.d.poll()
            self.batched += max(len(recs) - 1, 0)
            for count, iq in recs:
                c = self.cfg
                hdr = [count, c['ACQ:Length'], daq.N_RO, round(c['ACQ:Delay'] * 1e3), round(self.d.fs_dec * 1e3)]
                hdr += [round(c[f'CH{n}:Freq'] * 1e3) for n in range(daq.N_RO)]
                ts = time.time()
                await self.pv['REC'].write(np.r_[hdr, iq.ravel()].astype(np.int32), timestamp=ts)
                for n in range(daq.N_RO):
                    await self.pv[f'CH{n}:I'].write(iq[n, 0].astype(np.int32), timestamp=ts)
                    await self.pv[f'CH{n}:Q'].write(iq[n, 1].astype(np.int32), timestamp=ts)
                await self.pv['ACQ:Count'].write(count, timestamp=ts)
                last = (count, ts)
            if time.time() - t_tick >= 1:
                await self.pv['ACQ:Rate'].write(rate(prev, last, time.time(), self.pv['ACQ:Rate'].value))
                await self.pv['ACQ:Missed'].write(self.d.missed)
                await self.pv['ACQ:Batched'].write(self.batched)
                await self.pv['Heartbeat'].write(self.pv['Heartbeat'].value + 1)
                t_tick, prev = time.time(), last
            await asyncio.sleep(0.002)


def rate(prev, last, now, old):
    """Trigger rate between the newest records of two ticks, (count, stamp) each. Counting records per 1 s tick
    instead reads 2 or 3 Hz at 2.5 Hz. 0 after 5 s without a record; unchanged when there's nothing new."""
    if last is None or now - last[1] > 5:
        return 0.0
    if prev is None or last[0] <= prev[0] or last[1] <= prev[1]:     # nothing new, or a re-arm restarted the count
        return old
    return (last[0] - prev[0]) / (last[1] - prev[1])


def pv_list():
    """Every served PV, from the same Ioc.pv the server uses, built over FakeDaq (the stock firmware's limits)."""
    ioc = Ioc(daq.FakeDaq(), '', {'Version': 'dev', 'BuildDate': '', 'INFO:Firmware': 'fake', 'INFO:Qick': 'none'})
    kinds = [(ChannelDouble, 'double'), (ChannelInteger, 'long'), (ChannelEnum, 'enum'),
             (ChannelString, 'string'), (ChannelChar, 'char')]
    out = []
    for name, ch in sorted(ioc.pv.items()):
        e = {'name': name, 'type': next(t for c, t in kinds if isinstance(ch, c)),
             'access': 'rw' if isinstance(ch, Setpoint) else 'ro', 'count': ch.max_length or 1}
        if getattr(ch, 'units', ''):
            e['units'] = ch.units
        if isinstance(ch, ChannelEnum):
            e['enum'] = list(ch.enum_strings)
        out.append(e)
    return json.dumps(out, indent=1) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--bit', help="QICK tProc-v2 4x2 bitstream")
    ap.add_argument('--fake', action='store_true', help="no board: synthetic 10 Hz records")
    ap.add_argument('--prefix', default='BAM:RFSOC:')
    ap.add_argument('--interfaces', nargs='+', default=['0.0.0.0'])
    ap.add_argument('--state', help="JSON file for the setpoints and armed flag, kept across restarts")
    ap.add_argument('--list-pvs', action='store_true', help="print the served PVs as JSON and exit")
    ap.add_argument('--check', action='store_true', help="self-check and exit")
    a = ap.parse_args(argv)
    if a.check:
        return _check()
    if a.list_pvs:
        sys.stdout.reconfigure(newline='\n')        # LF even on Windows: the output is committed as pvs.json
        return sys.stdout.write(pv_list())
    if not (a.fake or a.bit):
        ap.error("--bit or --fake")
    if a.fake and a.prefix.startswith('PEG:'):
        ap.error("--fake must not serve production PEG: names (use PEGTEST:)")
    v = Path(__file__).resolve().parent.parent / 'VERSION'
    v = v.read_text().splitlines() if v.exists() else []
    info = {'Version': v[0] if v else 'dev', 'BuildDate': v[1] if len(v) > 1 else ''}
    if a.fake:
        info.update({'INFO:Firmware': 'fake', 'INFO:Qick': 'none'})
    else:
        import qick
        sha = hashlib.sha256(Path(a.bit).read_bytes()).hexdigest()
        info.update({'INFO:Firmware': f"{Path(a.bit).name} sha256:{sha}", 'INFO:Qick': qick.__version__})
    ioc = Ioc(daq.FakeDaq() if a.fake else daq.Daq(a.bit), a.prefix, info, a.state)

    async def start(async_lib):
        if ioc.armed0:
            try:
                ioc.d.arm(ioc.cfg)
            except Exception as e:
                print(f"warning: can't re-arm from the state file: {e!r}", file=sys.stderr)
                await ioc.pv['ACQ:Arm'].write('Off')
                ioc.save()
        asyncio.get_running_loop().create_task(ioc.poll())

    run({a.prefix + k: v for k, v in ioc.pv.items()}, interfaces=a.interfaces, startup_hook=start)


def _check():
    assert abs(rate((10, 100.0), (13, 101.2), 101.3, 0.0) - 2.5) < 1e-9   # 3 shots in 1.2 s, whatever the tick length
    assert rate((10, 100.0), (10, 100.0), 101.0, 2.5) == 2.5           # no new record this tick: keep the value
    assert rate((90, 100.0), (2, 101.0), 101.1, 2.5) == 2.5            # re-armed: count restarted
    assert rate((10, 100.0), (12, 100.8), 106.0, 2.5) == 0.0           # trigger stopped
    assert PVS_JSON.read_bytes() == pv_list().encode(), "board/pvs.json is stale: python board/ioc.py --list-pvs > board/pvs.json"
    try:
        main(['--fake', '--prefix', 'PEG:DIAG:BAM1:'])
        assert 0, "--fake with a PEG: prefix was accepted"
    except SystemExit as e:
        assert e.code == 2
    info = {'Version': 'dev', 'BuildDate': '', 'INFO:Firmware': 'fake', 'INFO:Qick': 'none'}
    with tempfile.TemporaryDirectory() as t:
        p = Path(t) / 'sub' / 'state.json'                  # the parent directory is created
        a = Ioc(daq.FakeDaq(), 'X:', info, p)
        assert a.cfg.keys() == daq.DEFAULTS.keys() and not a.armed0
        for k, v in [('ACQ:Delay', 2.5), ('AWG0:I', [0.1, -0.2, 0.3]), ('AWG0:Mode', 'env'), ('ACQ:Arm', 'On')]:
            asyncio.run(a.write(k, v))
        b = Ioc(daq.FakeDaq(), 'X:', info, p)
        assert b.armed0 and b.cfg['ACQ:Delay'] == 2.5 and b.cfg['AWG0:Mode'] == 'env'
        assert b.cfg.keys() == a.cfg.keys() and np.array_equal(b.cfg['AWG0:I'], [0.1, -0.2, 0.3])
        assert b.cfg['ACQ:Length'] == 256 and isinstance(b.cfg['ACQ:Length'], int)
        assert list(b.pv['AWG0:I'].value) == [0.1, -0.2, 0.3] and b.pv['ACQ:Arm'].value in (1, 'On')
        asyncio.run(a.write('ACQ:Arm', 'Off'))
        assert not Ioc(daq.FakeDaq(), 'X:', info, p).armed0
        for bad in ['{not json', json.dumps({'cfg': {'ACQ:Length': 100}, 'armed': True})]:     # unparseable; fails check()
            p.write_text(bad)
            c = Ioc(daq.FakeDaq(), 'X:', info, p)
            assert c.cfg.keys() == daq.DEFAULTS.keys() and c.cfg['ACQ:Length'] == 256 and not c.armed0
    print("ioc.py self-check OK")


if __name__ == '__main__':
    main()
