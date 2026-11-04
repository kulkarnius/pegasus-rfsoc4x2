"""Decode, check and edit the 4x2 clock-chip register files (TICS Pro hex exports, PLAN B3).

    python tools/clocks.py lmk FILE [--fclkin 10e6]       # decode + check an LMK04828 file
    python tools/clocks.py lmx FILE --fosc 245.76e6       # decode + check an LMX2594 file
    python tools/clocks.py derive STOCK_LMK OUTDIR        # write the wave-1 LMK variants

Every line's last 0x... token is a 24-bit SPI word: LMK = addr<<8 | data8, LMX = addr<<16 | data16.
Limits are from docs/lmk04828_datasheet.pdf and docs/lmx2594_datasheet.pdf. The PLL2 loop filter
values are from schematic p.16: C1 = 22 pF (C205), C2 = 2.2 nF (C204), R2 = 2.7 kOhm (R155), with
the VCXO = ABLJO-V-160 on OSCin, CLK IN SMA on CLKin0, and the Si5395 10 MHz on CLKin1.
"""
import re
import sys
from pathlib import Path
import numpy as np

HEX = re.compile(r"0x([0-9A-Fa-f]+)")
FOSC_LMK = 160e6                                  # VCXO on OSCin
LMK_VCO = {0: (2370e6, 2630e6), 1: (2920e6, 3080e6)}
LMK_CP = [100e-6, 400e-6, 1600e-6, 3200e-6]
KVCO = {0: (17e6, 27e6), 1: (17e6, 23e6)}         # Hz/V, LMK04828
LF = dict(C1=22e-12, C2=2.2e-9, R2=2.7e3)


def read(path):
    """[(line, word or None)] in file order: the order matters (resets first, LMX R0 last)."""
    out = []
    for line in Path(path).read_bytes().decode("ascii").splitlines(keepends=True):   # keep CRLF
        m = HEX.findall(line)
        out.append((line, int(m[-1], 16) if m else None))
    return out


def regs(lines, chip):
    sh, dm = (8, 0xFF) if chip == "lmk" else (16, 0xFFFF)
    am = 0x1FFF if chip == "lmk" else 0x7F
    return {(w >> sh) & am: w & dm for _, w in lines if w is not None}


def write(lines, r, chip, path):
    """Rewrite only the registers r changed: an address written twice (R0 reset, then R0) keeps both."""
    sh, am = (8, 0x1FFF) if chip == "lmk" else (16, 0x7F)
    orig, text = regs(lines, chip), []
    for line, w in lines:
        if w is not None and r[(w >> sh) & am] != orig[(w >> sh) & am]:
            new = (w & ~((1 << sh) - 1)) | r[(w >> sh) & am]
            m = list(HEX.finditer(line))[-1]
            line = line[:m.start(1)] + f"{new:0{len(m.group(1))}X}" + line[m.end(1):]
        text.append(line)
    Path(path).write_bytes("".join(text).encode("ascii"))


def bits(r, a, hi, lo):
    return (r.get(a, 0) >> lo) & ((1 << (hi - lo + 1)) - 1)


def setbits(r, a, hi, lo, v):
    m = ((1 << (hi - lo + 1)) - 1) << lo
    r[a] = (r.get(a, 0) & ~m) | ((v << lo) & m)


def lmk(r):
    """The frequency-setting fields of an LMK04828 register dict."""
    p = bits(r, 0x162, 7, 5)
    return dict(
        clkin_sel=bits(r, 0x147, 6, 4),
        clkin_r=[bits(r, 0x153 + 2 * i, 5, 0) << 8 | bits(r, 0x154 + 2 * i, 7, 0) for i in range(3)],
        pll1_n=bits(r, 0x159, 5, 0) << 8 | r.get(0x15A, 0),
        pll2_r=bits(r, 0x160, 3, 0) << 8 | r.get(0x161, 0),
        pll2_p=p if p else 8,
        dbl=bits(r, 0x162, 0, 0),
        pll2_n=bits(r, 0x166, 1, 0) << 16 | r.get(0x167, 0) << 8 | r.get(0x168, 0),
        vco=bits(r, 0x138, 6, 5),
        cp=bits(r, 0x169, 4, 3),
        dclk_div=[bits(r, 0x100 + 8 * k, 4, 0) or 32 for k in range(7)],   # DCLKout0,2,..,12
        sysref_div=bits(r, 0x13A, 4, 0) << 8 | r.get(0x13B, 0),
    )


def pll2_loop(icp, kvco, n):
    """Unity-gain frequency (Hz) and phase margin (deg) of PLL2 with the board's loop filter."""
    f = np.logspace(2, 8, 30001)
    s = 2j * np.pi * f
    c1, c2, r2 = LF["C1"], LF["C2"], LF["R2"]
    z = (1 + s * r2 * c2) / (s * (c1 + c2) * (1 + s * r2 * c1 * c2 / (c1 + c2)))
    g = icp * kvco * z / (n * s)
    i = np.argmin(abs(abs(g) - 1))
    return f[i], 180 + np.degrees(np.angle(g[i]))


def lmk_check(r, fclkin):
    """(report lines, error lines)."""
    d, rep, err = lmk(r), [], []
    if d["vco"] not in LMK_VCO:
        return [], [f"VCO_MUX={d['vco']} (external VCO): not handled"]
    pd2 = FOSC_LMK * (2 if d["dbl"] else 1) / d["pll2_r"]
    n = d["pll2_p"] * d["pll2_n"]
    vco = pd2 * n
    sel = d["clkin_sel"]
    pd1 = fclkin / d["clkin_r"][sel] if sel < 3 else float("nan")
    rep.append(f"CLKin{sel} {fclkin / 1e6:g} MHz / R {d['clkin_r'][sel] if sel < 3 else '?'} = PD1 "
               f"{pd1 / 1e6:.4g} MHz; VCXO/N1 = {FOSC_LMK / d['pll1_n'] / 1e6:.4g} MHz")
    rep.append(f"PLL2: PD {pd2 / 1e6:.6g} MHz x P {d['pll2_p']} x N {d['pll2_n']} = VCO{d['vco']} "
               f"{vco / 1e6:.6g} MHz, CP {LMK_CP[d['cp']] * 1e6:g} uA")
    for kv in KVCO[d["vco"]]:
        fc, pm = pll2_loop(LMK_CP[d["cp"]], kv, n)
        rep.append(f"  loop at Kvco {kv / 1e6:g} MHz/V: {fc / 1e3:.0f} kHz, phase margin {pm:.0f} deg")
        if pm < 45:
            err.append(f"PLL2 phase margin {pm:.0f} deg < 45 at Kvco {kv / 1e6:g} MHz/V")
    rep.append("  DCLKout0..12 (even): " + ", ".join(f"{vco / k / 1e6:.6g}" for k in d["dclk_div"])
               + f" MHz; SYSREF {vco / d['sysref_div'] / 1e6:.6g} MHz")
    lo, hi = LMK_VCO[d["vco"]]
    if not lo <= vco <= hi:
        err.append(f"VCO {vco / 1e6:g} MHz outside VCO{d['vco']} {lo / 1e6:g}-{hi / 1e6:g}")
    if pd2 > 155e6:
        err.append(f"PLL2 PD {pd2 / 1e6:g} > 155 MHz")
    if bits(r, 0x13F, 4, 4):                      # PLL2_N_CAL only matters here
        err.append("cascaded zero-delay mode (PLL2_NCLK_MUX = 1): not handled")
    if sel < 3:
        if pd1 > 40e6:
            err.append(f"PLL1 PD {pd1 / 1e6:g} > 40 MHz")
        if abs(pd1 - FOSC_LMK / d["pll1_n"]) > 1:
            err.append("PLL1: CLKin/R != VCXO/N1, PLL1 cannot lock")
    return rep, err


def lmx_check(r, fosc):
    pre, mult, rdiv = bits(r, 12, 11, 0) or 1, bits(r, 10, 11, 7) or 1, bits(r, 11, 11, 4) or 1
    dbl = bits(r, 9, 12, 12)
    pd = fosc * (2 if dbl else 1) / pre * mult / rdiv
    n = bits(r, 34, 2, 0) << 16 | r.get(36, 0)
    num, den = r.get(42, 0) << 16 | r.get(43, 0), r.get(38, 0) << 16 | r.get(39, 0)
    mash = bits(r, 44, 2, 0)
    vco = pd * (n + (num / den if mash and den else 0))
    chdiv = [2, 4, 6, 8, 12, 16, 24, 32, 48, 64, 72, 96, 128, 192, 256, 384, 512, 768][bits(r, 75, 10, 6)]
    outs = {0: vco / chdiv, 1: vco}
    fa, fb = outs.get(bits(r, 45, 12, 11)), outs.get(bits(r, 46, 1, 0))
    rep = [f"OSCin {fosc / 1e6:g} MHz -> PD {pd / 1e6:.6g} MHz x N {n}"
           + (f" + {num}/{den}" if mash else "") + f" = VCO {vco / 1e6:.6g} MHz, CHDIV {chdiv}; "
           f"OUTA {fa and fa / 1e6:.6g} MHz, OUTB {fb and fb / 1e6:.6g} MHz"]
    err = []
    if not 7.5e9 <= vco <= 15e9:
        err.append(f"VCO {vco / 1e6:g} MHz outside 7500-15000")
    if pd > (400e6 if mash == 0 else 300e6):
        err.append(f"PD {pd / 1e6:g} MHz too high for MASH_ORDER {mash}")
    if mash == 0 and n < (28 if vco <= 12.5e9 else 32):
        err.append(f"N {n} below the integer-mode minimum")
    if rdiv > 1 and fosc * (2 if dbl else 1) / pre * mult > 250e6:
        err.append("PLL_R input > 250 MHz")
    cal = bits(r, 1, 2, 0)
    if fosc / 2 ** cal > 200e6:
        err.append(f"CAL_CLK_DIV {cal}: fOSC/{2 ** cal} > 200 MHz")
    hp = bits(r, 0, 8, 7)
    if hp != (0 if pd <= 100e6 else 1 if pd <= 150e6 else 2 if pd <= 200e6 else 3):
        err.append(f"FCAL_HPFD_ADJ {hp} wrong for PD {pd / 1e6:g} MHz")
    lp = bits(r, 0, 6, 5)
    if lp != (0 if pd >= 10e6 else 1 if pd >= 5e6 else 2 if pd >= 2.5e6 else 3):
        err.append(f"FCAL_LPFD_ADJ {lp} wrong for PD {pd / 1e6:g} MHz")
    return rep, err


def lmk_pll2(r, pll2_r, p, n, vco_mux, cp=None):
    setbits(r, 0x160, 3, 0, pll2_r >> 8); r[0x161] = pll2_r & 0xFF
    setbits(r, 0x162, 7, 5, p % 8)
    setbits(r, 0x162, 0, 0, 0)
    setbits(r, 0x166, 1, 0, n >> 16); r[0x167] = (n >> 8) & 0xFF; r[0x168] = n & 0xFF
    setbits(r, 0x138, 6, 5, vco_mux)
    if cp is not None:
        setbits(r, 0x169, 4, 3, cp)


def lmk_pll1(r, sel, rdiv, n1):
    setbits(r, 0x147, 6, 4, sel)
    setbits(r, 0x153 + 2 * sel, 5, 0, rdiv >> 8); r[0x154 + 2 * sel] = rdiv & 0xFF
    setbits(r, 0x159, 5, 0, n1 >> 8); r[0x15A] = n1 & 0xFF


def derive(stock, outdir):
    """Wave-1 LMK variants: VCO 2457.6 -> 2380 MHz (PLL2 PD 6.4 -> 20 MHz: R 8, P 7, N 17), output
    dividers unchanged, so the stock /10, /20, /320 give 238, 119 and 7.4375 MHz (the SPEC §4 values).
    PLL1 keeps its phase detector near the stock 80 kHz: its loop filter is fixed and its gain goes
    as 1/N1 (stock N1 = 2000)."""
    lines = read(stock)
    out = Path(outdir)
    out.mkdir(exist_ok=True)
    variants = {"lmk_2380_clkin1_10M": None,               # PLL1 as stock: onboard 10 MHz, PD1 80 kHz
                "lmk_2380_clkin0_10M": (0, 125, 2000),     # 10 MHz on the CLK IN SMA, PD1 80 kHz
                "lmk_2380_clkin0_119M": (0, 1190, 1600),   # PD1 100 kHz
                "lmk_2380_clkin0_79M33": (0, 952, 1920)}   # master/36 = 238/3 MHz, PD1 83.3 kHz
    for name, pll1 in variants.items():
        r = regs(lines, "lmk")
        lmk_pll2(r, 8, 7, 17, 0, cp=3)
        if pll1:
            lmk_pll1(r, *pll1)
        write(lines, r, "lmk", out / f"{name}.txt")
        print(out / f"{name}.txt")


def demo():
    r = {}
    lmk_pll2(r, 8, 7, 17, 0, cp=3)
    lmk_pll1(r, 0, 952, 1920)
    for k in range(7):
        r[0x100 + 8 * k] = 12
    r[0x13A], r[0x13B] = 1, 64                    # 320
    d = lmk(r)
    assert (d["pll2_r"], d["pll2_p"], d["pll2_n"], d["vco"], d["clkin_r"][0], d["pll1_n"]) == (8, 7, 17, 0, 952, 1920)
    rep, err = lmk_check(r, 2856e6 / 36)
    assert not err, err
    assert "2380 MHz" in rep[1] and "7.4375" in rep[-1], rep
    lmk_pll1(r, 0, 952, 2000)
    assert lmk_check(r, 2856e6 / 36)[1], "PLL1 mismatch not caught"
    x = {12: 1, 10: 1 << 7, 11: 1 << 4, 34: 0, 36: 34, 44: 0, 75: 0, 45: 1 << 11, 46: 0, 0: 3 << 7, 1: 1}
    rep, err = lmx_check(x, 238e6)               # SPEC §4: 238 MHz -> 8092 MHz integer-N, CAL_CLK_DIV 1
    assert not err and "VCO 8092" in rep[0] and "OUTA 8092" in rep[0], (rep, err)


if __name__ == "__main__":
    demo()
    a = sys.argv[1:]
    if not a:
        print("self-check OK")
    elif a[0] == "derive":
        derive(a[1], a[2])
    else:
        opt = dict(zip(a[2::2], map(float, a[3::2])))
        lines = read(a[1])
        if a[0] == "lmk":
            rep, err = lmk_check(regs(lines, "lmk"), opt.get("--fclkin", 10e6))
        else:
            rep, err = lmx_check(regs(lines, "lmx"), opt["--fosc"])
        print("\n".join(rep + [f"ERROR: {e}" for e in err] or ["(no frequency registers found)"]))
        sys.exit(1 if err else 0)
