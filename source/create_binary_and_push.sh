#!/bin/bash
set -e

/home/melvin/.local/bin/pyinstaller p.py --onefile --bootloader-ignore-signals --log-level=WARN

cp dist/p ../dist/linux/p

git add ../dist/linux/p -f

git status

git commit -m "linux binary"

