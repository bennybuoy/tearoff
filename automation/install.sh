#!/usr/bin/env bash
# Switch the timers on:   install.sh on [HH:MM]     (daily time, default 06:30)
# Switch them off:        install.sh off
# Creates two systemd user timers: school days at HH:MM, and Sunday 16:30 for the
# week ahead. Run `loginctl enable-linger $USER` if they should fire while you
# are logged out.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNITS="$HOME/.config/systemd/user"
unit() {  # name, mode, calendar, description
  cat > "$UNITS/$1.service" <<EOF
[Unit]
Description=$4
After=network-online.target

[Service]
Type=oneshot
ExecStart=$HERE/morning.sh $2
TimeoutStartSec=20min
EOF
  cat > "$UNITS/$1.timer" <<EOF
[Unit]
Description=$4

[Timer]
OnCalendar=$3
Persistent=false

[Install]
WantedBy=timers.target
EOF
}
case "${1:-}" in
  on)
    mkdir -p "$UNITS"
    unit tearoff-daily daily "Mon..Fri ${2:-06:30}" "tearoff: morning briefing"
    unit tearoff-week week "Sun 16:30" "tearoff: week-ahead strip"
    systemctl --user daemon-reload
    systemctl --user enable --now tearoff-daily.timer tearoff-week.timer
    systemctl --user list-timers 'tearoff-*' --no-pager ;;
  off)
    systemctl --user disable --now tearoff-daily.timer tearoff-week.timer || true
    rm -f "$UNITS"/tearoff-daily.* "$UNITS"/tearoff-week.*
    systemctl --user daemon-reload; echo "timers removed" ;;
  *) echo "usage: install.sh on [HH:MM] | off"; exit 1 ;;
esac
