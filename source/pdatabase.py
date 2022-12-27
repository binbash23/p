#
# 20221103 jens heine <binbash@gmx.net>
#
# Copyright
#
import os.path
# import random
import sqlite3
import logging
import base64
import os
import sys
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.exceptions import InvalidSignature
from cryptography.fernet import InvalidToken
import binascii
import progressbar
from termcolor import colored
# import termcolor
from re import finditer
from re import IGNORECASE
import uuid
import colorama

colorama.init()

#
# GLOBAL VARIABLES
#
SQL_GET_MAX_CHANGE_DATE_IN_DATABASE = """
SELECT
  max(change_date)
FROM
(
SELECT
  VALUE as change_date
FROM
  configuration
WHERE
  attribute = 'DATABASE_CREATED'  
UNION
SELECT
  max(create_date) as change_date
FROM
  account
UNION
SELECT
  max(change_date) as change_date
FROM
  account
)
"""
SQL_MERGE_INSERT_MISSING_UUIDS_FROM_REMOTE_INTO_ORIGIN_DATABASE = """
insert into main.account (uuid, name, url, loginname, password, type, create_date, change_date, invalid_date)
select 
uuid, 
name,
url, 
loginname, 
password, 
type, 
create_date, 
change_date, 
invalid_date 
from 
merge_database.account 
where 
uuid not in (select uuid from main.account)
"""
SQL_MERGE_COUNT_LOCAL_MISSING_UUIDS_THAT_EXIST_IN_REMOTE_DATABASE = """
select
count(*)
from 
merge_database.account 
where 
uuid not in (select uuid from main.account)
"""
SQL_MERGE_COUNT_REMOTE_MISSING_UUIDS_THAT_EXIST_IN_LOCAL_DATABASE = """
select
count(*)
from 
main.account 
where 
uuid not in (select uuid from merge_database.account)
"""
SQL_MERGE_DROP_LOCAL_ACCOUNT_CHANGE_DATE_TRIGGER = "drop trigger if exists main.update_change_date_Trigger"
SQL_MERGE_INSERT_MISSING_UUIDS_FROM_ORIGIN_INTO_REMOTE_DATABASE = """
insert into merge_database.account (uuid, name, url, loginname, password, type, create_date, change_date, invalid_date)
select 
uuid, 
name, 
url,
loginname, 
password, 
type, 
create_date, 
change_date, 
invalid_date 
from 
main.account 
where 
uuid not in (select uuid from merge_database.account)    
"""
SQL_MERGE_CREATE_LOCAL_ACCOUNT_CHANGE_DATE_TRIGGER = """
CREATE TRIGGER main.update_change_date_Trigger
AFTER UPDATE On account
BEGIN
   UPDATE account SET change_date = (datetime(CURRENT_TIMESTAMP, 'localtime')) WHERE uuid = NEW.uuid;
END
"""
SQL_MERGE_DROP_REMOTE_ACCOUNT_CHANGE_DATE_TRIGGER = "drop trigger if exists merge_database.update_change_date_Trigger"
SQL_MERGE_CREATE_REMOTE_ACCOUNT_CHANGE_DATE_TRIGGER = """
CREATE TRIGGER merge_database.update_change_date_Trigger
AFTER UPDATE On account
BEGIN
   UPDATE account SET change_date = (datetime(CURRENT_TIMESTAMP, 'localtime')) WHERE uuid = NEW.uuid;
END
"""
SQL_MERGE_COUNT_ACCOUNTS_IN_REMOTE_DB_WHICH_EXIST_IN_LOCAL_BUT_HAVE_NEWER_CHANGE_DATES = """
SELECT
count(*)
FROM
main.account o,
merge_database.account r
WHERE
o.uuid = r.uuid
AND
r.change_date > o.change_date
"""
SQL_MERGE_DELETE_ACCOUNTS_IN_ORIGIN_THAT_EXIST_IN_REMOTE_WITH_NEWER_CHANGE_DATE = """
DELETE
FROM
main.account
WHERE
uuid in
(	
SELECT
o.uuid
FROM
main.account o,
merge_database.account r
WHERE
o.uuid = r.uuid
AND
r.change_date > o.change_date
)
"""
SQL_MERGE_COUNT_ACCOUNTS_IN_LOCAL_DB_WHICH_EXIST_IN_REMOTE_BUT_HAVE_NEWER_CHANGE_DATES = """
SELECT
count(*)
FROM
main.account o,
merge_database.account r
WHERE
o.uuid = r.uuid
AND
r.change_date < o.change_date
"""
SQL_MERGE_DELETE_ACCOUNTS_IN_REMOTE_THAT_EXIST_IN_ORIGIN_WITH_NEWER_CHANGE_DATE = """
DELETE
FROM
merge_database.account
WHERE
uuid in
(	
SELECT
o.uuid
FROM
main.account o,
merge_database.account r
WHERE
o.uuid = r.uuid
AND
r.change_date < o.change_date
)
"""
SQL_CREATE_DATABASE_SCHEMA = """
CREATE TABLE "account" (
    "uuid"	TEXT NOT NULL UNIQUE,
    "name"	TEXT,
    "url"	TEXT,
    "loginname"	TEXT,
    "password"	TEXT,
    "type"	TEXT,
    "create_date"	datetime not null default (datetime(CURRENT_TIMESTAMP, 'localtime')),
    "change_date"	datetime not null default (datetime(CURRENT_TIMESTAMP, 'localtime')),
    "invalid_date"	datetime, 
    invalid int generated always as (case when invalid_date is not null then 1 else 0 end)
)	;
CREATE TRIGGER update_change_date_Trigger
AFTER UPDATE On account
BEGIN
   UPDATE account SET change_date = (datetime(CURRENT_TIMESTAMP, 'localtime')) WHERE uuid = NEW.uuid;
END;    
CREATE TABLE "configuration" (
    "attribute"	TEXT,
    "value"	TEXT,
    PRIMARY KEY("attribute")
);
insert into configuration (attribute, value) values ('SCHEMA_VERSION', '1');    
"""
ACCOUNTS_ORDER_BY_STATEMENT = "order by change_date, name"
SQL_SELECT_ALL_ACCOUNTS = """
    select 
        uuid, 
        name,
        url,
        loginname,
        password,
        type
    from 
        account 
"""
SQL_SELECT_COUNT_ALL_FROM_ACCOUNT = "select count(*) from account"
SQL_SELECT_COUNT_ALL_VALID_FROM_ACCOUNT = "select count(*) from account where invalid = 0"
SQL_SELECT_COUNT_ALL_INVALID_FROM_ACCOUNT = "select count(*) from account where invalid = 1"
CONFIGURATION_TABLE_ATTRIBUTE_PASSWORD_TEST = "DATABASE_PASSWORD_TEST"
CONFIGURATION_TABLE_PASSWORD_TEST_VALUE_WHEN_NOT_ENCRYPTED = "DATABASE IS NOT ENCRYPTED"
CONFIGURATION_TABLE_ATTRIBUTE_UUID = "DATABASE_UUID"
CONFIGURATION_TABLE_ATTRIBUTE_LAST_MERGE_DATABASE = "LAST_MERGE_DATABASE_FILENAME"
CONFIGURATION_TABLE_ATTRIBUTE_LAST_MERGE_DATE = "LAST_MERGE_DATE"
CONFIGURATION_TABLE_ATTRIBUTE_SCHEMA_VERSION = "SCHEMA_VERSION"
CONFIGURATION_TABLE_ATTRIBUTE_DROPBOX_ACCESS_TOKEN_ACCOUNT_UUID = "DROPBOX_ACCESS_TOKEN_ACCOUNT_UUID"
CONFIGURATION_TABLE_ATTRIBUTE_DROPBOX_APPLICATION_ACCOUNT_UUID = "DROPBOX_APPLICATION_ACCOUNT_UUID"
CONFIGURATION_TABLE_ATTRIBUTE_SHELL_MAX_IDLE_TIMEOUT_MIN = "SHELL_MAX_IDLE_TIMEOUT_MIN"


class Account:
    uuid = ""
    name = ""
    url = ""
    loginname = ""
    password = ""
    type = ""
    create_date = ""
    change_date = ""
    invalid_date = ""

    def __init__(self, uuid="", name="", url="", loginname="", password="", type="", create_date="", change_date="",
                 invalid_date=""):
        self.uuid = uuid
        self.name = name
        self.url = url
        self.loginname = loginname
        self.password = password
        self.type = type
        self.create_date = create_date
        self.change_date = change_date
        self.invalid_date = invalid_date

    def __str__(self):
        return "UUID=" + self.uuid + \
               ", Name=" + self.name + \
               ", URL=" + self.url + \
               ", Loginname=" + self.loginname + \
               ", Password=" + self.password + \
               ", Type=" + self.type + \
               ", Createdate=" + self.create_date + \
               ", Changedate=" + self.change_date + \
               ", Invaliddate=" + self.invalid_date


def search_string_matches_account(search_string: str, account: Account) -> bool:
    if search_string is None or search_string == "":
        return False
    search_string = search_string.lower()
    if account.create_date is None:
        account.create_date = ""
    if account.change_date is None:
        account.change_date = ""
    if account.invalid_date is None:
        account.invalid_date = ""
    if search_string in account.name.lower() or \
            search_string in account.url.lower() or \
            search_string in account.loginname.lower() or \
            search_string in account.password.lower() or \
            search_string in account.create_date.lower() or \
            search_string in account.change_date.lower() or \
            search_string in account.invalid_date.lower() or \
            search_string in account.type.lower():
        return True
    return False


def set_attribute_value_in_configuration_table(_database_filename, _attribute_name, _value):
    if _database_filename is None or _database_filename == "":
        raise ValueError("Database name must not be empty!")
    if _attribute_name is None or _attribute_name == "":
        raise ValueError("Attribute name must not be empty!")
    try:
        database_connection = None
        database_connection = sqlite3.connect(_database_filename)
        cursor = database_connection.cursor()
        # First check if the attribute exists and create it if not
        if not is_attribute_in_configuration_table(_database_filename, _attribute_name):
            sqlstring = "insert into configuration (attribute, value) values (?, ?)"
            cursor.execute(sqlstring, [_attribute_name, ""])
            database_connection.commit()
            # print("--done")
        sqlstring = "update configuration set value=? where attribute=?"
        cursor.execute(sqlstring, [_value, _attribute_name])
        database_connection.commit()
        # print("--done2")
    except Exception:
        raise
    finally:
        if database_connection is not None:
            database_connection.close()


def is_attribute_in_configuration_table(_database_filename, _attribute_name):
    if _database_filename is None or _database_filename == "":
        raise ValueError("Database name must not be empty!")
    if _attribute_name is None or _attribute_name == "":
        raise ValueError("Attribute name must not be empty!")
    try:
        database_connection = None
        database_connection = sqlite3.connect(_database_filename)
        cursor = database_connection.cursor()
        sqlstring = "select value from configuration where attribute=?"
        sqlresult = cursor.execute(sqlstring, [_attribute_name])
        value = sqlresult.fetchone()
        if value is None or len(value) == 0:
            return False
    except Exception as e:
        raise
    finally:
        if database_connection is not None:
            database_connection.close()
    return True


def get_attribute_value_from_configuration_table(_database_filename, _attribute_name):
    if _database_filename is None or _database_filename == "":
        raise ValueError("Database name must not be empty!")
    if _attribute_name is None or _attribute_name == "":
        raise ValueError("Attribute name must not be empty!")
    try:
        database_connection = None
        database_connection = sqlite3.connect(_database_filename)
        cursor = database_connection.cursor()
        sqlstring = "select value from configuration where attribute=?"
        sqlresult = cursor.execute(sqlstring, [_attribute_name])
        value = sqlresult.fetchone()
        if value is None:
            # raise ValueError("Attribute: \"" + _attribute_name + "\" does not exist")
            return ""
        value = value[0]
    except Exception:
        raise
    finally:
        if database_connection is not None:
            database_connection.close()
    return value


def is_encrypted_database(_database_filename):
    value = get_attribute_value_from_configuration_table(_database_filename,
                                                         CONFIGURATION_TABLE_ATTRIBUTE_PASSWORD_TEST)
    if value is None or value == "":
        # print("Could not fetch a valid DATABASE_PASSWORD_TEST value from configuration table.")
        raise ValueError("Could not fetch a valid DATABASE_PASSWORD_TEST value from configuration table.")
    if value == CONFIGURATION_TABLE_PASSWORD_TEST_VALUE_WHEN_NOT_ENCRYPTED:
        return False
    else:
        return True


def get_database_uuid(_database_filename):
    value = get_attribute_value_from_configuration_table(_database_filename, CONFIGURATION_TABLE_ATTRIBUTE_UUID)
    return value


def get_account_count_valid(database_filename):
    count = 0
    try:
        database_connection = sqlite3.connect(database_filename)
        cursor = database_connection.cursor()
        sqlstring = SQL_SELECT_COUNT_ALL_VALID_FROM_ACCOUNT
        sqlresult = cursor.execute(sqlstring)
        result = sqlresult.fetchone()
        if result is None:
            raise ValueError("Error: Could not count valid accounts.")
        count = result[0]
    except Exception as e:
        raise
    finally:
        database_connection.close()
    return count


def get_database_creation_date(database_filename):
    # count = 0
    try:
        database_connection = sqlite3.connect(database_filename)
        cursor = database_connection.cursor()
        sqlstring = "select value from configuration where attribute = 'DATABASE_CREATED'"
        sqlresult = cursor.execute(sqlstring)
        result = sqlresult.fetchone()
        if result is None:
            raise ValueError("Error: Could not get database creation date.")
        created_date = result[0]
    except Exception as e:
        raise
    finally:
        database_connection.close()
    return created_date


def get_last_change_date_in_database(database_filename):
    count = 0
    try:
        database_connection = sqlite3.connect(database_filename)
        cursor = database_connection.cursor()
        sqlstring = SQL_GET_MAX_CHANGE_DATE_IN_DATABASE
        sqlresult = cursor.execute(sqlstring)
        result = sqlresult.fetchone()
        if result is None:
            raise ValueError("Error: Could not get last change date in database.")
        created_date = result[0]
    except Exception as e:
        raise
    finally:
        database_connection.close()
    return created_date


def get_account_count_invalid(database_filename):
    count = 0
    try:
        database_connection = sqlite3.connect(database_filename)
        cursor = database_connection.cursor()
        sqlstring = SQL_SELECT_COUNT_ALL_INVALID_FROM_ACCOUNT
        sqlresult = cursor.execute(sqlstring)
        result = sqlresult.fetchone()
        if result is None:
            raise ValueError("Error: Could not count invalid accounts.")
        count = result[0]
    except Exception as e:
        raise
    finally:
        database_connection.close()
    return count


def get_account_count(database_filename):
    count = 0
    try:
        database_connection = sqlite3.connect(database_filename)
        cursor = database_connection.cursor()
        sqlstring = SQL_SELECT_COUNT_ALL_FROM_ACCOUNT
        sqlresult = cursor.execute(sqlstring)
        result = sqlresult.fetchone()
        if result is None:
            raise ValueError("Error: Could not count accounts.")
        count = result[0]
    except Exception as e:
        raise
    finally:
        database_connection.close()
    return count


def print_database_statistics(database_filename):
    if not os.path.exists(database_filename):
        print(colored("Can not show database statistics because database file does not exist.", "red"))
        return
    # print()
    account_count = get_account_count(database_filename)
    account_count_valid = get_account_count_valid(database_filename)
    account_count_invalid = get_account_count_invalid(database_filename)
    database_uuid = get_database_uuid(database_filename)
    database_creation_date = get_database_creation_date(database_filename)
    last_change_date = get_last_change_date_in_database(database_filename)
    database_is_encrypted = is_encrypted_database(database_filename)
    if database_is_encrypted:
        database_is_encrypted = colored("YES", "green")
    else:
        database_is_encrypted = colored("NO", "red")
    last_merge_database = get_attribute_value_from_configuration_table(database_filename,
                                                                       CONFIGURATION_TABLE_ATTRIBUTE_LAST_MERGE_DATABASE)
    last_merge_date = get_attribute_value_from_configuration_table(database_filename,
                                                                   CONFIGURATION_TABLE_ATTRIBUTE_LAST_MERGE_DATE)
    schema_version = get_attribute_value_from_configuration_table(database_filename,
                                                                  CONFIGURATION_TABLE_ATTRIBUTE_SCHEMA_VERSION)
    dropbox_account_uuid = \
        get_attribute_value_from_configuration_table(database_filename,
                                                     CONFIGURATION_TABLE_ATTRIBUTE_DROPBOX_ACCESS_TOKEN_ACCOUNT_UUID)
    dropbox_application_account_uuid = \
        get_attribute_value_from_configuration_table(database_filename,
                                                     CONFIGURATION_TABLE_ATTRIBUTE_DROPBOX_APPLICATION_ACCOUNT_UUID)
    shell_idle_timeout_min = \
        get_attribute_value_from_configuration_table(database_filename,
                                                     CONFIGURATION_TABLE_ATTRIBUTE_SHELL_MAX_IDLE_TIMEOUT_MIN)
    print("Database File                       : " + database_filename)
    print("Database UUID                       : " + database_uuid)
    print("Database Schema Version             : " + schema_version)
    print("Database Created                    : " + database_creation_date)
    print("Database Last Changed               : " + last_change_date)
    print("Database Encrypted                  : " + str(database_is_encrypted))
    print("Database Size                       : " + str(os.path.getsize(database_filename) / 1024) + " Kb")
    print("Accounts (valid/invalid)            : " + str(account_count) + " (" + str(account_count_valid) + "/" +
          str(account_count_invalid) + ")")
    print("Last Merge Database                 : " + str(last_merge_database))
    print("Last Merge Date                     : " + str(last_merge_date))
    print("Dropbox refresh token account uuid  : " + str(dropbox_account_uuid))
    print("Dropbox application account uuid    : " + str(dropbox_application_account_uuid))
    print("Shell idle timeout in minutes       : " + str(shell_idle_timeout_min))


def create_fernet(salt, password):
    _hash = PBKDF2HMAC(algorithm=hashes.SHA256, length=32, salt=salt, iterations=232323)
    key = base64.urlsafe_b64encode(_hash.derive(password))
    f = Fernet(key)
    return f


def color_search_string(text_string, search_string, color):
    if text_string is None or text_string == "":
        return ""
    # if search_string is None or search_string == "" or text_string is None or text_string == "":
    if search_string is None or search_string == "":
        return text_string
    list_matching_indices = [m.start() for m in finditer(search_string, text_string, flags=IGNORECASE)]
    # print(list_matching_indices)
    if len(list_matching_indices) == 0:
        return text_string
    colored_string = text_string[0:list_matching_indices[0]]
    match_nr = 0
    for i in list_matching_indices:
        colored_string = colored_string + colored(text_string[i:i + len(search_string)], color)
        if len(list_matching_indices) - 1 > match_nr:
            colored_string = colored_string + text_string[
                                              (i + len(search_string)):list_matching_indices[match_nr + 1]]
        match_nr += 1
    colored_string = colored_string + \
                     text_string[list_matching_indices[len(list_matching_indices) - 1] + len(search_string):
                                 len(text_string)]
    return colored_string


class PDatabase:
    SALT = b"lastpass"  # The salt for the encryption is static. This might become a problem?!
    database_filename = "unset_database_name.db"
    DATABASE_PASSWORD_TEST_VALUE_LENGTH = 32  # how long should the dummy encrypted string be
    fernet = None
    show_account_details = False
    show_invalidated_accounts = False
    shadow_passwords = False
    SEARCH_STRING_HIGHLIGHTING_COLOR = "green"

    def __init__(self, database_filename, database_password, show_account_details=False,
                 show_invalidated_accounts=False, shadow_passwords: bool = False):
        if database_filename is None \
                or database_filename == "" \
                or database_password is None:
            print("Database filename is empty or database password is not set!")
            sys.exit(1)
            # raise ValueError("Database filename is empty or database password is empty!")

        self.database_filename = database_filename
        self.show_account_details = show_account_details
        self.show_invalidated_accounts = show_invalidated_accounts
        self.shadow_passwords = shadow_passwords
        # store password as byte[]
        if database_password != "":
            self.database_password = database_password.encode("UTF-8")
            self.fernet = create_fernet(self.SALT, self.database_password)
        else:
            self.database_password = ""
        self.create_initial_database()
        if not self.is_valid_database_password(self.database_filename, self.database_password):
            print(colored("Database password verification failed! Password is wrong!", 'red'))
            sys.exit(1)

    def delete_account(self, delete_uuid):
        if delete_uuid is None or delete_uuid == "":
            print("Error deleting account: UUID is empty.")
            return
        answer = input("Delete account with UUID: " + delete_uuid + " ([y]/n) : ")
        if answer != "y" and answer != "":
            print("Canceled.")
            return
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            sqlstring = "delete from account where uuid = '" + str(delete_uuid) + "'"
            cursor.execute(sqlstring)
            database_connection.commit()
            print("Account with UUID " + str(delete_uuid) + " deleted.")
        except Exception as e:
            raise
        finally:
            database_connection.close()

    def invalidate_account(self, invalidate_uuid: str):
        if invalidate_uuid is None or invalidate_uuid == "":
            return
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            sqlstring = "update account set invalid_date = datetime(CURRENT_TIMESTAMP, 'localtime') where uuid = '" + \
                        str(invalidate_uuid) + "'"
            cursor.execute(sqlstring)
            database_connection.commit()
        except Exception as e:
            raise
        finally:
            database_connection.close()

    def revalidate_account(self, revalidate_uuid: str):
        if revalidate_uuid is None or revalidate_uuid == "":
            return
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            sqlstring = "update account set invalid_date = NULL where uuid = " + str(revalidate_uuid) + "'"
            cursor.execute(sqlstring)
            database_connection.commit()
        except Exception as e:
            raise
        finally:
            database_connection.close()

    def decrypt_account(self, account: Account) -> Account:
        account.uuid = account.uuid
        account.name = self.decrypt_string_if_password_is_present(account.name)
        account.url = self.decrypt_string_if_password_is_present(account.url)
        account.loginname = self.decrypt_string_if_password_is_present(account.loginname)
        account.password = self.decrypt_string_if_password_is_present(account.password)
        account.type = self.decrypt_string_if_password_is_present(account.type)
        account.create_date = account.create_date
        account.change_date = account.change_date
        account.invalid_date = account.invalid_date
        return account

    def search_accounts(self, search_string: str):
        results_found = 0
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            if self.show_invalidated_accounts:
                sqlstring = "select uuid, name, url, loginname, password, type, create_date, change_date, \
                            invalid_date from account "
            else:
                sqlstring = "select uuid, name, url, loginname, password, type, create_date, change_date, \
                            invalid_date from account where invalid = 0 "
            sqlstring = sqlstring + ACCOUNTS_ORDER_BY_STATEMENT
            # print("exceuting: " + sqlstring)
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            print("Searching for *" + colored(search_string, self.SEARCH_STRING_HIGHLIGHTING_COLOR) +
                  "* in " + str(get_account_count(self.database_filename)) + " accounts:")
            print()
            for row in result:
                account = Account(uuid=row[0],
                                  name=row[1],
                                  url=row[2],
                                  loginname=row[3],
                                  password=row[4],
                                  type=row[5],
                                  create_date=row[6],
                                  change_date=row[7],
                                  invalid_date=row[8]
                                  )
                decrypted_account = self.decrypt_account(account)
                if search_string == "" or \
                        search_string_matches_account(search_string, decrypted_account):
                    results_found += 1
                    self.print_formatted_account_search_string_colored(decrypted_account, search_string)
                    print()
        except Exception as e:
            raise
        finally:
            database_connection.close()
        print("Found " + str(results_found) + " result(s).")

    def search_account_by_uuid(self, search_uuid):
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            if search_uuid is None or search_uuid == "":
                return
            sqlstring = "select uuid, name, url, loginname, password, type, create_date, change_date, invalid_date from \
                         account where uuid = '" + str(search_uuid) + "'"
            sqlresult = cursor.execute(sqlstring)
            row = sqlresult.fetchone()
            if row is None:
                print("UUID " + search_uuid + " not found.")
                return
            print()
            account = Account(uuid=row[0],
                              name=row[1],
                              url=row[2],
                              loginname=row[3],
                              password=row[4],
                              type=row[5],
                              create_date=row[6],
                              change_date=row[7],
                              invalid_date=row[8]
                              )
            # self.print_formatted_account(self.decrypt_account_row(result))
            self.print_formatted_account(self.decrypt_account(account))
        except Exception as e:
            raise
        finally:
            database_connection.close()

    def get_password_from_account_and_decrypt(self, account_uuid: str) -> str:
        if account_uuid is None or account_uuid.strip() == "":
            return None
        account = self.get_account_by_uuid_and_decrypt(account_uuid)
        if account is not None:
            return account.password
        else:
            return None

    def get_loginname_from_account_and_decrypt(self, account_uuid: str) -> str:
        if account_uuid is None or account_uuid.strip() == "":
            return None
        account = self.get_account_by_uuid_and_decrypt(account_uuid)
        if account is not None:
            return account.loginname
        else:
            return None

    def get_account_by_uuid_and_decrypt(self, search_uuid: str) -> Account:
        if search_uuid is None or search_uuid == "":
            return None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            sqlstring = "select uuid, name, url, loginname, password, type, create_date, change_date, invalid_date " + \
                        "from account where uuid = '" + str(search_uuid) + "'"
            sqlresult = cursor.execute(sqlstring)
            row = sqlresult.fetchone()
            if row is not None:
                # decrypt:
                decrypted_name = self.decrypt_string_if_password_is_present(row[1])
                decrypted_url = self.decrypt_string_if_password_is_present(row[2])
                decrypted_loginname = self.decrypt_string_if_password_is_present(row[3])
                decrypted_password = self.decrypt_string_if_password_is_present(row[4])
                decrypted_type = self.decrypt_string_if_password_is_present(row[5])
                # current_account = (result[0], decrypted_name, decrypted_url, decrypted_loginname, decrypted_password,
                #                    decrypted_type)
                account = Account(uuid=uuid,
                                  name=decrypted_name,
                                  url=decrypted_url,
                                  loginname=decrypted_loginname,
                                  password=decrypted_password,
                                  type=decrypted_type,
                                  create_date=str(row[6]),
                                  change_date=str(row[7]),
                                  invalid_date=str(row[8])
                                  )
                # print("->" + str(current_account))
                return account
        except Exception as e:
            raise
        finally:
            database_connection.close()

    def set_account_by_uuid_and_encrypt(self, account_uuid, name, url, loginname, password, type):
        if account_uuid is None or account_uuid == "":
            raise Exception("Account UUID is not set or empty.")
        # encrypt
        name = self.encrypt_string_if_password_is_present(name)
        url = self.encrypt_string_if_password_is_present(url)
        loginname = self.encrypt_string_if_password_is_present(loginname)
        password = self.encrypt_string_if_password_is_present(password)
        type = self.encrypt_string_if_password_is_present(type)
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            sqlstring = "update account set name = '" + name + "', " + \
                        "url = '" + url + "', " + \
                        "loginname = '" + loginname + "', " + \
                        "password = '" + password + "', " + \
                        "type = '" + type + "' " + \
                        "where uuid = '" + str(account_uuid) + "'"
            cursor.execute(sqlstring)
            database_connection.commit()
        except Exception as e:
            raise
        finally:
            database_connection.close()

    def print_formatted_account_search_string_colored(self, account: Account, search_string: str = ""):
        account.name = color_search_string(account.name, search_string, self.SEARCH_STRING_HIGHLIGHTING_COLOR)
        account.url = color_search_string(account.url, search_string, self.SEARCH_STRING_HIGHLIGHTING_COLOR)
        account.loginname = color_search_string(account.loginname, search_string, self.SEARCH_STRING_HIGHLIGHTING_COLOR)
        account.password = color_search_string(account.password, search_string, self.SEARCH_STRING_HIGHLIGHTING_COLOR)
        account.type = color_search_string(account.type, search_string, self.SEARCH_STRING_HIGHLIGHTING_COLOR)
        account.create_date = color_search_string(account.create_date, search_string,
                                                  self.SEARCH_STRING_HIGHLIGHTING_COLOR)
        account.change_date = color_search_string(account.change_date, search_string,
                                                  self.SEARCH_STRING_HIGHLIGHTING_COLOR)
        account.invalid_date = color_search_string(account.invalid_date, search_string,
                                                  self.SEARCH_STRING_HIGHLIGHTING_COLOR)
        self.print_formatted_account(account)

    def print_formatted_account(self, account: Account):
        print("ID          : " + str(account.uuid))
        print("Name        : " + str(account.name))
        print("URL         : " + str(account.url))
        print("Loginname   : " + str(account.loginname))
        if self.shadow_passwords:
            print("Password    : ********")
        else:
            print("Password    : " + str(account.password))
        print("Type        : " + str(account.type))
        if self.show_account_details:
            print("Created     : " + str(account.create_date))
            print("Changed     : " + str(account.change_date))
            print("Invalidated : " + str(account.invalid_date))

    def decrypt_and_encrypt_with_new_password(self, string_encrypted: str, new_password: str) -> str:
        string_decrypted = self.decrypt_string_if_password_is_present(string_encrypted)
        string_encrypted_new = self.encrypt_string_with_custom_password(string_decrypted, new_password)
        return string_encrypted_new

    def change_database_password(self, new_password: str) -> bool:
        if not self.is_valid_database_password(self.database_filename, self.database_password):
            print("Old database password is wrong.")
            return False
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            # Change the PASSWORD_TEST token in configuration table:
            print("Changing DATABASE_PASSWORD_TEST value in configuration table...")
            if new_password != "":
                random_string = str(
                    binascii.hexlify(os.urandom(self.DATABASE_PASSWORD_TEST_VALUE_LENGTH)).decode('UTF-8'))
                encrypted_value = self.encrypt_string_with_custom_password(random_string, new_password)
            else:
                encrypted_value = CONFIGURATION_TABLE_PASSWORD_TEST_VALUE_WHEN_NOT_ENCRYPTED
            sqlstring_update_password_test_value = "update configuration set value = '" + encrypted_value + \
                                                   "' where attribute = 'DATABASE_PASSWORD_TEST'"
            # DO NOT COMMIT HERE! A rollback must be possible, if anything goes wrong before everything has been
            # changed properly
            cursor.execute(sqlstring_update_password_test_value)
            # Iterate through all the accounts, decrypt every password with the old pw, encrypt it with the new
            # one and write it all back.
            account_count = get_account_count(self.database_filename)
            print("Re-encrypting " + str(account_count) + " accounts...")
            bar = progressbar.ProgressBar(max_value=account_count).start()
            bar.start()
            # Disable the update_change_date_trigger
            cursor.execute(SQL_MERGE_DROP_LOCAL_ACCOUNT_CHANGE_DATE_TRIGGER)
            sqlstring = SQL_SELECT_ALL_ACCOUNTS
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            results_found = 0
            for row in result:
                results_found += 1
                # get current account data (enrypted)
                current_uuid = row[0]
                current_name = row[1]
                current_url = row[2]
                current_loginname = row[3]
                current_password = row[4]
                current_type = row[5]
                # print(row)
                # re-encrypt that shit
                new_current_name = self.decrypt_and_encrypt_with_new_password(current_name, new_password)
                new_current_url = self.decrypt_and_encrypt_with_new_password(current_url, new_password)
                new_current_loginname = self.decrypt_and_encrypt_with_new_password(current_loginname, new_password)
                new_current_password = self.decrypt_and_encrypt_with_new_password(current_password, new_password)
                new_current_type = self.decrypt_and_encrypt_with_new_password(current_type, new_password)
                # and push it back into the db
                update_sql_string = "update account set name=?, " + \
                                    "url=?, " + \
                                    "loginname=?, " + \
                                    "password=?, " + \
                                    "type=? " + \
                                    "where uuid = '" + str(current_uuid) + "'"
                cursor.execute(update_sql_string, (new_current_name, new_current_url, new_current_loginname,
                                                   new_current_password, new_current_type))
                bar.update(results_found)
            bar.finish()
            cursor.execute(SQL_MERGE_CREATE_LOCAL_ACCOUNT_CHANGE_DATE_TRIGGER)
            # ERST commit, wenn ALLES erledigt ist, sonst salat in der db!!!
            database_connection.commit()
            print("Changed accounts: " + str(results_found))
        except KeyboardInterrupt as k:
            if bar:
                bar.finish()
            if database_connection:
                database_connection.rollback()
            print("Process canceled by user.")
            return
            # sys.exit(0)
        except Exception as e:
            if database_connection:
                database_connection.rollback()
            raise
        finally:
            database_connection.close()
        return True

    def encrypt_string_if_password_is_present(self, plain_text: str) -> str:
        if plain_text is not None and plain_text != "":
            if self.database_password != "":
                return self.fernet.encrypt(bytes(plain_text, 'UTF-8')).decode("UTF-8")
            else:
                return plain_text
        else:
            return ""

    def encrypt_string_with_custom_password(self, plain_text: str, password: str) -> str:
        if password == "":
            return plain_text
        _fernet = create_fernet(self.SALT, password.encode("UTF-8"))
        if plain_text is not None and plain_text != "":
            return _fernet.encrypt(bytes(plain_text, 'UTF-8')).decode("UTF-8")
        else:
            return ""

    def decrypt_string_if_password_is_present(self, encrypted_text: str) -> str:
        if encrypted_text == "" or encrypted_text is None:
            return ""
        if self.database_password != "":
            decrypted_string = self.fernet.decrypt(bytes(encrypted_text, "UTF-8")).decode("UTF-8")
            return decrypted_string
        else:
            return encrypted_text

    def decrypt_string_if_password_is_present_with_custom_password(self, encrypted_text: str, _database_password):
        if encrypted_text == "" or encrypted_text is None:
            return ""
        if _database_password != "":
            # _fernet = self.create_fernet(self.SALT, _database_password.encode("UTF-8"))
            _fernet = create_fernet(self.SALT, _database_password)
            decrypted_string = _fernet.decrypt(bytes(encrypted_text, "UTF-8")).decode("UTF-8")
            return decrypted_string
        else:
            return encrypted_text

    # def decrypt_string(self, encrypted_text):
    #     if encrypted_text == "":
    #         return ""
    #     decrypted_string = self.fernet.decrypt(bytes(encrypted_text, "UTF-8")).decode("UTF-8")
    #     return decrypted_string

    def add_account_and_encrypt(self, account: Account):
        account.name = self.encrypt_string_if_password_is_present(account.name)
        account.url = self.encrypt_string_if_password_is_present(account.url)
        account.loginname = self.encrypt_string_if_password_is_present(account.loginname)
        account.password = self.encrypt_string_if_password_is_present(account.password)
        account.type = self.encrypt_string_if_password_is_present(account.type)
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            if account.uuid is None or account.uuid == "":
                account.uuid = uuid.uuid4()
            sqlstring = "insert into account (uuid, name, url, loginname, password, type) values " + \
                        "('" + str(account.uuid) + \
                        "', '" + account.name + \
                        "', '" + account.url + \
                        "', '" + account.loginname + \
                        "', '" + account.password + \
                        "', '" + account.type + "')"
            cursor.execute(sqlstring)
            database_connection.commit()
            print("New account added.")
        except sqlite3.IntegrityError:
            print("Error: UUID " + str(account.uuid) + " already exists in database!")
        except Exception as e:
            raise
        finally:
            if database_connection:
                database_connection.close()

    def is_valid_database_password(self, _database_filename: str, _database_password: str) -> bool:
        try:
            value = get_attribute_value_from_configuration_table(_database_filename,
                                                                 CONFIGURATION_TABLE_ATTRIBUTE_PASSWORD_TEST)
            if value is None or value == "":
                print("Could not fetch a valid DATABASE_PASSWORD_TEST value from configuration table.")
                return False
            if value == CONFIGURATION_TABLE_PASSWORD_TEST_VALUE_WHEN_NOT_ENCRYPTED and _database_password == "":
                print(colored("Warning: The account database " + _database_filename + " is NOT encrypted.", "red"))
                return True
            else:
                if _database_password == "":
                    return False
                else:
                    self.decrypt_string_if_password_is_present_with_custom_password(value, _database_password)
        except (InvalidSignature, InvalidToken) as e:
            return False
        return True

    def create_initial_database(self):
        try:
            database_connection = None
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            logging.debug("Setting PRAGMA journal_mode = WAL for database.")
            cursor.execute("PRAGMA journal_mode = WAL")
            database_connection.commit()
            sqlstring = "select count(*) from account"
            sqlresult = cursor.execute(sqlstring)
            value = sqlresult.fetchone()[0]
            if value is not None:
                return
        except Exception as e:
            if str(e) == "database disk image is malformed":
                print(colored("Error: " + str(e), "red"))
                return
                # sys.exit(1)
        finally:
            if database_connection is not None:
                database_connection.close()
        # Something went wrong opening the sqlite db. Now try to create one with default schema
        try:
            database_connection = None
            print("Creating new p database: \"" + self.database_filename + "\" ...")
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            cursor.executescript(SQL_CREATE_DATABASE_SCHEMA)
            new_database_uuid = uuid.uuid4()
            print("Creating new UUID for database: " + str(new_database_uuid))
            sqlstring = "insert into configuration (attribute, value) values (?, ?)"
            cursor.execute(sqlstring, ("DATABASE_UUID", str(new_database_uuid)))
            sqlstring = "insert into configuration (attribute, value) values (?, ?)"
            if self.database_password != "":
                # print(colored("Creating an encrypted database with your password! Do not forget it!", 'green'))
                random_string = str(
                    binascii.hexlify(os.urandom(self.DATABASE_PASSWORD_TEST_VALUE_LENGTH)).decode('UTF-8'))
                encrypted_value = self.encrypt_string_if_password_is_present(random_string)
            else:
                print(colored("Creating an UNENCRYPTED database without any password!", 'red'))
                print(colored("You can encrypt the database later with the -c option.", "red"))
                encrypted_value = CONFIGURATION_TABLE_PASSWORD_TEST_VALUE_WHEN_NOT_ENCRYPTED
            cursor.execute(sqlstring, ("DATABASE_PASSWORD_TEST", encrypted_value))
            # add creation date of database
            sqlstring = "insert into configuration (attribute, value) values " + \
                        "('DATABASE_CREATED', datetime(CURRENT_TIMESTAMP, 'localtime'))"
            cursor.execute(sqlstring)
            # print("executed: " + sqlstring)
            database_connection.commit()
            # print("DATABASE_PASSWORD test value created and inserted into configuration table.")
        except Exception as e:
            raise
        finally:
            if database_connection is not None:
                database_connection.close()

    def create_add_statements(self):
        results_found = 0
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            sqlstring = "select uuid, name, url, loginname, password, type, create_date, change_date, \
                         invalid_date from account"
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            print()
            if self.database_password != "":
                current_password = self.database_password.decode('UTF-8')
            else:
                current_password = ""
            for row in result:
                account = Account(uuid=row[0],
                                  name=row[1],
                                  url=row[2],
                                  loginname=row[3],
                                  password=row[4],
                                  type=row[5],
                                  create_date=row[6],
                                  change_date=row[7],
                                  invalid_date=row[8]
                                  )
                decrypted_account = self.decrypt_account(account)
                results_found += 1
                print("p -p '" + current_password + "' -A " +
                      "-X '" + decrypted_account.uuid + "' " +
                      "-N '" + decrypted_account.name + "' " +
                      "-U '" + decrypted_account.url + "' " +
                      "-L '" + decrypted_account.loginname + "' " +
                      "-P '" + decrypted_account.password + "' " +
                      "-T '" + decrypted_account.type + "' ")
        except Exception as e:
            raise
        finally:
            database_connection.close()
        print()
        print("Found " + str(results_found) + " result(s).")

    def merge_last_known_database(self):
        last_known_database = \
            get_attribute_value_from_configuration_table(self.database_filename,
                                                         CONFIGURATION_TABLE_ATTRIBUTE_LAST_MERGE_DATABASE)
        if last_known_database is not None and last_known_database != "":
            self.merge_database(last_known_database)
        else:
            print(colored("Error: There is no last known database.", "red"))

    # returns -1 in error case, 0 when no error and no changes where made,
    # 1 when changes where made locally and 2 when changes where made in remote db
    # and 3 when changes where made locally and remote
    def merge_database(self, merge_database_filename: str) -> int:
        if not os.path.exists(merge_database_filename):
            print("Error: merge database does not exist: '" + merge_database_filename + "'")
            return -1
        print("Using merge database: " + merge_database_filename)
        # Check remote db for password
        print("Checking merge database password...")
        if not self.is_valid_database_password(merge_database_filename, self.database_password):
            print(colored("Error: because password for merge database: " + merge_database_filename +
                          " is not valid!", "red"))
            print("The database passwords must be the same in both databases.")
            print("")
            return -1
        # Set some attribute values in configuration table and create some attributes if not exist
        set_attribute_value_in_configuration_table(self.database_filename,
                                                   CONFIGURATION_TABLE_ATTRIBUTE_LAST_MERGE_DATABASE,
                                                   merge_database_filename)
        set_attribute_value_in_configuration_table(self.database_filename,
                                                   CONFIGURATION_TABLE_ATTRIBUTE_LAST_MERGE_DATE,
                                                   "")
        set_attribute_value_in_configuration_table(merge_database_filename,
                                                   CONFIGURATION_TABLE_ATTRIBUTE_LAST_MERGE_DATE,
                                                   "")
        # Start merging
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            print("Attaching merge database...")
            sqlstring = "attach '" + merge_database_filename + "' as merge_database"
            cursor.execute(sqlstring)

            # Step #0 do the math
            sqlresult = cursor.execute(SQL_MERGE_COUNT_LOCAL_MISSING_UUIDS_THAT_EXIST_IN_REMOTE_DATABASE)
            result = sqlresult.fetchone()
            count_uuids_in_remote_that_do_not_exist_in_local = result[0]
            sqlresult = cursor.execute(SQL_MERGE_COUNT_REMOTE_MISSING_UUIDS_THAT_EXIST_IN_LOCAL_DATABASE)
            result = sqlresult.fetchone()
            count_uuids_in_local_that_do_not_exist_in_remote = result[0]
            sqlresult = cursor.execute(
                SQL_MERGE_COUNT_ACCOUNTS_IN_REMOTE_DB_WHICH_EXIST_IN_LOCAL_BUT_HAVE_NEWER_CHANGE_DATES)
            result = sqlresult.fetchone()
            count_uuids_in_remote_with_newer_update_date_than_in_local = result[0]
            sqlresult = cursor.execute(
                SQL_MERGE_COUNT_ACCOUNTS_IN_LOCAL_DB_WHICH_EXIST_IN_REMOTE_BUT_HAVE_NEWER_CHANGE_DATES)
            result = sqlresult.fetchone()
            count_uuids_in_local_with_newer_update_date_than_in_remote = result[0]

            # Step #1 Sync new accounts from remote merge database into main database
            print(colored("Step #1: Analyzing Origin Database - " + self.database_filename, "green"))
            # print("Dropping update_date trigger (origin database)...")
            cursor.execute(SQL_MERGE_DROP_LOCAL_ACCOUNT_CHANGE_DATE_TRIGGER)
            print("Updating " + colored(str(count_uuids_in_remote_with_newer_update_date_than_in_local), "red")
                  + " local account(s) that have newer change dates in the remote database...")
            cursor.execute(SQL_MERGE_DELETE_ACCOUNTS_IN_ORIGIN_THAT_EXIST_IN_REMOTE_WITH_NEWER_CHANGE_DATE)
            print("Fetching " + colored(str(count_uuids_in_remote_that_do_not_exist_in_local), "red")
                  + " new account(s) from the remote database into the origin database...")
            cursor.execute(SQL_MERGE_INSERT_MISSING_UUIDS_FROM_REMOTE_INTO_ORIGIN_DATABASE)
            # print("Re-Creating update_date trigger (origin database)...")
            cursor.execute(SQL_MERGE_CREATE_LOCAL_ACCOUNT_CHANGE_DATE_TRIGGER)
            print("Origin database is now up to date (" +
                  colored(str(count_uuids_in_remote_with_newer_update_date_than_in_local +
                              count_uuids_in_remote_that_do_not_exist_in_local), "red") + " changes have been done)")
            # remember that there where changes in local db for return code:
            return_code = 0
            if count_uuids_in_remote_with_newer_update_date_than_in_local + \
                    count_uuids_in_remote_that_do_not_exist_in_local > 0:
                return_code = 1
            database_connection.commit()
            # Step #2 Sync new accounts from main database into remote database
            print(colored("Step #2: Analyzing Remote Database - " + merge_database_filename, "green"))
            # print("Dropping update_date trigger (remote database)...")
            cursor.execute(SQL_MERGE_DROP_REMOTE_ACCOUNT_CHANGE_DATE_TRIGGER)
            print("Updating " + colored(str(count_uuids_in_local_with_newer_update_date_than_in_remote), "red")
                  + " remote account(s) that have newer change dates in the origin database...")
            cursor.execute(SQL_MERGE_DELETE_ACCOUNTS_IN_REMOTE_THAT_EXIST_IN_ORIGIN_WITH_NEWER_CHANGE_DATE)
            print("Fetching " + colored(str(count_uuids_in_local_that_do_not_exist_in_remote), "red")
                  + " new account(s) from the origin database into the remote database...")
            cursor.execute(SQL_MERGE_INSERT_MISSING_UUIDS_FROM_ORIGIN_INTO_REMOTE_DATABASE)
            # print("Re-Creating update_date trigger (remote database)...")
            cursor.execute(SQL_MERGE_CREATE_REMOTE_ACCOUNT_CHANGE_DATE_TRIGGER)
            # Remember date of current merge action in origin and remote database
            cursor.execute("update configuration set value = datetime(CURRENT_TIMESTAMP, 'localtime')" +
                           " where attribute = ?", [CONFIGURATION_TABLE_ATTRIBUTE_LAST_MERGE_DATE])
            cursor.execute("update merge_database.configuration set value = datetime(CURRENT_TIMESTAMP, 'localtime')" +
                           " where attribute = ?", [CONFIGURATION_TABLE_ATTRIBUTE_LAST_MERGE_DATE])
            # Finally commit it
            database_connection.commit()
            print("Remote database is now up to date (" +
                  colored(str(count_uuids_in_local_with_newer_update_date_than_in_remote +
                              count_uuids_in_local_that_do_not_exist_in_remote), "red") + " changes have been done)")
            # remember that there where changes in remote db for return code:
            if count_uuids_in_local_with_newer_update_date_than_in_remote + \
                    count_uuids_in_local_that_do_not_exist_in_remote > 0:
                return_code += 2
        except Exception as e:
            raise
        finally:
            database_connection.close()
        return return_code


def main():
    # print(colored("test", "red"))
    # exit(0)
    # db = PDatabase("p.db", "a")
    # db.add_account_encrypted("nn", "", "", "", "")
    # db.change_database_password("b")
    # print(get_attribute_value_from_configuration_table('p.db', 'DATABASE_UUID'))
    print("is: " + str(is_attribute_in_configuration_table('p.db', 'TEST2')))
    print("get_attribute_value_from_configuration_table: " + get_attribute_value_from_configuration_table('p.db',
                                                                                                          'TEST2'))
    set_attribute_value_in_configuration_table('p.db', 'TEST2', "hallo")
    print("get_attribute_value_from_configuration_table: " + get_attribute_value_from_configuration_table('p.db',
                                                                                                          'TEST2'))
    print("is: " + str(is_attribute_in_configuration_table('p.db', 'TEST2')))


if __name__ == '__main__':
    main()
