#!/bin/python3
#
# 20230906 jens heine <binbash@gmx.net>
#
# Password/account database for managing all your accounts
#
import os
# import subprocess
import sys

new_filename_win = 'p.exe_latest'
old_filename_win = 'p.exe'
new_filename_linux = 'p_latest'
old_filename_linux = 'p'


def main():
    old_filename = old_filename_win
    new_filename = new_filename_win
    if os.path.exists(old_filename):
        print("Deleting old file")
        os.remove(old_filename)
    print("Renaming " + new_filename + " to " + old_filename + "...")
    os.rename(new_filename, old_filename)
    print("Starting p...")
    # subprocess.Popen(old_filename, shell=True)
    os.startfile(old_filename)
    print("Exiting updater")
    sys.exit(0)


if __name__ == '__main__':
    main()