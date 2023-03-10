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
UNION
SELECT
  max(create_date) as change_date
FROM
  deleted_account
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
SQL_MERGE_INSERT_MISSING_HISTORY_UUIDS_FROM_REMOTE_INTO_ORIGIN_DATABASE = """
insert into main.account_history (uuid, account_uuid, name, url, loginname, password, type, create_date)
select 
uuid,
account_uuid, 
name,
url, 
loginname, 
password, 
type, 
create_date
from 
merge_database.account_history 
where 
uuid not in (select uuid from main.account_history)
"""
SQL_MERGE_COUNT_LOCAL_MISSING_UUIDS_THAT_EXIST_IN_REMOTE_DATABASE = """
select
count(*)
from 
merge_database.account 
where 
uuid not in (select uuid from main.account)
"""
SQL_MERGE_COUNT_LOCAL_MISSING_HISTORY_UUIDS_THAT_EXIST_IN_REMOTE_DATABASE = """
select
count(*)
from 
merge_database.account_history
where 
uuid not in (select uuid from main.account_history)
"""
SQL_MERGE_COUNT_REMOTE_MISSING_UUIDS_THAT_EXIST_IN_LOCAL_DATABASE = """
select
count(*)
from 
main.account 
where 
uuid not in (select uuid from merge_database.account)
"""
SQL_MERGE_COUNT_REMOTE_MISSING_HISTORY_UUIDS_THAT_EXIST_IN_LOCAL_DATABASE = """
select
count(*)
from 
main.account_history
where 
uuid not in (select uuid from merge_database.account_history)
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
SQL_MERGE_INSERT_MISSING_HISTORY_UUIDS_FROM_ORIGIN_INTO_REMOTE_DATABASE = """
insert into merge_database.account_history (uuid, account_uuid, name, url, loginname, password, type, create_date)
select 
uuid, 
account_uuid,
name, 
url,
loginname, 
password, 
type, 
create_date
from 
main.account_history
where 
uuid not in (select uuid from merge_database.account_history)    
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
-- main table with accounts
CREATE TABLE if not EXISTS "account" (
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
CREATE TRIGGER if not EXISTS update_change_date_Trigger
AFTER UPDATE On account
BEGIN
   UPDATE account SET change_date = (datetime(CURRENT_TIMESTAMP, 'localtime')) WHERE uuid = NEW.uuid;
END;    
-- configuration values table
CREATE TABLE if not EXISTS "configuration" (
    "attribute"	TEXT,
    "value"	TEXT,
    PRIMARY KEY("attribute")
);
insert or replace into configuration (attribute, value) values ('SCHEMA_VERSION', '3');   
-- table for uuids that have been deleted
CREATE TABLE if not EXISTS "deleted_account" (
    "uuid"	TEXT NOT NULL UNIQUE,
    "create_date"	datetime not null default (datetime(CURRENT_TIMESTAMP, 'localtime'))
	);
-- table for account history entries
CREATE TABLE if not exists "account_history" (
    "uuid"	TEXT NOT NULL UNIQUE,
	"account_uuid" TEXT NOT NULL,
    "name"	TEXT,
    "url"	TEXT,
    "loginname"	TEXT,
    "password"	TEXT,
    "type"	TEXT,
    "create_date"	datetime not null default (datetime(CURRENT_TIMESTAMP, 'localtime'))
);
"""
SQL_CREATE_MERGE_DATABASE_SCHEMA = """
-- main table with accounts
CREATE TABLE if not EXISTS merge_database.account (
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
CREATE TRIGGER if not EXISTS merge_database.update_change_date_Trigger
AFTER UPDATE On account
BEGIN
   UPDATE account SET change_date = (datetime(CURRENT_TIMESTAMP, 'localtime')) WHERE uuid = NEW.uuid;
END;    
-- configuration values table
CREATE TABLE if not EXISTS merge_database.configuration (
    "attribute"	TEXT,
    "value"	TEXT,
    PRIMARY KEY("attribute")
);
insert or replace into merge_database.configuration (attribute, value) values ('SCHEMA_VERSION', '3');   
-- table for uuids that have been deleted
CREATE TABLE if not EXISTS merge_database.deleted_account (
    "uuid"	TEXT NOT NULL UNIQUE,
    "create_date"	datetime not null default (datetime(CURRENT_TIMESTAMP, 'localtime'))
	);
-- table for account history entries
CREATE TABLE if not exists merge_database.account_history (
    "uuid"	TEXT NOT NULL UNIQUE,
	"account_uuid" TEXT NOT NULL,
    "name"	TEXT,
    "url"	TEXT,
    "loginname"	TEXT,
    "password"	TEXT,
    "type"	TEXT,
    "create_date"	datetime not null default (datetime(CURRENT_TIMESTAMP, 'localtime'))
);	
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
SQL_SELECT_ALL_ACCOUNT_HISTORY = """
    select 
        uuid, 
        account_uuid,
        name,
        url,
        loginname,
        password,
        type
    from 
        account_history
"""
SQL_SELECT_COUNT_ALL_FROM_ACCOUNT = "select count(*) from account"
SQL_SELECT_COUNT_ALL_FROM_ACCOUNT_HISTORY = "select count(*) from account_history"
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
CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_MAX_IDLE_TIMEOUT_MIN = "SHELL_MAX_IDLE_TIMEOUT_MIN"
# CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_MAX_IDLE_TIMEOUT_MIN_BEFORE_CONSOLE_CLEAR = \
#     "SHELL_MAX_IDLE_TIMEOUT_MIN_BEFORE_CONSOLE_CLEAR"
CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHADOW_PASSWORDS = "PSHELL_SHADOW_PASSWORDS"
CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHOW_INVALIDATED_ACCOUNTS = "PSHELL_SHOW_INVALIDATED_ACCOUNTS"
CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHOW_ACCOUNT_DETAILS = "PSHELL_SHOW_ACCOUNT_DETAILS"
CONFIGURATION_TABLE_ATTRIBUTE_DATABASE_NAME = "DATABASE_NAME"
CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHOW_UNMERGED_CHANGES_WARNING = "PSHELL_SHOW_UNMERGED_CHANGES_WARNING"
CONFIGURATION_TABLE_ATTRIBUTE_TRACK_ACCOUNT_HISTORY = "TRACK_ACCOUNT_HISTORY"


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


# def accounts_are_equal(account1: Account, account2: Account) -> bool:
#     if account1 is None or account2 is None:
#         return False
#     if (account1.uuid == account2.uuid or (account1.uuid is None and account2.uuid is None)) and \
#             (account1.name == account2.name or (account1.name is None and account2.name is None) and \
#              (account1.url == account2.url or (account1.url is None and account2.url is None)) and \
#              (account1.loginname == account2.loginname or (
#                      account1.loginname is None and account2.loginname is None)) and \
#              (account1.password == account2.password or (account1.password is None and account2.password is None)) and \
#              (account1.type == account2.type or (account1.type is None and account2.type is None))):
#         return True
#     else:
#         return False

def accounts_are_equal(account1: Account, account2: Account) -> bool:
    if account1 is None or account2 is None:
        return False
    if (account1.uuid == account2.uuid) and \
            (account1.name == account2.name) and \
            (account1.url == account2.url) and \
            (account1.loginname == account2.loginname) and \
            (account1.password == account2.password) and \
            (account1.type == account2.type):
        return True
    else:
        return False


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
            search_string in account.uuid.lower() or \
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


def is_encrypted_database(database_filename):
    value = get_attribute_value_from_configuration_table(database_filename,
                                                         CONFIGURATION_TABLE_ATTRIBUTE_PASSWORD_TEST)
    if value is None or value == "":
        # print("Could not fetch a valid DATABASE_PASSWORD_TEST value from configuration table.")
        raise ValueError("Could not fetch a valid DATABASE_PASSWORD_TEST value from configuration table.")
    if value == CONFIGURATION_TABLE_PASSWORD_TEST_VALUE_WHEN_NOT_ENCRYPTED:
        return False
    else:
        return True


def get_database_uuid(database_filename):
    value = get_attribute_value_from_configuration_table(database_filename, CONFIGURATION_TABLE_ATTRIBUTE_UUID)
    return value


def get_database_name(database_filename):
    value = get_attribute_value_from_configuration_table(database_filename, CONFIGURATION_TABLE_ATTRIBUTE_DATABASE_NAME)
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


def get_account_history_count(database_filename):
    count = 0
    try:
        database_connection = sqlite3.connect(database_filename)
        cursor = database_connection.cursor()
        sqlstring = SQL_SELECT_COUNT_ALL_FROM_ACCOUNT_HISTORY
        sqlresult = cursor.execute(sqlstring)
        result = sqlresult.fetchone()
        if result is None:
            raise ValueError("Error: Could not count account history entries.")
        count = result[0]
    except Exception as e:
        raise
    finally:
        database_connection.close()
    return count

def get_account_count(database_filename, count_invalidated_accounts: bool = True):
    count = 0
    try:
        database_connection = sqlite3.connect(database_filename)
        cursor = database_connection.cursor()
        if count_invalidated_accounts:
            sqlstring = SQL_SELECT_COUNT_ALL_FROM_ACCOUNT
        else:
            sqlstring = SQL_SELECT_COUNT_ALL_VALID_FROM_ACCOUNT
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
        database_is_encrypted = colored("Yes", "green")
    else:
        database_is_encrypted = colored("No", "red")
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
    database_name = \
        get_attribute_value_from_configuration_table(database_filename,
                                                     CONFIGURATION_TABLE_ATTRIBUTE_DATABASE_NAME)
    if get_database_has_unmerged_changes(database_filename) is True:
        unmerged_changes = colored("Yes", "red")
    else:
        unmerged_changes = colored("No", "green")

    print("Database Name                       : " + database_name)
    print("Database UUID                       : " + database_uuid)
    print("Database File                       : " + os.path.abspath(database_filename))
    print("Database Created                    : " + database_creation_date)
    print("Database Schema Version             : " + schema_version)
    print("SQLite Database Version             : " + get_database_sqlite_version(database_filename))
    print("Database Encrypted                  : " + str(database_is_encrypted))
    print("Database Size                       : " + str(os.path.getsize(database_filename) / 1024) + " Kb")
    print("Database Last Changed               : " + last_change_date)
    print("Accounts (valid/invalid)            : " + str(account_count) + " (" + str(account_count_valid) + "/" +
          str(account_count_invalid) + ")")
    print("Last Merge Database                 : " + str(last_merge_database))
    print("Last Merge Date                     : " + str(last_merge_date))
    print("Database has unmerged changes       : " + unmerged_changes)
    print("Dropbox refresh token account uuid  : " + str(dropbox_account_uuid))
    print("Dropbox application account uuid    : " + str(dropbox_application_account_uuid))


def get_database_sqlite_version(database_filename: str) -> str:
    version = "unknown"
    try:
        database_connection = sqlite3.connect(database_filename)
        cursor = database_connection.cursor()
        sqlstring = "select sqlite_version()"
        sqlresult = cursor.execute(sqlstring)
        result = sqlresult.fetchone()
        if result is None:
            raise ValueError("Error: Could not get sqlite version.")
        version = result[0]
    except Exception as e:
        raise
    finally:
        database_connection.close()
    return version


def get_database_has_unmerged_changes(database_filename: str) -> str:
    last_change_date = get_last_change_date_in_database(database_filename)
    last_merge_date = get_attribute_value_from_configuration_table(database_filename,
                                                                   CONFIGURATION_TABLE_ATTRIBUTE_LAST_MERGE_DATE)
    if last_change_date is not None and last_merge_date is not None:
        last_change_date_later_than_last_merge_date = last_change_date > last_merge_date
    else:
        last_change_date_later_than_last_merge_date = False
    # if last_change_date_later_than_last_merge_date is True:
    #     last_change_date_later_than_last_merge_date = colored("Yes", "red")
    # else:
    #     last_change_date_later_than_last_merge_date = colored("No", "green")
    return last_change_date_later_than_last_merge_date


def create_fernet(salt, password, iteration_count: int) -> Fernet:
    # _hash = PBKDF2HMAC(algorithm=hashes.SHA256, length=32, salt=salt, iterations=232323)
    # _hash = PBKDF2HMAC(algorithm=hashes.SHA256, length=32, salt=salt, iterations=500000)
    _hash = PBKDF2HMAC(algorithm=hashes.SHA256, length=32, salt=salt, iterations=iteration_count)
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
    DEFAULT_SALT = b"98uAS (H CQCH AISDUHU/ZASD/7zhdw7e-;568!"  # The salt for the encryption is static. This might become a problem?!
    # DEFAULT_SALT = b"lastpass"  # The salt for the encryption is static. This might become a problem?!
    DEFAULT_ITERATION_COUNT = 500000

    database_filename = "unset_database_name.db"
    DATABASE_PASSWORD_TEST_VALUE_LENGTH = 32  # how long should the dummy encrypted string be
    fernet = None
    salt = None
    iteration_count: int = -1
    show_account_details: bool = False
    show_invalidated_accounts: bool = False
    shadow_passwords: bool = False
    SEARCH_STRING_HIGHLIGHTING_COLOR = "green"
    track_account_history: bool = True

    def __init__(self, database_filename, database_password, show_account_details=False,
                 show_invalidated_accounts=False, shadow_passwords: bool = False,
                 salt=DEFAULT_SALT, iteration_count: int = DEFAULT_ITERATION_COUNT,
                 track_account_history: bool = True):
        if database_filename is None \
                or database_filename == "" \
                or database_password is None:
            print(colored("Error: Database filename is empty or database password is not set!", "red"))
            # sys.exit(1)
            raise ValueError("Database filename is not set or database password is not set!")

        self.database_filename = database_filename
        self.show_account_details = show_account_details
        self.show_invalidated_accounts = show_invalidated_accounts
        self.shadow_passwords = shadow_passwords
        self.track_account_history = track_account_history
        self.salt = salt
        self.iteration_count = iteration_count
        # store password as byte[]
        if database_password != "":
            self.database_password = database_password.encode("UTF-8")
            self.fernet = create_fernet(self.salt, self.database_password, self.iteration_count)
        else:
            self.database_password = ""
        self.create_and_initialize_database()
        self.update_database_schema(self.database_filename)
        self.set_default_values_in_configuration_table()
        if not self.is_valid_database_password(self.database_filename, self.database_password):
            print(colored("Database password verification failed! Password is wrong!", 'red'))
            sys.exit(1)

    def set_default_values_in_configuration_table(self):
        if get_attribute_value_from_configuration_table(self.database_filename,
                                                        CONFIGURATION_TABLE_ATTRIBUTE_TRACK_ACCOUNT_HISTORY) == "":
            if self.track_account_history:
                set_attribute_value_in_configuration_table(self.database_filename,
                                                           CONFIGURATION_TABLE_ATTRIBUTE_TRACK_ACCOUNT_HISTORY,
                                                           "True")
            else:
                set_attribute_value_in_configuration_table(self.database_filename,
                                                           CONFIGURATION_TABLE_ATTRIBUTE_TRACK_ACCOUNT_HISTORY,
                                                           "False")

    def update_database_schema(self, database_filename: str):
        try:
            database_connection = sqlite3.connect(database_filename)
            cursor = database_connection.cursor()
            sqlstring = SQL_CREATE_DATABASE_SCHEMA
            cursor.executescript(sqlstring)
            database_connection.commit()
        except Exception as e:
            print(colored("Error: " + str(e)))
        finally:
            database_connection.close()

    # def __str__(self):
    #     id_string = "[" + get_database_uuid(self.database_filename) + "] - '" + self.database_filename + "'"
    #     if get_database_name(self) != "":
    #         id_string = "'" + get_database_name(self) + "' - " + id_string

    def print_current_secure_delete_mode(self, database_connection, cursor):
        sqlstring = "pragma secure_delete"
        try:
            print("SQLite secure_delete mode: " + str(cursor.execute(sqlstring).fetchall()[0][0]))
        except Exception as e:
            raise

    def delete_account(self, delete_uuid):
        if delete_uuid is None or delete_uuid == "":
            print("Error deleting account: UUID is empty.")
            return
        if self.get_account_exists(delete_uuid) is False:
            print("Error: Account uuid " + delete_uuid + " does not exist.")
            return
        answer = input("Delete account with UUID: " + delete_uuid + " ([y]/n) : ")
        if answer != "y" and answer != "":
            print("Canceled.")
            return
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            self.set_database_pragmas_to_secure_mode(database_connection, cursor)
            self.print_current_secure_delete_mode(database_connection, cursor)
            sqlstring = "delete from account where uuid = '" + str(delete_uuid) + "'"
            cursor.execute(sqlstring)
            # remember deleted uuid in deleted_account table for merge information
            if self.get_uuid_exists_in_deleted_accounts(str(delete_uuid)) is False:
                encrypted_uuid = self.encrypt_string_if_password_is_present(delete_uuid)
                sqlstring = "insert into deleted_account (uuid) values ('" + encrypted_uuid + "')"
                cursor.execute(sqlstring)
            database_connection.commit()
            print("Account with UUID " + str(delete_uuid) + " deleted.")
        except Exception as e:
            print(colored("Error: " + str(e)))
        finally:
            database_connection.close()

    def get_deleted_account_uuids_decrypted(self) -> []:
        result_array = []
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            sqlstring = "select uuid from deleted_account"
            # sqlstring = "select uuid from " + deleted_account_table_name
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            for row in result:
                current_uuid = row[0]
                decrypted_uuid = self.decrypt_string_if_password_is_present(current_uuid)
                result_array.append(decrypted_uuid)
        except Exception as e:
            print("Error: " + str(e))
            return None
        finally:
            database_connection.close()
        return result_array

    def get_deleted_account_uuids_decrypted_from_merge_database(self, merge_database_filename: str) -> []:
        result_array = []
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            sqlstring = "attach '" + merge_database_filename + "' as merge_database"
            cursor.execute(sqlstring)
            # sqlstring = "select uuid from deleted_account"
            sqlstring = "select uuid from " + "merge_database.deleted_account"
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            for row in result:
                current_uuid = row[0]
                decrypted_uuid = self.decrypt_string_if_password_is_present(current_uuid)
                result_array.append(decrypted_uuid)
        except Exception as e:
            print("Error: " + str(e))
            return None
        finally:
            database_connection.close()
        return result_array

    def execute_sql(self, sql_command):
        count = 0
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            sqlresult = cursor.execute(sql_command)
            result = sqlresult.fetchall()
            i = 0
            for row in result:
                # print(str(row[i]))
                print(str(row))
                i += 1
        except Exception as e:
            raise
        finally:
            database_connection.close()

    def get_uuid_exists_in_deleted_accounts(self, account_uuid) -> bool:
        if account_uuid in self.get_deleted_account_uuids_decrypted():
            return True
        else:
            return False

    # def get_uuid_exists_in_deleted_accounts(self, account_uuid) -> bool:
    #     try:
    #         database_connection = sqlite3.connect(self.database_filename)
    #         cursor = database_connection.cursor()
    #         sqlstring = "select uuid from deleted_account"
    #         # print("exceuting: " + sqlstring)
    #         sqlresult = cursor.execute(sqlstring)
    #         result = sqlresult.fetchall()
    #         for row in result:
    #             current_uuid = row[0]
    #             decrypted_uuid = self.decrypt_string_if_password_is_present(current_uuid)
    #             print("account_uuid   -> " + account_uuid)
    #             print("decrypted_uuid -> " + decrypted_uuid)
    #             if decrypted_uuid == account_uuid:
    #                 return True
    #     except Exception as e:
    #         print("Error: " + str(e))
    #         return False
    #     finally:
    #         database_connection.close()
    #     return False

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

    def search_account_history(self, uuid_string: str):
        results_found = 0
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            # if self.show_invalidated_accounts:
            #     sqlstring = "select uuid, name, url, loginname, password, type, create_date, change_date, \
            #                 invalid_date from account "
            # else:
            sqlstring = "select account_uuid as uuid, name, url, loginname, password, type, create_date from account_history where " + \
                        "account_uuid = '" + str(uuid_string) + "' order by create_date"
            # sqlstring = sqlstring + ACCOUNTS_ORDER_BY_STATEMENT
            # print("exceuting: " + sqlstring)
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            # print("Searching for *" + colored(search_string, self.SEARCH_STRING_HIGHLIGHTING_COLOR) +
            #       "* in " + str(get_account_count(self.database_filename, self.show_invalidated_accounts)) + " accounts:")
            print()
            for row in result:
                account = Account(uuid=row[0],
                                  name=row[1],
                                  url=row[2],
                                  loginname=row[3],
                                  password=row[4],
                                  type=row[5],
                                  create_date=row[6]
                                  )
                decrypted_account = self.decrypt_account(account)
                # if search_string == "" or \
                #         search_string_matches_account(search_string, decrypted_account):
                results_found += 1
                # self.print_formatted_account_search_string_colored(decrypted_account, search_string)
                self.print_formatted_account(decrypted_account)
                print()
            print("Latest version of account:")
            self.search_account_by_uuid(uuid_string)
            print()
        except Exception as e:
            raise
        finally:
            database_connection.close()
        print("Found " + str(results_found) + " result(s) in account history.")

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
                  "* in " + str(
                get_account_count(self.database_filename, self.show_invalidated_accounts)) + " accounts:")
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

    def search_invalidated_accounts(self, search_string: str):
        results_found = 0
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            # if self.show_invalidated_accounts:
            #     sqlstring = "select uuid, name, url, loginname, password, type, create_date, change_date, \
            #                 invalid_date from account "
            # else:
            sqlstring = "select uuid, name, url, loginname, password, type, create_date, change_date, \
                         invalid_date from account where invalid = 1 "
            sqlstring = sqlstring + ACCOUNTS_ORDER_BY_STATEMENT
            # print("exceuting: " + sqlstring)
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            print("Searching for *" + colored(search_string, self.SEARCH_STRING_HIGHLIGHTING_COLOR) +
                  "* in " + str(get_account_count_invalid(self.database_filename)) + " invalidated accounts:")
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

    def search_accounts_by_type(self, type_search_string: str):
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
            print("Searching for *" + colored(type_search_string, self.SEARCH_STRING_HIGHLIGHTING_COLOR) +
                  "* in " + str(get_account_count(self.database_filename, self.show_invalidated_accounts)) +
                  " accounts:")
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
                if type_search_string == "" or \
                        type_search_string.lower() in account.type.lower():
                    results_found += 1
                    self.print_formatted_account_search_string_colored(decrypted_account, type_search_string)
                    print()
        except Exception as e:
            raise
        finally:
            database_connection.close()
        print("Found " + str(results_found) + " result(s).")

    def get_accounts_decrypted(self, search_string: str) -> []:
        # results_found = 0
        account_array = []
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
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            # print("Searching for *" + colored(search_string, self.SEARCH_STRING_HIGHLIGHTING_COLOR) +
            # "* in " + str(get_account_count(self.database_filename)) + " accounts:")
            # print()
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
                    # results_found += 1
                    # self.print_formatted_account_search_string_colored(decrypted_account, search_string)
                    account_array.append(decrypted_account)
        except Exception as e:
            raise
        finally:
            database_connection.close()
        # print("Found " + str(results_found) + " result(s).")
        return account_array

    def get_accounts_decrypted_from_invalid_accounts(self, search_string: str) -> []:
        # results_found = 0
        account_array = []
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            # if self.show_invalidated_accounts:
            #     sqlstring = "select uuid, name, url, loginname, password, type, create_date, change_date, \
            #                 invalid_date from account "
            # else:
            sqlstring = "select uuid, name, url, loginname, password, type, create_date, change_date, \
                         invalid_date from account where invalid = 1 "
            sqlstring = sqlstring + ACCOUNTS_ORDER_BY_STATEMENT
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            # print("Searching for *" + colored(search_string, self.SEARCH_STRING_HIGHLIGHTING_COLOR) +
            # "* in " + str(get_account_count(self.database_filename)) + " accounts:")
            # print()
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
                    # results_found += 1
                    # self.print_formatted_account_search_string_colored(decrypted_account, search_string)
                    account_array.append(decrypted_account)
        except Exception as e:
            raise
        finally:
            database_connection.close()
        # print("Found " + str(results_found) + " result(s).")
        return account_array

    def get_accounts_decrypted_search_types(self, type_search_string: str) -> []:
        # results_found = 0
        account_array = []
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
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            # print("Searching for *" + colored(search_string, self.SEARCH_STRING_HIGHLIGHTING_COLOR) +
            # "* in " + str(get_account_count(self.database_filename)) + " accounts:")
            # print()
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
                if type_search_string == "" or \
                        type_search_string.lower() in account.type.lower():
                    # results_found += 1
                    # self.print_formatted_account_search_string_colored(decrypted_account, search_string)
                    account_array.append(decrypted_account)
        except Exception as e:
            raise
        finally:
            database_connection.close()
        # print("Found " + str(results_found) + " result(s).")
        return account_array

    def search_account_by_uuid(self, search_uuid) -> bool:
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            if search_uuid is None or search_uuid == "":
                return False
            sqlstring = "select uuid, name, url, loginname, password, type, create_date, change_date, invalid_date from \
                         account where uuid = '" + str(search_uuid) + "'"
            sqlresult = cursor.execute(sqlstring)
            row = sqlresult.fetchone()
            if row is None:
                print("UUID " + search_uuid + " not found.")
                return False
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
            return True
        except Exception as e:
            raise
        finally:
            database_connection.close()

    def get_account_exists(self, account_uuid) -> bool:
        account = self.get_account_by_uuid_and_decrypt(account_uuid)
        if account is not None:
            return True
        else:
            return False

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
                account = Account(uuid=search_uuid,
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

    # Set account by uuid = edit account. If account_history is enabled the old version
    # of the account will be saved in the table account_history
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
            self.set_database_pragmas_to_secure_mode(database_connection, cursor)
            self.print_current_secure_delete_mode(database_connection, cursor)

            # 1. First backup old version of the account
            if get_attribute_value_from_configuration_table(self.database_filename,
                                                            CONFIGURATION_TABLE_ATTRIBUTE_TRACK_ACCOUNT_HISTORY) \
                    == "True":
                # cursor = database_connection.cursor()
                account_history_uuid = uuid.uuid4()
                sqlstring = "insert into account_history (uuid, account_uuid, name, url, loginname, password, type) " + \
                            " select '" + str(account_history_uuid) + \
                            "' as uuid, uuid as account_uuid, name, url, loginname, password, type " + \
                            " from account where uuid = '" + str(account_uuid) + "'"
                cursor.execute(sqlstring)
                # database_connection.commit()
            # 2. Then change/set existing account to new values
            # cursor = database_connection.cursor()
            # self.set_database_pragmas_to_secure_mode(database_connection, cursor)
            # self.print_current_secure_delete_mode(database_connection, cursor)
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
        account.uuid = color_search_string(account.uuid, search_string, self.SEARCH_STRING_HIGHLIGHTING_COLOR)
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
        print("UUID        : " + str(account.uuid))
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
            # Iterate through all the accounts and the account_history, decrypt every entry with the old pw,
            # encrypt it with the new one and write it all back.
            account_count = get_account_count(self.database_filename)
            account_history_count = get_account_history_count(self.database_filename)
            print("Re-encrypting " + str(account_count) + " accounts...")
            print("Re-encrypting " + str(account_history_count) + " account history entries...")
            bar = progressbar.ProgressBar(max_value=(account_count + account_history_count)).start()
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

            sqlstring = SQL_SELECT_ALL_ACCOUNT_HISTORY
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            #results_found = 0
            for row in result:
                results_found += 1
                # get current account_history data (enrypted)
                current_uuid = row[0]
                current_account_uuid = row[1]
                current_name = row[2]
                current_url = row[3]
                current_loginname = row[4]
                current_password = row[5]
                current_type = row[6]
                # current_create_date = row[7]
                # print(row)
                # re-encrypt that shit
                new_current_name = self.decrypt_and_encrypt_with_new_password(current_name, new_password)
                new_current_url = self.decrypt_and_encrypt_with_new_password(current_url, new_password)
                new_current_loginname = self.decrypt_and_encrypt_with_new_password(current_loginname, new_password)
                new_current_password = self.decrypt_and_encrypt_with_new_password(current_password, new_password)
                new_current_type = self.decrypt_and_encrypt_with_new_password(current_type, new_password)
                # and push it back into the db
                update_sql_string = "update account_history set name=?, " + \
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
        # set encryption engine to new password
        # store password as byte[]
        if new_password != "":
            self.database_password = new_password.encode("UTF-8")
            self.fernet = create_fernet(self.salt, self.database_password, self.iteration_count)
        else:
            self.database_password = ""
            self.fernet = None
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
        _fernet = create_fernet(self.salt, password.encode("UTF-8"), self.iteration_count)
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
            # _fernet = self.create_fernet(self.DEFAULT_SALT, _database_password.encode("UTF-8"))
            _fernet = create_fernet(self.salt, _database_password, self.iteration_count)
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
            print("New account added: [UUID " + str(account.uuid) + "]")
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

    def set_database_pragmas_to_secure_mode(self, database_connection, cursor):
        logging.debug("Setting PRAGMA journal_mode = WAL for database.")
        cursor.execute("PRAGMA journal_mode = WAL")
        database_connection.commit()
        logging.debug("Setting PRAGMA auto_vacuum = FULL for database.")
        cursor.execute("PRAGMA auto_vacuum = FULL")
        database_connection.commit()
        # Set secure_delete_mode
        logging.debug("Setting PRAGMA secure_delete = True for database.")
        cursor.execute("PRAGMA secure_delete = True")
        database_connection.commit()

    def create_and_initialize_database(self):
        try:
            database_connection = None
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            self.set_database_pragmas_to_secure_mode(database_connection, cursor)
            # Set undo mode
            # logging.debug("Setting PRAGMA journal_mode = WAL for database.")
            # cursor.execute("PRAGMA journal_mode = WAL")
            # database_connection.commit()
            # logging.debug("Setting PRAGMA auto_vacuum = FULL for database.")
            # cursor.execute("PRAGMA auto_vacuum = FULL")
            # database_connection.commit()
            # # Set secure_delete_mode
            # logging.debug("Setting PRAGMA secure_delete = True for database.")
            # cursor.execute("PRAGMA secure_delete = True")
            # database_connection.commit()
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
            self.set_database_pragmas_to_secure_mode(database_connection, cursor)
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

    def get_database_password_as_string(self) -> str:
        if self.database_password == "":
            return ""
        return bytes(self.database_password).decode("UTF-8")

    # returns -1 in error case, 0 when no error and no changes where made,
    # 1 when changes where made locally and 2 when changes where made in remote db
    # and 3 when changes where made locally and remote
    def merge_database(self, merge_database_filename: str) -> int:
        if not os.path.exists(merge_database_filename):
            print("Error: merge database does not exist: '" + merge_database_filename + "'")
            return -1
        print("Using merge database: " + merge_database_filename + " " + get_database_name(merge_database_filename))
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

            print("Updating merge database schema...")
            sqlstring = SQL_CREATE_MERGE_DATABASE_SCHEMA
            cursor.executescript(sqlstring)
            database_connection.commit()

            #
            # step #0.1 do the complicated deleted accounts logic here:
            #
            deleted_uuids_in_local_db = self.get_deleted_account_uuids_decrypted()
            # print("deleted_in_local: " + str(deleted_uuids_in_local_db))
            deleted_uuids_in_remote_db = self.get_deleted_account_uuids_decrypted_from_merge_database(
                merge_database_filename)
            # print("deleted_in_remote: " + str(deleted_uuids_in_remote_db))
            deleted_uuids_in_local_db_note_in_remote = []
            deleted_uuids_in_remote_db_not_in_local = []
            if deleted_uuids_in_local_db != deleted_uuids_in_remote_db:
                deleted_uuids_in_local_db_note_in_remote = \
                    set(deleted_uuids_in_local_db) - set(deleted_uuids_in_remote_db)
                deleted_uuids_in_remote_db_not_in_local = \
                    set(deleted_uuids_in_remote_db) - set(deleted_uuids_in_local_db)
            print(colored("Step #0: Synchronizing deleted accounts in local and remote database...", "green"))
            if len(deleted_uuids_in_remote_db_not_in_local) > 0:
                print("Found " + colored(str(len(deleted_uuids_in_remote_db_not_in_local)), "red") +
                      " account(s) in remote db which are not in local deleted_account table...")
                # print("Deleting " + colored(str(len(deleted_uuids_in_remote_db_not_in_local)), "red") +
                #       " account(s) in local db which have been deleted in remote db...")
            for delete_uuid in deleted_uuids_in_remote_db_not_in_local:
                print("Searching account with UUID " + delete_uuid + " in local database:")
                account_found = self.search_account_by_uuid(delete_uuid)
                if account_found:
                    answer = input("Delete account in local database with UUID: " + delete_uuid + " ([y]/n) : ")
                    if answer != "y" and answer != "":
                        print("Canceled.")
                        continue
                    cursor.execute("delete from account where uuid = '" + delete_uuid + "'")
                    print("Account deleted.")
                cursor.execute("insert into deleted_account (uuid) values ('" +
                               self.encrypt_string_if_password_is_present(delete_uuid) + "')")
                print("UUID " + delete_uuid + " added to local deleted_account table..")
            if len(deleted_uuids_in_local_db_note_in_remote) > 0:
                print("Deleting " + colored(str(len(deleted_uuids_in_local_db_note_in_remote)), "red") +
                      " account(s) in remote db which have been deleted in local db...")
            for delete_uuid in deleted_uuids_in_local_db_note_in_remote:
                cursor.execute("delete from merge_database.account where uuid = '" + delete_uuid + "'")
                cursor.execute("insert into merge_database.deleted_account (uuid) values ('" +
                               self.encrypt_string_if_password_is_present(delete_uuid) + "')")
            print(str(len(deleted_uuids_in_local_db_note_in_remote)) + " Account(s) deleted.")
            database_connection.commit()

            #
            # Step #0.2 do the math
            #
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

            sqlresult = cursor.execute(SQL_MERGE_COUNT_LOCAL_MISSING_HISTORY_UUIDS_THAT_EXIST_IN_REMOTE_DATABASE)
            result = sqlresult.fetchone()
            count_history_uuids_in_remote_that_do_not_exist_in_local = result[0]
            sqlresult = cursor.execute(SQL_MERGE_COUNT_REMOTE_MISSING_HISTORY_UUIDS_THAT_EXIST_IN_LOCAL_DATABASE)
            result = sqlresult.fetchone()
            count_history_uuids_in_local_that_do_not_exist_in_remote = result[0]


            #
            # Step #1 Sync new accounts from remote merge database into main database
            #
            print(colored("Step #1: Analyzing Origin Database - " + self.database_filename
                          + " " + get_database_name(self.database_filename), "green"))
            # print("Dropping update_date trigger (origin database)...")
            cursor.execute(SQL_MERGE_DROP_LOCAL_ACCOUNT_CHANGE_DATE_TRIGGER)
            print("Updating " + colored(str(count_uuids_in_remote_with_newer_update_date_than_in_local), "red")
                  + " local account(s) that have newer change dates in the remote database...")
            cursor.execute(SQL_MERGE_DELETE_ACCOUNTS_IN_ORIGIN_THAT_EXIST_IN_REMOTE_WITH_NEWER_CHANGE_DATE)
            print("Fetching " + colored(str(count_uuids_in_remote_that_do_not_exist_in_local), "red")
                  + " new account(s) from the remote database into the origin database...")
            cursor.execute(SQL_MERGE_INSERT_MISSING_UUIDS_FROM_REMOTE_INTO_ORIGIN_DATABASE)

            print("Fetching " + colored(str(count_history_uuids_in_remote_that_do_not_exist_in_local), "red")
                  + " new account history entries from the remote database into the origin database...")
            cursor.execute(SQL_MERGE_INSERT_MISSING_HISTORY_UUIDS_FROM_REMOTE_INTO_ORIGIN_DATABASE)

            # print("Re-Creating update_date trigger (origin database)...")
            cursor.execute(SQL_MERGE_CREATE_LOCAL_ACCOUNT_CHANGE_DATE_TRIGGER)
            print("Origin database is now up to date (" +
                  colored(str(count_uuids_in_remote_with_newer_update_date_than_in_local +
                              count_uuids_in_remote_that_do_not_exist_in_local +
                              len(deleted_uuids_in_remote_db_not_in_local)), "red") + " changes have been done)")
            # remember that there where changes in local db for return code:
            return_code = 0
            if count_uuids_in_remote_with_newer_update_date_than_in_local + \
                    count_uuids_in_remote_that_do_not_exist_in_local > 0:
                return_code = 1
            database_connection.commit()
            #
            # Step #2 Sync new accounts from main database into remote database
            #
            print(colored("Step #2: Analyzing Remote Database - " + merge_database_filename
                          + " " + get_database_name(merge_database_filename), "green"))
            # print("Dropping update_date trigger (remote database)...")
            cursor.execute(SQL_MERGE_DROP_REMOTE_ACCOUNT_CHANGE_DATE_TRIGGER)
            print("Updating " + colored(str(count_uuids_in_local_with_newer_update_date_than_in_remote), "red")
                  + " remote account(s) that have newer change dates in the origin database...")
            cursor.execute(SQL_MERGE_DELETE_ACCOUNTS_IN_REMOTE_THAT_EXIST_IN_ORIGIN_WITH_NEWER_CHANGE_DATE)
            print("Fetching " + colored(str(count_uuids_in_local_that_do_not_exist_in_remote), "red")
                  + " new account(s) from the origin database into the remote database...")
            cursor.execute(SQL_MERGE_INSERT_MISSING_UUIDS_FROM_ORIGIN_INTO_REMOTE_DATABASE)

            print("Fetching " + colored(str(count_history_uuids_in_local_that_do_not_exist_in_remote), "red")
                  + " new account history entries from the origin database into the remote database...")
            cursor.execute(SQL_MERGE_INSERT_MISSING_HISTORY_UUIDS_FROM_ORIGIN_INTO_REMOTE_DATABASE)

            # print("Re-Creating update_date trigger (remote database)...")
            cursor.execute(SQL_MERGE_CREATE_REMOTE_ACCOUNT_CHANGE_DATE_TRIGGER)
            # Remember date of current merge action in origin and remote database
            cursor.execute("update configuration set value = datetime(CURRENT_TIMESTAMP, 'localtime')" +
                           " where attribute = ?", [CONFIGURATION_TABLE_ATTRIBUTE_LAST_MERGE_DATE])
            cursor.execute("update merge_database.configuration set value = datetime(CURRENT_TIMESTAMP, 'localtime')" +
                           " where attribute = ?", [CONFIGURATION_TABLE_ATTRIBUTE_LAST_MERGE_DATE])
            print("Remote database is now up to date (" +
                  colored(str(count_uuids_in_local_with_newer_update_date_than_in_remote +
                              count_uuids_in_local_that_do_not_exist_in_remote +
                              len(deleted_uuids_in_local_db_note_in_remote)), "red") + " changes have been done)")
            # Finally commit it
            database_connection.commit()
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
