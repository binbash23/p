#!/bin/bash
set -e

#pyinstaller p.py --onefile --bootloader-ignore-signals --log-level=WARN --clean
pyinstaller p.py --onefile --bootloader-ignore-signals --clean

cp dist/p ../dist/linux/p

git add ../dist/linux/p -f

git status

git commit -m "linux binary"

read -p "Press enter to git push..."

git push

