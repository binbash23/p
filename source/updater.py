#!/bin/python3
#
# 20230906 jens heine <binbash@gmx.net>
#
# Password/account database for managing all your accounts
#
import os
import subprocess
import sys
import optparse
import time

VERSION = "[updater] by Jens Heine <binbash@gmx.net> version: 2023.09.07"


# new_filename_win = 'p.exe_latest'
# old_filename_win = 'p.exe'
# new_filename_linux = 'p_latest'
# old_filename_linux = 'p'


def main():
    print()
    print(VERSION)
    print()
    time.sleep(3)

    parser = optparse.OptionParser()
    parser.add_option("-V", "--version", action="store_true", dest="version", default=False,
                      help="Show updater version info")
    parser.add_option("-D", "--database", action="store", dest="database",
                      help="Set database filename.")
    parser.add_option("-o", "--old_filename", action="store", dest="old_filename",
                      help="Set old filename.")
    parser.add_option("-n", "--new_filename", action="store", dest="new_filename",
                      help="Set new filename.")

    (options, args) = parser.parse_args()

    if options.version:
        # Version is printed per default on startup
        # print(VERSION)
        sys.exit(0)

    database_filename = 'p.db'
    if options.database is not None and options.database != "":
        database_filename = options.database
    absolute_filename = os.path.abspath(database_filename)
    print("Database filename : " + absolute_filename)

    old_filename = "p.exe"
    if options.old_filename is not None and options.old_filename != "":
        old_filename = options.old_filename
    print("Old filename      : " + old_filename)

    new_filename = "p.exe_latest"
    if options.new_filename is not None and options.new_filename != "":
        new_filename = options.new_filename
    print("New filename      : " + new_filename)

    if old_filename == "" \
            or new_filename == "" \
            or not os.path.exists(old_filename) \
            or not os.path.exists(new_filename):
        print("Error: old and new filename must be set and the files must exist!")
        time.sleep(10)
        sys.exit(1)

    if os.path.exists(old_filename):
        print("Deleting old file")
        os.remove(old_filename)
    print("Renaming " + new_filename + " to " + old_filename + "...")
    os.rename(new_filename, old_filename)
    # print("Starting p with database: " + absolute_filename + "...")
    print("Starting p...")
    # subprocess.Popen(old_filename, shell=True)
    time.sleep(3)
    os.startfile(old_filename)
    # subprocess.Popen([old_filename + " -D " + absolute_filename])
    print("Exiting updater")
    sys.exit(0)


if __name__ == '__main__':
    main()
