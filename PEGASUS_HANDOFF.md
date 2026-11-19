# Handoff: the BAM RFSoC digitizer into pegasus_epics_upgrade

From this repo (`rfsoc4x2`) to the `pegasus_epics_upgrade` repo. Written 2026-11-04,
updated 2026-11-05 after the board went into production.
This is part P of [PLAN.md](PLAN.md) "Wave 3", written so a session in the pegasus repo can
work from it alone. Follow that repo's own `CLAUDE.md` (worktree, papercuts, T1/T2 before a PR).

## 1. What the device is

A RealDigital RFSoC 4x2 that replaces a 20 GS/s scope on the BAM (beam arrival monitor) cavity. On each
trigger it captures one window from 3 ADC readouts (master 2856 MHz, cavity 4758.4 MHz, photodiode)
as decimated I/Q at 491.52 MS/s (552.96 before v0.2.0; `INFO:FsDec` and the `REC` header carry it), and it can
play 2 DAC outputs. It runs PYNQ v3.0.1 (Linux, aarch64)
with the stock QICK tProc-v2 firmware.

The IOC is `board/ioc.py`: Python, **caproto, CA only, no PVA**. It runs **on the board** under
systemd, because it drives the FPGA directly through QICK. Estimation (fits, phase) is not on the
board. Analysis code reads the records.

**Status (2026-11-05): live in production, production prefix.** The board sits at its production
location on 10.0.0.27 and runs **`v0.1.1`** under systemd as **`PEG:DIAG:BAM1:`** (switched from
`PEGTEST:DIAG:BAM1:` on 2026-11-05; the old prefix no longer answers). It's armed on the beamline
DG645 trigger at 2.5 Hz.
- **Gap-free run:** from 00:59:57 to 16:58 UTC, 15 h 58 min, `ACQ:Count` reached 143,692 against 143,700
  expected, with `ACQ:Missed` and `ACQ:Batched` both 0.
- **Clock:** within 1 ms of 10.0.0.1 five minutes after boot, and 0.05 ms after 16 h.
- **Not yet:** no RF is connected (a splitter with a capped input sits on readouts 0/1), so the records
  are noise until the master and cavity are cabled. The shot counter isn't on PegasusControl yet (P6).
- **Testing:** P1–P5 can be tested against the real board now, not only `ioc.py --fake` (§8).

**Pin `v0.2.0`** (tag at commit `e749ad0` since the 2026-11-19 history rewrite, `d020a25` before; installed 2026-11-17). Its `pvs.json` is byte-identical to
`v0.1.1`'s and `v0.1.0`'s. v0.2.0 moves the ADC rate from 4423.68 to 3932.16 MS/s (`BAM_ADC_FS` in
`/etc/bam-ioc.env`, rfsoc4x2 FREQ_PLAN.md): `INFO:FsDec` reads **491.52** instead of 552.96, so a record of
`ACQ:Length` samples spans L / 491.52 MHz. Consumers must take the sample spacing from `INFO:FsDec` or the `REC`
header, not a constant. v0.1.1's differences from v0.1.0, also in the board's behaviour, not its PVs:
- `ACQ:Rate` is computed from record timestamps; `v0.1.0` read 2–3 Hz at 2.5 Hz.
- timesyncd polls at most every 64 s.
- Jupyter is masked by the install.

## 2. The contract

| What | Owner | Where it lives | Check |
|---|---|---|---|
| PV leaf names, types, access, element counts | rfsoc4x2 (`board/ioc.py`) | `board/pvs.json`, generated from the dict the server serves. `ioc.py --check` fails if it's stale. | Pegasus copies it from a **tagged** rfsoc version, and its registry generator reads the copy (P2). |
| PV prefix | pegasus (registry allocation) | `PEG:DIAG:BAM1:` (allocated in P2, served since 2026-11-05). On the board it lives in `/etc/bam-ioc.env` as `BAM_PREFIX`; commissioning used `PEGTEST:DIAG:BAM1:`, the same `PEG:=PEGTEST:` convention as #219. | `caget <prefix>Version` |
| Version | rfsoc4x2 | A git tag. `tools/bundle.py` stamps it into the bundle's `VERSION` file, and the IOC serves it as `Version` (plain string) and `BuildDate` (UTC ISO-8601). Outside a bundle it serves `dev`. | Pin the tag next to the copied `pvs.json`; preflight compares it with `caget …:Version`. |
| `REC` layout | rfsoc4x2 | `INFO:RecFormat` (now `1`). Any layout change bumps it. The parser is `tools/record.py` in rfsoc4x2. | Record it as identity. |
| Deployment | rfsoc4x2 | `peg-bam-ioc/<version>/` bundle with `MANIFEST.sha256`. `board/install.sh` installs it to `/opt/bam/<version>`, sets the `current` symlink and runs systemd `bam-ioc`; `--rollback` reverts. Setpoints persist in `/var/lib/bam-ioc/state.json`. | Pegasus does **not** build, install or start it. |
| Host facts (IP, port, prefix, pinned version) | pegasus | Wherever pegasus keeps host facts (P1/P3) | — |

**Changing a PV later:** edit `ioc.py` in rfsoc4x2, regenerate `pvs.json`, and tag. Then open a pegasus
PR that updates the copy and the pin, plus `pv_registry.md`. The registry tests stay red until the
docs cover every served name, the same rule as pegasus's own IOCs.

## 3. What the IOC serves (57 PVs at v0.2.0, `board/pvs.json`)

Main after v0.2.0 adds `ACQ:Source` (enum external/soft) and `ACQ:SoftRate` (Hz), 59 PVs. Production must read
`ACQ:Source` = `external`; `soft` fires shots unrelated to the beam (bench only, never restored at IOC start).

The authority is `board\pvs.json` in the rfsoc4x2 checkout; read it rather than this summary. `<n>` = readout 0–2,
`<m>` = DAC 0–1, `<k>` = marker pin 0–7.

| Group | PVs | Notes |
|---|---|---|
| Control (rw) | `ACQ:Arm` (enum Off/On), `ACQ:Delay` (us), `ACQ:Length` (power of 2, 16–8192), `CH<n>:Freq` (MHz) | A write the firmware can't run is refused with `ECA_PUTFAIL` and a reason. While armed, any setpoint write re-arms at once. |
| AWG (rw) | `AWG<m>:Mode` (off/cw/env/raw), `:Freq`, `:Phase`, `:Gain`, `:Delay`, `:Nqz`, `:I`/`:Q` (double waveform ≤ 65536, ±1) | |
| Markers (rw) | `MRK<k>:Delay`, `MRK<k>:Width` (us; width 0 = off) | Pmod gate outputs. |
| Per shot (ro) | `REC` (int32 waveform ≤ 49160), `CH<n>:I`/`:Q` (int32 ≤ 8192), `ACQ:Count` | Consumers read **`REC`**, one whole shot. `CH<n>:I/Q` are for display only and can come from different shots. |
| Health (ro) | `ACQ:Missed`, `ACQ:Rate` (Hz), `ACQ:Batched`, `Heartbeat` (~1 Hz) | Posted once a second. |
| Identity (ro) | `Version`, `BuildDate`, `INFO:Qick` (strings); `INFO:Firmware` (**char waveform**, 128: bitstream name + sha256); `INFO:RecFormat`; `INFO:FsDec` (MHz); `INFO:T0` (us) | The aggregator's identity decode already handles char arrays (`service.py`). A bare `caget` of `INFO:Firmware` needs `-S`. |

Every readback refuses client writes.

## 4. Semantics the aggregator has to know

- **`REC` layout (`RecFormat` 1):** `[count, L, N_RO=3, delay_ns, fs_dec_kHz, freq_kHz × 3]`, then int16
  I/Q as int32, in the order `[channel][I,Q][sample]`. Size: 8 + 6L int32. That is 6176 bytes at the
  usual L = 256 and 196,640 bytes at L = 8192. **Clients need `EPICS_CA_MAX_ARRAY_BYTES` ≥ 1000000**
  (the default of 16384 only covers L ≤ 512).
- **Timestamp.** Every per-shot PV (`REC`, `CH<n>:I/Q`, `ACQ:Count`) carries one timestamp: the
  board's wall clock when the IOC first sees the shot complete. That's after the trigger by
  `INFO:T0` + `ACQ:Delay` + the window, plus a poll of ≤ 2 ms and the readout time. It should be a few
  ms, but it hasn't been measured; P6 measures it against the shot counter.
  - **The board's clock is good:** it tracks 10.0.0.1 within 1 ms from 5 min after boot, 0.05 ms after
    16 h. The service waits for `time-sync.target`, so no record goes out before the first sync.
  - **Any host that records BAM shots must be NTP-disciplined to 10.0.0.1 too** (`deploy/configure_time_sync.ps1`).
    The undisciplined workstation at 10.0.0.17 was 200 ms off, which would put every BAM stamp outside a 50 ms guard.
  - **Intervals between consecutive `REC` stamps** were 400.0 ± 0.8 ms on the DG645 at 2.5 Hz.
- **`ACQ:Batched`** counts records that came out of one poll together, so they share a timestamp and a
  timestamp-binning recorder could misassign them. It should stay 0; treat a rise as a fault. The one
  rise seen so far (16, once) was contact bounce while the trigger cable was being plugged in. Those
  bounce edges also advanced `ACQ:Count`.
- **`ACQ:Count` is not a shot id.** It's the firmware's counter and restarts at 1 on every arm, and
  **any setpoint write while armed re-arms**. Triggers that arrive during a re-arm are neither
  recorded nor counted in `Missed`. Use it as a cross-check against `PEG:TIM:CTR1:PulseId_RBV` between
  re-arms: a drop in `Count` marks a re-arm.
- **`ACQ:Missed`** counts ring-buffer gaps and overruns since the last arm.
- **Shape lock.** `REC`'s length follows `ACQ:Length`. `hdf5_writer._validate_channel_value` raises on
  a shape change, so **`ACQ:Length` must be fixed for a run**. Find out whether that error ends the run
  or drops the shot, and say which in the config comment (P4).
- **Restarts.** The IOC reloads its setpoints and armed state from its state file, so after a reboot it
  comes back armed with the same configuration.

## 5. Host facts (for network_config.md and the site file)

| | |
|---|---|
| Host | RFSoC 4x2, PYNQ v3.0.1 (PynqLinux, Ubuntu 22.04, aarch64), hostname `pynq`. **10.0.0.27**: a DHCP reservation on 10.0.0.1 for MAC `fc:c2:3d:6f:3e:27` (rfsoc B2). The board may move later; the reservation is where the address changes. |
| Installed | `/opt/bam/current` → `v0.3.0` (2026-11-19); `previous` → `v0.2.0` (`sudo bash /opt/bam/…/board/install.sh --rollback`). Site values in `/etc/bam-ioc.env`: `BAM_PREFIX=PEG:DIAG:BAM1:`, `BAM_IP=10.0.0.27`, `BAM_ADC_FS=3932.16` (delete the line and restart for the bitstream's 4423.68). Changing the prefix means editing `BAM_PREFIX` and `sudo systemctl restart bam-ioc`, done by whoever holds the board's sudo password. |
| CA server | Port **5064** (the only IOC on that host, so no ladder rung). Bound to 10.0.0.27 (`EPICS_CAS_INTF_ADDR_LIST`), beacons to `10.0.0.255`. **No PVA.** |
| Clients | The production env's `EPICS_CA_ADDR_LIST=10.0.0.255` broadcast already reaches port 5064. Add a unicast `10.0.0.27` entry if pegasus prefers explicit entries. |
| Other services | Only SSH (22) and CA (5064) listen. Jupyter (ports 80, 9090) is masked; the PYNQ default password is changed. |
| Time | `systemd-timesyncd` → `10.0.0.1`, no fallback, `PollIntervalMaxSec=64` (`board/timesyncd-pegasus.conf`). |
| Trigger | A DG645 output, measured 2026-11-05: a 50 Ω source set for a high-Z load, 0/3.0 V, clean edge, positive polarity, 2.5 Hz. It goes straight to J1 pin 10 with **no terminator**, which would halve it. It must come from the same T0 as the shot counter's fan-out, so one DG645 cycle gives one record and one `PulseId`. Confirm this when the counter moves to PegasusControl. |

## 6. Work in pegasus_epics_upgrade

| # | Task | Done when |
|---|---|---|
| P1 | **Issue + ADR 0017, "an IOC that runs on its instrument."** Record that the IOC's code, bundle and install live in rfsoc4x2, outside pegasus's bundle, install and supervisor system. Pegasus owns the name, the host facts and the recording, and its tests cover the copied `pvs.json`, the registry and the configs, never the IOC. Contrast with ADR 0010: the counter board's IOC runs on PegasusControl, while this is the first non-Windows IOC host. Add the RFSoC and the DG645 to `docs/planning/03_DEVICE_INVENTORY.md`, where the trigger source is `UNKNOWN`. Record in the triage doc §2 whether the BAM is in v1.0. | ADR merged, inventory rows in |
| P2 | **Registry.** Allocate the prefix (proposed `PEG:DIAG:BAM1:`: a beam diagnostic, like `PEG:DIAG:ICT1:`, with `PEG:RF:` left to the LLRF IOC). Copy `pvs.json` in with its pinned tag (location is your call, e.g. `iocs/external/bam/`). Add `IocInfo("bam", ("PEG:DIAG:BAM1:",), <role>)` and a `parse_bam()` that maps the JSON to `PVEntry` (`double`→`ai`/`ao`, `long`→`longin`/`longout`, `enum`→`mbbi`/`mbbo`, `string`→`stringin`, `char`→`waveform`, waveforms by `count` > 1; record types are your convention to settle). Add a `pv_registry.md` section, then regenerate. | `python -m common.pv_registry check` and the T1 registry tests pass |
| P3 | **Network and client env.** Host row in `docs/network_config.md` and in the README host diagram. Add `EPICS_CA_MAX_ARRAY_BYTES=1000000` to `config/epics_env.ps1` and `epics_env_test.ps1`. | `caget PEG:DIAG:BAM1:REC` from PegasusControl and the workstation using only the repo's env scripts (the board is up, §8) |
| P4 | **Aggregator channels** in the production configs (the `aggregator_hybrid_*.yaml` in use and `aggregator_pulse_id.yaml`). `REC` as `ca`, `class: fast`, identity `version: …:Version`, `build_date: …:BuildDate`, plus `firmware`/`rec_format` under extra. `ACQ:Count` as fast. `ACQ:Missed`, `ACQ:Batched`, `ACQ:Delay`, `ACQ:Length` and `CH<n>:Freq` as slow. Under ADR 0016, `REC` is an array channel with its own `Save:` enable once that lands. Comment the `ACQ:Length` rule. Add a T1 test that loads the configs (pattern: `tests/unit/test_aggregator_pulse_id_config.py`). | T1/T2 green |
| P5 | **T3.** If the simulated stack has no CA integer-array fast channel, add a fake `REC` there. Don't make T3 depend on rfsoc4x2. | T3 covers a fast CA array end to end |
| P6 | **T4 acceptance** on PegasusControl: board, Arduino shot counter, DG645 at 2.5 Hz, 1 h, `shot_id_source: external_pulse_id`. Checks: no BAM INCOMPLETE shots; `ACQ:Count` steps equal `PulseId_RBV` steps between re-arms; the `REC`-stamp − counter-stamp distribution recorded with its max below `guard_ms`; `ACQ:Batched` stays 0. Repeat at 10 Hz when #54 opens. | Verdict in `docs/qualification/` |

**Prerequisites for P6:**
- **Met on the rfsoc4x2 side:** a fixed address, NTP to 10.0.0.1, hardening, a tagged install (`v0.1.1`), and the DG645 output. The board has already run 16 h gap-free at 2.5 Hz.
- **Still open on the pegasus side:** the Arduino shot counter on PegasusControl (triage §5a item 1), checked to sit on the same DG645 T0 as the board.
- P1–P5 need none of these.

## 7. Decide before pegasus pins the names

Tags exist, but nothing in pegasus depends on these names yet, so they're still cheap to change: a
new rfsoc tag, then a reinstall. After the registry and configs pin them, they get expensive:

1. **The `_RBV` convention.** Pegasus marks read-back values `_RBV`. The BAM readbacks don't: `ACQ:Count`,
   `ACQ:Missed`, `ACQ:Rate`, `ACQ:Batched`, `CH<n>:I/Q`, `REC`, `INFO:*`. Either rename them in
   `ioc.py` before the tag or record the exception in the registry. Either way, the rename itself is
   rfsoc4x2's change.
2. **The prefix**, `PEG:DIAG:BAM1:` or something else.
3. **Whether a site file may exist with no `start.ps1`.** If pegasus tooling assumes every site file is
   launched, keep the host facts in `network_config.md` and next to the copied `pvs.json` instead.

## 8. Testing

**Against the real board** (read-only checks need nothing on the board side). Writes change the live
acquisition, and any setpoint write re-arms, so leave setpoints alone unless the run owner agrees.

```powershell
$env:EPICS_CA_ADDR_LIST="10.0.0.27"; $env:EPICS_CA_AUTO_ADDR_LIST="NO"; $env:EPICS_CA_MAX_ARRAY_BYTES="1000000"
python -m caproto.commandline.get PEG:DIAG:BAM1:Version PEG:DIAG:BAM1:ACQ:Rate PEG:DIAG:BAM1:ACQ:Missed
```

Expect `v0.3.0`, ≈ 2.50 and 0.

**Without the board**, from a PC on loopback (`numpy` and `caproto` installed):

```powershell
$env:EPICS_CA_ADDR_LIST="127.0.0.1"; $env:EPICS_CA_AUTO_ADDR_LIST="NO"; $env:EPICS_CA_MAX_ARRAY_BYTES="1000000"
python <rfsoc4x2 checkout>\board\ioc.py --fake --prefix PEGTEST:DIAG:BAM1: --interfaces 127.0.0.1
```

It serves every PV in `pvs.json` with synthetic 10 Hz records once `ACQ:Arm` is On. `--fake` refuses a
`PEG:` prefix on purpose, so a PC can never shadow the board. A T2 test that wants the real names has
to serve them from its own fake on the test port band, not from this script.

## 9. Don't

- Copy or fork `board/` code into pegasus, or build a Windows bundle for it.
- Treat `ACQ:Count` as the shot key.
- Change `ACQ:Length` during a recorded run.
