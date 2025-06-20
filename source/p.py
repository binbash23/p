#!/bin/python3
#
# 20221017 jens heine <binbash@gmx.net>
#
# Password/account database for managing all your accounts
#
import optparse
import sys
from optparse import OptionGroup

from dropbox_connector import *
from pdatabase import *
from pshell import *

colorama.init()

#
# VARIABLES
#
VERSION = "[p] by Jens Heine <binbash@gmx.net> version: 2025.06.19"
database_filename = "p.db"
URL_GITHUB_P_HOME = "https://github.com/binbash23/p"
URL_GITHUB_P_WIKI = "https://github.com/binbash23/p/wiki"
URL_DOWNLOAD_BINARY_P_WIN = "https://github.com/binbash23/p/raw/master/dist/windows/p.exe"
URL_DOWNLOAD_BINARY_P_LINUX = "https://github.com/binbash23/p/raw/master/dist/linux/p"
URL_DOWNLOAD_BINARY_P_ARM64 = "https://github.com/binbash23/p/raw/master/dist/arm64/p"
URL_DOWNLOAD_BINARY_P_UPDATER_WIN = "https://github.com/binbash23/p/raw/master/dist/windows/updater.exe"
URL_DOWNLOAD_BINARY_P_UPDATER_LINUX = "https://github.com/binbash23/p/raw/master/dist/linux/updater"
DOWNLOAD_P_UPDATE_FILENAME_WIN = "p.exe_latest"
DOWNLOAD_P_UPDATE_FILENAME_LINUX = "p_latest"
URL_DOWNLOAD_P_VERSION_WIN = "https://raw.githubusercontent.com/binbash23/p/master/dist/windows/version"
URL_DOWNLOAD_P_VERSION_LINUX = "https://raw.githubusercontent.com/binbash23/p/master/dist/linux/version"
URL_DOWNLOAD_P_VERSION_ARM64 = "https://raw.githubusercontent.com/binbash23/p/master/dist/arm64/version"
P_FILENAME_WIN = "p.exe"
P_FILENAME_LINUX = "p"
P_UPDATER_FILENAME_WIN = "updater.exe"
P_UPDATER_FILENAME_LINUX = "updater"
GIT_FULL_DOCUMENTATION_FILENAME = "Full-help-documentation.md"


def add_account_interactive(p_database: PDatabase, account_name=""):
    print("Add account")
    account = Account()
    try:
        account.uuid = uuid.uuid4()
        print("UUID          : " + str(account.uuid))
        if account_name == "":
            account.name = input("Name          : ")
        else:
            print("Name          : " + account_name)
            account.name = account_name
        account.url = input("URL           : ")
        account.loginname = input("Loginname     : ")
        if p_database.shadow_passwords:
            while True:
                password1 = pwinput.pwinput("Password      : ")
                password2 = pwinput.pwinput("Confirm       : ")
                if (password1 == password2) or (password1 is None and password2 is None):
                    account.password = password1
                    break
                print("Error: Passwords do not match. Please try again.")
        else:
            account.password = input("Password      : ")
        account.type = input("Type          : ")
        account.connector_type = input("Connectortype : ")
        answer = input("Correct ([y]/n) : ")
    except KeyboardInterrupt:
        print()
        print("Strg-C detected.")
        return
    if answer == "y" or answer == "":
        p_database.add_account_and_encrypt(account)
    else:
        print("Canceled")


def edit_account_interactive(p_database: PDatabase, edit_uuid: str):
    account = p_database.get_account_by_uuid_and_decrypt(edit_uuid)
    if account is None:
        print("UUID " + edit_uuid + " not found.")
        return
    print("Edit UUID " + edit_uuid)
    print("Press <return> to adopt old value or <space>+<return> to delete an existing value.")
    old_name = account.name
    old_url = account.url
    old_loginname = account.loginname
    old_password = account.password
    old_type = account.type
    old_connector_type = account.connector_type

    try:
        print("Name (old)      : " + old_name)
        new_name = input("Name (new)      : ")
        if new_name == "":
            new_name = old_name

        print("URL (old)       : " + old_url)
        new_url = input("URL (new)       : ")
        if new_url == "":
            new_url = old_url

        print("Loginname (old) : " + old_loginname)
        new_loginname = input("Loginname (new) : ")
        if new_loginname == "":
            new_loginname = old_loginname

        if p_database.shadow_passwords:
            print("Password (old)  : ****")
            change_shadowed_password = input("Do you want to change the password (y/[n]) : ")
            if change_shadowed_password == "y":
                while True:
                    password1 = pwinput.pwinput("New password    : ")
                    password2 = pwinput.pwinput("Confirm         : ")
                    if (password1 == password2) or (password1 is None and password2 is None):
                        new_password = password1
                        break
                    print("Error: Passwords do not match. Please try again.")
            else:
                new_password = old_password
        else:
            print("Password (old)  : " + old_password)
            change_unshadowed_password = input("Do you want to change the password (y/[n]) : ")
            if change_unshadowed_password == "y":
                new_password = input("Password (new)  : ")
            else:
                new_password = old_password

        print("Type (old)      : " + old_type)
        new_type = input("Type (new)      : ")
        if new_type == "":
            new_type = old_type

        print("Connectortype (old)      : " + old_connector_type)
        new_connector_type = input("Connectortype (new)      : ")
        if new_connector_type == "":
            new_connector_type = old_connector_type

        answer = input("Correct ([y]/n) : ")
    except KeyboardInterrupt:
        print()
        print("Canceled")
        return

    new_account = Account(edit_uuid, new_name.strip(), new_url.strip(), new_loginname.strip(), new_password,
                          new_type.strip(), new_connector_type.strip())
    if accounts_are_equal(account, new_account):
        print("Nothing changed.")
        return
    if answer == "y" or answer == "":
        p_database.set_account_by_uuid_and_encrypt(edit_uuid,
                                                   new_name.strip(),
                                                   new_url.strip(),
                                                   new_loginname.strip(),
                                                   new_password,
                                                   new_type.strip(),
                                                   new_connector_type.strip())
        print("Account changed")
    else:
        print("Canceled")


def change_database_password_interactive(p_database: PDatabase) -> bool:
    new_password = read_confirmed_database_password_from_user()
    return p_database.change_database_password(new_password)


def start_dropbox_configuration():
    print("")
    print(colored("Dropbox configuration", "green"))
    print("")
    print("With this process you will get the refresh access token from dropbox.")

    print("First register a new app in your dropbox account.")
    input("Press enter and a browser will open the dropbox developer site (login with your dropbox account)...")
    webbrowser.open("https://www.dropbox.com/developers")

    print("Now you have to change the permissions for the app to read/write files and folders (permissions tab).")
    print("You have to check:")
    print("- account_info.read")
    print("- files.metadata.write")
    print("- files.metadata.read")
    print("- files.content.write")
    print("- files.content.read")
    print()
    print("IMPORTANT NOTE: Everytime you change the permissions you will have to re-generate the access code!!!")
    input("Press enter when you have changed/set the permissions.")
    print()

    print("You need the application key and the application secret from your just created dropbox app" +
          " for this procedure.")
    application_key = input("Enter the dropbox application key    : ")
    if application_key == "":
        print("Error: the application key must not be empty.")
        input("Press enter to exit.")
        sys.exit(1)
    application_secret = input("Enter the dropbox application secret : ")
    if application_secret == "":
        print("Error: the application secret must not be empty.")
        input("Press enter to exit.")
        sys.exit(1)
    print("Now a browser will open and give you the dropbox access code...")
    get_generated_access_code(application_key)
    dropbox_access_code = input("Enter the dropbox access code        : ")
    if dropbox_access_code == "":
        print("Error: the dropbox access code must not be empty.")
        input("Press enter to exit.")
        sys.exit(1)
    print()
    print("Now a new dropbox refresh token will be retrieved from dropbox...")
    print()
    try:
        refresh_access_token = get_refresh_access_token(application_key, application_secret, dropbox_access_code)
    except Exception as e:
        print("Error parsing refresh access token from dropbox: " + str(e))
        input("Press enter to exit.")
        sys.exit(1)
    print()
    print("The generated refresh token is: " + refresh_access_token)
    print()
    print("Now add a new accounts to your p database (in pshell use the command: 'add'):")
    print()
    print("Add a new account with any name (i.e: 'Dropbox Connector') the application_key (" + application_key + ")" +
          " as the url and the application_secret (" + application_secret +
          ") as the login name and the long refresh token as the" +
          " password (" + refresh_access_token +
          "). The type field can be filled with 'Connector' and the connector type field must be filled " +
          "with 'dropbox'.")
    print("")
    print("You can set this dropbox account as the default dropbox merge account with this command (in pshell):")
    print("> setdropboxaccountuuid UUID_OF_THE_ACCOUNT_THAT_YOU_HAVE_JUST_CREATED")
    print()
    print("You  might verify if the dropbox uuid is set in the configuration by executing:")
    print("> status")
    print()
    print("You should see that the dropbox uuid is stored there.")
    print()
    print("When you execute")
    print("> merge2dropbox")
    print("then you local database will be synchronized to the dropbox version of the database.")
    print()


def list_db_files(path: str = ".", extension: str = ".db") -> []:
    file_array = []
    for file_object in os.listdir(path):
        if os.path.isfile(os.path.join(path, file_object)):
            # print("isfile--->" + file_object)
            if str(file_object).endswith(extension):
                file_array.append(file_object)
    return file_array


def multiple_db_files_exist(path: str = ".", extension: str = ".db") -> bool:
    if len(list_db_files(path, extension)) > 1:
        return True
    return False


#
# main
#
def main():
    print()
    print(p.VERSION)
    print()
    parser = optparse.OptionParser()
    parser.add_option("-a", "--add", action="store_true", dest="add", default=False,
                      help="Add new account interactive")
    parser.add_option("-c", "--change-database-password", action="store_true", dest="change_database_password",
                      default=False, help="Change database password interactive")
    parser.add_option("-C", "--create-add_statements", action="store_true", dest="create_add_statements",
                      default=False, help="Create add account statements for all existing accounts. " +
                                          "This is useful if you want to export your accounts and import them " +
                                          "into another p database.")
    parser.add_option("-d", "--delete", action="store", dest="delete_uuid",
                      help="Delete account by UUID. It is usually better to use -i UUID to invalidate an account.")
    parser.add_option("-D", "--database", action="store", dest="database",
                      help="Set database filename. It is also possible to create an environment variable: " +
                           "P_DATABASE=<database_filename>")
    parser.add_option("-e", "--edit", action="store", dest="edit_uuid", help="Edit account by UUID")
    parser.add_option("-E", "--database-password--empty", action="store_true", dest="database_password_empty",
                      help="Set empty database password")
    parser.add_option("-i", "--invalidate", action="store", dest="invalidate_uuid", help="Invalidate account by UUID")
    parser.add_option("-I", "--search-uuid", action="store", dest="search_uuid", help="Search account by UUID")
    parser.add_option("-l", "--list", action="store_true", dest="list", default=False,
                      help="List all accounts")
    parser.add_option("-p", "--database-password", action="store", dest="database_password",
                      help="Set database password. If you want to use an empty password use -E")
    parser.add_option("-q", "--query", action="store_true", dest="query", default=False,
                      help="Query p. Start interactive p shell.")
    parser.add_option("-Q", "--execute-query", action="store", dest="execute_query",
                      help="Pass command(s) to the pshell and execute them. Separate multiple commands with a ';'.")
    parser.add_option("-r", "--revalidate", action="store", dest="revalidate_uuid",
                      help="Revalidate/activate account by UUID")
    parser.add_option("-s", "--search", action="store", dest="search_string",
                      help="Search account. You can also search for an account like this: p <searchstring>")
    parser.add_option("-S", "--statistics", action="store_true", dest="statistics", default=False,
                      help="Show database statistics")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False,
                      help="Show account details (create date, ...)")
    parser.add_option("-V", "--version", action="store_true", dest="version", default=False,
                      help="Show p version info")
    parser.add_option("-x", "--show_invalidated", action="store_true", dest="show_invalidated", default=False,
                      help="Show also invalidated accounts (default=False)")
    parser.add_option("-Z", "--start-dropbox-configuration", action="store_true", dest="start_dropbox_configuration",
                      default=False, help="Start the dropbox configuration. You need the dropbox application key" +
                                          " and the dropbox application secret for this.")

    add_account_group = OptionGroup(parser, "Add new account with arguments (non interactive)")
    add_account_group.add_option("-A", "--Add", action="store_true", dest="add_account_cli", default=False,
                                 help="Add a new account non interactive")
    add_account_group.add_option("-L", "--Loginname", action="store", dest="NEW_ACCOUNT_LOGINNAME",
                                 help="Set loginname for new account")
    add_account_group.add_option("-N", "--Name", action="store", dest="NEW_ACCOUNT_NAME",
                                 help="Set name for new account")
    add_account_group.add_option("-P", "--Password", action="store", dest="NEW_ACCOUNT_PASSWORD",
                                 help="Set password for new account")
    add_account_group.add_option("-T", "--Type", action="store", dest="NEW_ACCOUNT_TYPE",
                                 help="Set type for new account")
    add_account_group.add_option("-U", "--Url", action="store", dest="NEW_ACCOUNT_URL",
                                 help="Set url for new account")
    add_account_group.add_option("-X", "--UUID", action="store", dest="NEW_ACCOUNT_UUID",
                                 help="Set uuid for new account (optional)")
    parser.add_option_group(add_account_group)

    (options, args) = parser.parse_args()

    if options.version:
        # Version is printed per default on startup
        # print(VERSION)
        sys.exit(0)

    # Check if there are commands on the command line to be executed in the pshell
    if options.execute_query:
        _args_user_input_list = str(options.execute_query).strip().split(PSHELL_COMMAND_DELIMITER)
    else:
        _args_user_input_list = None

    # check if the users wants to start the dropbox configuration process
    if options.start_dropbox_configuration:
        start_dropbox_configuration()
        input("Press enter to exit.")
        sys.exit(0)

    # Get password and database file name. then open/create database file
    # First get database filename
    global database_filename
    database_filename_is_explicit_set = False
    # check if the p_database info is set in environment variable
    try:
        if os.environ['P_DATABASE']:
            database_filename = os.environ['P_DATABASE']
            database_filename_is_explicit_set = True
    except KeyError:
        # no environment variable with that name found
        pass
    if options.database is not None and options.database != "":
        database_filename = options.database
        database_filename_is_explicit_set = True

    if not database_filename_is_explicit_set:
        if multiple_db_files_exist():
            print("Which database do you want to access?")
            print()
            db_filenames = list_db_files()
            i = 1
            for filename in db_filenames:
                print("[" + str(i) + "] - " + filename)
                i += 1
            print()
            print("[" + str(i) + "] - Create new database file")
            print("[" + str(i+1) + "] - Exit")
            print()

            while True:
                try:
                    filename_nr = input("Enter number (default=1): ")
                    if filename_nr == "":
                        filename_nr = "1"
                    if filename_nr == str(i):  # enter new database name was selected
                        print()
                        database_filename = input("Enter new database filename : ")
                        break
                    elif filename_nr == str(i+1):  # Exit selected
                        print()
                        sys.exit(0)
                    else:
                        database_filename = db_filenames[int(filename_nr) - 1]
                        break
                except KeyboardInterrupt as e:
                    print()
                    sys.exit(0)
                except Exception as e:
                    print("Error: " + str(e))
                    # sys.exit(1)

    absolute_filename = os.path.abspath(database_filename)
    print("Database filename        : " + absolute_filename)

    # check here, if statistics should be shown. this must be done without trying to decrypt/create the db connection
    if options.statistics:
        print_database_statistics(database_filename)
        sys.exit(0)

    # second fetch password:
    database_password = None
    if options.database_password is not None:
        database_password = options.database_password
    if options.database_password_empty:
        database_password = ""

    database_logical_name = None
    if database_password is None:
        if os.path.exists(database_filename):
            try:
                current_database_name = pdatabase.get_database_name(database_filename)
                if current_database_name is None or current_database_name == "":
                    print("Logical database name    : [empty]")
                else:
                    print("Logical database name    : " + current_database_name)

                try_no = 0
                while try_no < 3:
                    try_no += 1
                    database_password = pwinput.pwinput("Enter database password  : ")
                    if is_valid_database_password(database_filename, database_password.encode("UTF-8")):
                        print("Access granted.")
                        break
                    print("Access denied: Password is wrong.")
                if not is_valid_database_password(database_filename, database_password.encode("UTF-8")):
                    sys.exit(1)

            except KeyboardInterrupt:
                print()
                return
        else:
            print()
            print("> Information: Database file does not exist and will be created now.")
            print("> Create a new password to encrypt the database file. Do not forget this password!")
            print("> If you do not want to encrypt the database, leave the password empty.")
            print()
            try:
                while True:
                    database_password = pwinput.pwinput("Enter database password   : ")
                    database_password_confirm = pwinput.pwinput("Confirm database password : ")
                    if database_password == database_password_confirm:
                        break
                    print(colored("Error: Passwords do not match.", "red"))

                print("If you want you can set an optional logical database name now.")
                database_logical_name = input("Enter a database name     : ")
            except KeyboardInterrupt:
                print()
                return

    if database_password is None:
        print(colored("Database password is not set! Enter password on command line or use -p or -E option.", "red"))
        input("Press enter to exit.")
        sys.exit(1)

    # check if the verbose switch is set:
    show_account_details = False
    if options.verbose:
        show_account_details = True
    # check if the show_invalidated switch is set:
    show_invalidated_accounts = False
    if options.show_invalidated:
        show_invalidated_accounts = True
    # Now try to open/create the database:
    try:
        p_database = PDatabase(database_filename, database_password, show_account_details,
                               show_invalidated_accounts, initial_database_name=database_logical_name)
    except Exception as e:
        print("Error: " + str(e))
        input("Press enter to exit.")
        sys.exit(1)

    # from here we have a valid database ready to access

    # check if the interactive shell should be opened
    if options.query:
        start_pshell(p_database, _args_user_input_list)
        input("Press enter to exit.")
        sys.exit(0)

    if options.add_account_cli:
        new_account = Account(uuid=options.NEW_ACCOUNT_UUID or "",
                              name=options.NEW_ACCOUNT_NAME or "",
                              url=options.NEW_ACCOUNT_URL or "",
                              loginname=options.NEW_ACCOUNT_LOGINNAME or "",
                              password=options.NEW_ACCOUNT_PASSWORD or "",
                              type=options.NEW_ACCOUNT_TYPE or "")
        p_database.add_account_and_encrypt(new_account)
        sys.exit(0)
    if options.search_string is not None:
        p_database.search_accounts(options.search_string or "")
        sys.exit(0)
    if options.create_add_statements:
        p_database.create_add_statements()
        sys.exit(0)
    if options.delete_uuid is not None:
        p_database.delete_account(options.delete_uuid)
        sys.exit(0)
    if options.edit_uuid is not None:
        edit_account_interactive(p_database, str(options.edit_uuid).strip())
        sys.exit(0)
    if options.search_uuid is not None:
        p_database.search_account_by_uuid(options.search_uuid)
        sys.exit(0)
    if options.invalidate_uuid is not None:
        p_database.invalidate_account(options.invalidate_uuid)
        sys.exit(0)
    if options.revalidate_uuid is not None:
        p_database.revalidate_account(options.revalidate_uuid)
        sys.exit(0)
    if options.change_database_password:
        change_database_password_interactive(p_database)
        sys.exit(0)
    if options.list:
        p_database.search_accounts("")
        sys.exit(0)
    if options.add:
        add_account_interactive(p_database)
        sys.exit(0)
    # when there are no options but a search string, search for the string in database
    if len(sys.argv) == 2 and sys.argv[1] is not None:
        p_database.search_accounts(sys.argv[1])

    # start the interactive p shell mode
    start_pshell(p_database, _args_user_input_list)


if __name__ == '__main__':
    main()
