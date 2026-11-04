"""Rank sample rates on the 119 MHz grid (2856/24) by how cleanly the
machine tones alias. Everything here is commensurate with 2.856 GHz.

    python tools/freqplan.py [adc|dac]
"""
import sys

F0 = 119e6                               # 2856/24
FCAV = 4758.4e6                          # BAM cavity f0, fitted (BAM\Sims\bam_constants.m)
TONES = {"2856": 2856e6, "4760": FCAV,   # key kept as "4760": the nominal design value
         "2856x2": 5712e6, "2856x3": 8568e6, "4760x2": 2 * FCAV}
# Gen3 (XCZU48DR) limits; DAC lower bound is a practical choice, not a hard limit
LIMITS = {"adc": (1.0e9, 5.0e9), "dac": (2.0e9, 9.85e9)}


def alias(f, fs):
    """(Nyquist zone, apparent frequency in [0, fs/2])."""
    zone = int(f // (fs / 2)) + 1
    r = f % fs
    return zone, min(r, fs - r)


def score(fs):
    """Worst-case spacing (Hz) of any tone alias from DC, fs/2, fs/4 and every other alias."""
    a = {k: alias(f, fs)[1] for k, f in TONES.items()}
    keep_out = [0, fs / 2, fs / 4]       # fs/4: interleaving-spur and DDC-image hot spot
    d = [abs(x - k) for x in a.values() for k in keep_out]
    v = list(a.values())
    d += [abs(v[i] - v[j]) for i in range(len(v)) for j in range(i + 1, len(v))]
    return min(d)


def table(kind, top=10):
    lo, hi = LIMITS[kind]
    rates = [n * F0 for n in range(int(lo // F0) + 1, int(hi // F0) + 1)]
    rows = sorted(rates, key=score, reverse=True)[:top]
    out = [f"{'fs (MHz)':>9} {'n':>3} {'margin':>7}  " +
           "  ".join(f"{k}:z/alias" for k in ("2856", "4760"))]
    for fs in rows:
        z1, a1 = alias(TONES["2856"], fs)
        z2, a2 = alias(TONES["4760"], fs)
        out.append(f"{fs/1e6:9.0f} {round(fs/F0):3d} {score(fs)/1e6:7.0f}  "
                   f"z{z1}/{a1/1e6:6.0f}     z{z2}/{a2/1e6:6.0f}")
    return "\n".join(out)


if __name__ == "__main__":
    # self-check: 4.76 GHz at fs = 3.808 GHz is 3rd zone, aliased to 952 MHz = fs/4
    assert alias(4760e6, 3808e6) == (3, 952e6)
    assert score(3808e6) < 2e6           # cavity lands 1.6 MHz off fs/4 -> must rank worst
    print(table(sys.argv[1] if len(sys.argv) > 1 else "adc"))
