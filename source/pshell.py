#!/bin/python3
#
# 20221213 jens heine <binbash@gmx.net>
#
# Password/account database for managing all your accounts
#
import getpass

import p
import pdatabase
import dropboxconnector
import pyperclip3
#import clipboard
import datetime
from termcolor import colored
import os
from inputimeout import inputimeout, TimeoutOccurred
import time
import textwrap


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

    def print_manual(self):
        print()
        print("COMMAND")
        print(" " + self.command)
        print()
        print("SYNOPSIS")
        print(" " + self.synopsis)
        print()
        print("DESCRIPTION")
        formatted_description = textwrap.wrap(self.description,
                                              width=78,
                                              initial_indent=" ",
                                              subsequent_indent=" ")
        for row in formatted_description:
            print(row)
        print()


# SHELL_COMMANDS = ( ShellCommand(command="version", synopsis="version", description="show p program version") )
SHELL_COMMANDS = [
    ShellCommand("add", "add", "Add a new account."),
    ShellCommand("changepassword", "changepassword", "Change password of current database."),
    ShellCommand("changedropboxdbpassword", "changedropboxdbpassword", "Change password of the dropbox database."),
    ShellCommand("clear", "clear", "Clear console."),
    # ShellCommand("cleartimeout", "cleartimeout [MINUTES]", "Set or show console clear timeout in MINUTES."),
    ShellCommand("cplast", "cplast", "Copy password from the latest found account to clipboard."),
    ShellCommand("copypassword", "copypassword UUID", "Copy password from UUID to clipboard."),
    ShellCommand("delete", "delete UUID", "Delete account with UUID."),
    ShellCommand("deletedropboxdatabase", "deletedropboxdatabase", "Delete dropbox database."),
    ShellCommand("edit", "edit UUID", "Edit account with UUID."),
    ShellCommand("!", "! COMMAND", "Execute COMMAND in native shell."),
    ShellCommand("exit", "exit", "Quit pshell."),
    ShellCommand("help", "help [COMMAND]", "Show help for all pshell commands or show description for COMMAND."),
    ShellCommand("idletime", "idletime", "Show idletime in seconds after last command."),
    ShellCommand("invalidate", "invalidate UUID", "Invalidate account with UUID."),
    ShellCommand("list", "list", "List all accounts."),
    ShellCommand("lock", "lock", "Lock pshell console."),
    ShellCommand("#", "#", "Lock pshell console."),
    ShellCommand("merge2dropbox", "merge2dropbox", "Merge local database with dropbox database copy."),
    ShellCommand("merge2file", "merge2file FILENAME",
                 "Merge local database with another database identified by FILENAME."),
    ShellCommand("merge2lastknownfile", "merge2lastknownfile",
                 "Merge local database with the last known merge database."),
    ShellCommand("quit", "quit", "Quit pshell."),
    ShellCommand("revalidate", "revalidate UUID", "Revalidate account with UUID."),
    ShellCommand("search", "search SEARCHSTRING", "Search SEARCHSTRING in account database."),
    ShellCommand("sc", "sc SEARCHSTRING", "Search SEARCHSTRING in accounts and copy the password of the" +
                 " account found to clipboard."),
    ShellCommand("sca", "sca SEARCHSTRING", "Search SEARCHSTRING in accounts and copy one after another the URL, " +
                 "loginname and password of the account found to clipboard."),
    ShellCommand("scl", "scl SEARCHSTRING", "Search SEARCHSTRING in accounts and copy the loginname of the" +
                 " account found to clipboard."),
    ShellCommand("scu", "scu SEARCHSTRING", "Search SEARCHSTRING in accounts and copy the URL of the" +
                 " account found to clipboard."),
    ShellCommand("setdatabasename", "setdatabasename NAME", "Set database to NAME."),
    ShellCommand("setdropboxapplicationuuid", "setdropboxapplicationuuid UUID",
                 "Set the dropbox application account uuid in configuration."),
    ShellCommand("setdropboxtokenuuid", "setdropboxtokenuuid UUID",
                 "Set the dropbox token account uuid in configuration."),
    ShellCommand("shadowpasswords", "shadowpasswords on|off", "Shadow passwords in console output."),
    ShellCommand("showconfig", "showconfig", "Show current configuration."),
    ShellCommand("showinvalidated", "showinvalidated on|off", "Show invalidated accounts."),
    ShellCommand("showunmergedwarning", "showunmergedwarning on|off", "Show warning on startup if there are " +
                 "unmerged changes in local database compared to the latest known merge database."),
    ShellCommand("sql", "sql COMMAND", "Execute COMMAND in database."),
    ShellCommand("status", "status", "Show configuration and database status."),
    ShellCommand("timeout", "timeout [MINUTES]", "Set the maximum pshell inactivity timeout to MINUTES before " +
                 "locking the pshell (0 = disable timeout). Without MINUTES the current timeout is shown."),
    ShellCommand("verbose", "verbose on|off", "Show verbose account infos true or false."),
    ShellCommand("version", "version", "Show program version info.")
]

DEFAULT_PSHELL_MAX_IDLE_TIMEOUT_MIN = 30
pshell_max_idle_minutes_timeout = DEFAULT_PSHELL_MAX_IDLE_TIMEOUT_MIN
# DEFAULT_PSHELL_MAX_IDLE_TIMEOUT_MIN_BEFORE_CLEAR_CONSOLE = 1
# pshell_max_idle_minutes_timeout_min_before_clear_console = DEFAULT_PSHELL_MAX_IDLE_TIMEOUT_MIN_BEFORE_CLEAR_CONSOLE
show_unmerged_changes_warning_on_startup = True


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


def parse_bool(string: str) -> bool:
    if string is None:
        return False
    if string == "True" or str == "true":
        return True
    else:
        return False


def load_pshell_configuration(p_database: pdatabase.PDatabase):
    global pshell_max_idle_minutes_timeout
    pshell_max_idle_minutes_timeout = pdatabase.get_attribute_value_from_configuration_table(
        p_database.database_filename,
        pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_MAX_IDLE_TIMEOUT_MIN)
    if not pshell_max_idle_minutes_timeout.isnumeric() \
            or pshell_max_idle_minutes_timeout is None \
            or pshell_max_idle_minutes_timeout == "":
        pshell_max_idle_minutes_timeout = DEFAULT_PSHELL_MAX_IDLE_TIMEOUT_MIN
        pdatabase.set_attribute_value_in_configuration_table(
            p_database.database_filename,
            pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_MAX_IDLE_TIMEOUT_MIN, pshell_max_idle_minutes_timeout)

    # global pshell_max_idle_minutes_timeout_min_before_clear_console
    # pshell_max_idle_minutes_timeout_min_before_clear_console = pdatabase.get_attribute_value_from_configuration_table(
    #     p_database.database_filename,
    #     pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_MAX_IDLE_TIMEOUT_MIN_BEFORE_CONSOLE_CLEAR)
    # if not pshell_max_idle_minutes_timeout_min_before_clear_console.isnumeric() \
    #         or pshell_max_idle_minutes_timeout_min_before_clear_console is None \
    #         or pshell_max_idle_minutes_timeout_min_before_clear_console == "":
    #     pshell_max_idle_minutes_timeout_min_before_clear_console = \
    #         DEFAULT_PSHELL_MAX_IDLE_TIMEOUT_MIN_BEFORE_CLEAR_CONSOLE
    #     pdatabase.set_attribute_value_in_configuration_table(
    #         p_database.database_filename,
    #         pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_MAX_IDLE_TIMEOUT_MIN_BEFORE_CONSOLE_CLEAR,
    #         pshell_max_idle_minutes_timeout_min_before_clear_console)

    config_value = pdatabase.get_attribute_value_from_configuration_table(
        p_database.database_filename,
        pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHADOW_PASSWORDS)
    if config_value is not None and (config_value == "True" or config_value == "False"):
        p_database.shadow_passwords = parse_bool(config_value)
        # print("->" + p_database.shadow_passwords)
    config_value = pdatabase.get_attribute_value_from_configuration_table(
        p_database.database_filename,
        pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHOW_ACCOUNT_DETAILS)
    if config_value is not None and (config_value == "True" or config_value == "False"):
        p_database.show_account_details = parse_bool(config_value)
    config_value = pdatabase.get_attribute_value_from_configuration_table(
        p_database.database_filename,
        pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHOW_INVALIDATED_ACCOUNTS)
    if config_value is not None and (config_value == "True" or config_value == "False"):
        p_database.show_invalidated_accounts = parse_bool(config_value)
    global show_unmerged_changes_warning_on_startup
    config_value = pdatabase.get_attribute_value_from_configuration_table(
        p_database.database_filename,
        pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHOW_UNMERGED_CHANGES_WARNING)
    if config_value is not None and (config_value == "True" or config_value == "False"):
        show_unmerged_changes_warning_on_startup = parse_bool(config_value)


def clear_console():
    # windows
    if os.name == 'nt':
        os.system('cls')
    # for mac and linux os.name is posix
    else:
        os.system('clear')


def start_pshell(p_database: pdatabase.PDatabase):
    global pshell_max_idle_minutes_timeout
    global show_unmerged_changes_warning_on_startup
    load_pshell_configuration(p_database)

    clear_console()
    user_input = ""
    latest_found_account = None
    prompt_string = p_database.database_filename + "> "
    if pdatabase.get_database_name(p_database.database_filename) != "":
        prompt_string = pdatabase.get_database_name(p_database.database_filename) + " - " + prompt_string
    pdatabase.print_database_statistics(p_database.database_filename)
    if show_unmerged_changes_warning_on_startup is True and \
            pdatabase.get_database_has_unmerged_changes(p_database.database_filename) is True:
        print(colored("Note: You have unmerged changes in your local database.", 'red'))
    manual_locked = False
    while user_input != "quit":
        last_activity_date = datetime.datetime.now()
        if not manual_locked:
            try:
                # user_input = input(prompt_string)
                # Eingabe mit timeout oder ohne machen:
                if int(pshell_max_idle_minutes_timeout) > 0:
                    user_input = inputimeout(prompt=prompt_string, timeout=(int(pshell_max_idle_minutes_timeout) * 60))
                else:
                    user_input = input(prompt_string)
            except KeyboardInterrupt:
                return
            except TimeoutOccurred:
                pass
        now_date = datetime.datetime.now()
        time_diff = now_date - last_activity_date
        if manual_locked or (int(pshell_max_idle_minutes_timeout) != 0 and
                             int(time_diff.total_seconds() / 60) >= int(pshell_max_idle_minutes_timeout)):
            while True:
                if manual_locked:
                    clear_console()
                    print(p.VERSION)
                    print("PShell locked.")
                else:
                    clear_console()
                    print(p.VERSION)
                    print("PShell locked (timeout " + str(pshell_max_idle_minutes_timeout) + " min)")
                try:
                    user_input_pass = getpass.getpass("Enter database password: ")
                except KeyboardInterrupt:
                    print()
                    return
                if user_input_pass is None or user_input_pass != p_database.get_database_password_as_string():
                    print("Error: password is wrong.")
                    time.sleep(2)
                    # clear_console()
                else:
                    # password is ok
                    clear_console()
                    print("PShell unlocked.")
                    if manual_locked:
                        manual_locked = False
                        user_input = ""
                    break
        shell_command = expand_string_2_shell_command(user_input)
        if shell_command is None:
            if user_input == "":
                # print("Empty command.")
                pass
            else:
                print("Unknown command '" + user_input + "'")
                print("Enter 'help' for command help")
            continue
        # proceed possible commands
        if shell_command.command == "!":
            if len(shell_command.arguments) == 1:
                print("COMMAND is missing.")
                print(shell_command)
                continue
            os.system(shell_command.arguments[1])
            continue
        if shell_command.command == "add":
            p.add(p_database)
            continue
        if shell_command.command == "changedropboxdbpassword":
            p.change_dropbox_database_password(p_database)
            continue
        if shell_command.command == "changepassword":
            try:
                p.change_database_password(p_database)
            except KeyboardInterrupt:
                print()
                print("Canceled.")
            continue
        if shell_command.command == "clear":
            clear_console()
            continue
        if shell_command.command == "copypassword":
            if len(shell_command.arguments) == 1:
                print("UUID is missing.")
                print(shell_command)
                continue
            password = p_database.get_password_from_account_and_decrypt(shell_command.arguments[1])
            try:
                pyperclip3.copy(password)
                # clipboard.copy(password)
                # print("Password copied to clipboard.")
                print("<Password copied to clipboard>")
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
        if shell_command.command == "deletedropboxdatabase":
            p.delete_dropbox_database(p_database)
            continue
        if shell_command.command == "edit":
            if len(shell_command.arguments) == 1:
                print("UUID is missing.")
                print(shell_command)
                continue
            p.edit(p_database, shell_command.arguments[1])
            continue
        if shell_command.command == "help":
            if len(shell_command.arguments) == 1:
                print()
                print(colored(" PShell command help", "green"))
                print(colored(" Type 'help COMMAND' to get usage details for COMMAND", "green"))
                print(colored(" You can type the first distinct letter(s) of any COMMAND to be faster.", "green"))
                print()
                for shell_command in SHELL_COMMANDS:
                    # print(str(shell_command))
                    print(shell_command.synopsis)
            else:
                help_command = expand_string_2_shell_command(shell_command.arguments[1])
                help_command.print_manual()
            continue
        if shell_command.command == "idletime":
            idle_time = round(time_diff.total_seconds())
            if idle_time < 120:
                idle_time_str = str(idle_time) + " sec"
            else:
                idle_time = round(idle_time / 60)
                idle_time_str = str(idle_time) + " min"
            # print("Idle time: " + str(round(time_diff.total_seconds())) + " s")
            print("Idle time: " + idle_time_str)
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
        if shell_command.command == "lock" or shell_command.command == "#":
            manual_locked = True
            # print("Pshell locked.")
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
            # remember latest found account:
            account_array = p_database.get_accounts_decrypted(shell_command.arguments[1])
            if len(account_array) == 0:
                latest_found_account = None
                continue
            else:
                latest_found_account = account_array[len(account_array) - 1]
            continue
        if shell_command.command == "cplast":
            if latest_found_account is None:
                print("There is no account to copy.")
                continue
            pyperclip3.copy(latest_found_account.password)
            # clipboard.copy(latest_found_account.password)
            # print("Password from account '" + latest_found_account.name + "' copied to clipboard.")
            print("<Password copied to clipboard>")
            continue
        if shell_command.command == "sc":
            if len(shell_command.arguments) == 1:
                print("SEARCHSTRING is missing.")
                print(shell_command)
                continue
            account_array = p_database.get_accounts_decrypted(shell_command.arguments[1])
            if len(account_array) == 0:
                print("No account found.")
                continue
            if len(account_array) != 1:
                i = 1
                # print()
                for acc in account_array:
                    print()
                    print(" [" + str(i) + "]" + " - Name: " + acc.name)
                    # p_database.print_formatted_account_search_string_colored(acc, shell_command.arguments[1])
                    i = i + 1
                print("")
                index = input("Multiple accounts found. Please specify the # you need: ")
                if index == "":
                    print("Nothing selected.")
                    continue
                try:
                    pyperclip3.copy(account_array[int(index) - 1].password)
                    # clipboard.copy(account_array[int(index) - 1].password)
                    # print("Password from account: '" + account_array[int(index) - 1].name + "' copied to clipboard.")
                    print("<Password copied to clipboard>")
                except Exception as e:
                    print("Error: " + str(e))
                continue
            try:
                # pyperclip3.copy(password)
                pyperclip3.copy(account_array[0].password)
                # clipboard.copy(account_array[0].password)
                # print("Password from account: '" + account_array[0].name + "' copied to clipboard.")
                print("<Password copied to clipboard>")
            except Exception as e:
                print("Error copying password to clipboard: " + str(e))
            continue
        if shell_command.command == "sca":
            if len(shell_command.arguments) == 1:
                print("SEARCHSTRING is missing.")
                print(shell_command)
                continue
            account_array = p_database.get_accounts_decrypted(shell_command.arguments[1])
            if len(account_array) == 0:
                print("No account found.")
                continue
            if len(account_array) != 1:
                i = 1
                # print()
                for acc in account_array:
                    print()
                    print(" [" + str(i) + "]" + " - Name: " + acc.name)
                    # p_database.print_formatted_account_search_string_colored(acc, shell_command.arguments[1])
                    i = i + 1
                print("")
                index = input("Multiple accounts found. Please specify the # you need: ")
                if index == "":
                    print("Nothing selected.")
                    continue
                try:
                    pyperclip3.copy(account_array[int(index) - 1].url)
                    # clipboard.copy(account_array[int(index) - 1].url)
                    # print("URL from account: '" + account_array[int(index) - 1].name + "' copied to clipboard.")
                    print("<URL copied to clipboard>")
                    input("Press enter to copy loginname")
                    pyperclip3.copy(account_array[int(index) - 1].loginname1)
                    # clipboard.copy(account_array[int(index) - 1].loginname)
                    # print("Loginname from account: '" + account_array[int(index) - 1].name + "' copied to clipboard.")
                    print("<Loginname copied to clipboard>")
                    input("Press enter to copy password")
                    pyperclip3.copy(account_array[int(index) - 1].password)
                    # clipboard.copy(account_array[int(index) - 1].password)
                    # print("Password from account: '" + account_array[int(index) - 1].name + "' copied to clipboard.")
                    print("<Password copied to clipboard>")
                except KeyboardInterrupt as ke:
                    print()
                    continue
                except Exception as e:
                    print("Error: " + str(e))
                continue
            try:
                pyperclip3.copy(account_array[0].url)
                # clipboard.copy(account_array[0].url)
                # print("URL from account: '" + account_array[0].name + "' copied to clipboard.")
                print("<URL copied to clipboard>")
                input("Press enter to copy loginname")
                pyperclip3.copy(account_array[0].loginname)
                # clipboard.copy(account_array[0].loginname)
                # print("Loginname from account: '" + account_array[0].name + "' copied to clipboard.")
                print("<Loginname copied to clipboard>")
                input("Press enter to copy password")
                pyperclip3.copy(account_array[0].password)
                # clipboard.copy(account_array[0].password)
                # print("Password from account: '" + account_array[0].name + "' copied to clipboard.")
                print("<Password copied to clipboard>")
            except KeyboardInterrupt as ke:
                print()
                continue
            except Exception as e:
                print("Error copying URL, loginname and password to clipboard: " + str(e))
            continue
        if shell_command.command == "scl":
            if len(shell_command.arguments) == 1:
                print("SEARCHSTRING is missing.")
                print(shell_command)
                continue
            account_array = p_database.get_accounts_decrypted(shell_command.arguments[1])
            if len(account_array) == 0:
                print("No account found.")
                continue
            if len(account_array) != 1:
                i = 1
                # print()
                for acc in account_array:
                    print()
                    print(" [" + str(i) + "]" + " - Name: " + acc.name)
                    # p_database.print_formatted_account_search_string_colored(acc, shell_command.arguments[1])
                    i = i + 1
                print("")
                index = input("Multiple accounts found. Please specify the # you need: ")
                if index == "":
                    print("Nothing selected.")
                    continue
                try:
                    pyperclip3.copy(account_array[int(index) - 1].loginname)
                    # clipboard.copy(account_array[int(index) - 1].loginname)
                    # print("Loginname from account: '" + account_array[int(index) - 1].name + "' copied to clipboard.")
                    print("<Loginname copied to clipboard>")
                except Exception as e:
                    print("Error: " + str(e))
                continue
            try:
                pyperclip3.copy(account_array[0].loginname)
                # clipboard.copy(account_array[0].loginname)
                # print("Loginname from account: '" + account_array[0].name + "' copied to clipboard.")
                print("<Loginname copied to clipboard>")
            except Exception as e:
                print("Error copying loginname to clipboard: " + str(e))
            continue
        if shell_command.command == "scu":
            if len(shell_command.arguments) == 1:
                print("SEARCHSTRING is missing.")
                print(shell_command)
                continue
            account_array = p_database.get_accounts_decrypted(shell_command.arguments[1])
            if len(account_array) == 0:
                print("No account found.")
                continue
            if len(account_array) != 1:
                i = 1
                # print()
                for acc in account_array:
                    print()
                    print(" [" + str(i) + "]" + " - Name: " + acc.name)
                    # p_database.print_formatted_account_search_string_colored(acc, shell_command.arguments[1])
                    i = i + 1
                print("")
                index = input("Multiple accounts found. Please specify the # you need: ")
                if index == "":
                    print("Nothing selected.")
                    continue
                try:
                    pyperclip3.copy(account_array[int(index) - 1].url)
                    # clipboard.copy(account_array[int(index) - 1].url)
                    # print("URL from account: '" + account_array[int(index) - 1].name + "' copied to clipboard.")
                    print("<URL copied to clipboard>")
                except Exception as e:
                    print("Error: " + str(e))
                continue
            try:
                pyperclip3.copy(account_array[0].url)
                # clipboard.copy(account_array[0].url)
                # print("URL from account: '" + account_array[0].name + "' copied to clipboard.")
                print("<URL copied to clipboard>")
            except Exception as e:
                print("Error copying URL to clipboard: " + str(e))
        if shell_command.command == "setdatabasename":
            if len(shell_command.arguments) == 1:
                print("NAME is missing.")
                print(shell_command)
                continue
            p.set_attribute_value_in_configuration_table(
                p_database.database_filename,
                pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_DATABASE_NAME,
                shell_command.arguments[1])
            prompt_string = p_database.database_filename + "> "
            if pdatabase.get_database_name(p_database.database_filename) != "":
                prompt_string = pdatabase.get_database_name(p_database.database_filename) + " - " + prompt_string
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
            if len(shell_command.arguments) == 1:
                print("on/off is missing.")
                print(shell_command)
                continue
            if shell_command.arguments[1] == "on":
                p_database.shadow_passwords = True
                pdatabase.set_attribute_value_in_configuration_table(
                    p_database.database_filename,
                    pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHADOW_PASSWORDS,
                    "True")
                continue
            if shell_command.arguments[1] == "off":
                p_database.shadow_passwords = False
                pdatabase.set_attribute_value_in_configuration_table(
                    p_database.database_filename,
                    pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHADOW_PASSWORDS,
                    "False")
                continue
            print("Error: on or off expected.")
            continue
        if shell_command.command == "showconfig":
            print("PShell timeout                      : " + str(pshell_max_idle_minutes_timeout))
            print("Show invalidated accounts           : " + str(p_database.show_invalidated_accounts))
            print("Shadow passwords                    : " + str(p_database.shadow_passwords))
            print("Show accounts verbose               : " + str(p_database.show_account_details))
            print("Show unmerged changes warning       : " + str(show_unmerged_changes_warning_on_startup))
            continue
        if shell_command.command == "showinvalidated":
            # print(shell_command.arguments)
            if len(shell_command.arguments) == 1:
                print("on/off is missing.")
                print(shell_command)
                continue
            if shell_command.arguments[1] == "on":
                p_database.show_invalidated_accounts = True
                pdatabase.set_attribute_value_in_configuration_table(
                    p_database.database_filename,
                    pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHOW_INVALIDATED_ACCOUNTS,
                    "True")
                continue
            if shell_command.arguments[1] == "off":
                p_database.show_invalidated_accounts = False
                pdatabase.set_attribute_value_in_configuration_table(
                    p_database.database_filename,
                    pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHOW_INVALIDATED_ACCOUNTS,
                    "False")
                continue
            print("Error: on or off expected.")
            continue
        if shell_command.command == "showunmergedwarning":
            # print(shell_command.arguments)
            if len(shell_command.arguments) == 1:
                print("on/off is missing.")
                print(shell_command)
                continue
            if shell_command.arguments[1] == "on":
                show_unmerged_changes_warning_on_startup = True
                pdatabase.set_attribute_value_in_configuration_table(
                    p_database.database_filename,
                    pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHOW_UNMERGED_CHANGES_WARNING,
                    "True")
                continue
            if shell_command.arguments[1] == "off":
                show_unmerged_changes_warning_on_startup = False
                pdatabase.set_attribute_value_in_configuration_table(
                    p_database.database_filename,
                    pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHOW_UNMERGED_CHANGES_WARNING,
                    "False")
                continue
            print("Error: on or off expected.")
            continue
        if shell_command.command == "sql":
            if len(shell_command.arguments) == 1:
                print("COMMAND is missing.")
                print(shell_command)
                continue
            print("->" + shell_command.arguments[1])
            print("Executing sql command: <" + shell_command.arguments[1] + ">")
            try:
                p_database.execute_sql(shell_command.arguments[1])
            except Exception as e:
                print("Error executing sql command: " + str(e))
            continue
        if shell_command.command == "timeout":
            if len(shell_command.arguments) == 1:
                print("PShell max idle timeout is " + str(pshell_max_idle_minutes_timeout) + " min")
                # print(shell_command)
                continue
            try:
                pshell_max_idle_minutes_timeout = int(shell_command.arguments[1])
                pdatabase.set_attribute_value_in_configuration_table(
                    p_database.database_filename,
                    pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_MAX_IDLE_TIMEOUT_MIN,
                    pshell_max_idle_minutes_timeout)
            except Exception as e:
                print("Error setting pshell timeout: " + str(e))
            continue
        if shell_command.command == "verbose":
            if len(shell_command.arguments) == 1:
                print("on/off is missing.")
                print(shell_command)
                continue
            if shell_command.arguments[1] == "on":
                p_database.show_account_details = True
                pdatabase.set_attribute_value_in_configuration_table(
                    p_database.database_filename,
                    pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHOW_ACCOUNT_DETAILS,
                    "True")
                continue
            if shell_command.arguments[1] == "off":
                p_database.show_account_details = False
                pdatabase.set_attribute_value_in_configuration_table(
                    p_database.database_filename,
                    pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHOW_ACCOUNT_DETAILS,
                    "False")
                continue
            print("Error: on or off expected.")
            continue
        if shell_command.command == "status":
            pdatabase.print_database_statistics(p_database.database_filename)
            continue
        # if shell_command.command == "upload2dropbox":
        #     continue
        #     # tobe implemented
        #     print("An eventually existing database in dropbox will be overwritten!")
        #     local_path = os.path.dirname(p_database.database_filename)
        #     # dropbox_upload_file(access_token, local_path, p_database.database_filename,
        #     #                     "/" + DROPBOX_P_DATABASE_FILENAME)
        #     dropboxconnector.dropbox_upload_file(dropbox_connection, local_path, p_database.database_filename,
        #                                          "/" + DROPBOX_P_DATABASE_FILENAME)
        #     continue
        if shell_command.command == "version":
            print(p.VERSION)
            continue
        # # Unknown command detected
        # print("Command ")
    print("Exiting pshell.")
