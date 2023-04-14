#!/bin/python3
#
# 20221213 jens heine <binbash@gmx.net>
#
# Password/account database for managing all your accounts
#
import sys
import getpass
# import stdiomask
import p
import pdatabase
from pdatabase import ShellHistoryEntry
import dropboxconnector
import pyperclip3
import datetime
from termcolor import colored
import os
from inputimeout import inputimeout, TimeoutOccurred
import time
import textwrap
import requests


# class ShellHistoryEntry:
#     execution_date = ""
#     user_input = ""
#
#     def __init__(self, execution_date=None, user_input=""):
#         if execution_date is None:
#             self.execution_date = datetime.datetime.now()
#         else:
#             self.execution_date = execution_date
#         self.user_input = user_input


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

    def __eq__(self, other):
        if self.command == other.command:
            return True
        else:
            return False

    def __lt__(self, other):
        if self.command < other.command:
            return True
        else:
            return False

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


SHELL_COMMANDS = [
    ShellCommand("0", "0", "Alias. This alias can be set with the alias command."),
    ShellCommand("1", "1", "Alias. This alias can be set with the alias command."),
    ShellCommand("2", "2", "Alias. This alias can be set with the alias command."),
    ShellCommand("3", "3", "Alias. This alias can be set with the alias command."),
    ShellCommand("4", "4", "Alias. This alias can be set with the alias command."),
    ShellCommand("5", "5", "Alias. This alias can be set with the alias command."),
    ShellCommand("6", "6", "Alias. This alias can be set with the alias command."),
    ShellCommand("7", "7", "Alias. This alias can be set with the alias command."),
    ShellCommand("8", "8", "Alias. This alias can be set with the alias command."),
    ShellCommand("9", "9", "Alias. This alias can be set with the alias command."),
    ShellCommand("add", "add", "Add a new account."),
    ShellCommand("alias", "alias [0-9 [<COMMAND>]]", "Show or set an alias. An alias is like a " +
                 "programmable command. Possible alias names are the numbers from 0 to 9. To set the " +
                 "command 'sc email' on the alias 1 you have to type: 'alias 1 sc Email'. After that you" +
                 " can run the command by just typing 1. To see all aliases just type 'alias'. If you want " +
                 "to see the command programmed on the alias 3 for example, type 'alias 3'. To unset an alias, " +
                 "for example the 3, type 'alias 3 -'."),
    ShellCommand("changepassword", "changepassword", "Change the master password of current database. This " +
                 "can take some minutes if there are a lot accounts in it."),
    ShellCommand("changedropboxdbpassword", "changedropboxdbpassword", "Change password of the dropbox database."),
    ShellCommand("clear", "clear", "Clear console. The screen will be blanked."),
    ShellCommand("clearhistory", "clearhistory", "Clear command history."),
    ShellCommand("cplast", "cplast", "Copy password from the latest found account to clipboard."),
    ShellCommand("copypassword", "copypassword <UUID>", "Copy password from UUID to clipboard."),
    ShellCommand("delete", "delete <UUID>", "Delete account with UUID. You can also invalidate the account " +
                 "instead of deleting it."),
    ShellCommand("forgetdeletedaccounts", "forgetdeletedaccounts", "Delete all entries in deleted_accounts " +
                 "table. This table is used and merged between databases to spread the information about which" +
                 " account with which UUID has been deleted. Emptying this table removes any traces of account " +
                 "UUID's which have existed in this database. You should empty this table on all databases. " +
                 "Otherwise the table will be filled again after the next merge with a database which has entries " +
                 "in the deleted_accounts table."),
    ShellCommand("deletedropboxdatabase", "deletedropboxdatabase", "Delete dropbox database file in the " +
                 "configured dropbox account."),
    ShellCommand("edit", "edit <UUID>", "Edit account with UUID."),
    ShellCommand("!", "! <COMMAND>", "Execute COMMAND in native shell."),
    ShellCommand("exit", "exit", "Quit pshell."),
    ShellCommand("help", "help [COMMAND]", "Show help for all pshell commands or show the specific help " +
                 "description for COMMAND."),
    ShellCommand("history", "history", "Show history of all user inputs in the the pshell."),
    ShellCommand("forgetaccounthistory", "forgetaccounthistory", "Delete all older/archived versions of accounts."),
    ShellCommand("idletime", "idletime", "Show idletime in seconds after last command."),
    ShellCommand("invalidate", "invalidate <UUID>", "Invalidate account with UUID."),
    ShellCommand("list", "list", "List all accounts."),
    ShellCommand("listinvalidated", "listinvalidated", "List all invalidated accounts."),
    ShellCommand("lock", "lock", "Lock pshell console. You will need to enter the password to unlock the pshell again"),
    ShellCommand("#", "#", "Lock pshell console."),
    ShellCommand("maxhistorysize", "maxhistorysize [MAX_SIZE]", "Show current max history size or set it. This " +
                 "limits the amount of history entries that will be saved in the shell_history table in the " +
                 "database. To disable the pshell history, set this value to 0."),
    ShellCommand("merge2dropbox", "merge2dropbox", "Merge local database with dropbox database copy."),
    ShellCommand("merge2file", "merge2file <FILENAME>",
                 "Merge local database with another database identified by FILENAME."),
    ShellCommand("merge2lastknownfile", "merge2lastknownfile",
                 "Merge local database with the last known merge database. The last know database can be seen " +
                 "with the status command"),
    ShellCommand("opendatabase", "opendatabase <DATABASE_FILENAME>", "Try to open a p database file with the " +
                 "name DATABASE_FILENAME. If the database does not exist, a new one with the filename will" +
                 " be created. With this command you can switch between multiple p databases."),
    ShellCommand("quit", "quit", "Quit pshell."),
    ShellCommand("redo", "redo [<HISTORY_INDEX>|?]", "Redo the last shell command. The redo command itself will not" +
                 " appear in the command history. You can choose the index of the command in your history if" +
                 " you want. If you choose no index, the latest command will be executed. If you use redo ? you " +
                 "will see the current command history with the indices to choose from."),
    ShellCommand("revalidate", "revalidate <UUID>", "Revalidate account with UUID."),
    ShellCommand("search", "search <SEARCHSTRING>", "Search for SEARCHSTRING in all account columns."),
    ShellCommand("searchinvalidated", "searchinvalidated <SEARCHSTRING>",
                 "Search for SEARCHSTRING in all columns of invalidated accounts."),
    ShellCommand("sc", "sc <SEARCHSTRING>", "Search for SEARCHSTRING in all account columns and copy the " +
                 "password of the account found to the clipboard."),
    ShellCommand("sca", "sca <SEARCHSTRING>", "Search for SEARCHSTRING in all account columns and copy one" +
                 " after another the URL, loginname and password of the account found to clipboard."),
    ShellCommand("scl", "scl <SEARCHSTRING>", "Search for SEARCHSTRING in account columns and copy the loginname" +
                 " of the account found to clipboard."),
    ShellCommand("scu", "scu <SEARCHSTRING>", "Search for SEARCHSTRING in all account columns and copy the URL of the" +
                 " account found to clipboard."),
    ShellCommand("sp", "sp <UUID>", "Set password for account with UUID. If shadow passwords is on, the password " +
                 "will be read hidden so that none can gather it from your screen."),
    ShellCommand("st", "st <SEARCHSTRING>", "Search for SEARCHSTRING in the type field of all accounts"),
    ShellCommand("setdatabasename", "setdatabasename <NAME>", "Set database to NAME. This is a logical name for " +
                 "the current database."),
    ShellCommand("setdropboxapplicationuuid", "setdropboxapplicationuuid <UUID>",
                 "Set the dropbox application account uuid in configuration."),
    ShellCommand("setdropboxtokenuuid", "setdropboxtokenuuid <UUID>",
                 "Set the dropbox token account uuid in configuration."),
    ShellCommand("shadowpasswords", "shadowpasswords [on|off]", "Set shadow passwords to on or off in console output" +
                 " or show current shadow status. This is useful if you are not alone watching the output " +
                 "of this program on the monitor."),
    ShellCommand("showaccounthistory", "showaccounthistory <UUID>", "Show change history of account with UUID."),
    ShellCommand("showconfig", "showconfig", "Show current configuration of the environment including if account " +
                 "passwords are shadowed, if verbose mode is ..."),
    ShellCommand("showinvalidated", "showinvalidated [on|off]", "Show invalidated accounts. If empty " +
                 "the current status will be shown."),
    ShellCommand("showunmergedwarning", "showunmergedwarning [on|off]", "Show warning on startup if there are " +
                 "unmerged changes in local database compared to the latest known merge database. If empty " +
                 "the current status will be shown."),
    ShellCommand("sql", "sql <COMMAND>", "Execute COMMAND in database in native SQL language. The p database " +
                 "is fully accessable with sql commands."),
    ShellCommand("status", "status", "Show configuration and database status. A short overview of the database " +
                 "will be shown including number of accounts, encryption status, database name..."),
    ShellCommand("timeout", "timeout [<MINUTES>]", "Set the maximum pshell inactivity timeout to MINUTES before " +
                 "locking the pshell (0 = disable timeout). Without MINUTES the current timeout is shown."),
    ShellCommand("trackaccounthistory", "trackaccounthistory on|off", "Track the history of changed accounts. " +
                 "You may also want to use the command: 'forgetaccounthistory' to delete all archived accounts."),
    ShellCommand("updatep", "updatep", "Update p. Depending on your operating system, the latest p binary will" +
                 " be downloaded from git and saved in the current folder with the ending '_latest'. You have " +
                 "to stop p after that and delete the old p binary and replace it with the new one."),
    ShellCommand("verbose", "verbose on|off", "Show verbose account infos true or false. If verbose is on " +
                 "then creation, change and invalidation timestamps will be shown."),
    ShellCommand("version", "version", "Show program version info.")
]
SHELL_COMMANDS.sort()

DEFAULT_PSHELL_MAX_IDLE_TIMEOUT_MIN = 30
pshell_max_idle_minutes_timeout = DEFAULT_PSHELL_MAX_IDLE_TIMEOUT_MIN
DEFAULT_PSHELL_MAX_HISTORY_SIZE = 100
pshell_max_history_size = DEFAULT_PSHELL_MAX_HISTORY_SIZE
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


def print_shell_command_history(shell_history_array: [ShellCommand]):
    i = 1
    for current_shell_history_entry in shell_history_array:
        print(" [" + str(i) + "] - " +
              str(current_shell_history_entry.execution_date) +
              " - " + current_shell_history_entry.user_input)
        i += 1


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

    global pshell_max_history_size
    pshell_max_history_size = pdatabase.get_attribute_value_from_configuration_table(
        p_database.database_filename,
        pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_MAX_HISTORY_SIZE)
    if not pshell_max_history_size.isnumeric() \
            or pshell_max_history_size is None \
            or pshell_max_history_size == "":
        pshell_max_history_size = DEFAULT_PSHELL_MAX_HISTORY_SIZE
        pdatabase.set_attribute_value_in_configuration_table(
            p_database.database_filename,
            pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_MAX_HISTORY_SIZE, pshell_max_history_size)

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
    config_value = pdatabase.get_attribute_value_from_configuration_table(
        p_database.database_filename,
        pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_TRACK_ACCOUNT_HISTORY)
    if config_value is not None and (config_value == "True" or config_value == "False"):
        p_database.track_account_history = parse_bool(config_value)


def os_is_windows() -> bool:
    # windows
    if os.name == 'nt':
        return True
    # for mac and linux os.name is posix
    else:
        False


def clear_console():
    # windows
    if os_is_windows():
        os.system('cls')
    # for mac and linux os.name is posix
    else:
        os.system('clear')


def start_pshell(p_database: pdatabase.PDatabase):
    global pshell_max_idle_minutes_timeout
    global pshell_max_history_size
    global show_unmerged_changes_warning_on_startup
    load_pshell_configuration(p_database)

    # time.sleep(1)
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
    # shell_history_array = []
    shell_history_array = p_database.get_shell_history_entries_decrypted()
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
                if user_input.strip() != "":
                    current_shell_history_entry = ShellHistoryEntry(user_input=user_input)
                    #shell_history_array.append(current_shell_history_entry)
            except KeyboardInterrupt:
                # return
                print()
                continue
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
                    print(colored("PShell locked.", "red"))
                else:
                    clear_console()
                    print(p.VERSION)
                    print(colored("PShell locked (timeout " + str(pshell_max_idle_minutes_timeout) + " min)", "red"))
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
                    print(colored("PShell unlocked.", "green"))
                    if manual_locked:
                        manual_locked = False
                    user_input = ""
                    break
        shell_command = expand_string_2_shell_command(user_input)
        # check for empty string
        if shell_command is None:
            if user_input == "":
                # print("Empty command.")
                pass
            else:
                print("Unknown command '" + user_input + "'")
                print("Enter 'help' for command help")
            continue
        #
        # proceed possible commands
        #

        # check if the command is the "redo last command" command
        if shell_command.command == "redo":
            # delete the redo command from hist
            #shell_history_array.pop()
            shell_history_array = p_database.get_shell_history_entries_decrypted()
            if len(shell_history_array) == 0:
                print("Shell history is empty.")
                continue

            redo_index = -1
            # when there is no index of the command history array given, use the latest one
            if len(shell_command.arguments) == 1:
                redo_index = len(shell_history_array)
            else:
                if shell_command.arguments[1].strip() == "?":
                    print_shell_command_history(shell_history_array)
                    try:
                        redo_index = int(input("Enter history index: "))
                    except KeyboardInterrupt:
                        print()
                        continue
                    except Exception as e:
                        print("Error: " + str(e))
                        continue
                else:
                    try:
                        redo_index = int(shell_command.arguments[1])
                    except Exception as e:
                        print("Error: " + str(e))
                        continue
            if redo_index < 0 or redo_index > len(shell_history_array):
                print("Error: Index not found in command history.")
                continue
            last_user_input = (shell_history_array[redo_index - 1]).user_input
            # change the current shell_command to the last command before the redo command
            shell_command = expand_string_2_shell_command(last_user_input)
            print("Redo: " + last_user_input)
            if shell_command is None:
                print("Unknown command '" + last_user_input + "'")
                print("Enter 'help' for command help")
                continue
        else:
            p_database.add_shell_history_entry(current_shell_history_entry, pshell_max_history_size)
        # and proceed parsing the command...:

        # check if the command is an alias. then the alias must be replaced with the stored command
        if shell_command.command in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9"):
            alias_command = p_database.get_alias_command_decrypted(shell_command.command)
            shell_command = expand_string_2_shell_command(alias_command)
            current_shell_history_entry = ShellHistoryEntry(user_input=alias_command)
            #shell_history_array.append(current_shell_history_entry)
            p_database.add_shell_history_entry(current_shell_history_entry, pshell_max_history_size)

        # continue with command processing

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
        if shell_command.command == "alias":
            if len(shell_command.arguments) == 1:
                aliases = p_database.get_alias_commands_decrypted()
                for alias in aliases:
                    print(alias)
            else: # 2 arguments
                alias_argument_list = shell_command.arguments[1].split(maxsplit=1)
                current_alias = alias_argument_list[0]
                if current_alias  not in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9"):
                    print("Error: Only aliases from 0..9 are allowed.")
                    continue
                else:
                    if len(alias_argument_list) == 1:
                        command = p_database.get_alias_command_decrypted(current_alias)
                        print(command)
                        continue
                    else:
                        current_command = alias_argument_list[1]
                        if current_command == '-':
                            current_command = ""
                        p_database.set_alias_command_and_encrypt(current_alias, current_command)
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
        if shell_command.command == "clearhistory":
            #shell_history_array = []
            p_database.delete_all_shell_history_entries()
            continue
        if shell_command.command == "copypassword":
            if len(shell_command.arguments) == 1:
                print("UUID is missing.")
                print(shell_command)
                continue
            password = p_database.get_password_from_account_and_decrypt(shell_command.arguments[1])
            try:
                pyperclip3.copy(password)
                print("CLIPBOARD: Password")
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
        if shell_command.command == "forgetdeletedaccounts":
            try:
                answer = input("Delete information about deleted account uuid's ([y]/n) : ")
            except KeyboardInterrupt:
                print()
                print("Strg-C detected.")
                continue
            if answer == "y" or answer == "":
                p_database.delete_from_deleted_account_table()
                print("Deleted.")
            else:
                print("Canceled")
            continue
        if shell_command.command == "forgetaccounthistory":
            try:
                answer = input("Delete older versions of all accounts ([y]/n) : ")
            except KeyboardInterrupt:
                print()
                print("Strg-C detected.")
                continue
            if answer == "y" or answer == "":
                p_database.delete_from_account_history_table()
                print("Deleted.")
            else:
                print("Canceled")
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
                if help_command is not None:
                    help_command.print_manual()
                else:
                    print("Unknown command: " + shell_command.arguments[1])
            continue
        if shell_command.command == "history":
            #print_shell_command_history(shell_history_array)
            print_shell_command_history(p_database.get_shell_history_entries_decrypted())
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
        if shell_command.command == "listinvalidated":
            p_database.search_invalidated_accounts("")
            continue
        if shell_command.command == "lock" or shell_command.command == "#":
            manual_locked = True
            # print("Pshell locked.")
            continue
        if shell_command.command == "maxhistorysize":
            if len(shell_command.arguments) == 1:
                if pshell_max_history_size < 1:
                    print("PShell max history size is " + str(pshell_max_history_size) + " (disabled)")
                else:
                    print("PShell max history size is " + str(pshell_max_history_size))
                continue
            try:
                pshell_max_history_size = int(shell_command.arguments[1])
                pdatabase.set_attribute_value_in_configuration_table(
                    p_database.database_filename,
                    pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_MAX_HISTORY_SIZE,
                    pshell_max_history_size)
            except Exception as e:
                print("Error setting pshell max history size: " + str(e))
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
        if shell_command.command == "opendatabase":
            if len(shell_command.arguments) == 1:
                print("DATABASE_FILENAME is missing.")
                print(shell_command)
                continue
            new_database_filename = shell_command.arguments[1].strip()
            if os.path.exists(new_database_filename):
                try:
                    new_database_password = getpass.getpass("Enter database password: ")
                except KeyboardInterrupt as k:
                    print()
                    continue
            else:
                print(colored("Database does not exist.", "red"))
                try:
                    new_database_password = getpass.getpass("Enter password for new database    : ")
                    new_database_password_confirm = getpass.getpass("Confirm password for new database  : ")
                except KeyboardInterrupt as k:
                    print()
                    continue
                if new_database_password != new_database_password_confirm:
                    print(colored("Error: Passwords do not match.", "red"))
                    sys.exit(1)
            if new_database_password is None:
                print(colored("Database password is not set! Enter password on command line or use -p or -E option.",
                              "red"))
                sys.exit(1)

            # Now try to open/create the database:
            new_p_database = pdatabase.PDatabase(new_database_filename, new_database_password)
            start_pshell(new_p_database)
            sys.exit()
        if shell_command.command == "quit" or shell_command.command == "exit":
            clear_console()
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
        if shell_command.command == "searchinvalidated":
            if len(shell_command.arguments) == 1:
                print("SEARCHSTRING is missing.")
                print(shell_command)
                continue
            p_database.search_invalidated_accounts(shell_command.arguments[1])
            # remember latest found account:
            account_array = p_database.get_accounts_decrypted_from_invalid_accounts(shell_command.arguments[1])
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
            print("CLIPBOARD: Password")
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
                try:
                    index = input("Multiple accounts found. Please specify the # you need: ")
                except KeyboardInterrupt:
                    print()
                    index = ""
                if index == "":
                    print("Nothing selected.")
                    continue
                try:
                    pyperclip3.copy(account_array[int(index) - 1].password)
                    print("CLIPBOARD: Password")
                except Exception as e:
                    print("Error: " + str(e))
                continue
            try:
                pyperclip3.copy(account_array[0].password)
                print("CLIPBOARD: Password")
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
                    print("CLIPBOARD: URL")
                    input("<Press enter>")
                    pyperclip3.copy(account_array[int(index) - 1].loginname)
                    print("CLIPBOARD: Loginname")
                    input("<Press enter>")
                    pyperclip3.copy(account_array[int(index) - 1].password)
                    print("CLIPBOARD: Password")
                except KeyboardInterrupt as ke:
                    print()
                    continue
                except Exception as e:
                    print("Error: " + str(e))
                continue
            try:
                pyperclip3.copy(account_array[0].url)
                print("CLIPBOARD: URL")
                input("<Press enter>")
                pyperclip3.copy(account_array[0].loginname)
                print("CLIPBOARD: Loginname")
                input("<Press enter>")
                pyperclip3.copy(account_array[0].password)
                print("CLIPBOARD: Password")
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
                    print("CLIPBOARD: Loginname")
                except Exception as e:
                    print("Error: " + str(e))
                continue
            try:
                pyperclip3.copy(account_array[0].loginname)
                print("CLIPBOARD: Loginname")
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
                    print("CLIPBOARD: URL")
                except Exception as e:
                    print("Error: " + str(e))
                continue
            try:
                pyperclip3.copy(account_array[0].url)
                print("CLIPBOARD: URL")
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
                # print("on/off is missing.")
                # print(shell_command)
                current_status = pdatabase.get_attribute_value_from_configuration_table(
                    p_database.database_filename,
                    pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHADOW_PASSWORDS)
                print("Status: " + current_status)
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
        if shell_command.command == "showaccounthistory":
            if len(shell_command.arguments) == 1:
                print("UUID is missing.")
                print(shell_command)
                continue
            p_database.search_account_history(shell_command.arguments[1])
            continue
        if shell_command.command == "showconfig":
            print("PShell timeout                      : " + str(pshell_max_idle_minutes_timeout))
            print("PShell max history size             : " + str(pshell_max_history_size))
            print("Show invalidated accounts           : " + str(p_database.show_invalidated_accounts))
            print("Shadow passwords                    : " + str(p_database.shadow_passwords))
            print("Show accounts verbose               : " + str(p_database.show_account_details))
            print("Show unmerged changes warning       : " + str(show_unmerged_changes_warning_on_startup))
            print("Track account history               : " + str(p_database.track_account_history))
            continue
        if shell_command.command == "showinvalidated":
            # print(shell_command.arguments)
            if len(shell_command.arguments) == 1:
                # print("on/off is missing.")
                # print(shell_command)
                current_status = pdatabase.get_attribute_value_from_configuration_table(
                    p_database.database_filename,
                    pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHOW_INVALIDATED_ACCOUNTS)
                print("Status: " + current_status)
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
                # print("on/off is missing.")
                # print(shell_command)
                current_status = pdatabase.get_attribute_value_from_configuration_table(
                    p_database.database_filename,
                    pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHOW_UNMERGED_CHANGES_WARNING)
                print("Status: " + current_status)
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
        if shell_command.command == "sp":
            if len(shell_command.arguments) == 1:
                print("UUID is missing.")
                print(shell_command)
                continue
            if not p_database.get_account_exists(shell_command.arguments[1]):
                print("Error: Account UUID " + shell_command.arguments[1] + " not found.")
                continue
            try:
                if pdatabase.get_attribute_value_from_configuration_table(
                        p_database.database_filename,
                        pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHADOW_PASSWORDS) == 'True':
                    new_password = getpass.getpass("New password     : ")
                    new_password_confirm = getpass.getpass("Confirm password : ")
                    if (new_password != new_password_confirm) \
                            or (new_password is None and new_password_confirm is None):
                        print("Error: Passwords do not match.")
                        continue
                else:
                    new_password = input("New password  : ")
                answer = input("Correct ([y]/n) : ")
            except KeyboardInterrupt:
                print()
                print("Strg-C detected.")
                continue
            if answer == "y" or answer == "":
                p_database.set_password_of_account(shell_command.arguments[1], new_password)
            else:
                print("Canceled")
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
        if shell_command.command == "status":
            pdatabase.print_database_statistics(p_database.database_filename)
            continue
        if shell_command.command == "st":
            if len(shell_command.arguments) == 1:
                print("SEARCHSTRING is missing.")
                print(shell_command)
                continue
            p_database.search_accounts_by_type(shell_command.arguments[1])
            # remember latest found account:  xxx
            account_array = p_database.get_accounts_decrypted_search_types(shell_command.arguments[1])
            if len(account_array) == 0:
                latest_found_account = None
                continue
            else:
                latest_found_account = account_array[len(account_array) - 1]
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
        if shell_command.command == "trackaccounthistory":
            # print(shell_command.arguments)
            if len(shell_command.arguments) == 1:
                # print("on/off is missing.")
                # print(shell_command)
                current_status = pdatabase.get_attribute_value_from_configuration_table(
                    p_database.database_filename,
                    pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_TRACK_ACCOUNT_HISTORY)
                print("Status: " + current_status)
                continue
            if shell_command.arguments[1] == "on":
                p_database.track_account_history = True
                pdatabase.set_attribute_value_in_configuration_table(
                    p_database.database_filename,
                    pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_TRACK_ACCOUNT_HISTORY,
                    "True")
                continue
            if shell_command.arguments[1] == "off":
                p_database.track_account_history = False
                pdatabase.set_attribute_value_in_configuration_table(
                    p_database.database_filename,
                    pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_TRACK_ACCOUNT_HISTORY,
                    "False")
                continue
            print("Error: on or off expected.")
            continue
        if shell_command.command == "updatep":
            if os_is_windows():
                download_url = p.URL_DOWNLOAD_BINARY_P_WIN
                download_p_filename = p.DOWNLOAD_P_UPDATE_FILENAME_WIN
                p_filename = p.P_FILENAME_WIN
            else:
                download_url = p.URL_DOWNLOAD_BINARY_P_LINUX
                download_p_filename = p.DOWNLOAD_P_UPDATE_FILENAME_LINUX
                p_filename = p.P_FILENAME_LINUX
            print("Downloading latest p binary to: " + download_p_filename)
            req = requests.get(download_url)
            open(download_p_filename, "wb").write(req.content)
            print("Download ready.")
            print("Now quit p and rename the file '" + download_p_filename + "' to '" + p_filename +
                  "'. Then restart p and you have the latest version.")
            continue
        if shell_command.command == "verbose":
            if len(shell_command.arguments) == 1:
                # print("on/off is missing.")
                # print(shell_command)
                current_status = pdatabase.get_attribute_value_from_configuration_table(
                    p_database.database_filename,
                    pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHOW_ACCOUNT_DETAILS)
                print("Status: " + current_status)
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
