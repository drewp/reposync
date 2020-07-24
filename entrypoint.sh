#!/bin/sh

echo "nameserver 10.43.0.10 8.8.8.8" > /etc/resolv.conf

exec python3.8 hg_status.py -v