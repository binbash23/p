#!/bin/python3
#
# 20221017 jens heine <binbash@gmx.net>
#
# Password/account database for managing all your accounts
#
import optparse
from optparse import OptionGroup

from dropbox_connector import *
from pdatabase import *
from pshell import *

colorama.init()

#
# VARIABLES
#
VERSION = "[p] by Jens Heine <binbash@gmx.net> version: 2024.01.13"
database_filename = 'p.db'
URL_GITHUB_P_HOME = "https://github.com/binbash23/p"
URL_GITHUB_P_WIKI = "https://github.com/binbash23/p/wiki"
URL_DOWNLOAD_BINARY_P_WIN = "https://github.com/binbash23/p/raw/master/dist/windows/p.exe"
URL_DOWNLOAD_BINARY_P_LINUX = "https://github.com/binbash23/p/raw/master/dist/linux/p"
URL_DOWNLOAD_BINARY_P_UPDATER_WIN = "https://github.com/binbash23/p/raw/master/dist/windows/updater.exe"
URL_DOWNLOAD_BINARY_P_UPDATER_LINUX = "https://github.com/binbash23/p/raw/master/dist/linux/updater"
DOWNLOAD_P_UPDATE_FILENAME_WIN = "p.exe_latest"
DOWNLOAD_P_UPDATE_FILENAME_LINUX = "p_latest"
P_FILENAME_WIN = "p.exe"
P_FILENAME_LINUX = "p"
P_UPDATER_FILENAME_WIN = "updater.exe"
P_UPDATER_FILENAME_LINUX = "updater"
GIT_FULL_DOCUMENTATION_FILENAME = "Full-help-documentation.md"


def add(p_database: PDatabase):
    print("Add account")
    account = Account()
    try:
        account.uuid = uuid.uuid4()
        print("UUID          : " + str(account.uuid))
        account.name = input("Name          : ")
        account.url = input("URL           : ")
        account.loginname = input("Loginname     : ")
        if p_database.shadow_passwords:
            while True:
                password1 = getpass.getpass("Password      : ")
                password2 = getpass.getpass("Confirm       : ")
                if (password1 == password2) or (password1 is None and password2 is None):
                    account.password = password1
                    break
                print("Error: Passwords do not match. Please try again.")
        else:
            account.password = input("Password      : ")
        account.type =           input("Type          : ")
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


def edit(p_database: PDatabase, edit_uuid: str):
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
                    password1 = getpass.getpass("New password    : ")
                    password2 = getpass.getpass("Confirm         : ")
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
        # sys.exit(0)

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


def change_database_password(p_database: PDatabase) -> bool:
    new_password = read_confirmed_database_password_from_user()
    return p_database.change_database_password(new_password)


def start_dropbox_configuration():
    print("")
    print(colored("Dropbox configuration", "green"))
    print("")
    print("With this process you will get the refresh access token from dropbox.")

    print("First register a new app in your dropbox account.")
    input("Press enter and a webbrowser will open the dropbox developer site (login with your dropbox account)...")
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
    application_secret = input("Enter the dropbox application secret : ")
    print("Now a webbrowser will open and give you the dropbox access code...")
    get_generated_access_code(application_key)
    dropbox_access_code = input("Enter the dropbox access code        : ")
    print()
    print("Now a new dropbox refresh token will be retrieved from dropbox...")
    print()
    refresh_access_token = get_refresh_access_token(application_key, application_secret, dropbox_access_code)
    print()
    print("The generated refresh token is: " + refresh_access_token)
    print()
    print("Now add two new accounts to your p database (in pshell use the command: 'add'):")
    print()
    print("Account #1:")
    print("A new account with any name (i.e: 'Dropbox app') the application_key (" + application_key + ")" +
          " as the loginname and the application_secret (" + application_secret + ") as the password. All other " +
          "fields can be left empty.")
    print()
    print("Account #2:")
    print("A new account with any name (i.e.: 'Dropbox Refresh Token') and the long refresh token as the" +
          " password (" + refresh_access_token + "). All other fields can be left empty.")
    print("")
    print("Now you have to tell p which 2 account UUID's must be used to access the dropbox.")
    print("One account (#1) is for the dropbox app information, the other (#2) is for the refresh token information.")
    print("P stores the dropbox account infos in the configuration and you can query the config in the pshell " +
          "with the command 'status'.")
    print()
    print("Configure the #1 account uuid with the -z option (or set it in the pshell with the command" +
          " 'setdropboxapplicationuuid <UUID>' where you set UUID to the UUID of the just created account #1.)")
    print("Example:")
    print("> p.exe -z 'c0f98849-0677-4f12-80ff-c22cb6578d1a'")
    print()
    print("Configure the #2 account uuid with the -y option (or set it in the pshell with the command " +
          "'setdropboxtokenuuid <UUID>' where you set UUID to the UUID of the just created account #2.)")
    print("Example:")
    print("> p.exe -y '123ab849-7395-1672-987f-442cbafb8d1a'")
    print()
    print("Now you should be able to synchronize your p database with the -Y option.")
    print("It might be helpful to run p in a powershell with '.\\p.exe' to be able to see error messages.")
    print()


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
    parser.add_option("-m", "--merge-last-known", action="store_true", dest="merge_last_known",
                      help="Merge with last known remote database.")
    parser.add_option("-M", "--merge-database", action="store", dest="merge_database",
                      help="Merge two databases and synchronize them. Both databases will be synchronized " +
                           "to an equal state. Both passwords must be the same!")
    parser.add_option("-p", "--database-password", action="store", dest="database_password",
                      help="Set database password. If you want to use an empty password use -E")
    parser.add_option("-q", "--query", action="store_true", dest="query", default=False,
                      help="Query p. Start interactive p shell.")
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
    parser.add_option("-y", "--set-dropbox-token-uuid", action="store", dest="dropbox_token_uuid",
                      help="Set dropbox-access-token account uuid to sync your database into dropbox.")
    parser.add_option("-Y", "--merge-with-dropbox", action="store_true", dest="merge_with_dropbox", default=False,
                      help="Merge your local database with dropbox.")
    parser.add_option("-z", "--set-dropbox-application-uuid", action="store", dest="dropbox_application_uuid",
                      help="Set dropbox application account uuid. The username must be the application key and " +
                           "the password the application secret.")
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

    # check if the users wants to start the dropbox configuration process
    if options.start_dropbox_configuration:
        start_dropbox_configuration()
        sys.exit(0)

    # Get password and database file name. then open/create database file
    # First get database filename
    global database_filename
    # check if the p_database info is set in environment variable
    try:
        if os.environ['P_DATABASE']:
            database_filename = os.environ['P_DATABASE']
    except KeyError:
        # no environment variable with that name found
        pass
    if options.database is not None and options.database != "":
        database_filename = options.database
    absolute_filename = os.path.abspath(database_filename)
    print("Database filename         : " + absolute_filename)

    # check here, if statistics should be shown. this must be done without trying to decrypt/create the db connection
    if options.statistics:
        print_database_statistics(database_filename)
        sys.exit(0)

    # check here if a dropbox account uuid stuff should be set in the configuration table (can be done without password)
    # #1 check for dropbox token uuid
    if options.dropbox_token_uuid is not None:
        set_attribute_value_in_configuration_table(
            database_filename, CONFIGURATION_TABLE_ATTRIBUTE_DROPBOX_ACCESS_TOKEN_ACCOUNT_UUID,
            options.dropbox_token_uuid)
        print("Dropbox access token account uuid registered in configuration (use -S to view config).")
        sys.exit(0)
    # #2 check for dropbox application uuid
    if options.dropbox_application_uuid is not None:
        set_attribute_value_in_configuration_table(
            database_filename, CONFIGURATION_TABLE_ATTRIBUTE_DROPBOX_APPLICATION_ACCOUNT_UUID,
            options.dropbox_application_uuid)
        print("Dropbox application account uuid registered in configuration (use -S to view config).")
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
                    print("Logical database name     : [empty]")
                else:
                    print("Logical database name     : " + current_database_name)
                database_password = getpass.getpass("Enter database password   : ")
            except KeyboardInterrupt as k:
                print()
                return
        else:
            print()
            print("> Information: Database file does not exist and will be created now.")
            print("> Create a new password to encrypt the database file. Do not forget this password!")
            print("> If you do not want to encrypt the database, leave the password empty.")
            print()
            try:
                database_password = getpass.getpass("Enter database password   : ")
                database_password_confirm = getpass.getpass("Confirm database password : ")
                print("If you want you can set an optional logical database name now.")
                database_logical_name = input("Enter a database name     : ")
            except KeyboardInterrupt as k:
                print()
                return
            if database_password != database_password_confirm:
                print(colored("Error: Passwords do not match.", "red"))
                sys.exit(1)
    if database_password is None:
        print(colored("Database password is not set! Enter password on command line or use -p or -E option.", "red"))
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
    except:
        sys.exit(1)

    # from here we have a valid database ready to access

    # check if the interactive shell should be opened
    if options.query:
        start_pshell(p_database)
        sys.exit(0)

    # check here if a dropbox database merge should be done
    if options.merge_with_dropbox:
        dropbox_connection_credentials = p_database.get_dropbox_connection_credentials()
        if dropbox_connection_credentials is None:
            sys.exit(1)
        dropbox_connector = DropboxConnector(dropbox_connection_credentials[0],
                                             dropbox_connection_credentials[1],
                                             dropbox_connection_credentials[2])
        p_database.merge_database_with_connector(dropbox_connector)
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
        edit(p_database, str(options.edit_uuid).strip())
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
        change_database_password(p_database)
        sys.exit(0)
    if options.list:
        p_database.search_accounts("")
        sys.exit(0)
    if options.merge_last_known:
        p_database.merge_database_with_default_merge_target_file()
        sys.exit(0)
    if options.merge_database is not None:
        p_database.merge_database(options.merge_database)
        sys.exit(0)
    if options.add:
        add(p_database)
        sys.exit(0)
    # when there are no options but a search string, search for the string in database
    if len(sys.argv) == 2 and sys.argv[1] is not None:
        p_database.search_accounts(sys.argv[1])
    # start the interactive p shell mode
    #    if len(sys.argv) == 1:
    start_pshell(p_database)


if __name__ == '__main__':
    main()
