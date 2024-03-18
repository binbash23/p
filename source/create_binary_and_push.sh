#!/bin/bash
#
# 20240225 jens heine <binbash@gmx.net>
#
set -e

git pull

#pyinstaller p.py --onefile --bootloader-ignore-signals --log-level=WARN --clean
pyinstaller p.py --onefile --bootloader-ignore-signals --clean

cp dist/p ../dist/linux/p

dist/p -V > ../dist/linux/version

git add ../dist/linux/p -f
git add ../dist/linux/version -f

git status

read -p "Press enter to commit..."

git commit -m "linux binary"

read -p "Press enter to git push..."

git push

git status

