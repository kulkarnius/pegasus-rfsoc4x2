"""Build the board bundle: python tools/bundle.py [--allow-dirty] [--out artifacts/bundles]

Output: <out>/peg-bam-ioc/<version>/peg-bam-ioc-<version>/ and the same as a .zip.
On the board: unzip, cd peg-bam-ioc-<version>, `sudo bash board/install.sh` (run via bash:
zip permissions from Windows are unreliable). Stdlib only; `--check` runs a self-test.
"""
import argparse, datetime, hashlib, shutil, subprocess, sys, tempfile, zipfile
from pathlib import Path

NAME = "peg-bam-ioc"
FW = ["fw/qick_4x2.bit", "fw/qick_4x2.hwh", "fw/soccfg.json"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def verify(root, sums="SHA256SUMS"):
    """Python `sha256sum -c`: return the list of problems (empty = all OK)."""
    bad = []
    for line in Path(root, sums).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, path = line.split(" ", 1)
        path = path[1:]  # drop the ' ' or '*' mode flag
        p = Path(root, path)
        if not p.is_file():
            bad.append(f"missing: {path}")
        elif sha(p) != digest:
            bad.append(f"MISMATCH: {path}")
    return bad


def build(root, out, version, board_files):
    root, out = Path(root), Path(out)
    vdir = out / NAME / version
    if vdir.exists():
        sys.exit(f"{vdir} exists; refusing to overwrite")
    top = vdir / f"{NAME}-{version}"
    top.mkdir(parents=True)
    rels = board_files + FW + [f"fw/wheels/{w.name}" for w in sorted(root.glob("fw/wheels/*.whl"))]
    for rel in rels:
        dst = top / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / rel, dst)  # bytes as they are
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (top / "VERSION").write_bytes(f"{version}\n{now}\n".encode())
    files = sorted(p.relative_to(top).as_posix() for p in top.rglob("*") if p.is_file())
    (top / "MANIFEST.sha256").write_bytes(
        "".join(f"{sha(top / f)} *{f}\n" for f in files).encode())
    zpath = vdir / f"{NAME}-{version}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(top.rglob("*")):
            if p.is_file():
                z.write(p, f"{NAME}-{version}/{p.relative_to(top).as_posix()}")
    return top, zpath


def git(*a):
    return subprocess.run(["git", *a], capture_output=True, text=True, check=True, encoding="utf-8").stdout.strip()


def _check():
    with tempfile.TemporaryDirectory() as t:
        root = Path(t, "repo")
        files = {"board/ioc.py": b"x\n", "fw/qick_4x2.bit": b"\0\1", "fw/qick_4x2.hwh": b"h",
                 "fw/soccfg.json": b"{}", "fw/wheels/a-1-py3-none-any.whl": b"w"}
        for f, b in files.items():
            Path(root, f).parent.mkdir(parents=True, exist_ok=True)
            Path(root, f).write_bytes(b)
        Path(root, "SHA256SUMS").write_text(
            "".join(f"{sha(root / f)} *{f}\n" for f in files if f.startswith("fw/")))
        assert verify(root) == []
        top, z = build(root, Path(t, "out"), "v0-test", ["board/ioc.py"])
        assert verify(top, "MANIFEST.sha256") == []
        assert top.joinpath("VERSION").read_text().splitlines()[0] == "v0-test"
        assert f"{NAME}-v0-test/MANIFEST.sha256" in zipfile.ZipFile(z).namelist()
        (top / "board/ioc.py").write_bytes(b"tampered\n")
        assert verify(top, "MANIFEST.sha256") == ["MISMATCH: board/ioc.py"]
        (root / "fw/qick_4x2.bit").write_bytes(b"other")
        assert verify(root) == ["MISMATCH: fw/qick_4x2.bit"]
    print("bundle self-check OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-dirty", action="store_true")
    ap.add_argument("--out", default="artifacts/bundles")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        return _check()
    root = Path(__file__).resolve().parent.parent
    version = git("-C", str(root), "describe", "--tags", "--always", "--dirty")
    if version.endswith("-dirty") and not a.allow_dirty:
        sys.exit(f"dirty tree ({version}); commit or pass --allow-dirty")
    bad = verify(root)
    if bad:
        sys.exit("SHA256SUMS check failed:\n  " + "\n  ".join(bad))
    board = git("-C", str(root), "ls-files", "board").splitlines()
    if (root / "board/pvs.json").is_file() and "board/pvs.json" not in board:
        board.append("board/pvs.json")
    top, z = build(root, Path(a.out), version, board)
    print(f"{top}\n{z}  ({z.stat().st_size / 1e6:.1f} MB)")
    print("On the board: unzip, cd into the folder, `sudo bash board/install.sh`")


if __name__ == "__main__":
    main()
