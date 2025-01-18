#!/bin/bash
#
# 20250118 jens heine <binbash@gmx.net>
#
set -e

cd ..
python3 -m venv venv
source venv/bin/activate
python3 -m pip install -r source/requirements.txt
cd -

echo
echo "!!!  IMPORTANT  !!!"
echo ">>> No execute the following command to activate the virtual environment:"
echo ">>> source ../venv/bin/activate"
