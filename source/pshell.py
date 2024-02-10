#!/bin/python3
#
# 20221213 jens heine <binbash@gmx.net>
#
# Password/account database for managing all your accounts
#
import datetime
import getpass
import os
import sys
import textwrap
import time
import uuid

import pyperclip3
import wget
from inputimeout import inputimeout, TimeoutOccurred
from termcolor import colored

import connector_manager
import p
import password_generator
import pdatabase
import print_slow
from pdatabase import ShellHistoryEntry


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
        print(" " + colored(self.command, "green"))
        print()
        print("SYNOPSIS")
        print(" " + self.synopsis)
        print()
        print("DESCRIPTION")
        formatted_description = []
        for line in self.description.splitlines():
            for sub_line in textwrap.wrap(line,
                                          width=78,
                                          initial_indent=" ",
                                          subsequent_indent=" "):
                formatted_description.append(sub_line)
        for row in formatted_description:
            print(row)
        print()

    def generate_git_manual(self) -> str:
        t = ""
        t = t + "# " + self.__escape_for_git_doc(self.command) + "\n\n"
        t = t + "**SYNOPSIS**" + "\n\n"
        t = t + " " + self.__escape_for_git_doc(self.synopsis) + "\n\n"
        t = t + "**DESCRIPTION**" + "\n\n"
        formatted_description = []
        for line in self.description.splitlines():
            for sub_line in textwrap.wrap(line,
                                          width=78,
                                          initial_indent=" ",
                                          subsequent_indent=" "):
                formatted_description.append(sub_line)
        for row in formatted_description:
            t = t + self.__escape_for_git_doc(row) + "\n\n"
        t = t + "\n\n"
        return t

    def __escape_for_git_doc(self, string: str) -> str:
        if string.startswith("#"):
            string = "\\" + string
        string = string.replace("<", "\<")
        string = string.replace(">", "\>")
        # string = string.replace("'", "\'")
        return string


SHELL_COMMANDS = [
    ShellCommand("/", "/ <SEARCHSTRING>", "/ is an alias to the search command. For " +
                 "more info see the help for the search command. It is also possible to search like this: " +
                 "'/SEARCHSTRING' (without the space after the slash)."),
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
    ShellCommand("10", "10", "Alias. This alias can be set with the alias command."),
    ShellCommand("add", "add [ACCOUNT_NAME]", "Add a new account.\nExample:\n" +
                 "UUID            : 51689195-4977-4c06-a19f-ac70823fbd4a \n-> The UUID is an unique identifier for the account\n" +
                 "Name            : user@gmx.de GMX EMail Account        \n-> Choose a name for the new account\n" +
                 "URL             : gmx.de                               \n-> If there is an url where the account is located, add it here\n" +
                 "Loginname       : user123@gmx.de                       \n-> The login name for the account\n" +
                 "Password        : 123secret                            \n-> The password for the account\n" +
                 "Type            : Emailaccount                         \n-> Choose a name for the type of this account\n" +
                 "Connectortype   :                                      \n-> If this is a connector account, put ssh/dropbox/file or webdav here\n"),
    ShellCommand("alias", "alias [0-9 [<COMMAND>]]", "Show or set an alias. An alias is like a " +
                 "programmable command. Possible alias names are the numbers from 0 to 9.\nTo set the " +
                 "command 'sc email' on the alias 1 you have to type: 'alias 1 sc Email'. After that you" +
                 " can run the command by just typing '1'.\nTo see all aliases just type 'alias'. If you want " +
                 "to see the command programmed on the alias 3 for example, type 'alias 3'.\nTo unset an alias, " +
                 "for example the 3, type 'alias 3 -'.\nIt is possible to combine multiple commands in one alias " +
                 "with separating the commands by a semicolon.\nExample: 'alias 1 status;version'\nThis will execute " +
                 "the command 'status' and after that the command 'version' when you type '1' on the " +
                 "command line."),
    ShellCommand("cc", "cc", "Clear clipboard. Remove anything from clipboard."),
    ShellCommand("changepassword", "changepassword", "Change the master password of current database.\nThis " +
                 "can take some minutes if there are a lot accounts in it.\nNot only the accounts will " +
                 "be re-encrypted but also account history, aliases, command history and so on."),
    ShellCommand("changeconnectordbname", "changeconnectordbname <UUID>|SEARCHSTRING",
                 "Change the database name for the database from the connector identified by UUID or SEARCHSTRING."),
    ShellCommand("changeconnectordbpassword", "changeconnectordbpassword <UUID>|SEARCHSTRING",
                 "Change the database password for the database from the connector identified by UUID or SEARCHSTRING."),
    ShellCommand("changedropboxdbpassword", "changedropboxdbpassword [<UUID>|<SEARCHSTRING>]",
                 "Change password of the dropbox " +
                 "database.\nThe database will be downloaded from the dropbox account and you can enter a new " +
                 "password. After re-encrypting the dropbox version of the database, the database will be " +
                 "uploaded again."),
    ShellCommand("changedropboxdbname", "changedropboxdbname [<UUID>|<SEARCHSTRING>]",
                 "Change database name of the dropbox " +
                 "database.\nThe database will be downloaded from the dropbox account and you can enter a new " +
                 "database name. Then the database will be " +
                 "uploaded again."),
    ShellCommand("changesshdbpassword", "changesshdbpassword [<UUID>|<SEARCHSTRING>]", "Change password of the ssh " +
                 "database.\nThe database will be downloaded from the ssh account and you can enter a new " +
                 "password. After re-encrypting the ssh version of the database, the database will be " +
                 "uploaded again. If no UUID for the ssh target is given, the eventually configured default" +
                 " ssh UUID from the configuration table will be taken."),
    ShellCommand("changewebdavdbpassword", "changewebdavdbpassword [<UUID>|<SEARCHSTRING>]",
                 "Change password of the webdav " +
                 "database.\nThe database will be downloaded from the webdav account and you can enter a new " +
                 "password. After re-encrypting the webdav version of the database, the database will be " +
                 "uploaded again. If no UUID for the webdav target is given, the eventually configured default" +
                 " webdav UUID from the configuration table will be taken."),
    ShellCommand("changesshdbname", "changesshdbname [<UUID>|<SEARCHSTRING>]", "Change the database name of the ssh " +
                 "database.\nThe database will be downloaded from the ssh account and you can enter a new " +
                 "database name. Then the database will be " +
                 "uploaded again. If no UUID for the ssh target is given, the eventually configured default" +
                 " ssh UUID from the configuration table will be taken."),
    ShellCommand("changewebdavdbname", "changewebdavdbname [<UUID>|<SEARCHSTRING>]",
                 "Change the database name of the webdav " +
                 "database.\nThe database will be downloaded from the webdav account and you can enter a new " +
                 "database name. Then the database will be " +
                 "uploaded again. If no UUID for the webdav target is given, the eventually configured default" +
                 " webdav UUID from the configuration table will be taken."),
    ShellCommand("clear", "clear", "Clear console. The screen will be blanked."),
    ShellCommand("clearhistory", "clearhistory", "Clear command history."),
    ShellCommand("cplast", "cplast", "Copy password from the latest found account to the clipboard."),
    ShellCommand("duplicate", "duplicate <UUID>|<SEARCHSTRING>",
                 "Duplicate account with UUID into a new account. You can also use a SEARCHSTRING to " +
                 "identify the account to be duplicated."),
    ShellCommand("copypassword", "copypassword <UUID>|<SEARCHSTRING>", "Copy password from UUID to the clipboard."),
    ShellCommand("countorphanedaccounthistoryentries", "countorphanedaccounthistoryentries ",
                 "Count orphaned account history entries."),
    ShellCommand("delete", "delete <UUID>|<SEARCHSTRING>",
                 "Delete account with UUID. If you do not know the UUID, use a SEARCHSTRING and you " +
                 "will be offered possible accounts to delete.\nA deleted account can not be recovered! It is usually better to invalidate an account."),
    ShellCommand("deleteconnectordb", "deleteconnectordb <UUID>|<SEARCHSTRING>",
                 "Delete the database that is located in the connector account identified by UUID or SEARCHSTRING."),
    ShellCommand("deletemergehistory", "deletemergehistory",
                 "Delete all information about old merge events."),
    ShellCommand("deleteorphanedaccounthistoryentries", "deleteorphanedaccounthistoryentries ",
                 "Delete orphaned account history entries."),
    ShellCommand("executeonstart", "executeonstart [<COMMAND>]",
                 "You can set a command to be executed when the pshell starts. Executing this command without an" +
                 " argument shows the current command which is configured to be executed on start.\n" +
                 "To unset the startup command run 'executeonstart -'.\nTo see the current configuration run 'showconfig'.\n" +
                 "Example: run 2 merge command on start:\nexecuteonstart merge2webdav;merge2file"),
    ShellCommand("executeonstop", "executeonstop [<COMMAND>]",
                 "You can set a command to be executed when the pshell exits. Executing this command without an" +
                 " argument shows the current command which is configured to be executed on exiting.\n" +
                 "To unset the startup command run 'executeonstop -'.\nTo see the current configuration run 'showconfig'.\n" +
                 "Example run 2 merge commands on stop:\nexecuteonstop merge2webdav;merge2file"),
    ShellCommand("forgetdeletedaccounts", "forgetdeletedaccounts", "Delete all entries in deleted_accounts " +
                 "table. This table is used and merged between databases to spread the information about which" +
                 " account with which UUID has been deleted. Emptying this table removes any traces of account " +
                 "UUID's which have existed in this database.\nYou should empty this table on all databases. " +
                 "Otherwise the table will be filled again after the next merge with a database which has entries " +
                 "in the deleted_accounts table."),
    ShellCommand("edit", "edit <SEARCHSTRING>", "Edit account. If <SEARCHSTRING> matched multiple accounts, you " +
                 "can choose one of a list."),
    ShellCommand("!", "! <COMMAND>", "Execute COMMAND in native shell. It is also possible " +
                 "to execute the command without the space before the slash like '!dir' for example."),
    ShellCommand("exit", "exit", "Quit pshell."),
    ShellCommand("forgetaccounthistory", "forgetaccounthistory", "Delete all older/archived versions of accounts."),
    ShellCommand("generategithelp", "generategithelp", "Generate full help documentation in git style"),
    ShellCommand("generatenewdatabaseuuid", "generatenewdatabaseuuid", "Generate a " +
                 "new UUID for the current database. This is useful if you have copied the database file and want " +
                 "to use it as a new instance. You might also set a new database name. This is just for identifying " +
                 "the different database files."),
    ShellCommand("generatepassword", "generatepassword [LENGTH]", "Generate a " +
                 "random password with LENGTH characters. When LENGTH is not set, a 10 char password will be generated."),
    ShellCommand("help", "help [COMMAND]", "Show help for all pshell commands or show the specific help " +
                 "description for COMMAND."),
    ShellCommand("helpverbose", "helpverbose", "Show all help texts for all pshell commands."),
    ShellCommand("history", "history [MAX_ENTRIES]", "Show history of all user inputs in the the pshell.\n" +
                 "If MAX_ENTRIES is set, only the latest MAX_ENTRIES of the command history will be displayed."),
    ShellCommand("idletime", "idletime", "Show idletime in seconds after last command."),
    ShellCommand("invalidate", "invalidate <UUID>|<SEARCHSTRING>", "Invalidate account with UUID or SEARCHSTRING. " +
                 "If you do not know the UUID, just enter a searchstring and you will be offered possible accounts" +
                 " to invalidate.\nIf you invalidate an account the account will be invisible in normal operation." +
                 " If you search something, invalidated accounts are not visible unless you change the settings (" +
                 "see command 'help showinvalidated')."),
    ShellCommand("list", "list", "List all accounts ordered by the last change date."),
    ShellCommand("listconnectorfiles", "listconnectorfiles <UUID>|<SEARCHSTRING>",
                 "List all files in the connector account with <UUID>."),
    ShellCommand("listinvalidated", "listinvalidated", "List all invalidated accounts."),
    ShellCommand("lock", "lock", "Lock pshell console. You will need to enter the password to unlock the pshell again"),
    ShellCommand("#", "#", "Lock pshell console."),
    ShellCommand("maxhistorysize", "maxhistorysize [MAX_SIZE]", "Show current max history size or set it. This " +
                 "limits the amount of history entries that will be saved in the shell_history table in the " +
                 "database.\nTo disable the pshell history, set this value to 0."),
    ShellCommand("merge2dropbox", "merge2dropbox [<UUID>|<SEARCHSTRING>]",
                 "Merge local database with dropbox database copy. If UUID is not given, the configuration " +
                 "will be searched for the default dropbox account uuid. The account has to have connector type = 'dropbox'.\n" +
                 "Example account for a dropbox connector:\n" +
                 "UUID            : 0266d735-87fe-49c1-b02c-c248e4e2caa0\n" +
                 "Name            : <FREE_TEXT>\n" +
                 "URL             : <dropbox application key>\n" +
                 "Loginname       : <dropbox application secret>\n" +
                 "Password        : <dropbox refresh token>\n" +
                 "Type            : <FREE_TEXT>\n" +
                 "Connectortype   : dropbox\n" +
                 " "),
    ShellCommand("merge2file", "merge2file [<UUID>|<SEARCHSTRING>]",
                 "Merge local database with the default file connector database. If UUID is given the account" +
                 " with the UUID will be used to merge with. This account must have the connector type = 'file'." +
                 "This can be set with: setdefaultmergetargetfile.\n" +
                 "Example account for a file connector:\n" +
                 "UUID            : 0266d735-87fe-49c1-b02c-c248e4e2caa0\n" +
                 "Name            : <FREE_TEXT>\n" +
                 "URL             : /home/bert/p/\n" +
                 "Loginname       : <FREE_TEXT>\n" +
                 "Password        : <FREE_TEXT>\n" +
                 "Type            : <FREE_TEXT>\n" +
                 "Connectortype   : file\n" +
                 " "),
    ShellCommand("merge2ssh", "merge2ssh [<UUID>|<SEARCHSTRING>]",
                 "Merge local database with a ssh target which has to be accessible with the account UUID.\n" +
                 "If UUID is not given, the configuration table will be searched for a default ssh account UUID " +
                 "and, if one is found, it will be used to connect to the ssh target. You can use the " +
                 "command 'setsshaccountuuid' to set the default ssh account UUID. The account has to have a connector type = 'ssh'.\n" +
                 "Example account for a ssh connector:\n" +
                 "UUID            : 0266d735-87fe-49c1-b02c-c248e4e2caa0\n" +
                 "Name            : <FREE_TEXT>\n" +
                 "URL             : <hostname>:/home/bert/p/\n" +
                 "Loginname       : <USERNAME>\n" +
                 "Password        : <PASSWORD>\n" +
                 "Type            : <FREE_TEXT>\n" +
                 "Connectortype   : ssh\n" +
                 " "),
    ShellCommand("merge2webdav", "merge2webdav [<UUID>|<SEARCHSTRING>]",
                 "Merge local database with a webdav target which has to be accessible with the account UUID.\n" +
                 "If UUID is not given, the configuration table will be searched for a default webdav account UUID " +
                 "and, if one is found, it will be used to connect to the webdav target. You can use the " +
                 "command 'setwebdavaccountuuid' to set the default webdav account UUID. The account has to have connector type set to 'webdav'.\n" +
                 "Example account for a webdav connector:\n" +
                 "UUID            : 0266d735-87fe-49c1-b02c-c248e4e2caa0\n" +
                 "Name            : <FREE_TEXT>\n" +
                 "URL             : https://<hostname>/p/\n" +
                 "Loginname       : <USERNAME>\n" +
                 "Password        : <PASSWORD>\n" +
                 "Type            : <FREE_TEXT>\n" +
                 "Connectortype   : webdav\n" +
                 " "),
    ShellCommand("mergewith", "mergewith <UUID>|<SEARCHSTRING>",
                 "Merge with with the account with UUID or the account that matches SEARCHSTRING.\n" +
                 "If SEARCHSTRING is not a unique account you will be asked, which account should be used.\n" +
                 "The target account has to have the attribute connector_type set to one of these values:\n" +
                 "file, ssh, webdav, dropbox depending on the kind of protocol that has to be used to connect to the account.\n"),
    ShellCommand("opendatabase", "opendatabase <DATABASE_FILENAME>", "Try to open a p database file with the " +
                 "name DATABASE_FILENAME. If the database does not exist, a new one with the filename will" +
                 " be created.\nWith this command you can switch between multiple p databases."),
    ShellCommand("quit", "quit", "Quit pshell."),
    ShellCommand("redo", "redo [<HISTORY_INDEX>|?]", "Redo the last shell command. The redo command itself will not" +
                 " appear in the command history. You can choose the index of the command in your history if" +
                 " you want.\nIf you choose no index, the latest command will be executed.\nIf you use redo ? you " +
                 "will see the current command history with the indices to choose from."),
    ShellCommand("remove", "remove <UUID>|<SEARCHSTRING>", "The save as the delete command."),
    ShellCommand("revalidate", "revalidate <UUID>|<SEARCHSTRING>", "Revalidate account with UUID or use " +
                 "SEARCHSTRING to find the account you want to revalidate."),
    ShellCommand("search", "search <SEARCHSTRING>", "Search for SEARCHSTRING in all account columns."),
    ShellCommand("searchhelp", "searchhelp <SEARCHSTRING>", "Search for all commands that contain SEARCHSTRING."),
    ShellCommand("she", "she <SEARCHSTRING>", "Alias for searchhelp."),
    ShellCommand("searchhelpverbose", "searchhelpverbose <SEARCHSTRING>", "Search for SEARCHSTRING in all help texts."),
    ShellCommand("searchinvalidated", "searchinvalidated <SEARCHSTRING>",
                 "Search for SEARCHSTRING in all columns of invalidated accounts."),
    ShellCommand("setfileaccountuuid", "setfileaccountuuid <UUID>|<SEARCHSTRING>",
                 "Set a default account in the configuration table to connect to a file target. " +
                 "This account will be used if the command merge2file is called without an account UUID."),
    ShellCommand("setsshaccountuuid", "setsshaccountuuid <UUID>|<SEARCHSTRING>",
                 "Set a default account in the configuration table to connect to a ssh target." +
                 "This account will be used if the command merge2ssh is called without an account UUID."),
    ShellCommand("setwebdavaccountuuid", "setwebdavaccountuuid <UUID>|<SEARCHSTRING>",
                 "Set a default account in the configuration table to connect to a webdav target." +
                 "This account will be used if the command merge2webdav is called without an account UUID."),
    ShellCommand("sc", "sc <SEARCHSTRING>", "Search for SEARCHSTRING in all accounts. " +
                 "If one or more account(s) match the SEARCHSTRING, the password of the first account will be copied " +
                 "to the clipboard.\nNote: Linux users need to install pyperclip3 and xclip to use the copy/paste feature!"),
    ShellCommand("sca", "sca <SEARCHSTRING>", "Search for SEARCHSTRING in all accounts. " +
                 "If one or more account(s) match the SEARCHSTRING, the URL, loginname and password of the first " +
                 "account will be copied to the clipboard one after another. \nNote: Linux users need to install " +
                 "pyperclip3 and xclip to use the copy/paste feature!"),
    ShellCommand("scl", "scl <SEARCHSTRING>", "Search for SEARCHSTRING in all accounts. " +
                 "If one or more account(s) match the SEARCHSTRING, the loginname of the first account will be copied " +
                 "to the clipboard.\nNote: Linux users need to install pyperclip3 and xclip to use the copy/paste feature!"),
    ShellCommand("scu", "scu <SEARCHSTRING>", "Search for SEARCHSTRING in all accounts. " +
                 "If one or more account(s) match the SEARCHSTRING, the URL of the first account will be copied " +
                 "to the clipboard.\nNote: Linux users need to install pyperclip3 and xclip to use the copy/paste feature!"),
    ShellCommand("slowprintenabled", "slowprintenabled [on|off]", "Enable, disable or show the " +
                 "status of the slow printing feature. The slow printing feature prints lots of queries a bit slower," +
                 " which looks kinda cool :) But if you think it's annoying, disable it (created for ben)."),
    ShellCommand("sp", "sp <UUID>|<SEARCHSTRING>", "Set password for account with UUID or SEARCHSTRING. If" +
                 " shadow passwords is on, the password will be read hidden so that none can gather it from " +
                 "your screen. If you do not no the <UUID>, use a <SEARCHSTRING> and you will be offered possible " +
                 "accounts the change the password for."),
    ShellCommand("st", "st <SEARCHSTRING>", "Search for SEARCHSTRING in the type field of all accounts"),
    ShellCommand("setdatabasename", "setdatabasename <NAME>", "Set database to NAME. This is a logical name for " +
                 "the current database. To unset the database name, set it to '-'"),
    ShellCommand("setdropboxaccountuuid", "setdropboxaccountuuid <UUID>",
                 "Set the default dropbox account uuid in the configuration. Whenever you run merge2dropbox, " +
                 "this UUID will be used as the default dropbox account."),
    ShellCommand("shadowpasswords", "shadowpasswords [on|off]", "Set shadow passwords to on or off in console output" +
                 " or show current shadow status.\nThis is useful if you are not alone watching the output " +
                 "of this program on the monitor."),
    ShellCommand("showaccounthistory", "showaccounthistory <UUID>|<SEARCHSTRING>", "Show change history of" +
                 " account with <UUID>. If you do not know the uuid, use a <SEARCHSTRING> and you can choose from " +
                 "possible existing accounts which include your <SEARCHSTRING>."),
    ShellCommand("showconfig", "showconfig", "Show current configuration of the environment including if account " +
                 "passwords are shadowed, if verbose mode is ..."),
    ShellCommand("showlinks", "showlinks", "Show links to github homepage, binary " +
                 "downloads etc."),
    ShellCommand("showinvalidated", "showinvalidated [on|off]", "Show invalidated accounts. If empty " +
                 "the current status will be shown."),
    ShellCommand("showmergehistory", "showmergehistory", "Show the history of all database merge events."),
    ShellCommand("showmergedetail", "showmergedetail <UUID>",
                 "Show the merge history detail for merge event with UUID."),
    ShellCommand("showlatestmerge", "showlatestmerge", "Show the merge history detail for the latest merge event."),
    ShellCommand("showstatusonstartup", "showstatusonstartup [on|off]",
                 "Show status when pshell starts."),
    ShellCommand("showunmergedchanges", "showunmergedchanges", "Show all changes since the " +
                 "last successfully merge event. This includes new created accounts, changed accounts and the " +
                 "uuid's of deleted accounts."),
    ShellCommand("showunmergedwarning", "showunmergedwarning [on|off]", "Show warning on startup if there are " +
                 "unmerged changes in local database compared to the latest known merge database.\nWith no " +
                 "arguments, the current status will be shown."),
    ShellCommand("sql", "sql <COMMAND>", "Execute COMMAND in database in native SQL language. The p database " +
                 "is fully accessible with sql commands."),
    ShellCommand("status", "status", "Show configuration and database status.\nA short overview of the database " +
                 "will be shown including number of accounts, encryption status, database name..."),
    ShellCommand("timeout", "timeout [<MINUTES>]", "Set the maximum pshell inactivity timeout to MINUTES before " +
                 "locking the pshell (0 = disable timeout). Without MINUTES the current timeout is shown."),
    ShellCommand("trackaccounthistory", "trackaccounthistory on|off", "Track the history of changed accounts. " +
                 "You may also want to use the command: 'forgetaccounthistory' to delete all archived accounts."),
    ShellCommand("updatep", "updatep",
                 "Update p program. This command will download the latest p executable from git."),
    ShellCommand("verbose", "verbose on|off", "Show verbose account infos true or false.\nIf verbose is on " +
                 "then creation, change and invalidation timestamps will be shown."),
    ShellCommand("version", "version", "Show program version info.")
]
SHELL_COMMANDS.sort()

DEFAULT_PSHELL_MAX_IDLE_TIMEOUT_MIN = 30
pshell_max_idle_minutes_timeout = DEFAULT_PSHELL_MAX_IDLE_TIMEOUT_MIN
DEFAULT_PSHELL_MAX_HISTORY_SIZE = 10
pshell_max_history_size = DEFAULT_PSHELL_MAX_HISTORY_SIZE
show_unmerged_changes_warning_on_startup = True
show_status_on_startup = True
pshell_print_slow_enabled = True
PSHELL_COMMAND_DELIMITER = ";"


# Try to find the uuid for a given searchstring. If there are multiple accounts that match,
# then ask the user which one to take.
def find_uuid_for_searchstring_interactive(searchstring: str, p_database: pdatabase) -> str | None:
    # matching_uuid = None
    searchstring = searchstring.strip()
    if searchstring == "" or searchstring is None:
        print("Searchstring is missing.")
        return None
    account_array = p_database.get_accounts_decrypted(searchstring)
    if len(account_array) == 0:
        print("No account found.")
        return None
    if len(account_array) != 1:
        i = 1
        # print()
        for acc in account_array:
            print()
            print(" [" + str(i).rjust(2) + "]" + " - Name: " + acc.name)
            i = i + 1
        print("")
        try:
            index = input("Multiple accounts found. Please specify the # you need: ")
        except KeyboardInterrupt as e:
            print()
            index = ""
        if index == "":
            print("Nothing selected.")
            return None
        try:
            matching_uuid = account_array[int(index) - 1].uuid
        except Exception as e:
            print("Error: " + str(e))
            return None
        return matching_uuid
    try:
        matching_uuid = account_array[0].uuid
    except Exception as e:
        print("Error copying password to the clipboard: " + str(e))
        return None
    return matching_uuid


def get_prompt_string(p_database: pdatabase.PDatabase) -> str:
    logical_database_name = pdatabase.get_database_name(p_database.database_filename)
    if logical_database_name != "":
        prompt_string = "[" + logical_database_name + "] pshell> "
    else:
        prompt_string = "[" + p_database.database_filename + "] pshell> "
    return prompt_string


def expand_string_2_shell_command(string: str) -> ShellCommand | None:
    if string is None or string.strip() == "":
        return None

    # it is possible to search with "/SEARCHSTR" and to execute an os command with "!CMD"
    # so I separate / and ! here from the rest
    if string.startswith("/"):
        string = string.replace("/", "/ ", 1)
    if string.startswith("!"):
        string = string.replace("!", "! ", 1)

    tokens = string.split()
    first_token = tokens[0]
    for shell_command in SHELL_COMMANDS:
        if shell_command.command.startswith(first_token):
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


def print_shell_command_history(shell_history_array: [ShellCommand], show_entry_count=0):
    if show_entry_count == 0:
        i = len(shell_history_array)
    else:
        i = len(shell_history_array) - (len(shell_history_array) - show_entry_count)
        if i > len(shell_history_array):
            i = len(shell_history_array)
    while i > 0:
        print(" [" + str(i).rjust(3) + "] - " +
              str(shell_history_array[i - 1].execution_date) +
              " - " + shell_history_array[i - 1].user_input)
        i -= 1


def load_pshell_configuration(p_database: pdatabase.PDatabase):
    global pshell_print_slow_enabled
    config_value = pdatabase.get_attribute_value_from_configuration_table(
        p_database.database_filename,
        pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_PRINT_SLOW_ENABLED)
    if config_value is not None and (config_value == "True" or config_value == "False"):
        print_slow.set_delay_enabled(parse_bool(config_value))

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
    if pshell_max_history_size is not None and not pshell_max_history_size.isnumeric() \
            or pshell_max_history_size is None \
            or pshell_max_history_size == "":
        pshell_max_history_size = DEFAULT_PSHELL_MAX_HISTORY_SIZE
        pdatabase.set_attribute_value_in_configuration_table(
            p_database.database_filename,
            pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_MAX_HISTORY_SIZE, pshell_max_history_size)
    else:
        pshell_max_history_size = int(pshell_max_history_size)

    global show_status_on_startup
    config_value = pdatabase.get_attribute_value_from_configuration_table(
        p_database.database_filename,
        pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHOW_STATUS_ON_STARTUP)
    if config_value is not None and (config_value == "True" or config_value == "False"):
        show_status_on_startup = parse_bool(config_value)

    config_value = pdatabase.get_attribute_value_from_configuration_table(
        p_database.database_filename,
        pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHADOW_PASSWORDS)
    if config_value is not None and (config_value == "True" or config_value == "False"):
        p_database.shadow_passwords = parse_bool(config_value)
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


def is_windows_os() -> bool:
    # windows
    if os.name == 'nt':
        return True
    # for mac and linux os.name is posix
    else:
        return False


def is_posix_os() -> bool:
    if os.name == 'posix':
        return True
    # for mac and linux os.name is posix
    else:
        return False


def is_aarch64_architecture() -> bool:
    if is_windows_os():
        return False
    try:
        if os.uname().machine == 'aarch64':
            return True
    except Exception:
        pass
    return False


def is_x86_64_architecture() -> bool:
    if is_windows_os():
        return False
    try:
        if os.uname().machine == 'x86_64':
            return True
    except Exception:
        pass
    return False


def clear_console():
    # windows
    if is_windows_os():
        os.system('cls')
    # for mac and linux os.name is posix
    else:
        os.system('clear')


def start_pshell(p_database: pdatabase.PDatabase):
    global pshell_max_idle_minutes_timeout
    global pshell_max_history_size
    global show_unmerged_changes_warning_on_startup
    global show_status_on_startup
    load_pshell_configuration(p_database)

    clear_console()
    user_input = ""
    user_input_list = []
    exit_is_pending = False

    execute_on_start_command = p_database.get_execute_on_start_command()
    if execute_on_start_command:
        print("Execute on start command: " + execute_on_start_command)
        user_input_list.extend(execute_on_start_command.split(PSHELL_COMMAND_DELIMITER))

    latest_found_account = None

    if show_status_on_startup is True:
        pdatabase.print_database_statistics(p_database.database_filename)

    if show_unmerged_changes_warning_on_startup is True and \
            pdatabase.get_database_has_unmerged_changes(p_database.database_filename) is True:
        print(colored("Note: You have unmerged changes in your local database.", 'red'))
    manual_locked = False
    if pshell_max_history_size < 1:
        p_database.delete_all_shell_history_entries()
    # shell_history_array = p_database.get_shell_history_entries_decrypted()

    while user_input != "quit":
        # while True:
        prompt_string = get_prompt_string(p_database)
        last_activity_date = datetime.datetime.now()

        # process pending commands in user_input_list if > 0 or read new input from keyboard into user_input_list
        # if not manual_locked:
        if not manual_locked and len(user_input_list) == 0:
            try:
                # Eingabe mit timeout oder ohne machen:
                if int(pshell_max_idle_minutes_timeout) > 0:
                    input_line = inputimeout(prompt=prompt_string, timeout=(int(pshell_max_idle_minutes_timeout) * 60))
                else:
                    input_line = input(prompt_string)
                user_input_list = input_line.split(PSHELL_COMMAND_DELIMITER)
            except KeyboardInterrupt:
                print()
                continue
            except TimeoutOccurred:
                pass

        if len(user_input_list) > 0:
            user_input = user_input_list.pop(0).strip()

        if user_input != "":
            current_shell_history_entry = ShellHistoryEntry(user_input=user_input)
        else:
            current_shell_history_entry = None

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
                print(prompt_string)
                try:
                    user_input_pass = getpass.getpass("Enter database password: ")
                except KeyboardInterrupt:
                    print()
                    return
                if user_input_pass is None or user_input_pass != p_database.get_database_password_as_string():
                    print("Error: password is wrong.")
                    time.sleep(2)
                else:
                    # password is ok
                    clear_console()
                    print(colored("PShell unlocked.", "green"))
                    if manual_locked:
                        manual_locked = False
                    user_input = ""
                    break

        # # it is possible to search with "/SEARCHSTR" and to execute an os command with "!CMD"
        # # so I separate / and ! here from the rest
        # if user_input.startswith("/"):
        #     user_input = user_input.replace("/", "/ ", 1)
        # if user_input.startswith("!"):
        #     user_input = user_input.replace("!", "! ", 1)

        # Create shell_command object from user_input
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

        # check if the (next) command is the alias command and there are more commands in the user_input_list.
        # The alias command has to be used with 2 arguments for our special case here: alias Nr CMD
        # Then the rest of the user_input_list is used as the argument for the alias command.
        # This is necessary to enable i.e. : alias 1 c1;c2;c3
        if (shell_command.command == "alias"
                and len(user_input_list) > 0
                and len(shell_command.arguments) > 1):
            while len(user_input_list) > 0:
                shell_command.arguments[1] = (shell_command.arguments[1] + PSHELL_COMMAND_DELIMITER +
                                              user_input_list.pop(0))

        #
        # proceed possible commands
        #

        # check if the command is the "redo last command" command
        if shell_command.command == "redo":
            shell_history_array = p_database.get_shell_history_entries_decrypted()
            if len(shell_history_array) == 0:
                print("Shell history is empty.")
                continue
            # redo_index = -1
            # when there is no index of the command history array given, use the latest one
            if len(shell_command.arguments) == 1:
                redo_index = 1
            else:
                if shell_command.arguments[1].strip() == "?":
                    print_shell_command_history(shell_history_array)
                    try:
                        redo_index_input = input("Enter history index: ")
                        if not redo_index_input.isnumeric():
                            continue
                        else:
                            redo_index = int(redo_index_input)
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
            print("Redo command: " + last_user_input)
            if shell_command is None:
                print("Unknown command '" + last_user_input + "'")
                print("Enter 'help' for command help")
                continue
            else:
                current_shell_history_entry = ShellHistoryEntry(user_input=last_user_input)
        # else:
        p_database.add_shell_history_entry(current_shell_history_entry, pshell_max_history_size)
        # and proceed parsing the command...:

        # check if the command is an alias. then the alias must be replaced with the stored command(s)
        if shell_command.command in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"):
            # Read stored command(s) from database and populate user_input_list
            alias_command = p_database.get_alias_command_decrypted(shell_command.command)
            if alias_command == "":
                print("Error: Alias " + shell_command.command + " is not set")
            else:
                user_input_list.extend(alias_command.split(PSHELL_COMMAND_DELIMITER))
            continue

        # continue with command processing

        if shell_command.command == "!":
            if len(shell_command.arguments) == 1:
                print("COMMAND is missing.")
                print(shell_command.synopsis)
                continue
            os.system("bash -i -c """ + shell_command.arguments[1] + """)
            continue

        if shell_command.command == "add":
            new_account_name = ""
            if len(shell_command.arguments) == 2:
                new_account_name = shell_command.arguments[1].strip()
            p.add(p_database, account_name=new_account_name)
            continue

        if shell_command.command == "alias":
            if len(shell_command.arguments) == 1:
                aliases = p_database.get_alias_commands_decrypted()
                for alias in aliases:
                    try:
                        print_slow.print_slow(alias)
                    except KeyboardInterrupt:
                        print()
                        continue
            else:  # 2 arguments
                alias_argument_list = shell_command.arguments[1].split(maxsplit=1)
                current_alias = alias_argument_list[0]
                if current_alias not in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"):
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

        if shell_command.command == "cc":
            pyperclip3.clear()
            continue

        if shell_command.command == "changedropboxdbpassword":
            account_uuid = None
            if len(shell_command.arguments) > 1:
                account_uuid = find_uuid_for_searchstring_interactive(shell_command.arguments[1].strip(), p_database)
            # if not account_uuid:
            #     continue
            try:
                connector = connector_manager.get_dropbox_connector(p_database, account_uuid)
                connector_manager.change_database_password_from_connector(p_database, connector)
            except Exception as e:
                print(str(e))
            continue

        if shell_command.command == "changeconnectordbname":
            if len(shell_command.arguments) == 1:
                print("Error: UUID or account name is missing.")
                continue
            account_uuid = find_uuid_for_searchstring_interactive(shell_command.arguments[1].strip(), p_database)
            if not account_uuid:
                continue
            try:
                connector = connector_manager.get_connector(p_database, account_uuid)
                connector_manager.change_database_name_from_connector(p_database, connector)
            except Exception as e:
                print(str(e))
            continue

        if shell_command.command == "changeconnectordbpassword":
            # account_uuid = None
            if len(shell_command.arguments) == 1:
                print("Error: UUID or account name is missing.")
                continue
            account_uuid = find_uuid_for_searchstring_interactive(shell_command.arguments[1].strip(), p_database)
            if not account_uuid:
                continue
            try:
                connector = connector_manager.get_connector(p_database, account_uuid)
                connector_manager.change_database_password_from_connector(p_database, connector)
            except Exception as e:
                print(str(e))
            continue

        if shell_command.command == "changedropboxdbname":
            account_uuid = None
            if len(shell_command.arguments) > 1:
                account_uuid = find_uuid_for_searchstring_interactive(shell_command.arguments[1].strip(), p_database)
            try:
                connector = connector_manager.get_dropbox_connector(p_database, account_uuid)
                connector_manager.change_database_name_from_connector(p_database, connector)
            except Exception as e:
                print(str(e))
            continue

        if shell_command.command == "changesshdbname":
            account_uuid = None
            if len(shell_command.arguments) > 1:
                account_uuid = find_uuid_for_searchstring_interactive(shell_command.arguments[1].strip(), p_database)
            try:
                connector = connector_manager.get_ssh_connector(p_database, account_uuid)
                connector_manager.change_database_name_from_connector(p_database, connector)
            except Exception as e:
                print(str(e))
            continue

        if shell_command.command == "changesshdbpassword":
            account_uuid = None
            if len(shell_command.arguments) > 1:
                account_uuid = find_uuid_for_searchstring_interactive(shell_command.arguments[1].strip(), p_database)
            try:
                connector = connector_manager.get_ssh_connector(p_database, account_uuid)
                connector_manager.change_database_password_from_connector(p_database, connector)
            except Exception as e:
                print(str(e))
            continue

        if shell_command.command == "changewebdavdbpassword":
            account_uuid = None
            if len(shell_command.arguments) > 1:
                account_uuid = find_uuid_for_searchstring_interactive(shell_command.arguments[1].strip(), p_database)
            try:
                connector = connector_manager.get_webdav_connector(p_database, account_uuid)
                connector_manager.change_database_password_from_connector(p_database, connector)
            except Exception as e:
                print(str(e))
            continue

        if shell_command.command == "changewebdavdbname":
            account_uuid = None
            if len(shell_command.arguments) > 1:
                account_uuid = find_uuid_for_searchstring_interactive(shell_command.arguments[1].strip(), p_database)
            try:
                connector = connector_manager.get_webdav_connector(p_database, account_uuid)
                connector_manager.change_database_name_from_connector(p_database, connector)
            except Exception as e:
                print(str(e))
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
            p_database.delete_all_shell_history_entries()
            continue

        if shell_command.command == "copypassword":
            if len(shell_command.arguments) == 1:
                print("UUID is missing.")
                print(shell_command.synopsis)
                continue
            # account = p_database.get_account_by_uuid_and_decrypt(shell_command.arguments[1].strip())
            account_uuid = find_uuid_for_searchstring_interactive(shell_command.arguments[1].strip(), p_database)
            if not account_uuid:
                continue
            account = p_database.get_account_by_uuid_and_decrypt(account_uuid)
            try:
                # pyperclip3.copy(password)
                print("Account   : " + account.name)
                print("CLIPBOARD : Password")
                pyperclip3.copy(account.password)
            except Exception as e:
                print("Error copying password to the clipboard: " + str(e))
            continue

        if shell_command.command == "countorphanedaccounthistoryentries":
            try:
                orphaned_account_history_entries = p_database.get_orphaned_account_history_entries_count()
                print("Orphaned account history entries: " + str(orphaned_account_history_entries))
            except Exception as e:
                print("Error counting orphaned history entries: " + str(e))
            continue

        if shell_command.command == "delete" or shell_command.command == "remove":
            if len(shell_command.arguments) == 1:
                print("UUID or SEARCHSTRING is missing.")
                print(shell_command.synopsis)
                continue
            search_string = shell_command.arguments[1].strip()
            uuid_to_delete = find_uuid_for_searchstring_interactive(search_string, p_database)
            if uuid_to_delete is None:
                continue
            p_database.delete_account(uuid_to_delete)
            continue

        if shell_command.command == "duplicate":
            if len(shell_command.arguments) == 1:
                print("UUID or SEARCHSTRING is missing.")
                print(shell_command.synopsis)
                continue
            search_string = shell_command.arguments[1].strip()
            uuid_to_duplicate = find_uuid_for_searchstring_interactive(search_string, p_database)
            if uuid_to_duplicate is None:
                print("SEARCHSTRING or UUID not found.")
                continue
            p_database.duplicate_account(uuid_to_duplicate)
            continue

        if shell_command.command == "edit":
            if len(shell_command.arguments) == 1:
                print("UUID or SEARCHSTRING is missing.")
                print(shell_command.synopsis)
                continue
            uuid_to_edit = find_uuid_for_searchstring_interactive(shell_command.arguments[1].strip(), p_database)
            if uuid_to_edit is not None:
                p.edit(p_database, uuid_to_edit)
            continue

        if shell_command.command == "deleteorphanedaccounthistoryentries":
            try:
                p_database.delete_orphaned_account_history_entries()
            except Exception as e:
                print("Error deleting orphaned history entries: " + str(e))
            continue

        if shell_command.command == "deleteconnectordb":
            account_uuid = None
            if len(shell_command.arguments) > 1:
                account_uuid = find_uuid_for_searchstring_interactive(shell_command.arguments[1].strip(), p_database)
            if not account_uuid:
                continue
            try:
                connector = connector_manager.get_connector(p_database, account_uuid)
                connector_manager.delete_database_in_connector(p_database, connector)
            except Exception as e:
                print("Error: " + str(e))
            continue

        if shell_command.command == "deletemergehistory":
            p_database.delete_merge_history()

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

        if shell_command.command == "executeonstart":
            if len(shell_command.arguments) == 1:
                execute_on_start_command = p_database.get_execute_on_start_command()
                if execute_on_start_command == "":
                    execute_on_start_command = "None"
                print("Execute on start command : " + execute_on_start_command)
                continue
            try:
                if shell_command.arguments[1].strip() == "-":
                    execute_on_start_command = ""
                else:
                    # If the user wanted to execute multiple commands on start like : merge2d;merge2w
                    # then we have to collect all remaining user_input_list elements together again:
                    while len(user_input_list) > 0:
                        shell_command.arguments[1] = (shell_command.arguments[1] + PSHELL_COMMAND_DELIMITER +
                                                      user_input_list.pop(0))
                    execute_on_start_command = shell_command.arguments[1].strip()
                p_database.set_execute_on_start_command(execute_on_start_command)
            except Exception as e:
                print("Error setting execute on start command: " + str(e))
            continue

        if shell_command.command == "executeonstop":
            if len(shell_command.arguments) == 1:
                execute_on_stop_command = p_database.get_execute_on_stop_command()
                if execute_on_stop_command == "":
                    execute_on_stop_command = "None"
                print("Execute on stop command : " + execute_on_stop_command)
                continue
            try:
                if shell_command.arguments[1].strip() == "-":
                    execute_on_stop_command = ""
                else:
                    # If the user wanted to execute multiple commands on stop like : merge2d;merge2w
                    # then we have to collect all remaining user_input_list elements together again:
                    while len(user_input_list) > 0:
                        shell_command.arguments[1] = (shell_command.arguments[1] + PSHELL_COMMAND_DELIMITER +
                                                      user_input_list.pop(0))
                    execute_on_stop_command = shell_command.arguments[1].strip()
                p_database.set_execute_on_stop_command(execute_on_stop_command)
            except Exception as e:
                print("Error setting execute on stop command: " + str(e))
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

        if shell_command.command == "generategithelp":
            print("Saving git formatted full documentation to: " + p.GIT_FULL_DOCUMENTATION_FILENAME)
            lines = ""
            for sc in SHELL_COMMANDS:
                lines = lines + sc.generate_git_manual()
            try:
                doc_file = open(p.GIT_FULL_DOCUMENTATION_FILENAME, "w")
                doc_file.write(lines)
                doc_file.close()
            except Exception as e:
                print("Error generating git documentation: " + str(e))
            continue

        if shell_command.command == "generatepassword":
            password_length = 10
            if len(shell_command.arguments) == 2:
                try:
                    password_length = int(shell_command.arguments[1])
                except Exception as e:
                    print("Error: " + str(e))
            print("Password: " + password_generator.get_password(password_length))
            continue

        if shell_command.command == "help":
            if len(shell_command.arguments) == 1:
                print()
                print(colored(" PShell command help", "green"))
                print()
                print(colored(" Type 'help COMMAND' to get usage details for COMMAND", "green"))
                print(colored(" It is enough to type the first distinct letter(s) of any COMMAND.", "green"))
                print()
                print(colored(" You can search through all command help texts with 'searchhelp <SEARCHSTRING>'",
                              "green"))
                print(colored(" to get a list of commands which contain SEARCHSTRING in their help text.", "green"))
                print()
                print(colored(" You can also use 'searchhelpverbose <SEARCHSTRING>' to print the full help text(s)",
                              "green"))
                print(colored(" of commands which contain SEARCHSTRING in their help text.", "green"))
                print()
                print(colored(" Complete list of p commands:", "green"))
                print()
                for shell_command in SHELL_COMMANDS:
                    # print(str(shell_command))
                    print(colored(shell_command.synopsis, "green"))
                    # print()
            else:
                help_command = expand_string_2_shell_command(shell_command.arguments[1])
                if help_command is not None:
                    help_command.print_manual()
                else:
                    print("Unknown command: " + shell_command.arguments[1])
            continue

        if shell_command.command == "helpverbose":
            print()
            for sc in SHELL_COMMANDS:
                sc.print_manual()
                print()
            continue

        if shell_command.command == "history":
            shell_history_array = p_database.get_shell_history_entries_decrypted()
            max_hist_entries = len(shell_history_array)
            if len(shell_command.arguments) > 1:
                try:
                    max_hist_entries = int(shell_command.arguments[1])
                except Exception as e:
                    print("Error: " + str(e))
            print_shell_command_history(shell_history_array, max_hist_entries)
            continue

        if shell_command.command == "idletime":
            idle_time = round(time_diff.total_seconds())
            if idle_time < 120:
                idle_time_str = str(idle_time) + " sec"
            else:
                idle_time = round(idle_time / 60)
                idle_time_str = str(idle_time) + " min"
            print("Idle time: " + idle_time_str)
            continue

        if shell_command.command == "invalidate":
            if len(shell_command.arguments) == 1:
                print("SEARCHSTRING or UUID is missing.")
                print(shell_command.synopsis)
                continue
            search_string = shell_command.arguments[1].strip()
            uuid_to_invalidate = find_uuid_for_searchstring_interactive(search_string, p_database)
            if not uuid_to_invalidate:
                continue
            if p_database.invalidate_account(uuid_to_invalidate):
                print("Account with UUID: " + uuid_to_invalidate + " has been invalidated.")
            continue

        if shell_command.command == "list":
            p_database.search_accounts("")
            continue

        if shell_command.command == "listconnectorfiles":
            account_uuid = None
            if len(shell_command.arguments) > 1:
                account_uuid = find_uuid_for_searchstring_interactive(shell_command.arguments[1].strip(), p_database)
            if not account_uuid:
                continue
            try:
                connector = connector_manager.get_connector(p_database, account_uuid)
                files = connector.list_files("")
                if len(files) > 0:
                    print("Files found in the connector:")
                    for f in files:
                        print(f)
                else:
                    print("No files found in connector.")
                continue
            except Exception as e:
                print("Error: " + str(e))
            continue

        if shell_command.command == "listinvalidated":
            p_database.search_invalidated_accounts("")
            continue

        if shell_command.command == "lock" or shell_command.command == "#":
            manual_locked = True
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
            account_uuid = None
            if len(shell_command.arguments) > 1:
                account_uuid = find_uuid_for_searchstring_interactive(shell_command.arguments[1].strip(), p_database)
            try:
                connector = connector_manager.get_dropbox_connector(p_database, account_uuid)
                p_database.merge_database_with_connector(connector)
            except Exception as e:
                print("Error: " + str(e))
            continue

        if shell_command.command == "merge2file":
            account_uuid = None
            if len(shell_command.arguments) > 1:
                account_uuid = find_uuid_for_searchstring_interactive(shell_command.arguments[1].strip(), p_database)
            try:
                connector = connector_manager.get_file_connector(p_database, account_uuid)
                p_database.merge_database_with_connector(connector)
            except Exception as e:
                print("Error: " + str(e))
            continue

        if shell_command.command == "merge2ssh":
            account_uuid = None
            if len(shell_command.arguments) > 1:
                account_uuid = find_uuid_for_searchstring_interactive(shell_command.arguments[1].strip(), p_database)
            try:
                connector = connector_manager.get_ssh_connector(p_database, account_uuid)
                p_database.merge_database_with_connector(connector)
            except Exception as e:
                print("Error: " + str(e))
            continue

        if shell_command.command == "merge2webdav":
            account_uuid = None
            if len(shell_command.arguments) > 1:
                account_uuid = find_uuid_for_searchstring_interactive(shell_command.arguments[1].strip(), p_database)
            try:
                connector = connector_manager.get_webdav_connector(p_database, account_uuid)
                p_database.merge_database_with_connector(connector)
            except Exception as e:
                print("Error: " + str(e))
            continue

        if shell_command.command == "mergewith":
            if len(shell_command.arguments) == 1:
                print("UUID or SEARCHSTRING is missing.")
                print(shell_command.synopsis)
                continue
            account_uuid = None
            if len(shell_command.arguments) > 1:
                # account_uuid = shell_command.arguments[1].strip()
                account_uuid = find_uuid_for_searchstring_interactive(shell_command.arguments[1].strip(),
                                                                      p_database)
            if not account_uuid:
                continue
            try:
                connector = connector_manager.get_connector(p_database, account_uuid)
                p_database.merge_database_with_connector(connector)
            except Exception as e:
                print("Error: " + str(e))
            continue

        if shell_command.command == "opendatabase":
            if len(shell_command.arguments) == 1:
                print("DATABASE_FILENAME is missing.")
                print(shell_command.synopsis)
                continue
            new_database_filename = shell_command.arguments[1].strip()
            if os.path.exists(new_database_filename):
                try:
                    new_database_password = getpass.getpass("Enter database password: ")
                except KeyboardInterrupt:
                    print()
                    continue
            else:
                print(colored("Database does not exist.", "red"))
                try:
                    new_database_password = getpass.getpass("Enter password for new database    : ")
                    new_database_password_confirm = getpass.getpass("Confirm password for new database  : ")
                except KeyboardInterrupt:
                    print()
                    continue
                if new_database_password != new_database_password_confirm:
                    print(colored("Error: Passwords do not match.", "red"))
                    input("Press enter to exit.")
                    sys.exit(1)
            if new_database_password is None:
                print(colored("Database password is not set! Enter password on command line or use -p or -E option.",
                              "red"))
                input("Press enter to exit.")
                sys.exit(1)

            # Now try to open/create the database:
            if not pdatabase.is_valid_database_password(new_database_filename, new_database_password.encode("UTF-8")):
                print("Error opening database: Password is wrong.")
                continue
            new_p_database = pdatabase.PDatabase(new_database_filename, new_database_password)
            start_pshell(new_p_database)
            input("Press enter to exit.")
            sys.exit()

        if shell_command.command == "quit" or shell_command.command == "exit":
            execute_on_stop_command = p_database.get_execute_on_stop_command()
            if execute_on_stop_command != "" and not exit_is_pending:
                clear_console()
                print("Executing command on stop: " + execute_on_stop_command)
                user_input_list.extend(execute_on_stop_command.split(PSHELL_COMMAND_DELIMITER))
                user_input_list.extend(["quit"])
                exit_is_pending = True
                continue
            # clear_console()
            break

        if shell_command.command == "generatenewdatabaseuuid":
            new_database_uuid = str(uuid.uuid4())
            pdatabase.set_attribute_value_in_configuration_table(p_database.database_filename,
                                                                 pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_UUID,
                                                                 new_database_uuid)
            print("New database UUID is now: " + pdatabase.get_database_uuid(p_database.database_filename))
            continue

        if shell_command.command == "revalidate":
            if len(shell_command.arguments) == 1:
                print("UUID or SEARCHSTRING is missing.")
                print(shell_command.synopsis)
                continue
            search_string = shell_command.arguments[1].strip()
            old_show_invalidated_value = p_database.show_invalidated_accounts
            p_database.show_invalidated_accounts = True
            uuid_to_revalidate = find_uuid_for_searchstring_interactive(search_string, p_database)
            p_database.show_invalidated_accounts = old_show_invalidated_value
            if uuid_to_revalidate is None:
                continue
            if p_database.revalidate_account(uuid_to_revalidate):
                print("Account " + uuid_to_revalidate + " revalidated.")
            else:
                print("Could not revalidate account " + uuid_to_revalidate + ".")
            continue

        if shell_command.command == "search" or shell_command.command == "/":
            if len(shell_command.arguments) == 1:
                print("SEARCHSTRING is missing.")
                print(shell_command.synopsis)
                continue
            p_database.search_accounts(shell_command.arguments[1].strip())
            # remember latest found account:
            account_array = p_database.get_accounts_decrypted(shell_command.arguments[1].strip())
            if len(account_array) == 0:
                latest_found_account = None
                continue
            else:
                latest_found_account = account_array[len(account_array) - 1]
            continue

        if shell_command.command == "searchhelp" or shell_command.command == "she":
            if len(shell_command.arguments) == 1:
                print("SEARCHSTRING is missing.")
                print(shell_command.synopsis)
                continue
            search_string = shell_command.arguments[1].strip().lower()
            if search_string == "":
                continue
            print()
            print(colored("Searching in all help texts for: '" + search_string + "'", "green"))
            print()
            results_found = 0
            for sc in SHELL_COMMANDS:
                if search_string in sc.command.lower():
                    results_found += 1
                    print(colored(sc.command, "green"))
                    # print()
            if results_found > 0:
                print()
            else:
                print("No results found.")
                print()
            continue

        if shell_command.command == "searchhelpverbose":
            if len(shell_command.arguments) == 1:
                print("SEARCHSTRING is missing.")
                print(shell_command.synopsis)
                continue
            search_string = shell_command.arguments[1].strip().lower()
            print()
            for sc in SHELL_COMMANDS:
                if search_string in sc.command.lower() or \
                        search_string in sc.synopsis.lower() or \
                        search_string in sc.description.lower():
                    sc.print_manual()
                    print()
            continue

        if shell_command.command == "searchinvalidated":
            if len(shell_command.arguments) == 1:
                print("SEARCHSTRING is missing.")
                print(shell_command.synopsis)
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

        if shell_command.command == "setfileaccountuuid":
            if len(shell_command.arguments) == 1:
                print("UUID of file account is missing.")
                print(shell_command.synopsis)
                continue
            new_file_account_uuid = shell_command.arguments[1].strip()
            if new_file_account_uuid == "-":
                new_file_account_uuid = ""
            else:
                new_file_account_uuid = find_uuid_for_searchstring_interactive(shell_command.arguments[1].strip(),
                                                                               p_database)
            p.set_attribute_value_in_configuration_table(
                p_database.database_filename,
                pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_CONNECTOR_DEFAULT_FILE_ACCOUNT_UUID,
                new_file_account_uuid)
            continue

        if shell_command.command == "setsshaccountuuid":
            if len(shell_command.arguments) == 1:
                print("UUID of ssh account is missing.")
                print(shell_command.synopsis)
                continue
            new_ssh_account_uuid = shell_command.arguments[1].strip()
            if new_ssh_account_uuid == "-":
                new_ssh_account_uuid = ""
            else:
                new_ssh_account_uuid = find_uuid_for_searchstring_interactive(shell_command.arguments[1].strip(),
                                                                              p_database)
            # if new_ssh_account_uuid == "-":
            #     new_ssh_account_uuid = ""
            p.set_attribute_value_in_configuration_table(
                p_database.database_filename,
                pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_CONNECTOR_DEFAULT_SSH_ACCOUNT_UUID,
                new_ssh_account_uuid)
            continue

        if shell_command.command == "setwebdavaccountuuid":
            if len(shell_command.arguments) == 1:
                print("UUID of webdav account is missing.")
                print(shell_command.synopsis)
                continue
            new_webdav_account_uuid = shell_command.arguments[1].strip()
            if new_webdav_account_uuid == "-":
                new_webdav_account_uuid = ""
            else:
                new_webdav_account_uuid = find_uuid_for_searchstring_interactive(shell_command.arguments[1].strip(),
                                                                                 p_database)
            # if new_webdav_account_uuid == "-":
            #     new_webdav_account_uuid = ""
            p.set_attribute_value_in_configuration_table(
                p_database.database_filename,
                pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_CONNECTOR_DEFAULT_WEBDAV_ACCOUNT_UUID,
                new_webdav_account_uuid)
            continue

        if shell_command.command == "cplast":
            if latest_found_account is None:
                print("There is no account to copy.")
                continue
            pyperclip3.copy(latest_found_account.password)
            print("Account   : " + latest_found_account.name)
            print("Clipboard : Password")
            continue

        if shell_command.command == "sc":
            if len(shell_command.arguments) == 1:
                print("SEARCHSTRING is missing.")
                print(shell_command.synopsis)
                continue
            account_array = p_database.get_accounts_decrypted(shell_command.arguments[1].strip())
            if len(account_array) == 0:
                print("No account found.")
                continue
            if len(account_array) != 1:
                i = 1
                # print()
                for acc in account_array:
                    print()
                    print(" [" + str(i).rjust(2) + "]" + " - Name: " + acc.name)
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
                    # print("Account   : " + account_array[int(index) - 1].name)
                    print("Account   : ", end='')
                    print_slow.print_slow(account_array[int(index) - 1].name)
                    # print("Clipboard : Password")
                    print("Clipboard : ", end='')
                    print_slow.print_slow("Password")
                except Exception as e:
                    print("Error: " + str(e))
                continue
            try:
                pyperclip3.copy(account_array[0].password)
                # print("Account   : " + account_array[0].name)
                print("Account   : ", end='')
                print_slow.print_slow(account_array[0].name)
                # print("Clipboard : Password")
                print("Clipboard : ", end='')
                print_slow.print_slow("Password")
            except Exception as e:
                print("Error copying password to the clipboard: " + str(e))
            continue

        if shell_command.command == "sca":
            if len(shell_command.arguments) == 1:
                print("SEARCHSTRING is missing.")
                print(shell_command.synopsis)
                continue
            account_uuid = find_uuid_for_searchstring_interactive(shell_command.arguments[1].strip(), p_database)
            if account_uuid is None:
                continue
            account = p_database.get_account_by_uuid_and_decrypt(account_uuid)
            try:
                # pyperclip3.copy(account_array[0].url)
                pyperclip3.copy(account.url)

                print("Account   : ", end='')
                print_slow.print_slow(account.name)
                print("Clipboard : ", end='')
                print_slow.print_slow("URL")
                input("<Press enter>")

                pyperclip3.copy(account.loginname)

                print("Clipboard : ", end='')
                print_slow.print_slow("Loginname")
                input("<Press enter>")

                pyperclip3.copy(account.password)

                print("Clipboard : ", end='')
                print_slow.print_slow("Password")
            except KeyboardInterrupt:
                print()
                continue
            except Exception as e:
                print("Error copying URL, loginname and password to the clipboard: " + str(e))
            continue

        if shell_command.command == "scl":
            if len(shell_command.arguments) == 1:
                print("SEARCHSTRING is missing.")
                print(shell_command.synopsis)
                continue
            account_uuid = find_uuid_for_searchstring_interactive(shell_command.arguments[1].strip(), p_database)
            if account_uuid is None:
                continue
            account = p_database.get_account_by_uuid_and_decrypt(account_uuid)
            try:
                pyperclip3.copy(account.loginname)
                print("Account   : ", end='')
                print_slow.print_slow(account.name)
                print("Clipboard : ", end='')
                print_slow.print_slow("Loginname")
            except Exception as e:
                print("Error copying loginname to the clipboard: " + str(e))
            continue

        if shell_command.command == "scu":
            if len(shell_command.arguments) == 1:
                print("SEARCHSTRING is missing.")
                print(shell_command.synopsis)
                continue
            account_uuid = find_uuid_for_searchstring_interactive(shell_command.arguments[1].strip(), p_database)
            if account_uuid is None:
                continue
            account = p_database.get_account_by_uuid_and_decrypt(account_uuid)
            try:
                pyperclip3.copy(account.url)
                print("Account   : ", end='')
                print_slow.print_slow(account.name)
                print("Clipboard : ", end='')
                print_slow.print_slow("URL")
            except Exception as e:
                print("Error copying URL to the clipboard: " + str(e))

        if shell_command.command == "slowprintenabled":
            if len(shell_command.arguments) == 1:
                print("Status: " + str(print_slow.DELAY_ENABLED))
                continue
            if shell_command.arguments[1] == "on":
                print_slow.set_delay_enabled(True)
                pdatabase.set_attribute_value_in_configuration_table(
                    p_database.database_filename,
                    pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_PRINT_SLOW_ENABLED,
                    "True")
                continue
            if shell_command.arguments[1] == "off":
                print_slow.set_delay_enabled(False)
                pdatabase.set_attribute_value_in_configuration_table(
                    p_database.database_filename,
                    pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_PRINT_SLOW_ENABLED,
                    "False")
                continue
            print("Error: on or off expected.")
            continue

        if shell_command.command == "setdatabasename":
            if len(shell_command.arguments) == 1:
                print("NAME is missing.")
                print(shell_command.synopsis)
                continue
            new_database_name = shell_command.arguments[1].strip()
            if new_database_name == "-":
                new_database_name = ""
            p.set_attribute_value_in_configuration_table(
                p_database.database_filename,
                pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_DATABASE_NAME,
                new_database_name)
            continue

        if shell_command.command == "setdropboxaccountuuid":
            if len(shell_command.arguments) == 1:
                print("UUID is missing.")
                print(shell_command.synopsis)
                continue
            new_dropbox_account_uuid = shell_command.arguments[1].strip()
            if new_dropbox_account_uuid == "-":
                new_dropbox_account_uuid = ""
            else:
                new_dropbox_account_uuid = find_uuid_for_searchstring_interactive(shell_command.arguments[1].strip(),
                                                                                  p_database)
            p.set_attribute_value_in_configuration_table(
                p_database.database_filename,
                pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_CONNECTOR_DEFAULT_DROPBOX_ACCOUNT_UUID,
                new_dropbox_account_uuid)
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
                print("UUID or SEARCHSTRING is missing.")
                print(shell_command.synopsis)
                continue
            search_string = shell_command.arguments[1].strip()
            uuid_to_show_accounthistory_from = find_uuid_for_searchstring_interactive(search_string, p_database)
            if uuid_to_show_accounthistory_from is None:
                continue
            p_database.search_account_history(uuid_to_show_accounthistory_from)
            continue

        if shell_command.command == "showconfig":
            show_config(p_database)
            # print("PShell timeout                      : ", end="")
            # print_slow.print_slow(colored(str(pshell_max_idle_minutes_timeout), "green"))
            # print("PShell max history size             : ", end="")
            # print_slow.print_slow(colored(str(pshell_max_history_size), "green"))
            # print("Show invalidated accounts           : ", end="")
            # print_slow.print_slow(colored(str(p_database.show_invalidated_accounts), "green"))
            # print("Shadow passwords                    : ", end="")
            # print_slow.print_slow(colored(str(p_database.shadow_passwords), "green"))
            # print("Show accounts verbose               : ", end="")
            # print_slow.print_slow(colored(str(p_database.show_account_details), "green"))
            # print("Show unmerged changes warning       : ", end="")
            # print_slow.print_slow(colored(str(show_unmerged_changes_warning_on_startup), "green"))
            # print("Show status on startup              : ", end="")
            # print_slow.print_slow(colored(str(show_status_on_startup), "green"))
            # print("Track account history               : ", end="")
            # print_slow.print_slow(colored(str(p_database.track_account_history), "green"))
            # print("Slow print enabled                  : ", end="")
            # print_slow.print_slow(colored(str(print_slow.DELAY_ENABLED), "green"))
            # print("Execute on start                    : ", end="")
            # print_slow.print_slow(colored(str(p_database.get_execute_on_start_command()), "green"))
            # print("Execute on stop                     : ", end="")
            # print_slow.print_slow(colored(str(p_database.get_execute_on_stop_command()), "green"))
            continue

        if shell_command.command == "showlinks":
            print("p github home            : ", end="")
            print_slow.print_slow(colored(str(p.URL_GITHUB_P_HOME), "green"))
            print("p github wiki            : ", end="")
            print_slow.print_slow(colored(str(p.URL_GITHUB_P_WIKI), "green"))
            print("p binary windows         : ", end="")
            print_slow.print_slow(colored(str(p.URL_DOWNLOAD_BINARY_P_WIN), "green"))
            print("p binary linux           : ", end="")
            print_slow.print_slow(colored(str(p.URL_DOWNLOAD_BINARY_P_LINUX), "green"))
            print("p binary raspberry pi    : ", end="")
            print_slow.print_slow(colored(str(p.URL_DOWNLOAD_BINARY_P_RASPBERRY), "green"))
            print("p updater binary windows : ", end="")
            print_slow.print_slow(colored(str(p.URL_DOWNLOAD_BINARY_P_UPDATER_WIN), "green"))
            print("p updater binary linux   : ", end="")
            print_slow.print_slow(colored(str(p.URL_DOWNLOAD_BINARY_P_UPDATER_LINUX), "green"))
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

        if shell_command.command == "showmergehistory":
            pdatabase.print_merge_history(p_database.database_filename)

        if shell_command.command == "showlatestmerge":
            pdatabase.print_latest_merge_history_detail(p_database.database_filename)

        if shell_command.command == "showmergedetail":
            if len(shell_command.arguments) == 1:
                print("Error: Merge history UUID is missing.")
                print(shell_command.synopsis)
                continue
            pdatabase.print_merge_history_detail(p_database.database_filename, shell_command.arguments[1].strip())

        if shell_command.command == "showstatusonstartup":
            # print(shell_command.arguments)
            if len(shell_command.arguments) == 1:
                print("Status: " + str(show_status_on_startup))
                continue
            if shell_command.arguments[1] == "on":
                show_status_on_startup = True
                pdatabase.set_attribute_value_in_configuration_table(
                    p_database.database_filename,
                    pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHOW_STATUS_ON_STARTUP,
                    "True")
                continue
            if shell_command.arguments[1] == "off":
                show_status_on_startup = False
                pdatabase.set_attribute_value_in_configuration_table(
                    p_database.database_filename,
                    pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHOW_STATUS_ON_STARTUP,
                    "False")
                continue
            print("Error: on or off expected.")
            continue

        if shell_command.command == "showunmergedchanges":
            p_database.show_unmerged_changes()
            continue

        if shell_command.command == "showunmergedwarning":
            # print(shell_command.arguments)
            if len(shell_command.arguments) == 1:
                print("Status: " + str(show_unmerged_changes_warning_on_startup))
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
                print("UUID or SEARCHSTRING is missing.")
                print(shell_command.synopsis)
                continue
            search_string = shell_command.arguments[1].strip()
            uuid_to_change_password = find_uuid_for_searchstring_interactive(search_string, p_database)
            if uuid_to_change_password is None:
                continue
            if not p_database.get_account_exists(uuid_to_change_password):
                print("Error: Account UUID " + uuid_to_change_password + " not found.")
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
                p_database.set_password_of_account(uuid_to_change_password, new_password)
            else:
                print("Canceled")
            continue

        if shell_command.command == "sql":
            if len(shell_command.arguments) == 1:
                print("COMMAND is missing.")
                print(shell_command.synopsis)
                continue
            # print("->" + shell_command.arguments[1])
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
                print(shell_command.synopsis)
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
            print("Starting update process.")
            print("Please make sure that you are in the directory where the p binary is located.")
            print("Your current directory is: " + os.getcwd())
            try:
                input("Press enter to start or strg-c to cancel...")
            except KeyboardInterrupt:
                print()
                continue
            try:
                if is_windows_os():
                    print("Detected system is windows")
                    download_url = p.URL_DOWNLOAD_BINARY_P_WIN
                    download_p_filename = p.DOWNLOAD_P_UPDATE_FILENAME_WIN
                    p_filename = p.P_FILENAME_WIN
                    p_updater_download_url = p.URL_DOWNLOAD_BINARY_P_UPDATER_WIN
                    p_updater = p.P_UPDATER_FILENAME_WIN
                elif is_posix_os():
                    if is_x86_64_architecture():
                        print("Detected system is linux x86_64")
                        download_url = p.URL_DOWNLOAD_BINARY_P_LINUX
                        download_p_filename = p.DOWNLOAD_P_UPDATE_FILENAME_LINUX
                        p_filename = p.P_FILENAME_LINUX
                        p_updater_download_url = p.URL_DOWNLOAD_BINARY_P_UPDATER_LINUX
                        p_updater = p.P_UPDATER_FILENAME_LINUX
                    elif is_aarch64_architecture():
                        print("Detected system is linux on arm_64")
                        download_url = p.URL_DOWNLOAD_BINARY_P_RASPBERRY
                        download_p_filename = p.DOWNLOAD_P_UPDATE_FILENAME_LINUX
                        p_filename = p.P_FILENAME_LINUX
                        p_updater_download_url = p.URL_DOWNLOAD_BINARY_P_UPDATER_LINUX
                        p_updater = p.P_UPDATER_FILENAME_LINUX
                else:
                    print("Error: Detected system is unknown: " + str(os.uname()))
                    continue

                print("Downloading latest p binary to: " + download_p_filename)
                print("Please wait, this can take a while...")
                # req = requests.get(download_url)
                # open(download_p_filename, "wb").write(req.content)
                # wget.download(download_url, out=download_p_filename, bar=wget.bar_thermometer)
                try:
                    wget.download(download_url, out=download_p_filename)
                except KeyboardInterrupt:
                    print()
                    print("Download canceled.")
                    continue
                print("Download ready.")

                if is_windows_os():
                    if not os.path.exists(p_updater):
                        print("updater executable not found.")
                        print("Downloading it...")
                        # req = requests.get(p_updater_download_url)
                        # open(p_updater, "wb").write(req.content)
                        try:
                            wget.download(p_updater_download_url, out=p_updater)
                        except KeyboardInterrupt:
                            print()
                            print("Download canceled.")
                            continue
                        print("Download ready.")
                        # continue

                    print("Starting updater: " + p_updater + "...")
                    time.sleep(2)
                    # os.startfile(p_updater + " -D " + p_database.database_filename + " -o " + p_filename +
                    #              " -n " + download_p_filename)
                    # os.startfile(p_updater, " -D " + p_database.database_filename + " -o " + p_filename +
                    #             " -n " + download_p_filename)
                    os.startfile(p_updater)
                    sys.exit(0)
                else:
                    # This is a linux system
                    print("Renaming downloaded file " + p.DOWNLOAD_P_UPDATE_FILENAME_LINUX + " to " +
                          p.P_FILENAME_LINUX)
                    os.rename(p.DOWNLOAD_P_UPDATE_FILENAME_LINUX, p.P_FILENAME_LINUX)
                    print("Making p binary executable...")
                    os.system("chmod +x " + p.P_FILENAME_LINUX)
                    print("Please start p again.")
                    input("Press enter to exit.")
                    sys.exit(0)
            except Exception as ex:
                print("Error updating: " + str(ex))
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

        if shell_command.command == "version":
            print(p.VERSION)
            continue

        # # Unknown command detected
        # print("Command ")
    print("Exiting pshell.")


def show_config(p_database: pdatabase):
    print("PShell timeout                      : ", end="")
    print_slow.print_slow(colored(str(pshell_max_idle_minutes_timeout), "green"))
    print("PShell max history size             : ", end="")
    print_slow.print_slow(colored(str(pshell_max_history_size), "green"))
    print("Show invalidated accounts           : ", end="")
    print_slow.print_slow(colored(str(p_database.show_invalidated_accounts), "green"))
    print("Shadow passwords                    : ", end="")
    print_slow.print_slow(colored(str(p_database.shadow_passwords), "green"))
    print("Show accounts verbose               : ", end="")
    print_slow.print_slow(colored(str(p_database.show_account_details), "green"))
    print("Show unmerged changes warning       : ", end="")
    print_slow.print_slow(colored(str(show_unmerged_changes_warning_on_startup), "green"))
    print("Show status on startup              : ", end="")
    print_slow.print_slow(colored(str(show_status_on_startup), "green"))
    print("Track account history               : ", end="")
    print_slow.print_slow(colored(str(p_database.track_account_history), "green"))
    print("Slow print enabled                  : ", end="")
    print_slow.print_slow(colored(str(print_slow.DELAY_ENABLED), "green"))
    print("Execute on start                    : ", end="")
    print_slow.print_slow(colored(str(p_database.get_execute_on_start_command()), "green"))
    print("Execute on stop                     : ", end="")
    print_slow.print_slow(colored(str(p_database.get_execute_on_stop_command()), "green"))
    print("Default dropbox merge target        : ", end="")
    print_slow.print_slow(colored(pdatabase.get_attribute_value_from_configuration_table(
        p_database.database_filename,
        pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_CONNECTOR_DEFAULT_DROPBOX_ACCOUNT_UUID), "green"))
    print("Default ssh merge target            : ", end="")
    print_slow.print_slow(colored(pdatabase.get_attribute_value_from_configuration_table(
        p_database.database_filename,
        pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_CONNECTOR_DEFAULT_SSH_ACCOUNT_UUID), "green"))
    print("Default webdav merge target         : ", end="")
    print_slow.print_slow(colored(pdatabase.get_attribute_value_from_configuration_table(
        p_database.database_filename,
        pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_CONNECTOR_DEFAULT_WEBDAV_ACCOUNT_UUID), "green"))
    print("Default file merge target           : ", end="")
    print_slow.print_slow(colored(pdatabase.get_attribute_value_from_configuration_table(
        p_database.database_filename,
        pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_CONNECTOR_DEFAULT_FILE_ACCOUNT_UUID), "green"))
