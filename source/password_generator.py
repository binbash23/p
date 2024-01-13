"""
20240113 jens heine <binbash@gmx.net>
Generate a pseudo random password
"""

import string
import random


def get_password(length=10) -> str:
    base_list = list(string.ascii_lowercase)
    base_list.extend(list(string.ascii_uppercase))
    base_list.extend(list(string.digits))
    base_list.extend(list(string.punctuation))

    # print("Base list: " + str(base_list))

    start_index = 0
    end_index = len(base_list)
    random_string = ""
    random.seed()

    for i in range(length):
        random.shuffle(base_list)
        random_index = random.randint(start_index, end_index - 1)
        random_string = random_string + base_list[random_index]

    return random_string
