#!/bin/bash
# Read-only board probe, no root needed (PLAN wave 3 B2-B4): what install.sh and bam-ioc.service assume.
#   ssh -i ~/.ssh/claude_bench xilinx@<ip> 'bash -s' < tools/board_probe.sh
s() { echo "== $1"; shift; "$@" 2>&1 | head -n 20; }
s os        grep -E '^(PRETTY_NAME|VERSION_ID)=' /etc/os-release
s kernel    uname -rm
s ip        ip -4 -br addr
s netcfg    bash -c 'ls /etc/netplan /etc/network/interfaces.d; cat /etc/network/interfaces /etc/network/interfaces.d/*'
s ntp10     python3 -c "import socket,struct,time; s=socket.socket(2,2); s.settimeout(2); t0=time.time(); s.sendto(b'\x1b'+47*b'\0',('10.0.0.1',123)); d=s.recv(48); t3=time.time(); t=struct.unpack('!I',d[40:44])[0]-2208988800+struct.unpack('!I',d[44:48])[0]/2**32; print('10.0.0.1 answers; offset %.1f ms, rtt %.1f ms' % ((t-(t0+t3)/2)*1e3, (t3-t0)*1e3))"
s dhcp      bash -c 'ls /var/lib/dhcp/ 2>/dev/null; ls /run/systemd/netif/leases 2>/dev/null; nmcli -t dev 2>/dev/null'
s time      timedatectl
s ntp       timedatectl show-timesync --all
s waitsync  systemctl list-unit-files systemd-time-wait-sync.service systemd-timesyncd.service
s rtc       ls /dev/rtc*
s venv      bash -c 'source /etc/profile.d/boardname.sh && source /etc/profile.d/pynq_venv.sh && which python3 && python3 -V && python3 -c "import numpy, qick, caproto; print(numpy.__version__, qick.__version__, caproto.__version__)"'
s profile   ls /etc/profile.d/boardname.sh /etc/profile.d/pynq_venv.sh /etc/profile.d/xrt_setup.sh
s jupyter   systemctl is-enabled jupyter.service
s bamioc    systemctl status --no-pager bam-ioc.service
s opt       ls -la /opt/bam /etc/bam-ioc.env /var/lib/bam-ioc
s home      ls /home/xilinx/bam
s disk      df -h / /home
s sudo      sudo -n true
s ufw       bash -c 'command -v ufw && ufw status 2>&1'
s clock     date -u +%Y-%m-%dT%H:%M:%S.%NZ
