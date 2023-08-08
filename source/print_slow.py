#!/bin/python3
#
# 20230805 jens heine <binbash@gmx.net>
#
# Password/account database for managing all your accounts
#
import time
import sys

DEFAULT_DELAY = 0.008
#DEFAULT_DELAY = 0.05

def print_slow(text: str, delay: int = DEFAULT_DELAY):
    for char in text:
        # print(char, end='')
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()
