#!/bin/bash
set -e

/home/melvin/.local/bin/pyinstaller p.py --onefile

cp dist/lastpass ../dist/linux/p

git add ../dist/linux/p -f

git status

git commit -m "New linux binary"

