#!/bin/python3
#
# 20230805 jens heine <binbash@gmx.net>
#
# Password/account database for managing all your accounts
#
import sys
import time

DEFAULT_DELAY: float = 0.008
DELAY_ENABLED: bool = True


def print_slow(text: str, delay: float = DEFAULT_DELAY):
    if not DELAY_ENABLED:
        print(text)
        return

    for char in text:
        # print(char, end='')
        sys.stdout.write(char)
        sys.stdout.flush()
        try:
            time.sleep(delay)
        except KeyboardInterrupt as ke:
            return
    print()


def set_delay_enabled(enabled: bool):
    global DELAY_ENABLED
    DELAY_ENABLED = enabled
