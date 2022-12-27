#!/bin/python3
#
# 20221213 jens heine <binbash@gmx.net>
#
# Password/account database for managing all your accounts
#

import p
import pdatabase
#import pyperclip3
import clipboard
import datetime

class ShellCommand:
    command = ""
    arguments = [""]
    synopsis = ""
    description = ""

    def __init__(self, command="", synopsis="", description=""):
        self.command = command
        self.synopsis = synopsis
        self.description = description

    def __str__(self):
        return self.command + " - Synopsis: " + self.synopsis + " - Description: " + self.description


# SHELL_COMMANDS = ( ShellCommand(command="version", synopsis="version", description="show p program version") )
SHELL_COMMANDS = [
    ShellCommand("add", "add", "Add a new account"),
    ShellCommand("changepassword", "changepassword", "Change password of current database"),
    ShellCommand("copypassword", "copypassword UUID", "Copy password from UUID to clipboard"),
    ShellCommand("delete", "delete UUID", "Delete account with UUID"),
    ShellCommand("edit", "edit UUID", "Edit account with UUID"),
    ShellCommand("exit", "exit", "Quit shell"),
    ShellCommand("help", "help", "Show help for all shell commands"),
    ShellCommand("idletime", "idletime", "Show idletime in seconds after last command"),
    ShellCommand("invalidate", "invalidate UUID", "Invalidate account with UUID"),
    ShellCommand("list", "list", "List all accounts"),
    ShellCommand("merge2dropbox", "merge2dropbox", "Merge local database with dropbox database copy"),
    ShellCommand("merge2file", "merge2file FILENAME",
                 "Merge local database with another database identified by FILENAME"),
    ShellCommand("merge2lastknownfile", "merge2lastknownfile",
                 "Merge local database with the last known merge database"),
    ShellCommand("quit", "quit", "Quit shell"),
    ShellCommand("revalidate", "revalidate UUID", "Revalidate account with UUID"),
    ShellCommand("search", "search SEARCHSTRING", "Search SEARCHSTRING in account database"),
    ShellCommand("setdropboxapplicationuuid", "setdropboxapplicationuuid UUID",
                 "Set the dropbox application account uuid in configuration"),
    ShellCommand("setdropboxtokenuuid", "setdropboxtokenuuid UUID",
                 "Set the dropbox token account uuid in configuration"),
    ShellCommand("shadowpasswords", "shadowpasswords on/off", "Shadow passwords true or false"),
    ShellCommand("showconfig", "showconfig", "Show current configuration"),
    ShellCommand("showinvalidated", "showinvalidated on/off", "Show invalidated accounts true or false"),
    ShellCommand("status", "status", "Show configuration and database status."),
    ShellCommand("timeout", "timeout MINUTES", "Set the maximum shell inactivity timeout to MINUTES"),
    ShellCommand("verbose", "verbose on/off", "Show verbose account infos true or false"),
    ShellCommand("version", "version", "Show program version info")
]

DEFAULT_SHELL_MAX_IDLE_TIMEOUT_MIN = 30

def expand_string_2_shell_command(string: str) -> ShellCommand:
    if string is None or string.strip() == "":
        return None
    tokens = string.split()
    first_token = tokens[0]
    for shell_command in SHELL_COMMANDS:
        # print("x" + first_token + "x in x" + shell_command.command + "x")
        # if first_token.lower() in shell_command.command.lower():
        if shell_command.command.startswith(first_token):
            # print("xx-" + str(string[len(tokens[0]) + 1:len(string)]) + "-")
            # print("--" + str(len(tokens)))
            if len(tokens) == 1:
                shell_command.arguments = [tokens[0]]
            else:
                shell_command.arguments = [tokens[0], string[len(tokens[0]) + 1:len(string)]]
            return shell_command
    return None


def start_p_shell(p_database: pdatabase.PDatabase):
    print("Shell mode enabled. Use 'quit' or strg-c to quit or help for more infos.")
    shell_max_idle_minutes_timeout = pdatabase.get_attribute_value_from_configuration_table(
        p_database.database_filename,
        pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_SHELL_MAX_IDLE_TIMEOUT_MIN)
    if not shell_max_idle_minutes_timeout.isnumeric() \
            or shell_max_idle_minutes_timeout is None \
            or shell_max_idle_minutes_timeout == "":
        shell_max_idle_minutes_timeout = DEFAULT_SHELL_MAX_IDLE_TIMEOUT_MIN
        pdatabase.set_attribute_value_in_configuration_table(
            p_database.database_filename,
            pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_SHELL_MAX_IDLE_TIMEOUT_MIN, shell_max_idle_minutes_timeout)
    user_input = ""
    while user_input != "quit":
        last_activity_date = datetime.datetime.now()
        try:
            user_input = input("DB: " + p_database.database_filename + "> ")
        except KeyboardInterrupt:
            # user_input = "quit"
            return
        now_date = datetime.datetime.now()
        time_diff = now_date - last_activity_date
        if shell_max_idle_minutes_timeout != 0 and\
                int(time_diff.total_seconds() / 60) > int(shell_max_idle_minutes_timeout):
            print("Exiting shell due to idle timeout (" + str(shell_max_idle_minutes_timeout) + " min)")
            return
        shell_command = expand_string_2_shell_command(user_input)
        if shell_command is None:
            print("Enter 'help' for command help")
            continue
        # proceed possible commands
        if shell_command.command == "add":
            p.add(p_database)
            continue
        if shell_command.command == "changepassword":
            p.change_database_password(p_database)
            continue
        if shell_command.command == "copypassword":
            if len(shell_command.arguments) == 1:
                print("UUID is missing.")
                print(shell_command)
                continue
            password = p_database.get_password_from_account_and_decrypt(shell_command.arguments[1])
            try:
                #pyperclip3.copy(password)
                clipboard.copy(password)
                print("Password copied to clipboard.")
            except Exception as e:
                print("Error copying password to clipboard: " + str(e))
            continue
        if shell_command.command == "delete":
            if len(shell_command.arguments) == 1:
                print("UUID is missing.")
                print(shell_command)
                continue
            p_database.delete_account(shell_command.arguments[1])
            continue
        if shell_command.command == "edit":
            if len(shell_command.arguments) == 1:
                print("UUID is missing.")
                print(shell_command)
                continue
            p.edit(p_database, shell_command.arguments[1])
            continue
        if shell_command.command == "help":
            for shell_command in SHELL_COMMANDS:
                print(str(shell_command))
            continue
        if shell_command.command == "idletime":
            print("Idle time: " + str(time_diff.total_seconds()) + " s")
            continue
        if shell_command.command == "invalidate":
            if len(shell_command.arguments) == 1:
                print("UUID is missing.")
                print(shell_command)
                continue
            p_database.invalidate_account(shell_command.arguments[1])
            continue
        if shell_command.command == "list":
            p_database.search_accounts("")
            continue
        if shell_command.command == "merge2dropbox":
            p.merge_with_dropbox(p_database)
            continue
        if shell_command.command == "merge2file":
            if len(shell_command.arguments) == 1:
                print("FILENAME is missing.")
                print(shell_command)
                continue
            p_database.merge_database(shell_command.arguments[1])
            continue
        if shell_command.command == "merge2lastknownfile":
            p_database.merge_last_known_database()
            continue
        if shell_command.command == "quit" or shell_command.command == "exit":
            break
        if shell_command.command == "revalidate":
            if len(shell_command.arguments) == 1:
                print("UUID is missing.")
                print(shell_command)
                continue
            p_database.revalidate_account(shell_command.arguments[1])
            continue
        if shell_command.command == "search":
            if len(shell_command.arguments) == 1:
                print("SEARCHSTRING is missing.")
                print(shell_command)
                continue
            p_database.search_accounts(shell_command.arguments[1])
            continue
        if shell_command.command == "setdropboxapplicationuuid":
            if len(shell_command.arguments) == 1:
                print("UUID is missing.")
                print(shell_command)
                continue
            p.set_attribute_value_in_configuration_table(
                p_database.database_filename,
                pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_DROPBOX_APPLICATION_ACCOUNT_UUID,
                shell_command.arguments[1])
            continue
        if shell_command.command == "setdropboxtokenuuid":
            if len(shell_command.arguments) == 1:
                print("UUID is missing.")
                print(shell_command)
                continue
            p.set_attribute_value_in_configuration_table(
                p_database.database_filename,
                pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_DROPBOX_ACCESS_TOKEN_ACCOUNT_UUID,
                shell_command.arguments[1])
            continue
        if shell_command.command == "shadowpasswords":
            # print(shell_command.arguments)
            # print("x" + str(len(shell_command.arguments)))
            if len(shell_command.arguments) == 1:
                print("on/off is missing.")
                print(shell_command)
                continue
            if shell_command.arguments[1] == "on":
                p_database.shadow_passwords = True
            if shell_command.arguments[1] == "off":
                p_database.shadow_passwords = False
            continue
        if shell_command.command == "showconfig":
            print("Show invalidated accounts           : " + str(p_database.show_invalidated_accounts))
            print("Shadow passwords                    : " + str(p_database.shadow_passwords))
            print("Show accounts verbose               : " + str(p_database.show_account_details))
            continue
        if shell_command.command == "showinvalidated":
            # print(shell_command.arguments)
            if len(shell_command.arguments) == 1:
                print("on/off is missing.")
                print(shell_command)
                continue
            if shell_command.arguments[1] == "on":
                p_database.show_invalidated_accounts = True
            if shell_command.arguments[1] == "off":
                p_database.show_invalidated_accounts = False
            continue
        if shell_command.command == "timeout":
            if len(shell_command.arguments) == 1:
                print("MINUTES are missing.")
                print(shell_command)
                continue
            try:
                shell_max_idle_minutes_timeout = int(shell_command.arguments[1])
                pdatabase.set_attribute_value_in_configuration_table(
                    p_database.database_filename,
                    pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_SHELL_MAX_IDLE_TIMEOUT_MIN,
                    shell_max_idle_minutes_timeout)
            except Exception as e:
                print("Error setting shell timeout: " + str(e))
            continue
        if shell_command.command == "verbose":
            # print(shell_command.arguments)
            if len(shell_command.arguments) == 1:
                print("on/off is missing.")
                print(shell_command)
                continue
            if shell_command.arguments[1] == "on":
                p_database.show_account_details = True
            if shell_command.arguments[1] == "off":
                p_database.show_account_details = False
            continue
        if shell_command.command == "status":
            pdatabase.print_database_statistics(p_database.database_filename)
            continue
        if shell_command.command == "version":
            print(p.VERSION)
            continue
    print("Exiting shell mode.")
