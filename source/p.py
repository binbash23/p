#!/bin/python3
#
# 20221017 jens heine <binbash@gmx.net>
#
# Password/account database for managing all your accounts
#
import optparse
from optparse import OptionGroup
from pdatabase import *
import getpass
from termcolor import colored
import colorama
from dropboxconnector import *
# import p_shell
from pshell import *

colorama.init()

#
# VARIABLES
#
VERSION = "p by Jens Heine <binbash@gmx.net> version: 2023.01.24"
database_filename = 'p.db'
TEMP_MERGE_DATABASE_FILENAME = "temp_dropbox_p.db"


def add(p_database: PDatabase):
    print("Add account")
    account = Account()
    try:
        account.uuid = uuid.uuid4()
        print("UUID      : " + str(account.uuid))
        account.name = input("Name      : ")
        account.url = input("URL       : ")
        account.loginname = input("Loginname : ")
        account.password = input("Password  : ")
        account.type = input("Type      : ")
        answer = input("Correct ([y]/n) : ")
    except KeyboardInterrupt:
        print()
        print("Strg-C detected.")
        return
    if answer == "y" or answer == "":
        # p_database.add_account_and_encrypt(None, new_name, new_url, new_loginname, new_password, new_type)
        p_database.add_account_and_encrypt(account)
        # print("Added")
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
    old_loginame = account.loginname
    old_password = account.password
    old_type = account.type

    try:
        print("Name (old)      : " + old_name)
        new_name = input("Name (new)      : ")
        if new_name == "":
            new_name = old_name

        print("URL (old)       : " + old_url)
        new_url = input("URL (new)       : ")
        if new_url == "":
            new_url = old_url

        print("Loginname (old) : " + old_loginame)
        new_loginname = input("Loginname (new) : ")
        if new_loginname == "":
            new_loginname = old_loginame

        print("Password (old)  : " + old_password)
        new_password = input("Password (new)  : ")
        if new_password == "":
            new_password = old_password

        print("Type (old)      : " + old_type)
        new_type = input("Type (new)      : ")
        if new_type == "":
            new_type = old_type

        answer = input("Correct ([y]/n) : ")
    except KeyboardInterrupt:
        print()
        print("Canceled")
        return
        # sys.exit(0)

    if answer == "y" or answer == "":
        p_database.set_account_by_uuid_and_encrypt(edit_uuid,
                                                   new_name.strip(),
                                                   new_url.strip(),
                                                   new_loginname.strip(),
                                                   new_password.strip(),
                                                   new_type.strip())
        print("Account changed")
    else:
        print("Canceled")


def change_database_password(p_database: PDatabase) -> bool:
    new_password = getpass.getpass("Enter new database password   : ")
    new_password_confirm = getpass.getpass("Confirm new database password : ")
    if new_password != new_password_confirm:
        logging.error("Passwords do not match.")
        return False
    return p_database.change_database_password(new_password)


def change_dropbox_database_password(p_database: PDatabase) -> bool:
    print("Change dropbox database password")
    dropbox_connection = create_dropbox_connection(p_database)
    if not dropbox_database_exists(p_database):
        return False
    print("Downloading database from dropbox...")
    dropbox_download_file(dropbox_connection, "/" + DROPBOX_P_DATABASE_FILENAME, TEMP_MERGE_DATABASE_FILENAME)
    try:
        remote_password = getpass.getpass("Enter current dropbox database password: ")
        dropbox_p_database = PDatabase(TEMP_MERGE_DATABASE_FILENAME, remote_password)
        result = change_database_password(dropbox_p_database)
        if not result:
            print("Error changing dropbox database password.")
            return False
        print("Uploading changed database back to dropbox...")
        local_path = os.path.dirname(TEMP_MERGE_DATABASE_FILENAME)
        dropbox_upload_file(dropbox_connection, local_path, TEMP_MERGE_DATABASE_FILENAME,
                            "/" + DROPBOX_P_DATABASE_FILENAME)
    except Exception as e:
        pass
    finally:
        os.remove(TEMP_MERGE_DATABASE_FILENAME)
    return True


def dropbox_database_exists(p_database: PDatabase) -> bool:
    dropbox_connection = create_dropbox_connection(p_database)
    print("Checking for remote database...")
    try:
        exists = dropbox_file_exists(dropbox_connection, "", DROPBOX_P_DATABASE_FILENAME)
    except Exception as e:
        print("Error checking for remote database file: " + str(e))
        return False
    if exists:
        print("Remote database exists.")
        return True
    else:
        print("Remote database not found.")
        return False


def delete_dropbox_database(p_database: PDatabase) -> bool:
    dropbox_connection = create_dropbox_connection(p_database)
    if not dropbox_database_exists(p_database):
        return False
    print("Deleting database from dropbox...")
    try:
        answer = input("Are you sure ([y]/n) : ")
    except KeyboardInterrupt:
        print()
        print("Canceled")
        return False
    if answer == "y" or answer == "":
        dropbox_delete_file(dropbox_connection, "/" + DROPBOX_P_DATABASE_FILENAME)
    else:
        print("Canceled")


def create_dropbox_connection(p_database: PDatabase) -> dropbox.Dropbox:
    # #1 retrieve dropbox token account uuid...
    dropbox_account_uuid = \
        get_attribute_value_from_configuration_table(p_database.database_filename,
                                                     CONFIGURATION_TABLE_ATTRIBUTE_DROPBOX_ACCESS_TOKEN_ACCOUNT_UUID)
    if dropbox_account_uuid is None or str(dropbox_account_uuid).strip() == "":
        print(colored("Error: Dropbox Account Token uuid not found in configuration. Use -y to set it.", "red"))
        return None
    else:
        print("Using Dropbox Account Token uuid from config : " +
              colored(dropbox_account_uuid, "green"))
    # print("Token uuid : " + dropbox_account_uuid)
    access_token = p_database.get_password_from_account_and_decrypt(dropbox_account_uuid)
    # print("Token      : " + access_token)
    if access_token is None or str(access_token).strip() == "":
        print(colored("Error: Dropbox Account Token is empty. Make sure the token is set in the password field.",
                      "red"))
        return None
    else:
        print("Dropbox Account Token found.")

    # #2 retrieve dropbox application account uuid...
    dropbox_application_account_uuid = \
        get_attribute_value_from_configuration_table(p_database.database_filename,
                                                     CONFIGURATION_TABLE_ATTRIBUTE_DROPBOX_APPLICATION_ACCOUNT_UUID)
    if dropbox_application_account_uuid is None or str(dropbox_application_account_uuid).strip() == "":
        print(colored("Error: Dropbox Application Account uuid not found in configuration. Use -z to set it.", "red"))
        return None
    else:
        print("Using Dropbox Application Account uuid from config : " +
              colored(dropbox_application_account_uuid, "green"))
    dropbox_application_key = p_database.get_loginname_from_account_and_decrypt(dropbox_application_account_uuid)
    dropbox_application_secret = \
        p_database.get_password_from_account_and_decrypt(dropbox_application_account_uuid)
    if dropbox_application_key is None or str(dropbox_application_key).strip() == "":
        print(colored("Error: Dropbox application_key is empty. Make sure the application_key is set in the " +
                      "loginname field.", "red"))
        return None
    if dropbox_application_secret is None or str(dropbox_application_secret).strip() == "":
        print(colored("Error: Dropbox application_secret is empty. Make sure the application_secret is set in the " +
                      "password field.", "red"))
        return None
    print("Dropbox application_key and application_secret found.")

    print("Creating dropbox connection...")
    dropbox_connection = create_dropbox_connection_with_refresh_token(dropbox_application_key,
                                                                      dropbox_application_secret,
                                                                      access_token)
    return dropbox_connection


def merge_with_dropbox(p_database: PDatabase):
    print("Merge with dropbox...")
    dropbox_connection = create_dropbox_connection(p_database)
    if dropbox_connection is None:
        print("Error: Could not create dropbox connection")
        return
    if not dropbox_database_exists(p_database):
        print("Creating initial cloud database...")
        # print("->" + str(bytes(p_database.database_password).decode("UTF-8")))
        cloud_p_database = PDatabase(TEMP_MERGE_DATABASE_FILENAME, p_database.get_database_password_as_string())
        set_attribute_value_in_configuration_table(TEMP_MERGE_DATABASE_FILENAME,
                                                   CONFIGURATION_TABLE_ATTRIBUTE_DATABASE_NAME,
                                                   "Cloud Database")
        print("Merging current database into new database...")
        p_database.merge_database(TEMP_MERGE_DATABASE_FILENAME)
        print("Uploading initial cloud database: '" +
              TEMP_MERGE_DATABASE_FILENAME + "' to dropbox...")
        local_path = os.path.dirname(TEMP_MERGE_DATABASE_FILENAME)
        dropbox_upload_file(dropbox_connection, local_path, TEMP_MERGE_DATABASE_FILENAME,
                            "/" + DROPBOX_P_DATABASE_FILENAME)
        os.remove(TEMP_MERGE_DATABASE_FILENAME)
        return
    print("Downloading database from dropbox...")
    dropbox_download_file(dropbox_connection, "/" + DROPBOX_P_DATABASE_FILENAME, TEMP_MERGE_DATABASE_FILENAME)
    print("Merging local database with the version from dropbox...")
    return_code = p_database.merge_database(TEMP_MERGE_DATABASE_FILENAME)
    if return_code > 1:
        print("Uploading merged database back to dropbox...")
        local_path = os.path.dirname(TEMP_MERGE_DATABASE_FILENAME)
        dropbox_upload_file(dropbox_connection, local_path, TEMP_MERGE_DATABASE_FILENAME,
                            "/" + DROPBOX_P_DATABASE_FILENAME)
    else:
        print("No changes in remote database. Skipping upload.")
    os.remove(TEMP_MERGE_DATABASE_FILENAME)


def start_dropbox_configuration():
    print("")
    print(colored("Dropbox configuration", "green"))
    print("")
    print("With this process you will get the refresh access token from dropbox.")

    print("First register a new app in your dropbox account.")
    input("Press enter and a webbrowser will open the dropbox developer site (login with your dropbox account)...")
    webbrowser.open("https://www.dropbox.com/developers")
    # webbrowser.open("https://www.dropbox.com/developers/reference/getting-started")
    # https: // www.dropbox.com / developers
    # or https: // www.dropbox.com / developers / apps?_tk = pilot_lp & _ad = topbar4 & _camp = myapps

    print("Now you have to change the permissions for the app to read/write files and folders (permissions tab).")
    input("Press enter when you have changed the permissions.")
    print()

    print("You need the application key and the application secret from your just created dropbox app" +
          " for this procedure.")
    application_key = input("Enter the dropbox application key    : ")
    application_secret = input("Enter the dropbox application secret : ")
    print("Now a webbrowser will open and give you the dropbox access code...")
    get_generated_access_code(application_key)
    dropbox_access_code = input("Enter the dropbox access code        : ")
    print("Now a the dropbox refresh token will be retrieved from dropbox...")
    get_refresh_access_token(application_key, application_secret, dropbox_access_code)
    print("Now add two new accounts to your p database:")
    print("#1 A new account with the application_key as the loginname and the application_secret as the password.")
    print("#2 A new account with the refresh token as the password.")
    print("")
    print("Then configure the #1 account uuid with the -z option")
    print("Example:")
    print("> p.exe -z 'c0f98849-0677-4f12-80ff-c22cb6578d1a'")
    print("Then configure the #2 account uuid with the -y option")
    print("Example:")
    print("> p.exe -y '123ab849-7395-1672-987f-442cbafb8d1a'")
    print("Now you should be able to synchronize your p database with the -Y option.")


#
# main
#
def main():
    print(p.VERSION)
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
        print(VERSION)
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
    print("Using Database: " + database_filename)

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

    # if options.database_password is not None:
    #     database_password = options.database_password
    if database_password is None:
    # else:
        if os.path.exists(database_filename):
            try:
                database_password = getpass.getpass("Enter database password: ")
            except KeyboardInterrupt as k:
                print()
                return
        else:
            print(colored("Database does not exist.", "red"))
            database_password = getpass.getpass("Enter password for new database    : ")
            database_password_confirm = getpass.getpass("Confirm password for new database  : ")
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
    p_database = PDatabase(database_filename, database_password, show_account_details,
                           show_invalidated_accounts)

    # from here we have a valid database ready to access

    # check if the interactive shell should be opened
    if options.query:
        start_pshell(p_database)
        sys.exit(0)

    # check here if a dropbox database merge should be done
    if options.merge_with_dropbox:
        merge_with_dropbox(p_database)
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
        edit(p_database, options.edit_uuid)
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
        p_database.merge_last_known_database()
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
    # when there are no options start the interactive p shell mode
    if len(sys.argv) == 1:
        start_pshell(p_database)


if __name__ == '__main__':
    main()
