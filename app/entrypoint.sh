#!/bin/sh
set -eu
# Railway mounts volumes as root. Drop privileges before starting the desktop.
mkdir -p /data/profile
chown -R browser:browser /data/profile
exec gosu browser python3 /app/runtime.py
