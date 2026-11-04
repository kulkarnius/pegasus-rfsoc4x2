#!/bin/bash
# Run on the board as root, from the unpacked bundle:  sudo bash board/install.sh [--rollback]
# Installs to /opt/bam/<version>, repoints /opt/bam/current (old one -> /opt/bam/previous), restarts bam-ioc.
# Site values are in /etc/bam-ioc.env (never overwritten). Setpoints live in /var/lib/bam-ioc.
set -euo pipefail

point() {  # point <link> <target>: atomic repoint
    ln -sfn "$2" "$1.new" && mv -T "$1.new" "$1"
}

if [ "${1:-}" = "--rollback" ]; then
    cur=$(readlink /opt/bam/current); prev=$(readlink /opt/bam/previous)
    point /opt/bam/current "$prev"; point /opt/bam/previous "$cur"
    systemctl restart bam-ioc
    echo "rolled back: $cur -> $prev"
    systemctl --no-pager status bam-ioc | head
    exit 0
fi

cd "$(dirname "$0")/.."
sha256sum -c --quiet MANIFEST.sha256 || { echo "MANIFEST.sha256 check failed; aborting" >&2; exit 1; }
VER=$(head -n1 VERSION)
DEST=/opt/bam/$VER

# First run: the site file. Done before the copy so the rerun doesn't trip on an existing $DEST.
if [ ! -e /etc/bam-ioc.env ]; then
    cp board/bam-ioc.env.example /etc/bam-ioc.env
    echo "Created /etc/bam-ioc.env: edit BAM_PREFIX, BAM_IP, EPICS_CAS_INTF_ADDR_LIST (and the beacon list), then rerun." >&2
    exit 1
fi
if grep -q XXX /etc/bam-ioc.env; then echo "/etc/bam-ioc.env still has a placeholder (XXX); edit and rerun" >&2; exit 1; fi

[ ! -e "$DEST" ] || { echo "$DEST exists; refusing to overwrite" >&2; exit 1; }
mkdir -p /opt/bam && cp -a "$PWD" "$DEST"

# Offline wheels into the PYNQ venv. (The service itself sources /etc/profile.d/boardname.sh:
# xrfclk reads $BOARD at import, which sudo / non-login shells lack.)
set +u; source /etc/profile.d/pynq_venv.sh; set -u
pip install --no-index --find-links "$DEST/fw/wheels" qick caproto

cp "$DEST/board/bam-ioc.service" /etc/systemd/system/
mkdir -p /etc/systemd/timesyncd.conf.d
cp "$DEST/board/timesyncd-pegasus.conf" /etc/systemd/timesyncd.conf.d/pegasus.conf
systemctl enable systemd-time-wait-sync.service
systemctl restart systemd-timesyncd
mkdir -p /var/lib/bam-ioc

if [ -L /opt/bam/current ]; then point /opt/bam/previous "$(readlink /opt/bam/current)"; fi
point /opt/bam/current "$DEST"
systemctl daemon-reload
systemctl enable bam-ioc
systemctl restart bam-ioc
systemctl --no-pager status bam-ioc | head
echo "From the PC: EPICS_CA_ADDR_LIST=<BAM_IP> EPICS_CA_AUTO_ADDR_LIST=NO python -m caproto.commandline.get <BAM_PREFIX>Version   (expect $VER)"
