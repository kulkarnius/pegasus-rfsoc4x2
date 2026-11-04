# Handoff: the BAM RFSoC digitizer into pegasus_epics_upgrade

From `C:\fpga\rfsoc4x2` to the `pegasus_epics_upgrade` repo, 2026-11-04.
This is part P of [PLAN.md](PLAN.md) "Wave 3", written so a session in the pegasus repo can
work from it alone. Follow that repo's own `CLAUDE.md` (worktree, papercuts, T1/T2 before a PR).

## 1. What the device is

A RealDigital RFSoC 4x2 that replaces a 20 GS/s scope on the BAM (beam arrival monitor) cavity. On each
trigger it captures one window from 3 ADC readouts (master 2856 MHz, cavity 4758.4 MHz, photodiode)
as decimated I/Q at 552.96 MS/s, and it can play 2 DAC outputs. It runs PYNQ v3.0.1 (Linux, aarch64)
with the stock QICK tProc-v2 firmware.

The IOC is `board/ioc.py`: Python, **caproto, CA only, no PVA**. It runs **on the board** under
systemd, because it drives the FPGA directly through QICK. Estimation (fits, phase) is not on the
board. Analysis code reads the records.

Bench status: 10⁴ shots at 10 Hz with none missed, on a function generator. The beamline DG645 at
2.5 Hz is next, and so are the static IP and NTP on the board (rfsoc PLAN B1–B4). **The board is not
on the lab network as a production host yet.** Until it is, everything below is desk work against
`ioc.py --fake`.

**There is no tag yet.** The first one, `v0.1.0`, is cut when this work is committed in rfsoc4x2. Until
then, `pvs.json` is the working-tree file and `Version` serves `dev`, so pin to `v0.1.0` once it exists.

## 2. The contract

| What | Owner | Where it lives | Check |
|---|---|---|---|
| PV leaf names, types, access, element counts | rfsoc4x2 (`board/ioc.py`) | `board/pvs.json`, generated from the dict the server serves. `ioc.py --check` fails if it's stale. | Pegasus copies it from a **tagged** rfsoc version, and its registry generator reads the copy (P2). |
| PV prefix | pegasus (registry allocation) | Proposed `PEG:DIAG:BAM1:` (P2 decides). On the board it lives in `/etc/bam-ioc.env` as `BAM_PREFIX`; commissioning uses `PEGTEST:DIAG:BAM1:`, the same `PEG:=PEGTEST:` convention as #219. | `caget <prefix>Version` |
| Version | rfsoc4x2 | A git tag. `tools/bundle.py` stamps it into the bundle's `VERSION` file, and the IOC serves it as `Version` (plain string) and `BuildDate` (UTC ISO-8601). Outside a bundle it serves `dev`. | Pin the tag next to the copied `pvs.json`; preflight compares it with `caget …:Version`. |
| `REC` layout | rfsoc4x2 | `INFO:RecFormat` (now `1`). Any layout change bumps it. The parser is `tools/record.py` in rfsoc4x2. | Record it as identity. |
| Deployment | rfsoc4x2 | `peg-bam-ioc/<version>/` bundle with `MANIFEST.sha256`. `board/install.sh` installs it to `/opt/bam/<version>`, sets the `current` symlink and runs systemd `bam-ioc`; `--rollback` reverts. Setpoints persist in `/var/lib/bam-ioc/state.json`. | Pegasus does **not** build, install or start it. |
| Host facts (IP, port, prefix, pinned version) | pegasus | Wherever pegasus keeps host facts (P1/P3) | — |

**Changing a PV later:** edit `ioc.py` in rfsoc4x2, regenerate `pvs.json`, and tag. Then open a pegasus
PR that updates the copy and the pin, plus `pv_registry.md`. The registry tests stay red until the
docs cover every served name, the same rule as pegasus's own IOCs.

## 3. What the IOC serves (57 PVs, `board/pvs.json`)

The authority is `C:\fpga\rfsoc4x2\board\pvs.json`; read it rather than this summary. `<n>` = readout 0–2,
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
  ms, but it hasn't been measured. P6 measures it against the shot counter. It is only meaningful
  once the board's NTP points at 10.0.0.1 (rfsoc PLAN B3). The service waits for `time-sync.target`.
- **`ACQ:Batched`** counts records that came out of one poll together, so they share a timestamp and a
  timestamp-binning recorder could misassign them. It should stay 0; treat a rise as a fault.
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
| Host | RFSoC 4x2, PYNQ v3.0.1 (Ubuntu-based, aarch64). Hostname and static IP **not chosen yet** (rfsoc B2; today DHCP, last seen 10.0.0.151). |
| CA server | Port **5064** (the only IOC on that host, so no ladder rung). Bound to the board's IP (`EPICS_CAS_INTF_ADDR_LIST`), beacons to `10.0.0.255`. **No PVA.** |
| Clients | The production env's `EPICS_CA_ADDR_LIST=10.0.0.255` broadcast already reaches port 5064. Add a unicast `<ip>` entry if pegasus prefers explicit entries. |
| Time | `systemd-timesyncd` → `10.0.0.1`, no fallback (`board/timesyncd-pegasus.conf`). |
| Trigger | Its own DG645 output from the same T0 as the shot counter's fan-out, so one DG645 cycle gives one record and one `PulseId`. |

## 6. Work in pegasus_epics_upgrade

| # | Task | Done when |
|---|---|---|
| P1 | **Issue + ADR 0017, "an IOC that runs on its instrument."** Record that the IOC's code, bundle and install live in rfsoc4x2, outside pegasus's bundle, install and supervisor system. Pegasus owns the name, the host facts and the recording, and its tests cover the copied `pvs.json`, the registry and the configs, never the IOC. Contrast with ADR 0010: the counter board's IOC runs on PegasusControl, while this is the first non-Windows IOC host. Add the RFSoC and the DG645 to `docs/planning/03_DEVICE_INVENTORY.md`, where the trigger source is `UNKNOWN`. Record in the triage doc §2 whether the BAM is in v1.0. | ADR merged, inventory rows in |
| P2 | **Registry.** Allocate the prefix (proposed `PEG:DIAG:BAM1:`: a beam diagnostic, like `PEG:DIAG:ICT1:`, with `PEG:RF:` left to the LLRF IOC). Copy `pvs.json` in with its pinned tag (location is your call, e.g. `iocs/external/bam/`). Add `IocInfo("bam", ("PEG:DIAG:BAM1:",), <role>)` and a `parse_bam()` that maps the JSON to `PVEntry` (`double`→`ai`/`ao`, `long`→`longin`/`longout`, `enum`→`mbbi`/`mbbo`, `string`→`stringin`, `char`→`waveform`, waveforms by `count` > 1; record types are your convention to settle). Add a `pv_registry.md` section, then regenerate. | `python -m common.pv_registry check` and the T1 registry tests pass |
| P3 | **Network and client env.** Host row in `docs/network_config.md` and in the README host diagram. Add `EPICS_CA_MAX_ARRAY_BYTES=1000000` to `config/epics_env.ps1` and `epics_env_test.ps1`. | `caget <prefix>REC` from PegasusControl and the workstation using only the repo's env scripts (against `--fake` until the board is up: see §7) |
| P4 | **Aggregator channels** in the production configs (the `aggregator_hybrid_*.yaml` in use and `aggregator_pulse_id.yaml`). `REC` as `ca`, `class: fast`, identity `version: …:Version`, `build_date: …:BuildDate`, plus `firmware`/`rec_format` under extra. `ACQ:Count` as fast. `ACQ:Missed`, `ACQ:Batched`, `ACQ:Delay`, `ACQ:Length` and `CH<n>:Freq` as slow. Under ADR 0016, `REC` is an array channel with its own `Save:` enable once that lands. Comment the `ACQ:Length` rule. Add a T1 test that loads the configs (pattern: `tests/unit/test_aggregator_pulse_id_config.py`). | T1/T2 green |
| P5 | **T3.** If the simulated stack has no CA integer-array fast channel, add a fake `REC` there. Don't make T3 depend on rfsoc4x2. | T3 covers a fast CA array end to end |
| P6 | **T4 acceptance** on PegasusControl: board, Arduino shot counter, DG645 at 2.5 Hz, 1 h, `shot_id_source: external_pulse_id`. Checks: no BAM INCOMPLETE shots; `ACQ:Count` steps equal `PulseId_RBV` steps between re-arms; the `REC`-stamp − counter-stamp distribution recorded with its max below `guard_ms`; `ACQ:Batched` stays 0. Repeat at 10 Hz when #54 opens. | Verdict in `docs/qualification/` |

**Prerequisites for P6, from rfsoc4x2:** the board on its static IP with NTP (B2–B4), installed from a
tagged bundle, on its DG645 output. P1–P5 need none of these.

## 7. Decide before the first tag

These are cheap to settle now and expensive after the registry and configs pin the names:

1. **The `_RBV` convention.** Pegasus marks read-back values `_RBV`. The BAM readbacks don't: `ACQ:Count`,
   `ACQ:Missed`, `ACQ:Rate`, `ACQ:Batched`, `CH<n>:I/Q`, `REC`, `INFO:*`. Either rename them in
   `ioc.py` before the tag or record the exception in the registry. Either way, the rename itself is
   rfsoc4x2's change.
2. **The prefix**, `PEG:DIAG:BAM1:` or something else.
3. **Whether a site file may exist with no `start.ps1`.** If pegasus tooling assumes every site file is
   launched, keep the host facts in `network_config.md` and next to the copied `pvs.json` instead.

## 8. Testing without the board

From a PC on loopback (`numpy` and `caproto` installed):

```powershell
$env:EPICS_CA_ADDR_LIST="127.0.0.1"; $env:EPICS_CA_AUTO_ADDR_LIST="NO"; $env:EPICS_CA_MAX_ARRAY_BYTES="1000000"
python C:\fpga\rfsoc4x2\board\ioc.py --fake --prefix PEGTEST:DIAG:BAM1: --interfaces 127.0.0.1
```

It serves every PV in `pvs.json` with synthetic 10 Hz records once `ACQ:Arm` is On. `--fake` refuses a
`PEG:` prefix on purpose, so a PC can never shadow the board. A T2 test that wants the real names has
to serve them from its own fake on the test port band, not from this script.

## 9. Don't

- Copy or fork `board/` code into pegasus, or build a Windows bundle for it.
- Treat `ACQ:Count` as the shot key.
- Change `ACQ:Length` during a recorded run.
