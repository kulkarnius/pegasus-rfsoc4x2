"""The EPICS (Channel Access, caproto) face of daq.py. PLAN wave 2 F4.

    sudo python3 ioc.py --bit /home/xilinx/fw/qick_4x2.bit      # on the board
    python board/ioc.py --fake                                   # on the PC, no board

Every key of daq.DEFAULTS is a setpoint PV of the same name under --prefix. A write is checked and,
while armed, re-arms at once, so the next trigger uses it. A value the firmware can't run is
rejected back to the client. ACQ:Arm (Off/On) starts and stops triggered acquisition.
Readbacks: ACQ:Count/Missed/Rate, CH<n>:I/Q (latest record), and REC, one whole shot in one int32
array (layout in tools/record.py; consumers should read REC, not CH<n>:I/Q, so channels can't come
from different shots). Clients need EPICS_CA_MAX_ARRAY_BYTES >= 1000000 for the waveforms.

ponytail: a re-arm (compile + envelope DMA) runs inside the server loop, so every client stalls for
it. Fine at v1 setpoint rates; move it to an executor if that ever shows.
"""
import argparse
import asyncio
import time
import numpy as np
from caproto import ChannelDouble, ChannelEnum, ChannelInteger, CaprotoValueError
from caproto.asyncio.server import run
import daq

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


class Ioc:
    def __init__(self, d, prefix):
        self.d, self.prefix, self.cfg = d, prefix, dict(daq.DEFAULTS)
        self.pv = {}
        for key, v in self.cfg.items():
            if isinstance(v, str):
                ch = SetEnum(value=v, enum_strings=daq.MODES)
            elif isinstance(v, np.ndarray):
                ch = SetDouble(value=[0.0], max_length=d.env_len)      # caproto wants >= 1 element
            elif isinstance(v, int):
                ch = SetInteger(value=v)
            else:
                ch = SetDouble(value=v, precision=4, units=UNITS.get(key.split(':')[1], ''))
            ch.ioc, ch.key = self, key
            self.pv[key] = ch
        self.pv['ACQ:Arm'] = SetEnum(value='Off', enum_strings=['Off', 'On'])
        self.pv['ACQ:Arm'].ioc, self.pv['ACQ:Arm'].key = self, 'ACQ:Arm'
        for key in ['ACQ:Count', 'ACQ:Missed']:
            self.pv[key] = ChannelInteger(value=0)
        self.pv['ACQ:Rate'] = ChannelDouble(value=0.0, precision=2, units='Hz')
        self.pv['INFO:FsDec'] = ChannelDouble(value=d.fs_dec, precision=3, units='MHz')
        self.pv['INFO:T0'] = ChannelDouble(value=daq.T0, precision=3, units='us')
        Lmax = d.buf_len // 2
        for n in range(daq.N_RO):
            for c in 'IQ':
                self.pv[f'CH{n}:{c}'] = ChannelInteger(value=[0], max_length=Lmax)
        self.pv['REC'] = ChannelInteger(value=[0], max_length=5 + daq.N_RO + 2 * daq.N_RO * Lmax)

    async def write(self, key, value):
        """Apply one client write; raising rejects it and leaves the running config alone."""
        try:
            if key == 'ACQ:Arm':
                self.d.arm(self.cfg) if value == 'On' else self.d.disarm()
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
        except ValueError as e:
            raise CaprotoValueError(str(e)) from e

    async def poll(self):
        t_rate, n_rate = time.time(), 0
        while True:
            for count, iq in self.d.poll():
                c = self.cfg
                hdr = [count, c['ACQ:Length'], daq.N_RO, round(c['ACQ:Delay'] * 1e3), round(self.d.fs_dec * 1e3)]
                hdr += [round(c[f'CH{n}:Freq'] * 1e3) for n in range(daq.N_RO)]
                ts = time.time()
                await self.pv['REC'].write(np.r_[hdr, iq.ravel()].astype(np.int32), timestamp=ts)
                for n in range(daq.N_RO):
                    await self.pv[f'CH{n}:I'].write(iq[n, 0].astype(np.int32), timestamp=ts)
                    await self.pv[f'CH{n}:Q'].write(iq[n, 1].astype(np.int32), timestamp=ts)
                await self.pv['ACQ:Count'].write(count, timestamp=ts)
            if time.time() - t_rate >= 1:
                count = self.pv['ACQ:Count'].value
                await self.pv['ACQ:Rate'].write((count - n_rate) / (time.time() - t_rate) if count >= n_rate else 0.0)
                await self.pv['ACQ:Missed'].write(self.d.missed)
                t_rate, n_rate = time.time(), count
            await asyncio.sleep(0.002)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bit', help="QICK tProc-v2 4x2 bitstream")
    ap.add_argument('--fake', action='store_true', help="no board: synthetic 10 Hz records")
    ap.add_argument('--prefix', default='BAM:RFSOC:')
    ap.add_argument('--interfaces', nargs='+', default=['0.0.0.0'])
    a = ap.parse_args()
    if not (a.fake or a.bit):
        ap.error("--bit or --fake")
    ioc = Ioc(daq.FakeDaq() if a.fake else daq.Daq(a.bit), a.prefix)

    async def start(async_lib):
        asyncio.get_running_loop().create_task(ioc.poll())

    run({a.prefix + k: v for k, v in ioc.pv.items()}, interfaces=a.interfaces, startup_hook=start)


if __name__ == '__main__':
    main()
