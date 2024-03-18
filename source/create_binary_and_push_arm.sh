#!/bin/bash
#
# 20240225 jens heine <binbash@gmx.net>
#
set -e

git pull

#pyinstaller p.py --onefile --bootloader-ignore-signals --log-level=WARN --clean
pyinstaller p.py --onefile --bootloader-ignore-signals --clean

cp dist/p ../dist/arm64/p

dist/p -V > ../dist/arm64/version

git add ../dist/arm64/p -f
git add ../dist/arm64/version -f

git status

read -p "Press enter to commit..."

git commit -m "arm64/raspberry binary"

read -p "Press enter to git push..."

git push

git status

