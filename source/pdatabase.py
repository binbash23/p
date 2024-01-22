#
# 20221103 jens heine <binbash@gmx.net>
#
# Copyright
#
import base64
import binascii
import datetime
import logging
import os
import os.path
import sqlite3
import time
import uuid
from getpass import getpass
from re import IGNORECASE
from re import finditer

import colorama
import progressbar
from cryptography.exceptions import InvalidSignature
from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from termcolor import colored

import print_slow
from connector_interface import ConnectorInterface

colorama.init()

#
# GLOBAL VARIABLES
#
SQL_SELECT_MERGE_HISTORY_WITH_UUID = """
select
mh.uuid,
mh.connector_type,
mh.connector,
mh.execution_date,
mh.database_name_local as 'DB local',
mh.database_uuid_local as 'UUID local',
mh.database_name_remote as 'DB remote',
mh.database_uuid_remote as 'UUID remote',
mh.return_code as 'Result'
FROM
merge_history mh
where
mh.uuid = ?
order by 
mh.execution_date 
"""
SQL_SELECT_MERGE_HISTORY = """
select
mh.uuid,
mh.connector_type,
mh.connector,
mh.execution_date,
mh.database_name_local as 'DB local',
mh.database_uuid_local as 'UUID local',
mh.database_name_remote as 'DB remote',
mh.database_uuid_remote as 'UUID remote',
mh.return_code as 'Result'
FROM
merge_history mh
order by 
mh.execution_date 
"""
SQL_SELECT_MERGE_HISTORY_DETAIL_WITH_UUID = """
select
execution_date,
text
FROM
merge_history_detail
where
merge_history_uuid = ?
order by
execution_date
"""
SQL_SELECT_MERGE_HISTORY_LATEST_UUID = """
SELECT
uuid
FROM
merge_history
WHERE
execution_date = (select max(execution_date) from merge_history)
"""
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
insert into main.account (uuid, name, url, loginname, password, type, create_date, change_date, invalid_date, connector_type)
select 
uuid, 
name,
url, 
loginname, 
password, 
type, 
create_date, 
change_date, 
invalid_date,
connector_type
from 
merge_database.account 
where 
uuid not in (select uuid from main.account)
"""
SQL_MERGE_INSERT_MISSING_HISTORY_UUIDS_FROM_REMOTE_INTO_ORIGIN_DATABASE = """
insert into main.account_history (uuid, account_uuid, name, url, loginname, password, type, create_date, connector_type)
select 
uuid,
account_uuid, 
name,
url, 
loginname, 
password, 
type, 
create_date,
connector_type
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
insert into merge_database.account (uuid, name, url, loginname, password, type, create_date, change_date, invalid_date, connector_type)
select 
uuid, 
name, 
url,
loginname, 
password, 
type, 
create_date, 
change_date, 
invalid_date ,
connector_type
from 
main.account 
where 
uuid not in (select uuid from merge_database.account)    
"""
SQL_MERGE_INSERT_MISSING_HISTORY_UUIDS_FROM_ORIGIN_INTO_REMOTE_DATABASE = """
insert into merge_database.account_history (uuid, account_uuid, name, url, loginname, password, type, create_date, connector_type)
select 
uuid, 
account_uuid,
name, 
url,
loginname, 
password, 
type, 
create_date,
connector_type
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
    "connector_type"	TEXT,
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
    "connector_type"	TEXT,
    "create_date"	datetime not null default (datetime(CURRENT_TIMESTAMP, 'localtime'))
);
-- table for command history entries
CREATE TABLE if not exists "shell_history" (
    "uuid" TEXT NOT NULL UNIQUE,
	"create_date"	datetime not null default (datetime(CURRENT_TIMESTAMP, 'localtime')),
    "execution_date" TEXT NOT NULL,
	"user_input" TEXT NOT NULL
);
CREATE TABLE if not exists "alias" (
    "alias" TEXT NOT NULL UNIQUE,
	"command" TEXT
);
CREATE TABLE if not exists "merge_history" (
    "uuid" TEXT NOT NULL UNIQUE,
    "create_date"	datetime not null default (datetime(CURRENT_TIMESTAMP, 'localtime')),
    "execution_date" TEXT,
    "database_name_local" TEXT,
    "database_uuid_local" TEXT NOT NULL,
    "database_name_remote" TEXT,
    "database_uuid_remote" TEXT NOT NULL,
    "connector" TEXT,
    "connector_type" TEXT,
    "return_code" TEXT
);
CREATE TABLE if not exists "merge_history_detail" (
    "merge_history_uuid" TEXT NOT NULL,
    "create_date"	datetime not null default (datetime(CURRENT_TIMESTAMP, 'localtime')),
    "execution_date" TEXT,
    "text" TEXT NOT NULL
);
insert or replace into configuration (attribute, value) values ('SCHEMA_VERSION', '8');   
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
    "connector_type"	TEXT,
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
    "connector_type"	TEXT,
    "create_date"	datetime not null default (datetime(CURRENT_TIMESTAMP, 'localtime'))
);	
-- table for command history entries
CREATE TABLE if not exists merge_database.shell_history (
    "uuid" TEXT NOT NULL UNIQUE,
	"create_date"	datetime not null default (datetime(CURRENT_TIMESTAMP, 'localtime')),
    "execution_date" TEXT NOT NULL,
	"user_input" TEXT NOT NULL
);
CREATE TABLE if not exists merge_database.alias (
    "alias" TEXT NOT NULL UNIQUE,
	"command" TEXT
);
CREATE TABLE if not exists merge_database.merge_history (
    "uuid" TEXT NOT NULL UNIQUE,
    "create_date"	datetime not null default (datetime(CURRENT_TIMESTAMP, 'localtime')),
    "execution_date" TEXT,
    "database_name_local" TEXT,
    "database_uuid_local" TEXT NOT NULL,
    "database_name_remote" TEXT,
    "database_uuid_remote" TEXT NOT NULL,
    "connector" TEXT,
    "connector_type" TEXT,
    "return_code" TEXT
);
CREATE TABLE if not exists merge_database.merge_history_detail (
    "merge_history_uuid" TEXT NOT NULL,
    "create_date"	datetime not null default (datetime(CURRENT_TIMESTAMP, 'localtime')),
    "execution_date" TEXT,
    "text" TEXT NOT NULL
);
insert or replace into configuration (attribute, value) values ('SCHEMA_VERSION', '8'); 
"""
ACCOUNTS_ORDER_BY_STATEMENT = "order by change_date, name"
SQL_SELECT_ALL_ACCOUNTS = """
    select 
        uuid, 
        name,
        url,
        loginname,
        password,
        type,
        connector_type
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
        type,
        connector_type
    from 
        account_history
"""
SQL_SELECT_COUNT_ALL_FROM_ACCOUNT = "select count(*) from account"
SQL_SELECT_COUNT_ALL_FROM_ACCOUNT_HISTORY = "select count(*) from account_history"
SQL_DELETE_ALL_FROM_ACCOUNT_HISTORY = "delete from account_history"
SQL_SELECT_COUNT_ALL_FROM_DELETED_ACCOUNT = "select count(*) from deleted_account"
SQL_SELECT_COUNT_ALL_FROM_SHELL_HISTORY = "select count(*) from shell_history"
SQL_SELECT_COUNT_ALL_FROM_ALIAS = "select count(*) from alias"
SQL_SELECT_ALL_FROM_DELETED_ACCOUNT = "select uuid, create_date from deleted_account"
SQL_SELECT_ALL_FROM_SHELL_HISTORY = "select uuid, create_date, execution_date, user_input from shell_history"
SQL_SELECT_ALL_FROM_ALIAS = "select alias, command from alias"
SQL_DELETE_ALL_FROM_DELETED_ACCOUNT = "delete from deleted_account"
SQL_SELECT_COUNT_ALL_VALID_FROM_ACCOUNT = "select count(*) from account where invalid = 0"
SQL_SELECT_COUNT_ALL_INVALID_FROM_ACCOUNT = "select count(*) from account where invalid = 1"
CONFIGURATION_TABLE_ATTRIBUTE_PASSWORD_TEST = "DATABASE_PASSWORD_TEST"
CONFIGURATION_TABLE_PASSWORD_TEST_VALUE_WHEN_NOT_ENCRYPTED = "DATABASE IS NOT ENCRYPTED"
CONFIGURATION_TABLE_ATTRIBUTE_UUID = "DATABASE_UUID"
CONFIGURATION_TABLE_ATTRIBUTE_LAST_MERGE_DATABASE = "LAST_MERGE_DATABASE_FILENAME"
CONFIGURATION_TABLE_ATTRIBUTE_LAST_MERGE_DATE = "LAST_MERGE_DATE"
CONFIGURATION_TABLE_ATTRIBUTE_SCHEMA_VERSION = "SCHEMA_VERSION"
# CONFIGURATION_TABLE_ATTRIBUTE_DROPBOX_ACCESS_TOKEN_ACCOUNT_UUID = "DROPBOX_ACCESS_TOKEN_ACCOUNT_UUID"
# CONFIGURATION_TABLE_ATTRIBUTE_DROPBOX_APPLICATION_ACCOUNT_UUID = "DROPBOX_APPLICATION_ACCOUNT_UUID"
CONFIGURATION_TABLE_ATTRIBUTE_CONNECTOR_DEFAULT_DROPBOX_ACCOUNT_UUID = "CONNECTOR_DEFAULT_DROPBOX_ACCOUNT_UUID"
CONFIGURATION_TABLE_ATTRIBUTE_CONNECTOR_DEFAULT_WEBDAV_ACCOUNT_UUID = "CONNECTOR_DEFAULT_WEBDAV_ACCOUNT_UUID"
CONFIGURATION_TABLE_ATTRIBUTE_CONNECTOR_DEFAULT_SSH_ACCOUNT_UUID = "CONNECTOR_DEFAULT_SSH_ACCOUNT_UUID"
CONFIGURATION_TABLE_ATTRIBUTE_CONNECTOR_DEFAULT_FILE_ACCOUNT_UUID = "CONNECTOR_DEFAULT_FILE_ACCOUNT_UUID"
CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_MAX_IDLE_TIMEOUT_MIN = "PSHELL_MAX_IDLE_TIMEOUT_MIN"
CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_MAX_HISTORY_SIZE = "PSHELL_MAX_HISTORY_SIZE"
CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHADOW_PASSWORDS = "PSHELL_SHADOW_PASSWORDS"
CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHOW_STATUS_ON_STARTUP = "SHOW_STATUS_ON_STARTUP"
CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_PRINT_SLOW_ENABLED = "PSHELL_PRINT_SLOW_ENABLED"
CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHOW_INVALIDATED_ACCOUNTS = "PSHELL_SHOW_INVALIDATED_ACCOUNTS"
CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHOW_ACCOUNT_DETAILS = "PSHELL_SHOW_ACCOUNT_DETAILS"
CONFIGURATION_TABLE_ATTRIBUTE_DATABASE_NAME = "DATABASE_NAME"
CONFIGURATION_TABLE_ATTRIBUTE_PSHELL_SHOW_UNMERGED_CHANGES_WARNING = "PSHELL_SHOW_UNMERGED_CHANGES_WARNING"
CONFIGURATION_TABLE_ATTRIBUTE_TRACK_ACCOUNT_HISTORY = "TRACK_ACCOUNT_HISTORY"
# CONFIGURATION_TABLE_ATTRIBUTE_DEFAULT_MERGE_TARGET_FILE = "DEFAULT_MERGE_TARGET_FILE"
TEMP_MERGE_DATABASE_FILENAME = "temp_merge_database.db"
DEFAULT_SALT = b"98uAS (H CQCH AISDUHU/ZASD/7zhdw7e-;568!"  # The salt for the encryption is static. This might become a problem?!
DEFAULT_ITERATION_COUNT = 500000


class ShellHistoryEntry:
    execution_date = ""
    user_input = ""

    def __init__(self, execution_date=None, user_input=""):
        if execution_date is None:
            self.execution_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            self.execution_date = execution_date
        self.user_input = user_input


class Account:
    uuid = ""
    name = ""
    url = ""
    loginname = ""
    password = ""
    type = ""
    connector_type = ""
    create_date = ""
    change_date = ""
    invalid_date = ""

    def __init__(self, uuid="", name="", url="", loginname="", password="", type="", connector_type="",
                 create_date="", change_date="", invalid_date=""):
        self.uuid = uuid
        self.name = name
        self.url = url
        self.loginname = loginname
        self.password = password
        self.type = type
        self.connector_type = connector_type
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
            ", Connectortype=" + self.connector_type + \
            ", Createdate=" + self.create_date + \
            ", Changedate=" + self.change_date + \
            ", Invalidate=" + self.invalid_date


def accounts_are_equal(account1: Account, account2: Account) -> bool:
    if account1 is None or account2 is None:
        return False
    if (account1.uuid == account2.uuid) and \
            (account1.name == account2.name) and \
            (account1.url == account2.url) and \
            (account1.loginname == account2.loginname) and \
            (account1.password == account2.password) and \
            (account1.connector_type == account2.connector_type) and \
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
            search_string in account.connector_type.lower() or \
            search_string in account.type.lower():
        return True
    return False


def set_attribute_value_in_configuration_table(_database_filename, _attribute_name, _value):
    if _database_filename is None or _database_filename == "":
        raise ValueError("Database name must not be empty!")
    if _attribute_name is None or _attribute_name == "":
        raise ValueError("Attribute name must not be empty!")
    database_connection = None
    try:
        database_connection = sqlite3.connect(_database_filename)
        cursor = database_connection.cursor()
        # First check if the attribute exists and create it if not
        # print("-> hey")
        if not is_attribute_in_configuration_table(_database_filename, _attribute_name):
            # print("-> inserting")
            sqlstring = "insert into configuration (attribute, value) values (?, ?)"
            cursor.execute(sqlstring, [_attribute_name, _value])
            database_connection.commit()
            return
        sqlstring = "update configuration set value=? where attribute=?"
        cursor.execute(sqlstring, [_value, _attribute_name])
        database_connection.commit()
    except Exception:
        raise
    finally:
        database_connection.close()


def is_attribute_in_configuration_table(_database_filename, _attribute_name):
    if _database_filename is None or _database_filename == "":
        raise ValueError("Database name must not be empty!")
    if _attribute_name is None or _attribute_name == "":
        raise ValueError("Attribute name must not be empty!")
    database_connection = None
    try:
        database_connection = sqlite3.connect(_database_filename)
        cursor = database_connection.cursor()
        sqlstring = "select value from configuration where attribute=?"
        sqlresult = cursor.execute(sqlstring, [_attribute_name])
        value = sqlresult.fetchone()
        if value is None or len(value) == 0:
            return False
    except Exception:
        raise
    finally:
        database_connection.close()
    return True


def get_attribute_value_from_configuration_table(_database_filename, _attribute_name):
    if _database_filename is None or _database_filename == "":
        raise ValueError("Database name must not be empty!")
    if _attribute_name is None or _attribute_name == "":
        raise ValueError("Attribute name must not be empty!")
    database_connection = None
    try:
        database_connection = sqlite3.connect(_database_filename)
        cursor = database_connection.cursor()
        sqlstring = "select value from configuration where attribute=?"
        sqlresult = cursor.execute(sqlstring, [_attribute_name])
        value = sqlresult.fetchone()
        if value is None:
            return ""
        value = value[0]
    except Exception:
        raise
    finally:
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


def get_database_uuid(database_filename) -> str:
    value = get_attribute_value_from_configuration_table(database_filename, CONFIGURATION_TABLE_ATTRIBUTE_UUID)
    return value


def get_database_name(database_filename) -> str:
    value = get_attribute_value_from_configuration_table(database_filename, CONFIGURATION_TABLE_ATTRIBUTE_DATABASE_NAME)
    return value


def set_database_name(database_filename, new_database_name: str):
    set_attribute_value_in_configuration_table(database_filename, CONFIGURATION_TABLE_ATTRIBUTE_DATABASE_NAME,
                                               new_database_name)


# def print_merge_history(database_filename):
#     try:
#         database_connection = sqlite3.connect(database_filename)
#         cursor = database_connection.cursor()
#         sqlstring = "select * from merge_history"
#         sqlresult = cursor.execute(sqlstring)
#         result = sqlresult.fetchall()
#         for row in result:
#             print(row)
#     except Exception as e:
#         print("Error getting merge history entries from database.")
#     finally:
#         database_connection.close()

def print_merge_history(database_filename, merge_history_uuid=None) -> int:
    database_connection = None
    try:
        database_connection = sqlite3.connect(database_filename)
        cursor = database_connection.cursor()
        if merge_history_uuid is None:
            sqlresult = cursor.execute(SQL_SELECT_MERGE_HISTORY)
        else:
            sqlresult = cursor.execute(SQL_SELECT_MERGE_HISTORY_WITH_UUID, [merge_history_uuid])
        result = sqlresult.fetchall()
        if len(result) == 0:
            print("No merge history found.")
            return len(result)
        for row in result:
            print()
            print("Merge UUID      : " + str(row[0]))
            print("Date            : " + str(row[3]))
            print("Connection type : " + str(row[1]))
            print("Connector       : " + str(row[2]))
            print("Local DB Name   : " + str(row[4]))
            print("Local DB UUID   : " + str(row[5]))
            print("Remote DB Name  : " + str(row[6]))
            print("Remote DB UUID  : " + str(row[7]))
            print("Result          : " + str(row[8]))
        return len(result)
    except Exception as e:
        print("Error getting merge history entries from database: " + str(e))
    finally:
        database_connection.close()


def get_latest_merge_history_uuid(database_filename: str) -> str:
    database_connection = None
    try:
        database_connection = sqlite3.connect(database_filename)
        cursor = database_connection.cursor()
        sqlresult = cursor.execute(SQL_SELECT_MERGE_HISTORY_LATEST_UUID)
        latest_uuid = sqlresult.fetchone()
        return latest_uuid[0]
    except Exception as e:
        print("Error selecting latest uuid from merge_history: " + str(e))
    finally:
        database_connection.close()


def print_latest_merge_history_detail(database_filename):
    latest_merge_uuid = get_latest_merge_history_uuid(database_filename)
    if latest_merge_uuid:
        print_merge_history_detail(database_filename, latest_merge_uuid)
    else:
        print("No merge history found.")


def print_merge_history_detail(database_filename, merge_history_uuid):
    results = print_merge_history(database_filename, merge_history_uuid)
    if results == 0:
        return
    print()
    database_connection = None
    try:
        database_connection = sqlite3.connect(database_filename)
        cursor = database_connection.cursor()
        sqlresult = cursor.execute(SQL_SELECT_MERGE_HISTORY_DETAIL_WITH_UUID, [merge_history_uuid])
        result = sqlresult.fetchall()
        for row in result:
            print(str(row[0]) + " - " + str(row[1]))
        print()
    except Exception as e:
        print("Error getting merge history detail entries from database: " + str(e))
    finally:
        database_connection.close()


def append_merge_history(merge_history_uuid: str,
                         database_filename,
                         database_uuid_local: str,
                         database_uuid_remote: str,
                         database_name_local: str = "",
                         database_name_remote: str = "",
                         connector: str = "",
                         connector_type: str = "",
                         return_code: str = ""):
    database_connection = None
    try:
        if return_code == "0":
            return_code = "0 - No changes"
        elif return_code == "1":
            return_code = "1 - Changes in local database"
        elif return_code == "2":
            return_code = "2 - Changes in remote database"
        elif return_code == "3":
            return_code = "3 - Changes in local and remote database"
        database_connection = sqlite3.connect(database_filename)
        cursor = database_connection.cursor()
        execution_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sqlstring = ("insert into merge_history (uuid, execution_date, database_name_local, database_uuid_local, " +
                     "database_name_remote, database_uuid_remote, connector, connector_type, return_code) " +
                     "values (?, ?, ?, ?, ?, ?, ?, ?, ?)")
        cursor.execute(sqlstring, (merge_history_uuid, execution_date, database_name_local, database_uuid_local,
                                   database_name_remote, database_uuid_remote, connector, connector_type, return_code))

        database_connection.commit()
    except Exception as e:
        print("Error writing merge history entry to database: " + str(e))
    finally:
        database_connection.close()


def append_merge_history_detail(database_filename: str, merge_history_uuid: str, text: str):
    database_connection = None
    try:
        database_connection = sqlite3.connect(database_filename)
        cursor = database_connection.cursor()

        # print("PRAGMA lock_status: " + str(cursor.execute("PRAGMA lock_status").fetchall()[0][0]))
        # print("Writing: " + text)
        # print("PRAGMA busy_timeout: " + str(cursor.execute("PRAGMA busy_timeout=10000").fetchall()[0][0]))

        execution_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:%f")
        sqlstring = ("insert into merge_history_detail (merge_history_uuid, execution_date, text) " +
                     "values (?, ?, ?)")
        cursor.execute(sqlstring, (merge_history_uuid, execution_date, text))
        # print("---> executed: " + sqlstring + merge_history_uuid + execution_date + text)
        database_connection.commit()
    except Exception as e:
        print("Error writing merge history detail entry to database:\n" + text + "\n" + str(e))
    finally:
        database_connection.close()


def get_database_identification_string(database_filename) -> str:
    id_string = ""
    database_name = get_database_name(database_filename)
    if database_name is not None and database_name != "":
        id_string = database_name
    id_string = id_string + "/" + get_database_uuid(database_filename)
    return id_string


def get_account_count_valid(database_filename):
    count = 0
    database_connection = None
    try:
        database_connection = sqlite3.connect(database_filename)
        cursor = database_connection.cursor()
        sqlstring = SQL_SELECT_COUNT_ALL_VALID_FROM_ACCOUNT
        sqlresult = cursor.execute(sqlstring)
        result = sqlresult.fetchone()
        if result is None:
            raise ValueError("Error: Could not count valid accounts.")
        count = result[0]
    except Exception:
        raise
    finally:
        database_connection.close()
    return count


def get_database_creation_date(database_filename):
    database_connection = None
    try:
        database_connection = sqlite3.connect(database_filename)
        cursor = database_connection.cursor()
        sqlstring = "select value from configuration where attribute = 'DATABASE_CREATED'"
        sqlresult = cursor.execute(sqlstring)
        result = sqlresult.fetchone()
        if result is None:
            raise ValueError("Error: Could not get database creation date.")
        created_date = result[0]
    except Exception:
        raise
    finally:
        database_connection.close()
    return created_date


def get_last_change_date_in_database(database_filename):
    count = 0
    database_connection = None
    try:
        database_connection = sqlite3.connect(database_filename)
        cursor = database_connection.cursor()
        sqlstring = SQL_GET_MAX_CHANGE_DATE_IN_DATABASE
        sqlresult = cursor.execute(sqlstring)
        result = sqlresult.fetchone()
        if result is None:
            raise ValueError("Error: Could not get last change date in database.")
        created_date = result[0]
    except Exception:
        raise
    finally:
        database_connection.close()
    return created_date


def get_account_count_invalid(database_filename):
    count = 0
    database_connection = None
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


def get_account_history_table_count(database_filename):
    count = 0
    database_connection = None
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


def get_deleted_account_table_count(database_filename):
    count = 0
    database_connection = None
    try:
        database_connection = sqlite3.connect(database_filename)
        cursor = database_connection.cursor()
        sqlstring = SQL_SELECT_COUNT_ALL_FROM_DELETED_ACCOUNT
        sqlresult = cursor.execute(sqlstring)
        result = sqlresult.fetchone()
        if result is None:
            raise ValueError("Error: Could not count deleted_account entries.")
        count = result[0]
    except Exception as e:
        raise
    finally:
        database_connection.close()
    return count


def get_shell_history_table_count(database_filename):
    count = 0
    database_connection = None
    try:
        database_connection = sqlite3.connect(database_filename)
        cursor = database_connection.cursor()
        sqlstring = SQL_SELECT_COUNT_ALL_FROM_SHELL_HISTORY
        sqlresult = cursor.execute(sqlstring)
        result = sqlresult.fetchone()
        if result is None:
            raise ValueError("Error: Could not count shell_history entries.")
        count = result[0]
    except Exception as e:
        raise
    finally:
        database_connection.close()
    return count


def get_alias_table_count(database_filename):
    count = 0
    database_connection = None
    try:
        database_connection = sqlite3.connect(database_filename)
        cursor = database_connection.cursor()
        sqlstring = SQL_SELECT_COUNT_ALL_FROM_ALIAS
        sqlresult = cursor.execute(sqlstring)
        result = sqlresult.fetchone()
        if result is None:
            raise ValueError("Error: Could not count alias entries.")
        count = result[0]
    except Exception:
        raise
    finally:
        database_connection.close()
    return count


def get_account_history_count(database_filename: str, account_uuid: str) -> int:
    count = 0
    database_connection = None
    try:
        database_connection = sqlite3.connect(database_filename)
        cursor = database_connection.cursor()
        sqlstring = 'select count(*) from account_history where account_uuid="' + account_uuid + '"'
        sqlresult = cursor.execute(sqlstring)
        result = sqlresult.fetchone()
        if result is None:
            raise ValueError("Error: Could not count account history entries for uuid: " + account_uuid)
        count = result[0]
    except Exception:
        raise
    finally:
        database_connection.close()
    return count


def get_account_count(database_filename, also_count_invalidated_accounts: bool = True):
    count = 0
    database_connection = None
    try:
        database_connection = sqlite3.connect(database_filename)
        cursor = database_connection.cursor()
        if also_count_invalidated_accounts:
            sqlstring = SQL_SELECT_COUNT_ALL_FROM_ACCOUNT
        else:
            sqlstring = SQL_SELECT_COUNT_ALL_VALID_FROM_ACCOUNT
        sqlresult = cursor.execute(sqlstring)
        result = sqlresult.fetchone()
        if result is None:
            raise ValueError("Error: Could not count accounts.")
        count = result[0]
    except Exception:
        raise
    finally:
        database_connection.close()
    return count


def print_database_statistics(database_filename):
    if not os.path.exists(database_filename):
        print(colored("Can not show database statistics because database file does not exist.", "red"))
        return
    account_count = get_account_count(database_filename)
    account_count_valid = get_account_count_valid(database_filename)
    account_count_invalid = get_account_count_invalid(database_filename)
    account_history_count = get_account_history_table_count(database_filename)
    shell_history_count = get_shell_history_table_count(database_filename)
    alias_count = get_alias_table_count(database_filename)
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
                                                     CONFIGURATION_TABLE_ATTRIBUTE_CONNECTOR_DEFAULT_DROPBOX_ACCOUNT_UUID)
    # dropbox_application_account_uuid = \
    #     get_attribute_value_from_configuration_table(database_filename,
    #                                                  CONFIGURATION_TABLE_ATTRIBUTE_DROPBOX_APPLICATION_ACCOUNT_UUID)
    ssh_account_uuid = \
        get_attribute_value_from_configuration_table(database_filename,
                                                     CONFIGURATION_TABLE_ATTRIBUTE_CONNECTOR_DEFAULT_SSH_ACCOUNT_UUID)
    file_account_uuid = \
        get_attribute_value_from_configuration_table(database_filename,
                                                     CONFIGURATION_TABLE_ATTRIBUTE_CONNECTOR_DEFAULT_FILE_ACCOUNT_UUID)
    webdav_account_uuid = \
        get_attribute_value_from_configuration_table(database_filename,
                                                     CONFIGURATION_TABLE_ATTRIBUTE_CONNECTOR_DEFAULT_WEBDAV_ACCOUNT_UUID)
    # default_merge_target_file = \
    #     get_attribute_value_from_configuration_table(database_filename,
    #                                                  CONFIGURATION_TABLE_ATTRIBUTE_DEFAULT_MERGE_TARGET_FILE)
    database_name = \
        get_attribute_value_from_configuration_table(database_filename,
                                                     CONFIGURATION_TABLE_ATTRIBUTE_DATABASE_NAME)
    if get_database_has_unmerged_changes(database_filename) is True:
        unmerged_changes = colored("Yes", "red")
    else:
        unmerged_changes = colored("No", "green")

    try:
        print("Database Name                       : ", end="")
        print_slow.print_slow(database_name)
        print("Database UUID                       : ", end="")
        print_slow.print_slow(database_uuid)
        print("Database File                       : ", end="")
        print_slow.print_slow(os.path.abspath(database_filename))
        print("Database Created                    : ", end="")
        print_slow.print_slow(database_creation_date)
        print("Database Schema Version             : ", end="")
        print_slow.print_slow(schema_version)
        print("SQLite Database Version             : ", end="")
        print_slow.print_slow(get_database_sqlite_version(database_filename))
        print("Database Encrypted                  : ", end="")
        print_slow.print_slow(str(database_is_encrypted))
        print("Database Size                       : ", end="")
        print_slow.print_slow(str(os.path.getsize(database_filename) / 1024) + " Kb")
        print("Database Last Changed               : ", end="")
        print_slow.print_slow(last_change_date)
        print("Accounts (valid/invalid)            : ", end="")
        print_slow.print_slow(
            str(account_count) + " (" + str(account_count_valid) + "/" + str(account_count_invalid) + ")")
        print("Account history entries             : ", end="")
        print_slow.print_slow(str(account_history_count))
        print("Shell command history entries       : ", end="")
        print_slow.print_slow(str(shell_history_count))
        print("Aliases                             : ", end="")
        print_slow.print_slow(str(alias_count))
        print("Account UUID's in deleted table     : ", end="")
        print_slow.print_slow(str(get_deleted_account_table_count(database_filename)))
        print("Last Merge Database                 : ", end="")
        print_slow.print_slow(str(last_merge_database))
        print("Last Merge Date                     : ", end="")
        print_slow.print_slow(str(last_merge_date))
        print("Database has unmerged changes       : ", end="")
        print_slow.print_slow(unmerged_changes)
        print("Merge destination DROPBOX           : ", end="")
        print_slow.print_slow(str(dropbox_account_uuid))
        print("Merge destination SSH               : ", end="")
        print_slow.print_slow(str(ssh_account_uuid))
        print("Merge destination WEBDAV            : ", end="")
        print_slow.print_slow(str(webdav_account_uuid))
        print("Merge destination FILE              : ", end="")
        print_slow.print_slow(str(file_account_uuid))
        # print("Merge destination local file        : ", end="")
        # print_slow.print_slow(str(default_merge_target_file))
    except KeyboardInterrupt:
        print()


def get_database_sqlite_version(database_filename: str) -> str:
    version = "unknown"
    database_connection = None
    try:
        database_connection = sqlite3.connect(database_filename)
        cursor = database_connection.cursor()
        sqlstring = "select sqlite_version()"
        sqlresult = cursor.execute(sqlstring)
        result = sqlresult.fetchone()
        if result is None:
            raise ValueError("Error: Could not get sqlite version.")
        version = result[0]
    except Exception:
        raise
    finally:
        database_connection.close()
    return version


def get_last_merge_date(database_filename: str) -> str:
    last_merge_date = get_attribute_value_from_configuration_table(database_filename,
                                                                   CONFIGURATION_TABLE_ATTRIBUTE_LAST_MERGE_DATE)
    return last_merge_date


def get_database_has_unmerged_changes(database_filename: str) -> str:
    last_change_date = get_last_change_date_in_database(database_filename)
    last_merge_date = get_attribute_value_from_configuration_table(database_filename,
                                                                   CONFIGURATION_TABLE_ATTRIBUTE_LAST_MERGE_DATE)
    if last_change_date is not None and last_merge_date is not None:
        last_change_date_later_than_last_merge_date = last_change_date > last_merge_date
    else:
        last_change_date_later_than_last_merge_date = False
    return last_change_date_later_than_last_merge_date


def _create_fernet(salt, password_bytes: bytes, iteration_count: int) -> Fernet:
    _hash = PBKDF2HMAC(algorithm=hashes.SHA256, length=32, salt=salt, iterations=iteration_count)
    key = base64.urlsafe_b64encode(_hash.derive(password_bytes))
    f = Fernet(key)
    return f


def color_search_string(text_string, search_string, color):
    if text_string is None or text_string == "":
        return ""
    # if search_string is None or search_string == "" or text_string is None or text_string == "":
    if search_string is None or search_string == "":
        return text_string
    list_matching_indices = [m.start() for m in finditer(search_string, text_string, flags=IGNORECASE)]
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


def print_found_n_results(n_results: int):
    if n_results == 1:
        print("Found 1 result.")
    else:
        print("Found " + str(n_results) + " results.")


def read_confirmed_database_password_from_user() -> str:
    new_password = getpass("Enter new database password   : ")
    new_password_confirm = getpass("Confirm new database password : ")
    while new_password != new_password_confirm:
        logging.error("Passwords do not match.")
        new_password = getpass("Enter new database password   : ")
        new_password_confirm = getpass("Confirm new database password : ")
    return new_password


class PDatabase:
    # DEFAULT_SALT = b"98uAS (H CQCH AISDUHU/ZASD/7zhdw7e-;568!"  # The salt for the encryption is static. This might become a problem?!
    # DEFAULT_ITERATION_COUNT = 500000

    database_filename = "unset_database_name.db"
    _database_password_bytes: bytes = b""
    _DATABASE_PASSWORD_TEST_VALUE_LENGTH = 64  # how long should the dummy encrypted string be
    _fernet = None
    _salt = None
    _iteration_count: int = -1
    show_account_details: bool = False
    show_invalidated_accounts: bool = False
    shadow_passwords: bool = False
    _SEARCH_STRING_HIGHLIGHTING_COLOR = "green"
    track_account_history: bool = True

    def __init__(self, database_filename, database_password: str, show_account_details=False,
                 show_invalidated_accounts=False, shadow_passwords: bool = False,
                 salt=DEFAULT_SALT, iteration_count: int = DEFAULT_ITERATION_COUNT,
                 track_account_history: bool = True, initial_database_name: str = None):
        if database_filename is None \
                or database_filename == "" \
                or database_password is None:
            print(colored("Error: Database filename is empty or database password is not set!", "red"))
            raise ValueError("Database filename is not set or database password is not set!")

        self.database_filename = database_filename
        self.show_account_details = show_account_details
        self.show_invalidated_accounts = show_invalidated_accounts
        self.shadow_passwords = shadow_passwords
        self.track_account_history = track_account_history
        self._salt = salt
        self._iteration_count = iteration_count
        # store password as byte[]
        if database_password != "":
            # self.database_password = database_password.encode("UTF-8")
            self._database_password_bytes = database_password.encode("UTF-8")
            # self._fernet = _create_fernet(self._salt, self.database_password, self._iteration_count)
            self._fernet = _create_fernet(self._salt, self._database_password_bytes, self._iteration_count)
        else:
            # self.database_password = ""
            self._database_password_bytes = "".encode("UTF-8")
        self.create_and_initialize_database(initial_database_name)
        self.update_database_schema(self.database_filename)
        self.set_default_values_in_configuration_table()
        # if not is_valid_database_password(self.database_filename, self.database_password):
        if not is_valid_database_password(self.database_filename, self._database_password_bytes):
            print(colored("Database password verification failed! Password is wrong!", 'red'))
            print(colored("If the password is lost, the password database can not be opened anymore!", 'red'))
            print(colored("To create a new database, remove the old one and start p again.", 'red'))
            time.sleep(3)
            raise Exception("Database password is wrong.")

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
        database_connection = None
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

    def print_current_secure_delete_mode(self, cursor):
        sqlstring = "pragma secure_delete"
        try:
            print("SQLite secure_delete mode: " + str(cursor.execute(sqlstring).fetchall()[0][0]))
        except Exception:
            raise

    def duplicate_account(self, copy_uuid):
        if copy_uuid is None or copy_uuid == "":
            print("Error copying account: UUID is empty.")
            return
        if self.get_account_exists(copy_uuid) is False:
            print("Error: Account uuid " + copy_uuid + " does not exist.")
            return
        try:
            origin_account = self.get_account_by_uuid_and_decrypt(copy_uuid)
            new_account_uuid = str(uuid.uuid4())
            new_account = Account(new_account_uuid,
                                  origin_account.name,
                                  origin_account.url,
                                  origin_account.loginname,
                                  origin_account.password,
                                  origin_account.type,
                                  origin_account.connector_type)
            self.add_account_and_encrypt(new_account)
        except Exception as e:
            print(colored("Error: " + str(e)))

    def delete_account(self, delete_uuid):
        if delete_uuid is None or delete_uuid == "":
            print("Error deleting account: UUID is empty.")
            return
        if self.get_account_exists(delete_uuid) is False:
            print("Error: Account uuid " + delete_uuid + " does not exist.")
            return
        account_to_be_deleted = self.get_account_by_uuid_and_decrypt(delete_uuid)
        # account_name_to_be_deleted = account_to_be_deleted.name
        print()
        self.print_formatted_account(account_to_be_deleted,
                                     show_history_count=True,
                                     show_account_details=True)
        print()
        try:
            answer = input("Delete account ([y]/n) : ")
        except KeyboardInterrupt:
            answer = "n"
            print()
        if answer != "y" and answer != "":
            print("Canceled.")
            return
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            self.set_database_pragmas_to_secure_mode(database_connection, cursor)
            self.print_current_secure_delete_mode(cursor)
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
        database_connection = None
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

    def get_orphaned_account_history_entries_count(self) -> int:
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            self.set_database_pragmas_to_secure_mode(database_connection, cursor)
            sqlstring = "select count(*) FROM account_history h WHERE h.account_uuid not in (select uuid from account)"
            sqlresult = cursor.execute(sqlstring)
            # database_connection.commit()
            result = sqlresult.fetchone()
            if result is None:
                raise ValueError("Error: Could not count orphaned history entries.")
            count = result[0]
            return count
        except Exception:
            print("Error counting orphaned history entries from database.")
        finally:
            database_connection.close()

    def delete_orphaned_account_history_entries(self):
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            self.set_database_pragmas_to_secure_mode(database_connection, cursor)
            sqlstring = "delete FROM account_history WHERE account_uuid not in (select uuid from account)"
            cursor.execute(sqlstring)
            database_connection.commit()
        except Exception as e:
            print("Error deleting orphaned history entries from database: " + str(e))
            # e.with_traceback()
        finally:
            database_connection.close()

    def delete_all_shell_history_entries(self):
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            self.set_database_pragmas_to_secure_mode(database_connection, cursor)
            sqlstring = "delete from shell_history"
            cursor.execute(sqlstring)
            database_connection.commit()
        except Exception:
            print("Error deleting shell history entries from database.")
        finally:
            database_connection.close()

    def get_shell_history_entries_decrypted(self) -> [ShellHistoryEntry]:
        shell_history_array = []
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            sqlstring = "select execution_date, user_input from shell_history order by create_date desc"
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            for row in result:
                current_execution_date = row[0]
                current_user_input = row[1]
                current_execution_date_decrypted = self.decrypt_string_if_password_is_present(current_execution_date)
                current_user_input_decrypted = self.decrypt_string_if_password_is_present(current_user_input)
                new_shell_history = ShellHistoryEntry(execution_date=current_execution_date_decrypted,
                                                      user_input=current_user_input_decrypted)
                shell_history_array.append(new_shell_history)
        except Exception:
            print("Error getting shell history entries from database.")
            return shell_history_array
        finally:
            database_connection.close()
        # shell_history_array.reverse()
        return shell_history_array

    def get_alias_commands_decrypted(self) -> [str]:
        alias_commands = []
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            sqlstring = "select alias, command from alias order by cast(alias as int)"
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            for row in result:
                # print("->" + str(row))
                current_alias = row[0]
                current_command = self.decrypt_string_if_password_is_present(row[1])
                alias_commands.append(" [" + current_alias + "] - " + current_command)
        except Exception:
            print("Error getting all alias from database.")
            return alias_commands
        finally:
            database_connection.close()
        return alias_commands

    def get_alias_command_decrypted(self, alias: str) -> str:
        alias_command = ""
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            sqlstring = "select command from alias where alias = " + alias
            # sqlstring = "select command from alias where alias = ?"
            # print("alias_>" + alias)
            # sqlresult = cursor.execute(sqlstring, (alias))
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchone()
            if result is None:
                return alias_command
            encrypted_command = result[0]
            decrypted_command = self.decrypt_string_if_password_is_present(encrypted_command)
            alias_command = decrypted_command
        except Exception as e:
            print("Error getting alias from database.")
            print(str(e))
            return alias_command
        finally:
            database_connection.close()
        return alias_command

    def set_alias_command_and_encrypt(self, alias: str, command: str):
        if alias == "" or alias is None:
            return
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            encrypted_command = self.encrypt_string_if_password_is_present(command)
            if encrypted_command == "":
                # sqlstring = "delete from alias where alias = ?"
                # cursor.execute(sqlstring, alias)
                sqlstring = "delete from alias where alias = " + alias
                cursor.execute(sqlstring)
            else:
                sqlstring = "insert or replace into alias (alias, command) values (?, ?)"
                cursor.execute(sqlstring, (alias, encrypted_command))
            database_connection.commit()
        except Exception:
            print("Error setting alias into database.")
        finally:
            database_connection.close()

    def add_shell_history_entry(self, shell_history_entry: ShellHistoryEntry, max_history_size: int):
        if int(max_history_size) < 1:
            return
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            execution_date_encrypted = \
                self.encrypt_string_if_password_is_present(str(shell_history_entry.execution_date))
            command_encrypted = self.encrypt_string_if_password_is_present(shell_history_entry.user_input)
            sqlstring = "insert into shell_history (uuid, execution_date, user_input) values ('" + \
                        str(uuid.uuid4()) + "', '" + str(execution_date_encrypted) + \
                        "', '" + str(command_encrypted) + "') "
            cursor.execute(sqlstring)
            # delete too much existing entries from table
            sqlstring = "DELETE FROM shell_history WHERE uuid NOT IN (SELECT uuid FROM shell_history ORDER BY " + \
                        "create_date DESC LIMIT " + str(max_history_size) + ") "
            cursor = database_connection.cursor()
            cursor.execute(sqlstring)
            database_connection.commit()
        except Exception as e:
            print("Error appending shell history entry to database: " + str(e))
            return
        finally:
            database_connection.close()

    def get_deleted_account_uuids_decrypted_from_merge_database(self, merge_database_filename: str) -> []:
        result_array = []
        database_connection = None
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
        database_connection = None
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
            database_connection.commit()
        except Exception:
            raise
        finally:
            database_connection.close()

    def get_uuid_exists_in_deleted_accounts(self, account_uuid) -> bool:
        if account_uuid in self.get_deleted_account_uuids_decrypted():
            return True
        else:
            return False

    def invalidate_account(self, invalidate_uuid: str) -> bool:
        if invalidate_uuid is None or invalidate_uuid == "":
            return False
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            sqlstring = "update account set invalid_date = datetime(CURRENT_TIMESTAMP, 'localtime') where uuid = '" + \
                        str(invalidate_uuid) + "'"
            cursor.execute(sqlstring)
            database_connection.commit()
        except Exception:
            raise
        finally:
            database_connection.close()
        return True

    def revalidate_account(self, revalidate_uuid: str) -> bool:
        if revalidate_uuid is None or revalidate_uuid == "":
            return False
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            sqlstring = "update account set invalid_date = NULL where uuid = '" + str(revalidate_uuid) + "'"
            cursor.execute(sqlstring)
            database_connection.commit()
        except Exception:
            raise
        finally:
            database_connection.close()
        return True

    def decrypt_account(self, account: Account) -> Account:
        account.uuid = account.uuid
        account.name = self.decrypt_string_if_password_is_present(account.name)
        account.url = self.decrypt_string_if_password_is_present(account.url)
        account.loginname = self.decrypt_string_if_password_is_present(account.loginname)
        account.password = self.decrypt_string_if_password_is_present(account.password)
        account.type = self.decrypt_string_if_password_is_present(account.type)
        account.connector_type = self.decrypt_string_if_password_is_present(account.connector_type)
        account.create_date = account.create_date
        account.change_date = account.change_date
        account.invalid_date = account.invalid_date
        return account

    def search_account_history(self, uuid_string: str):
        results_found = 0
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            sqlstring = "select account_uuid as uuid, name, url, loginname, password, type, create_date, connector_type from account_history where " + \
                        "account_uuid = '" + str(uuid_string) + "' order by create_date"
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            print()
            if result is not None:
                print(colored("Older versions of account:", 'red'))
                print()
            for row in result:
                account = Account(uuid=row[0],
                                  name=row[1],
                                  url=row[2],
                                  loginname=row[3],
                                  password=row[4],
                                  type=row[5],
                                  create_date=row[6],
                                  connector_type=row[7]
                                  )
                decrypted_account = self.decrypt_account(account)
                results_found += 1
                try:
                    if results_found < 4:
                        self.print_formatted_account(decrypted_account, show_history_count=False, print_slowly=True)
                    else:
                        self.print_formatted_account(decrypted_account, show_history_count=False, print_slowly=False)
                except KeyboardInterrupt:
                    print()
                    return
                print()
            print(colored("Latest version of account:", 'green'))
            self.search_account_by_uuid(uuid_string)
            print()
        except Exception:
            raise
        finally:
            database_connection.close()
        print_found_n_results(results_found)

    def search_accounts(self, search_string: str):
        results_found = 0
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            if self.show_invalidated_accounts:
                sqlstring = "select uuid, name, url, loginname, password, type, create_date, change_date, \
                            invalid_date, connector_type from account "
            else:
                sqlstring = "select uuid, name, url, loginname, password, type, create_date, change_date, \
                            invalid_date, connector_type from account where invalid = 0 "
            sqlstring = sqlstring + ACCOUNTS_ORDER_BY_STATEMENT
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            print("Searching for *" + colored(search_string, self._SEARCH_STRING_HIGHLIGHTING_COLOR) +
                  "* in " + str(
                get_account_count(self.database_filename, self.show_invalidated_accounts)) + " accounts:")
            if len(result) > 0:
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
                                  invalid_date=row[8],
                                  connector_type=row[9]
                                  )
                decrypted_account = self.decrypt_account(account)
                if search_string == "" or \
                        search_string_matches_account(search_string, decrypted_account):
                    results_found += 1
                    try:
                        if results_found < 2:
                            self.print_formatted_account_search_string_colored(decrypted_account, search_string,
                                                                               print_slowly=True)
                        else:
                            self.print_formatted_account_search_string_colored(decrypted_account, search_string,
                                                                               print_slowly=False)
                    except KeyboardInterrupt:
                        print()
                        return
                    print()
        except Exception:
            raise
        finally:
            database_connection.close()
        print_found_n_results(results_found)

    def search_invalidated_accounts(self, search_string: str):
        results_found = 0
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            sqlstring = "select uuid, name, url, loginname, password, type, create_date, change_date, \
                         invalid_date, connector_type from account where invalid = 1 "
            sqlstring = sqlstring + ACCOUNTS_ORDER_BY_STATEMENT
            # print("executing: " + sqlstring)
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            print("Searching for *" + colored(search_string, self._SEARCH_STRING_HIGHLIGHTING_COLOR) +
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
                                  invalid_date=row[8],
                                  connector_type=row[9]
                                  )
                decrypted_account = self.decrypt_account(account)
                if search_string == "" or \
                        search_string_matches_account(search_string, decrypted_account):
                    results_found += 1
                    try:
                        if results_found < 4:
                            self.print_formatted_account_search_string_colored(decrypted_account, search_string,
                                                                               print_slowly=True)
                        else:
                            self.print_formatted_account_search_string_colored(decrypted_account, search_string,
                                                                               print_slowly=False)
                        print()
                    except KeyboardInterrupt:
                        print()
                        return
                    print()
        except Exception:
            raise
        finally:
            database_connection.close()
        print_found_n_results(results_found)

    def get_new_account_uuids_since(self, date_string: str) -> []:
        uuids = []
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            sqlstring = "select uuid from account where create_date >= '" + "" + date_string + "'"
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            for row in result:
                uuids.append(str(row[0]))
        except Exception:
            raise
        finally:
            database_connection.close()
        return uuids

    def get_changed_account_uuids_since(self, date_string: str) -> []:
        uuids = []
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            sqlstring = "select uuid from account where create_date <> change_date and change_date >= '" + "" + date_string + "'"
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            for row in result:
                uuids.append(str(row[0]))
        except Exception:
            raise
        finally:
            database_connection.close()
        return uuids

    def get_deleted_account_uuids_decrypted_since(self, date_string: str) -> []:
        uuids = []
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            sqlstring = "select uuid from deleted_account where create_date >= '" + "" + date_string + "'"
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            for row in result:
                decrypted_uuid = self.decrypt_string_if_password_is_present(str(row[0]))
                uuids.append(decrypted_uuid)
        except Exception:
            raise
        finally:
            database_connection.close()
        return uuids

    def show_unmerged_changes(self):
        last_merge_date = get_last_merge_date(self.database_filename)
        last_change_date = get_last_change_date_in_database(self.database_filename)
        print()
        print("Last merge  date : " + last_merge_date)
        print("Last change date : " + last_change_date)

        print()
        print("<New accounts since last merge>")
        print()
        uuids = self.get_new_account_uuids_since(last_merge_date)
        if len(uuids) == 0:
            print("None")
        for current_uuid in uuids:
            account = self.get_account_by_uuid_and_decrypt(current_uuid)
            self.print_formatted_account(account, show_history_count=False, print_slowly=False)
            print()

        print()
        print("<Changed accounts since last merge>")
        print()
        uuids = self.get_changed_account_uuids_since(last_merge_date)
        if len(uuids) == 0:
            print("None")
        for current_uuid in uuids:
            account = self.get_account_by_uuid_and_decrypt(current_uuid)
            self.print_formatted_account(account, show_history_count=False, print_slowly=False)
            print()

        print()
        print("<Deleted account uuid's since last merge>")
        print()
        uuids = self.get_deleted_account_uuids_decrypted_since(last_merge_date)
        if len(uuids) == 0:
            print("None")
        for current_uuid in uuids:
            print(current_uuid)
        print()

    def search_accounts_by_type(self, type_search_string: str):
        results_found = 0
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            if self.show_invalidated_accounts:
                sqlstring = "select uuid, name, url, loginname, password, type, create_date, change_date, \
                            invalid_date, connector_type from account "
            else:
                sqlstring = "select uuid, name, url, loginname, password, type, create_date, change_date, \
                            invalid_date, connector_type from account where invalid = 0 "
            sqlstring = sqlstring + ACCOUNTS_ORDER_BY_STATEMENT
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            print("Searching for *" + colored(type_search_string, self._SEARCH_STRING_HIGHLIGHTING_COLOR) +
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
                                  invalid_date=row[8],
                                  connector_type=row[9]
                                  )
                decrypted_account = self.decrypt_account(account)
                if type_search_string == "" or \
                        type_search_string.lower() in account.type.lower():
                    results_found += 1
                    try:
                        if results_found < 4:
                            self.print_formatted_account_search_string_colored(decrypted_account, type_search_string,
                                                                               print_slowly=True)
                        else:
                            self.print_formatted_account_search_string_colored(decrypted_account, type_search_string,
                                                                               print_slowly=False)
                    except KeyboardInterrupt:
                        print()
                        return
                    print()
        except Exception:
            raise
        finally:
            database_connection.close()
        print_found_n_results(results_found)

    def get_accounts_decrypted(self, search_string: str) -> []:
        account_array = []
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            if self.show_invalidated_accounts:
                sqlstring = "select uuid, name, url, loginname, password, type, create_date, change_date, \
                            invalid_date, connector_type from account "
            else:
                sqlstring = "select uuid, name, url, loginname, password, type, create_date, change_date, \
                            invalid_date, connector_type from account where invalid = 0 "
            sqlstring = sqlstring + ACCOUNTS_ORDER_BY_STATEMENT
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            for row in result:
                account = Account(uuid=row[0],
                                  name=row[1],
                                  url=row[2],
                                  loginname=row[3],
                                  password=row[4],
                                  type=row[5],
                                  create_date=row[6],
                                  change_date=row[7],
                                  invalid_date=row[8],
                                  connector_type=row[9]
                                  )
                decrypted_account = self.decrypt_account(account)
                if search_string == "" or \
                        search_string_matches_account(search_string, decrypted_account):
                    # results_found += 1
                    # self.print_formatted_account_search_string_colored(decrypted_account, search_string)
                    account_array.append(decrypted_account)
        except Exception:
            raise
        finally:
            database_connection.close()
        return account_array

    def get_accounts_decrypted_from_invalid_accounts(self, search_string: str) -> []:
        account_array = []
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            sqlstring = "select uuid, name, url, loginname, password, type, create_date, change_date, \
                         invalid_date, connector_type from account where invalid = 1 "
            sqlstring = sqlstring + ACCOUNTS_ORDER_BY_STATEMENT
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            for row in result:
                account = Account(uuid=row[0],
                                  name=row[1],
                                  url=row[2],
                                  loginname=row[3],
                                  password=row[4],
                                  type=row[5],
                                  create_date=row[6],
                                  change_date=row[7],
                                  invalid_date=row[8],
                                  connector_type=row[9]
                                  )
                decrypted_account = self.decrypt_account(account)
                if search_string == "" or \
                        search_string_matches_account(search_string, decrypted_account):
                    account_array.append(decrypted_account)
        except Exception:
            raise
        finally:
            database_connection.close()
        return account_array

    def get_accounts_decrypted_search_types(self, type_search_string: str) -> []:
        account_array = []
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            if self.show_invalidated_accounts:
                sqlstring = "select uuid, name, url, loginname, password, type, create_date, change_date, \
                            invalid_date, connector_type from account "
            else:
                sqlstring = "select uuid, name, url, loginname, password, type, create_date, change_date, \
                            invalid_date, connector_type from account where invalid = 0 "
            sqlstring = sqlstring + ACCOUNTS_ORDER_BY_STATEMENT
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            for row in result:
                account = Account(uuid=row[0],
                                  name=row[1],
                                  url=row[2],
                                  loginname=row[3],
                                  password=row[4],
                                  type=row[5],
                                  create_date=row[6],
                                  change_date=row[7],
                                  invalid_date=row[8],
                                  connector_type=row[9]
                                  )
                decrypted_account = self.decrypt_account(account)
                if type_search_string == "" or \
                        type_search_string.lower() in account.type.lower():
                    account_array.append(decrypted_account)
        except Exception:
            raise
        finally:
            database_connection.close()
        return account_array

    def search_account_by_uuid(self, search_uuid) -> bool:
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            if search_uuid is None or search_uuid == "":
                return False
            sqlstring = "select uuid, name, url, loginname, password, type, create_date, change_date, invalid_date, connector_type from \
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
                              invalid_date=row[8],
                              connector_type=row[9]
                              )
            try:
                self.print_formatted_account(self.decrypt_account(account))
            except KeyboardInterrupt:
                print()
                return False
            return True
        except Exception:
            raise
        finally:
            database_connection.close()

    def get_account_exists(self, account_uuid) -> bool:
        account = self.get_account_by_uuid_and_decrypt(account_uuid)
        if account is not None:
            return True
        else:
            return False

    def get_password_from_account_and_decrypt(self, account_uuid: str) -> str | None:
        if account_uuid is None or account_uuid.strip() == "":
            return None
        account = self.get_account_by_uuid_and_decrypt(account_uuid)
        if account is not None:
            return account.password
        else:
            return None

    def get_loginname_from_account_and_decrypt(self, account_uuid: str) -> str | None:
        if account_uuid is None or account_uuid.strip() == "":
            return None
        account = self.get_account_by_uuid_and_decrypt(account_uuid)
        if account is not None:
            return account.loginname
        else:
            return None

    def get_connector_type_from_account_and_decrypt(self, account_uuid: str) -> str | None:
        if account_uuid is None or account_uuid.strip() == "":
            return None
        account = self.get_account_by_uuid_and_decrypt(account_uuid)
        if account is not None:
            return account.connector_type
        else:
            return None

    def get_account_by_uuid_and_decrypt(self, search_uuid: str) -> Account | None:
        if search_uuid is None or search_uuid == "":
            return None
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            sqlstring = "select uuid, name, url, loginname, password, type, create_date, change_date, invalid_date, connector_type " + \
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
                decrypted_connector_type = self.decrypt_string_if_password_is_present(row[9])
                account = Account(uuid=search_uuid,
                                  name=decrypted_name,
                                  url=decrypted_url,
                                  loginname=decrypted_loginname,
                                  password=decrypted_password,
                                  type=decrypted_type,
                                  connector_type=decrypted_connector_type,
                                  create_date=str(row[6]),
                                  change_date=str(row[7]),
                                  invalid_date=str(row[8])
                                  )
                return account
        except Exception:
            raise
        finally:
            database_connection.close()
        return None

    def set_password_of_account(self, account_uuid: str, new_password: str):
        account = self.get_account_by_uuid_and_decrypt(account_uuid)
        if account is None:
            return
        self.set_account_by_uuid_and_encrypt(account.uuid,
                                             account.name,
                                             account.url,
                                             account.loginname,
                                             new_password,
                                             account.type,
                                             account.connector_type)

    # Set account by uuid = edit account. If account_history is enabled the old version
    # of the account will be saved in the table account_history
    def set_account_by_uuid_and_encrypt(self, account_uuid, name, url, loginname, password, type, connector_type):
        if account_uuid is None or account_uuid == "":
            raise Exception("Account UUID is not set or empty.")
        # encrypt
        name = self.encrypt_string_if_password_is_present(name)
        url = self.encrypt_string_if_password_is_present(url)
        loginname = self.encrypt_string_if_password_is_present(loginname)
        password = self.encrypt_string_if_password_is_present(password)
        type = self.encrypt_string_if_password_is_present(type)
        connector_type = self.encrypt_string_if_password_is_present(connector_type)
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            self.set_database_pragmas_to_secure_mode(database_connection, cursor)
            self.print_current_secure_delete_mode(cursor)

            # 1. First backup old version of the account
            if get_attribute_value_from_configuration_table(self.database_filename,
                                                            CONFIGURATION_TABLE_ATTRIBUTE_TRACK_ACCOUNT_HISTORY) \
                    == "True":
                # cursor = database_connection.cursor()
                account_history_uuid = uuid.uuid4()
                sqlstring = "insert into account_history (uuid, account_uuid, name, url, loginname, password, type, connector_type) " + \
                            " select '" + str(account_history_uuid) + \
                            "' as uuid, uuid as account_uuid, name, url, loginname, password, type, connector_type " + \
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
                        "connector_type = '" + connector_type + "', " + \
                        "type = '" + type + "' " + \
                        "where uuid = '" + str(account_uuid) + "'"
            cursor.execute(sqlstring)
            database_connection.commit()
        except Exception:
            raise
        finally:
            database_connection.close()

    def print_formatted_account_search_string_colored(self, account: Account, search_string: str = "",
                                                      print_slowly: bool = True, show_account_details: bool = False):
        account.uuid = color_search_string(account.uuid, search_string, self._SEARCH_STRING_HIGHLIGHTING_COLOR)
        account.name = color_search_string(account.name, search_string, self._SEARCH_STRING_HIGHLIGHTING_COLOR)
        account.url = color_search_string(account.url, search_string, self._SEARCH_STRING_HIGHLIGHTING_COLOR)
        account.loginname = color_search_string(account.loginname, search_string, self._SEARCH_STRING_HIGHLIGHTING_COLOR)
        account.password = color_search_string(account.password, search_string, self._SEARCH_STRING_HIGHLIGHTING_COLOR)
        account.type = color_search_string(account.type, search_string, self._SEARCH_STRING_HIGHLIGHTING_COLOR)
        account.connector_type = color_search_string(account.connector_type, search_string,
                                                     self._SEARCH_STRING_HIGHLIGHTING_COLOR)
        account.create_date = color_search_string(account.create_date, search_string,
                                                  self._SEARCH_STRING_HIGHLIGHTING_COLOR)
        account.change_date = color_search_string(account.change_date, search_string,
                                                  self._SEARCH_STRING_HIGHLIGHTING_COLOR)
        account.invalid_date = color_search_string(account.invalid_date, search_string,
                                                   self._SEARCH_STRING_HIGHLIGHTING_COLOR)
        self.print_formatted_account(account, print_slowly=print_slowly, show_account_details=show_account_details)

    def print_formatted_account(self, account: Account, show_history_count: bool = True, print_slowly: bool = True,
                                show_account_details: bool = False):
        if print_slowly is False:
            print_delay = 0
        else:
            print_delay = print_slow.DEFAULT_DELAY
        print("UUID            : ", end="")
        print_slow.print_slow(str(account.uuid), delay=print_delay)
        print("Name            : ", end="")
        print_slow.print_slow(str(account.name), delay=print_delay)
        print("URL             : ", end="")
        print_slow.print_slow(str(account.url), delay=print_delay)
        print("Loginname       : ", end="")
        print_slow.print_slow(str(account.loginname), delay=print_delay)
        if self.shadow_passwords:
            print("Password        : ********")
        else:
            print("Password        : ", end="")
            print_slow.print_slow(str(account.password), delay=print_delay)
        print("Type            : ", end="")
        print_slow.print_slow(str(account.type), delay=print_delay)
        print("Connectortype   : ", end="")
        print_slow.print_slow(str(account.connector_type), delay=print_delay)
        if self.show_account_details or show_account_details:
            print("Created         : ", end="")
            print_slow.print_slow(str(account.create_date), delay=print_delay)
            print("Changed         : ", end="")
            print_slow.print_slow(str(account.change_date), delay=print_delay)
            print("Invalidated     : ", end="")
            if account.invalid_date != "None":
                print_slow.print_slow(colored(str(account.invalid_date), "red"), delay=print_delay)
            else:
                print_slow.print_slow(colored(str(account.invalid_date), "green"), delay=print_delay)
            if show_history_count:
                print("Old Versions    : ", end="")
                print_slow.print_slow(str(get_account_history_count(self.database_filename, account.uuid)),
                                      delay=print_delay)

    def decrypt_and_encrypt_with_new_password(self, string_encrypted: str, new_password: str) -> str:
        string_decrypted = self.decrypt_string_if_password_is_present(string_encrypted)
        string_encrypted_new = self.encrypt_string_with_custom_password(string_decrypted, new_password)
        return string_encrypted_new

    def change_database_password(self, new_password: str) -> bool:
        # if not is_valid_database_password(self.database_filename, self.database_password):
        if not is_valid_database_password(self.database_filename, self._database_password_bytes):
            print("Old database password is wrong.")
            return False
        database_connection = None
        bar = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            # Change the PASSWORD_TEST token in configuration table:
            print("Changing DATABASE_PASSWORD_TEST value in configuration table...")
            if new_password != "":
                random_string = str(
                    binascii.hexlify(os.urandom(self._DATABASE_PASSWORD_TEST_VALUE_LENGTH)).decode('UTF-8'))
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
            account_history_count = get_account_history_table_count(self.database_filename)
            deleted_account_table_count = get_deleted_account_table_count(self.database_filename)
            shell_history_table_count = get_shell_history_table_count(self.database_filename)
            alias_table_count = get_alias_table_count(self.database_filename)
            print("Re-encrypting " + str(account_count) + " accounts...")
            print("Re-encrypting " + str(account_history_count) + " account history entries...")
            print("Re-encrypting " + str(deleted_account_table_count) + " deleted account entries...")
            print("Re-encrypting " + str(shell_history_table_count) + " shell history entries...")
            print("Re-encrypting " + str(alias_table_count) + " alias entries...")
            max_value = (account_count +
                         account_history_count +
                         deleted_account_table_count +
                         shell_history_table_count +
                         alias_table_count)
            bar = progressbar.ProgressBar(maxval=max_value)
            bar.start()
            # Disable the update_change_date_trigger
            cursor.execute(SQL_MERGE_DROP_LOCAL_ACCOUNT_CHANGE_DATE_TRIGGER)

            # reencrypt account table
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
                current_connector_type = row[6]
                # print(row)
                # re-encrypt that shit
                new_current_name = self.decrypt_and_encrypt_with_new_password(current_name, new_password)
                new_current_url = self.decrypt_and_encrypt_with_new_password(current_url, new_password)
                new_current_loginname = self.decrypt_and_encrypt_with_new_password(current_loginname, new_password)
                new_current_password = self.decrypt_and_encrypt_with_new_password(current_password, new_password)
                new_current_type = self.decrypt_and_encrypt_with_new_password(current_type, new_password)
                new_current_connector_type = self.decrypt_and_encrypt_with_new_password(current_connector_type,
                                                                                        new_password)
                # and push it back into the db
                update_sql_string = "update account set name=?, " + \
                                    "url=?, " + \
                                    "loginname=?, " + \
                                    "password=?, " + \
                                    "type=?, " + \
                                    "connector_type=? " + \
                                    "where uuid = '" + str(current_uuid) + "'"
                cursor.execute(update_sql_string, (new_current_name, new_current_url, new_current_loginname,
                                                   new_current_password, new_current_type, new_current_connector_type))
                bar.update(results_found)

            # reencrypt account_history table
            sqlstring = SQL_SELECT_ALL_ACCOUNT_HISTORY
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            # results_found = 0
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
                current_connector_type = row[7]
                # current_create_date = row[7]
                # print(row)
                # re-encrypt that shit
                new_current_name = self.decrypt_and_encrypt_with_new_password(current_name, new_password)
                new_current_url = self.decrypt_and_encrypt_with_new_password(current_url, new_password)
                new_current_loginname = self.decrypt_and_encrypt_with_new_password(current_loginname, new_password)
                new_current_password = self.decrypt_and_encrypt_with_new_password(current_password, new_password)
                new_current_type = self.decrypt_and_encrypt_with_new_password(current_type, new_password)
                new_current_connector_type = self.decrypt_and_encrypt_with_new_password(current_connector_type,
                                                                                        new_password)
                # and push it back into the db
                update_sql_string = "update account_history set name=?, " + \
                                    "url=?, " + \
                                    "loginname=?, " + \
                                    "password=?, " + \
                                    "type=?, " + \
                                    "connector_type=? " + \
                                    "where uuid = '" + str(current_uuid) + "'"
                cursor.execute(update_sql_string, (new_current_name, new_current_url, new_current_loginname,
                                                   new_current_password, new_current_type, new_current_connector_type))
                bar.update(results_found)

            # reencrypt deleted_account table
            sqlstring = SQL_SELECT_ALL_FROM_DELETED_ACCOUNT
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            # results_found = 0
            for row in result:
                results_found += 1
                # get current account_history data (encrypted)
                current_uuid = row[0]
                current_create_date = row[1]
                new_current_uuid = self.decrypt_and_encrypt_with_new_password(current_uuid, new_password)
                # delete old entry
                delete_sql_string = "delete from deleted_account where uuid = '" + current_uuid + "'"
                cursor.execute(delete_sql_string)

                # and create new encrypted entry
                insert_sql_string = "insert into deleted_account (uuid, create_date) values (?, ?)"
                cursor.execute(insert_sql_string, (new_current_uuid, current_create_date))
                bar.update(results_found)

            # reencrypt shell history table
            sqlstring = SQL_SELECT_ALL_FROM_SHELL_HISTORY
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            for row in result:
                results_found += 1
                # get current shell_history data (encrypted)
                current_uuid = row[0]
                current_create_date = row[1]
                current_execution_date = row[2]
                current_user_input = row[3]
                new_current_execution_date = self.decrypt_and_encrypt_with_new_password(current_execution_date,
                                                                                        new_password)
                new_current_user_input = self.decrypt_and_encrypt_with_new_password(current_user_input,
                                                                                    new_password)
                update_sql_string = "update shell_history set execution_date = ?, user_input = ? where uuid = ?"
                cursor.execute(update_sql_string, (new_current_execution_date, new_current_user_input, current_uuid))

            # reencrypt alias table
            sqlstring = SQL_SELECT_ALL_FROM_ALIAS
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            for row in result:
                results_found += 1
                # get current shell_history data (encrypted)
                current_alias = row[0]
                current_command = row[1]

                new_current_command = self.decrypt_and_encrypt_with_new_password(current_command,
                                                                                 new_password)
                update_sql_string = "update alias set command = ? where alias = ?"
                cursor.execute(update_sql_string, (new_current_command, current_alias))

            bar.finish()
            cursor.execute(SQL_MERGE_CREATE_LOCAL_ACCOUNT_CHANGE_DATE_TRIGGER)
            # ERST commit, wenn ALLES erledigt ist, sonst salat in der db!!!
            database_connection.commit()
            print("Changed entries: " + str(results_found))
        except KeyboardInterrupt:
            if bar:
                bar.finish()
            database_connection.rollback()
            print("Process canceled by user.")
            return False
        except Exception:
            if database_connection:
                database_connection.rollback()
            raise
        finally:
            database_connection.close()
        # set encryption engine to new password
        # store password as byte[]
        if new_password != "":
            # self.database_password = new_password.encode("UTF-8")
            self._database_password_bytes = new_password.encode("UTF-8")
            # self._fernet = create_fernet(self._salt, self.database_password, self._iteration_count)
            self._fernet = _create_fernet(self._salt, self._database_password_bytes, self._iteration_count)
        else:
            # self.database_password = ""
            self._database_password_bytes = "".encode("UTF-8")
            self._fernet = None
        return True

    def encrypt_string_if_password_is_present(self, plain_text: str) -> str:
        if plain_text is not None and plain_text != "":
            # if self.database_password != "":
            #     return self._fernet.encrypt(bytes(plain_text, 'UTF-8')).decode("UTF-8")
            if self._database_password_bytes != b"":
                return self._fernet.encrypt(bytes(plain_text, 'UTF-8')).decode("UTF-8")
            else:
                return plain_text
        else:
            return ""

    def encrypt_string_with_custom_password(self, plain_text: str, password: str) -> str:
        if password == "":
            return plain_text
        _fernet = _create_fernet(self._salt, password.encode("UTF-8"), self._iteration_count)
        if plain_text is not None and plain_text != "":
            return _fernet.encrypt(bytes(plain_text, 'UTF-8')).decode("UTF-8")
        else:
            return ""

    def decrypt_string_if_password_is_present(self, encrypted_text: str) -> str:
        if encrypted_text == "" or encrypted_text is None:
            return ""
        if self._database_password_bytes != b"":
        # if self.database_password != "":
            decrypted_string = self._fernet.decrypt(bytes(encrypted_text, "UTF-8")).decode("UTF-8")
            return decrypted_string
        else:
            return encrypted_text

    # def decrypt_string_if_password_is_present_with_custom_password(self, encrypted_text: str, _database_password):
    #     if encrypted_text == "" or encrypted_text is None:
    #         return ""
    #     if _database_password != "":
    #         _fernet = create_fernet(self.salt, _database_password, self.iteration_count)
    #         decrypted_string = _fernet.decrypt(bytes(encrypted_text, "UTF-8")).decode("UTF-8")
    #         return decrypted_string
    #     else:
    #         return encrypted_text

    def add_account_and_encrypt(self, account: Account):
        account.name = self.encrypt_string_if_password_is_present(account.name)
        account.url = self.encrypt_string_if_password_is_present(account.url)
        account.loginname = self.encrypt_string_if_password_is_present(account.loginname)
        account.password = self.encrypt_string_if_password_is_present(account.password)
        account.type = self.encrypt_string_if_password_is_present(account.type)
        account.connector_type = self.encrypt_string_if_password_is_present(account.connector_type)
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            if account.uuid is None or account.uuid == "":
                account.uuid = uuid.uuid4()
            sqlstring = "insert into account (uuid, name, url, loginname, password, type, connector_type) values " + \
                        "('" + str(account.uuid) + \
                        "', '" + account.name + \
                        "', '" + account.url + \
                        "', '" + account.loginname + \
                        "', '" + account.password + \
                        "', '" + account.type + \
                        "', '" + account.connector_type + "')"
            cursor.execute(sqlstring)
            database_connection.commit()
            print("New account added: [UUID " + str(account.uuid) + "]")
        except sqlite3.IntegrityError:
            print("Error: UUID " + str(account.uuid) + " already exists in database!")
        except Exception:
            raise
        finally:
            database_connection.close()

    # def is_valid_database_password(self, _database_filename: str, _database_password: str) -> bool:
    #     try:
    #         value = get_attribute_value_from_configuration_table(_database_filename,
    #                                                              CONFIGURATION_TABLE_ATTRIBUTE_PASSWORD_TEST)
    #         if value is None or value == "":
    #             print("Could not fetch a valid DATABASE_PASSWORD_TEST value from configuration table.")
    #             return False
    #         if value == CONFIGURATION_TABLE_PASSWORD_TEST_VALUE_WHEN_NOT_ENCRYPTED and _database_password == "":
    #             print(colored("Warning: The account database " + _database_filename + " is NOT encrypted.", "red"))
    #             return True
    #         else:
    #             if _database_password == "":
    #                 return False
    #             else:
    #                 self.decrypt_string_if_password_is_present_with_custom_password(value, _database_password)
    #     except (InvalidSignature, InvalidToken) as e:
    #         return False
    #     return True

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

    def create_and_initialize_database(self, initial_database_name: str = None):
        database_connection = None
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
            #
            sqlstring = "select count(*) from account"
            sqlresult = cursor.execute(sqlstring)
            value = sqlresult.fetchone()[0]
            if value is not None:
                return
        except Exception as e:
            if str(e) == "database disk image is malformed":
                print(colored("Error: " + str(e), "red"))
                return
        finally:
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
            if self._database_password_bytes != b"":
            # if self.database_password != "":
                # print(colored("Creating an encrypted database with your password! Do not forget it!", 'green'))
                random_string = str(
                    binascii.hexlify(os.urandom(self._DATABASE_PASSWORD_TEST_VALUE_LENGTH)).decode('UTF-8'))
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

            # set an initial logical database name if wanted
            if initial_database_name is not None:
                set_attribute_value_in_configuration_table(self.database_filename,
                                                           CONFIGURATION_TABLE_ATTRIBUTE_DATABASE_NAME,
                                                           initial_database_name)

            # print("DATABASE_PASSWORD test value created and inserted into configuration table.")
        except Exception:
            raise
        finally:
            database_connection.close()

    def create_add_statements(self):
        results_found = 0
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            sqlstring = "select uuid, name, url, loginname, password, type, create_date, change_date, \
                         invalid_date from account"
            sqlresult = cursor.execute(sqlstring)
            result = sqlresult.fetchall()
            print()
            # if self.database_password != "":
            #     current_password = self.database_password.decode('UTF-8')
            # else:
            #     current_password = ""
            current_password = self.get_database_password_as_string()
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
        except Exception:
            raise
        finally:
            database_connection.close()
        print()
        print_found_n_results(results_found)

    # def get_database_password_as_string(self) -> str:
    #     if self.database_password == "":
    #         return ""
    #     return bytes(self.database_password).decode("UTF-8")

    def get_database_password_as_string(self) -> str:
        if self._database_password_bytes == b"":
            return ""
        return self._database_password_bytes.decode("UTF-8")

    def get_database_filename_without_path(self) -> str | None:
        if self.database_filename is not None and self.database_filename != "":
            return os.path.basename(self.database_filename)
        else:
            return None

    def _merge_database(self, merge_database_filename: str, merge_history_uuid: str) -> int:
        """ raises -1 in error case, 0 when no error and no changes where made,
        1 when changes where made locally and 2 when changes where made in remote db
        and 3 when changes where made locally and remote """

        merge_history_detail_string_list = ["Starting merge process"]

        if not os.path.exists(merge_database_filename):
            print("Error: merge database does not exist: '" + merge_database_filename + "'")
            append_merge_history_detail(self.database_filename, merge_history_uuid,
                                        "Error: merge database does not exist: '" + merge_database_filename + "'")
            # merge_history_detail_string_list.extend(
            #     ["Error: merge database does not exist: '" + merge_database_filename + "'"])
            # raise Exception("Error: merge database does not exist: '" + merge_database_filename + "'")
            return -1
        # print("Using merge database: " + merge_database_filename + ": " +
        #       get_database_identification_string(merge_database_filename))
        # Check remote db for password
        # print("Checking merge database password...")
        if not is_valid_database_password(merge_database_filename, self._database_password_bytes):
        # if not is_valid_database_password(merge_database_filename, self.database_password):
            print(colored("Error: because password for merge database: " + merge_database_filename +
                          " is not valid!", "red"))
            print("The database passwords must be the same in both databases.")
            print("")
            append_merge_history_detail(self.database_filename, merge_history_uuid,
                                        "Error: because password for merge database: " + merge_database_filename +
                                        " is not valid!")
            # merge_history_detail_string_list.extend(
            #     ["Error: because password for merge database: " + merge_database_filename +
            #      " is not valid!"])
            # print("---->")
            # raise Exception("Error: because password for merge database: " + merge_database_filename +
            #      " is not valid!")
            return -1
        # Set some attribute values in configuration table and create some attributes if not exist
        set_attribute_value_in_configuration_table(self.database_filename,
                                                   CONFIGURATION_TABLE_ATTRIBUTE_LAST_MERGE_DATABASE,
                                                   get_database_identification_string(merge_database_filename))
        set_attribute_value_in_configuration_table(self.database_filename,
                                                   CONFIGURATION_TABLE_ATTRIBUTE_LAST_MERGE_DATE,
                                                   "")
        set_attribute_value_in_configuration_table(merge_database_filename,
                                                   CONFIGURATION_TABLE_ATTRIBUTE_LAST_MERGE_DATE,
                                                   "")
        # Start merging
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            # print("Attaching merge database...")
            # append_merge_history_detail(self.database_filename, merge_history_uuid,
            #                             "Attaching merge database " + merge_database_filename)
            merge_history_detail_string_list.extend(["Attaching merge database " + merge_database_filename])
            sqlstring = "attach '" + merge_database_filename + "' as merge_database"
            cursor.execute(sqlstring)

            # print("Updating merge database schema...")
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
            # print(colored("Step #0: Synchronizing deleted accounts in local and remote database...", "green"))
            # append_merge_history_detail(self.database_filename, merge_history_uuid,
            #                             "Step #0: Synchronizing deleted accounts in local and remote database...")
            merge_history_detail_string_list.extend(
                ["Step #0: Synchronizing deleted accounts in local and remote database..."])
            if len(deleted_uuids_in_remote_db_not_in_local) > 0:
                print("Found " + colored(str(len(deleted_uuids_in_remote_db_not_in_local)), "red") +
                      " account(s) in remote db which are not in local deleted_account table...")
                # append_merge_history_detail(self.database_filename, merge_history_uuid,
                #                             "Found " + str(len(deleted_uuids_in_remote_db_not_in_local)) +
                #                             " account(s) in remote db which are not in local deleted_account table...")
                merge_history_detail_string_list.extend(["Found " + str(len(deleted_uuids_in_remote_db_not_in_local)) +
                                                         " account(s) in remote db which are not in local deleted_account table..."])
            for delete_uuid in deleted_uuids_in_remote_db_not_in_local:
                print("Searching account with UUID " + delete_uuid + " in local database:")
                # append_merge_history_detail(self.database_filename, merge_history_uuid,
                #                             "Searching account with UUID " + delete_uuid + " in local database:")
                merge_history_detail_string_list.extend(
                    ["Searching account with UUID " + delete_uuid + " in local database:"])
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
                # append_merge_history_detail(self.database_filename, merge_history_uuid,
                #                             "UUID " + delete_uuid + " added to local deleted_account table.")
                merge_history_detail_string_list.extend(
                    ["UUID " + delete_uuid + " added to local deleted_account table."])
            if len(deleted_uuids_in_local_db_note_in_remote) > 0:
                # print("Deleting " + colored(str(len(deleted_uuids_in_local_db_note_in_remote)), "red") +
                #       " account(s) in remote db which have been deleted in local db...")
                # append_merge_history_detail(self.database_filename, merge_history_uuid,
                #                             "Deleting " + str(len(deleted_uuids_in_local_db_note_in_remote)) +
                #                             " account(s) in remote db which have been deleted in local db...")
                merge_history_detail_string_list.extend(
                    ["Deleting " + str(len(deleted_uuids_in_local_db_note_in_remote)) +
                     " account(s) in remote db which have been deleted in local db..."])
            for delete_uuid in deleted_uuids_in_local_db_note_in_remote:
                cursor.execute("delete from merge_database.account where uuid = '" + delete_uuid + "'")
                cursor.execute("insert into merge_database.deleted_account (uuid) values ('" +
                               self.encrypt_string_if_password_is_present(delete_uuid) + "')")
            # print(str(len(deleted_uuids_in_local_db_note_in_remote)) + " Account(s) deleted.")
            # append_merge_history_detail(self.database_filename, merge_history_uuid,
            #                             str(len(deleted_uuids_in_local_db_note_in_remote)) + " Account(s) deleted.")
            merge_history_detail_string_list.extend(
                [str(len(deleted_uuids_in_local_db_note_in_remote)) + " Account(s) deleted."])
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
            # print(colored("Step #1: Analyzing Origin Database - " + self.database_filename
            #               + " " + get_database_name(self.database_filename), "green"))
            # append_merge_history_detail(self.database_filename, merge_history_uuid,
            #                             "Step #1: Analyzing Origin Database - " + self.database_filename
            #                             + " " + get_database_name(self.database_filename))
            merge_history_detail_string_list.extend(["Step #1: Analyzing Origin Database - " + self.database_filename
                                                     + " " + get_database_name(self.database_filename)])
            # print("Dropping update_date trigger (origin database)...")
            cursor.execute(SQL_MERGE_DROP_LOCAL_ACCOUNT_CHANGE_DATE_TRIGGER)
            # print("Updating " + colored(str(count_uuids_in_remote_with_newer_update_date_than_in_local), "red")
            #       + " local account(s) that have newer change dates in the remote database...")
            # append_merge_history_detail(self.database_filename, merge_history_uuid,
            #                             "Updating " + str(count_uuids_in_remote_with_newer_update_date_than_in_local)
            #                             + " local account(s) that have newer change dates in the remote database...")
            merge_history_detail_string_list.extend(
                ["Updating " + str(count_uuids_in_remote_with_newer_update_date_than_in_local)
                 + " local account(s) that have newer change dates in the remote database..."])
            cursor.execute(SQL_MERGE_DELETE_ACCOUNTS_IN_ORIGIN_THAT_EXIST_IN_REMOTE_WITH_NEWER_CHANGE_DATE)
            # print("Fetching " + colored(str(count_uuids_in_remote_that_do_not_exist_in_local), "red")
            #       + " new account(s) from the remote database into the origin database...")
            # append_merge_history_detail(self.database_filename, merge_history_uuid,
            #                             "Fetching " + str(count_uuids_in_remote_that_do_not_exist_in_local)
            #                             + " new account(s) from the remote database into the origin database...")
            merge_history_detail_string_list.extend(["Fetching " + str(count_uuids_in_remote_that_do_not_exist_in_local)
                                                     + " new account(s) from the remote database into the origin database..."])
            cursor.execute(SQL_MERGE_INSERT_MISSING_UUIDS_FROM_REMOTE_INTO_ORIGIN_DATABASE)

            # print("Fetching " + colored(str(count_history_uuids_in_remote_that_do_not_exist_in_local), "red")
            #       + " new account history entries from the remote database into the origin database...")
            # append_merge_history_detail(self.database_filename, merge_history_uuid,
            #                             "Fetching " + str(count_history_uuids_in_remote_that_do_not_exist_in_local)
            #                             + " new account history entries from the remote database into the origin "
            #                               "database...")
            merge_history_detail_string_list.extend(
                ["Fetching " + str(count_history_uuids_in_remote_that_do_not_exist_in_local)
                 + " new account history entries from the remote database into the origin "
                   "database..."])
            cursor.execute(SQL_MERGE_INSERT_MISSING_HISTORY_UUIDS_FROM_REMOTE_INTO_ORIGIN_DATABASE)

            # print("Re-Creating update_date trigger (origin database)...")
            cursor.execute(SQL_MERGE_CREATE_LOCAL_ACCOUNT_CHANGE_DATE_TRIGGER)
            # print("Origin database is now up to date (" +
            #       colored(str(count_uuids_in_remote_with_newer_update_date_than_in_local +
            #                   count_uuids_in_remote_that_do_not_exist_in_local +
            #                   count_history_uuids_in_remote_that_do_not_exist_in_local +
            #                   len(deleted_uuids_in_remote_db_not_in_local)), "red") + " changes have been done)")
            # append_merge_history_detail(self.database_filename, merge_history_uuid,
            #                             "Origin database is now up to date (" +
            #                             str(count_uuids_in_remote_with_newer_update_date_than_in_local +
            #                                 count_uuids_in_remote_that_do_not_exist_in_local +
            #                                 count_history_uuids_in_remote_that_do_not_exist_in_local +
            #                                 len(deleted_uuids_in_remote_db_not_in_local)) + " changes have been done)")
            merge_history_detail_string_list.extend(["Origin database is now up to date (" +
                                                     str(count_uuids_in_remote_with_newer_update_date_than_in_local +
                                                         count_uuids_in_remote_that_do_not_exist_in_local +
                                                         count_history_uuids_in_remote_that_do_not_exist_in_local +
                                                         len(deleted_uuids_in_remote_db_not_in_local)) + " changes have been done)"])
            # remember that there were changes in local db for return code:
            return_code = 0
            if count_uuids_in_remote_with_newer_update_date_than_in_local + \
                    count_uuids_in_remote_that_do_not_exist_in_local > 0:
                return_code = 1
            database_connection.commit()
            #
            # Step #2 Sync new accounts from main database into remote database
            #
            # print(colored("Step #2: Analyzing Remote Database - " + merge_database_filename
            #               + " " + get_database_name(merge_database_filename), "green"))
            # append_merge_history_detail(self.database_filename, merge_history_uuid,
            #                             "Step #2: Analyzing Remote Database - " + merge_database_filename
            #                             + " " + get_database_name(merge_database_filename))
            merge_history_detail_string_list.extend(["Step #2: Analyzing Remote Database - " + merge_database_filename
                                                     + " " + get_database_name(merge_database_filename)])
            # print("Dropping update_date trigger (remote database)...")
            cursor.execute(SQL_MERGE_DROP_REMOTE_ACCOUNT_CHANGE_DATE_TRIGGER)
            # print("Updating " + colored(str(count_uuids_in_local_with_newer_update_date_than_in_remote), "red")
            #       + " remote account(s) that have newer change dates in the origin database...")
            # append_merge_history_detail(self.database_filename, merge_history_uuid,
            #                             "Updating " + str(count_uuids_in_local_with_newer_update_date_than_in_remote)
            #                             + " remote account(s) that have newer change dates in the origin database...")
            merge_history_detail_string_list.extend(
                ["Updating " + str(count_uuids_in_local_with_newer_update_date_than_in_remote)
                 + " remote account(s) that have newer change dates in the origin database..."])
            cursor.execute(SQL_MERGE_DELETE_ACCOUNTS_IN_REMOTE_THAT_EXIST_IN_ORIGIN_WITH_NEWER_CHANGE_DATE)
            # print("Pushing " + colored(str(count_uuids_in_local_that_do_not_exist_in_remote), "red")
            #       + " new account(s) from the origin database into the remote database...")
            # append_merge_history_detail(self.database_filename, merge_history_uuid,
            #                             "Pushing " + str(count_uuids_in_local_that_do_not_exist_in_remote)
            #                             + " new account(s) from the origin database into the remote database...")
            merge_history_detail_string_list.extend(["Pushing " + str(count_uuids_in_local_that_do_not_exist_in_remote)
                                                     + " new account(s) from the origin database into the remote database..."])
            cursor.execute(SQL_MERGE_INSERT_MISSING_UUIDS_FROM_ORIGIN_INTO_REMOTE_DATABASE)

            # print("Pushing " + colored(str(count_history_uuids_in_local_that_do_not_exist_in_remote), "red")
            #       + " new account history entries from the origin database into the remote database...")
            # append_merge_history_detail(self.database_filename, merge_history_uuid,
            #                             "Pushing " + str(count_history_uuids_in_local_that_do_not_exist_in_remote)
            #                             + " new account history entries from the origin database into the remote "
            #                               "database...")
            merge_history_detail_string_list.extend(
                ["Pushing " + str(count_history_uuids_in_local_that_do_not_exist_in_remote)
                 + " new account history entries from the origin database into the remote "
                   "database..."])
            cursor.execute(SQL_MERGE_INSERT_MISSING_HISTORY_UUIDS_FROM_ORIGIN_INTO_REMOTE_DATABASE)

            # print("Re-Creating update_date trigger (remote database)...")
            cursor.execute(SQL_MERGE_CREATE_REMOTE_ACCOUNT_CHANGE_DATE_TRIGGER)
            # Remember date of current merge action in origin and remote database
            cursor.execute("update configuration set value = datetime(CURRENT_TIMESTAMP, 'localtime')" +
                           " where attribute = ?", [CONFIGURATION_TABLE_ATTRIBUTE_LAST_MERGE_DATE])
            cursor.execute("update merge_database.configuration set value = datetime(CURRENT_TIMESTAMP, 'localtime')" +
                           " where attribute = ?", [CONFIGURATION_TABLE_ATTRIBUTE_LAST_MERGE_DATE])
            # print("Remote database is now up to date (" +
            #       colored(str(count_uuids_in_local_with_newer_update_date_than_in_remote +
            #                   count_uuids_in_local_that_do_not_exist_in_remote +
            #                   count_history_uuids_in_local_that_do_not_exist_in_remote +
            #                   len(deleted_uuids_in_local_db_note_in_remote)), "red") + " changes have been done)")
            # append_merge_history_detail(self.database_filename, merge_history_uuid,
            #                             "Remote database is now up to date (" +
            #                             str(count_uuids_in_local_with_newer_update_date_than_in_remote +
            #                                 count_uuids_in_local_that_do_not_exist_in_remote +
            #                                 count_history_uuids_in_local_that_do_not_exist_in_remote +
            #                                 len(deleted_uuids_in_local_db_note_in_remote)) + "changes have "
            #                                                                                  "been done)")
            merge_history_detail_string_list.extend(["Remote database is now up to date (" +
                                                     str(count_uuids_in_local_with_newer_update_date_than_in_remote +
                                                         count_uuids_in_local_that_do_not_exist_in_remote +
                                                         count_history_uuids_in_local_that_do_not_exist_in_remote +
                                                         len(deleted_uuids_in_local_db_note_in_remote)) + " changes have "
                                                                                                          "been done)"])
            # Finally commit it
            database_connection.commit()
            # remember that there were changes in remote db for return code
            # (and also check for deleted accs in remote db):
            if (
                    count_uuids_in_local_with_newer_update_date_than_in_remote + count_uuids_in_local_that_do_not_exist_in_remote > 0) or (
                    len(deleted_uuids_in_local_db_note_in_remote) > 0):
                return_code += 2
        except Exception:
            raise
        finally:
            database_connection.close()
            for string in merge_history_detail_string_list:
                append_merge_history_detail(self.database_filename, merge_history_uuid, string)
        return return_code

    def delete_from_account_history_table(self):
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            sqlstring = SQL_DELETE_ALL_FROM_ACCOUNT_HISTORY
            self.set_database_pragmas_to_secure_mode(database_connection, cursor)
            self.print_current_secure_delete_mode(cursor)
            cursor.execute(sqlstring)
            database_connection.commit()
        except Exception:
            raise
        finally:
            database_connection.close()

    def delete_from_deleted_account_table(self):
        database_connection = None
        try:
            database_connection = sqlite3.connect(self.database_filename)
            cursor = database_connection.cursor()
            sqlstring = SQL_DELETE_ALL_FROM_DELETED_ACCOUNT
            self.set_database_pragmas_to_secure_mode(database_connection, cursor)
            self.print_current_secure_delete_mode(cursor)
            cursor.execute(sqlstring)
            database_connection.commit()
        except Exception:
            raise
        finally:
            database_connection.close()

    def _create_initial_connector_database_interactive(self, database_filename: str) -> bool:
        print("Connector database does not yet exist.")
        print("Creating initial database...")
        if os.path.isfile(database_filename):
            os.remove(database_filename)
        try:
            new_database_name = input("Enter logical database name : ")
        except KeyboardInterrupt:
            print()
            print("Canceled")
            return False
        PDatabase(database_filename, self.get_database_password_as_string())
        set_attribute_value_in_configuration_table(database_filename,
                                                   CONFIGURATION_TABLE_ATTRIBUTE_DATABASE_NAME,
                                                   new_database_name)
        return True

    def _merge_database_with_file_connector(self, connector: ConnectorInterface, merge_history_uuid: str):
        if connector.get_type() != "file":
            raise Exception("Connector type is not 'file'")

        file_merge_bar = progressbar.ProgressBar(maxval=3)
        file_merge_bar.start()
        try:
            if not connector.exists(self.get_database_filename_without_path()):
                if not self._create_initial_connector_database_interactive(os.path.join(connector.get_remote_base_path(),
                                                                           os.path.basename(self.database_filename))):
                    return
            file_merge_bar.update(1)
            return_code = self._merge_database(
                os.path.join(connector.get_remote_base_path(), os.path.basename(self.database_filename)),
                merge_history_uuid)
            file_merge_bar.update(2)
            append_merge_history(merge_history_uuid=merge_history_uuid,
                                 database_filename=self.database_filename,
                                 database_uuid_local=get_database_uuid(self.database_filename),
                                 database_name_local=get_database_name(self.database_filename),
                                 database_uuid_remote=get_database_uuid(os.path.join(connector.get_remote_base_path(),
                                                                                     os.path.basename(
                                                                                         self.database_filename))),
                                 database_name_remote=get_database_name(os.path.join(connector.get_remote_base_path(),
                                                                                     os.path.basename(
                                                                                         self.database_filename))),
                                 connector=str(connector),
                                 connector_type=connector.get_type(),
                                 return_code=str(return_code)
                                 )
            file_merge_bar.update(3)
            return
        except Exception:
            raise
        finally:
            file_merge_bar.finish()



    def merge_database_with_connector(self, connector: ConnectorInterface):
        merge_history_uuid = str(uuid.uuid4())

        if connector.get_type() == "file":
            self._merge_database_with_file_connector(connector, merge_history_uuid)
            return
            # file_merge_bar = progressbar.ProgressBar(maxval=4)
            # if not connector.exists(self.get_database_filename_without_path()):
            #     if not self._create_initial_connector_database_interactive(
            #             os.path.join(connector.get_remote_base_path(),
            #                          os.path.basename(
            #                              self.database_filename))):
            #         return
            # return_code = self._merge_database(
            #     os.path.join(connector.get_remote_base_path(), os.path.basename(self.database_filename)),
            #     merge_history_uuid)
            # append_merge_history(merge_history_uuid=merge_history_uuid,
            #                      database_filename=self.database_filename,
            #                      database_uuid_local=get_database_uuid(self.database_filename),
            #                      database_name_local=get_database_name(self.database_filename),
            #                      database_uuid_remote=get_database_uuid(os.path.join(connector.get_remote_base_path(),
            #                                                                          os.path.basename(
            #                                                                              self.database_filename))),
            #                      database_name_remote=get_database_name(os.path.join(connector.get_remote_base_path(),
            #                                                                          os.path.basename(
            #                                                                              self.database_filename))),
            #                      connector=str(connector),
            #                      connector_type=connector.get_type(),
            #                      return_code=str(return_code)
            #                      )
            # return

        if not connector.exists(self.get_database_filename_without_path()):
            if not self._create_initial_connector_database_interactive(TEMP_MERGE_DATABASE_FILENAME):
                return
            # print("--->yes")
            # print("Merging local database into initial remote database...")
            append_merge_history_detail(self.database_filename, merge_history_uuid,
                                        "Merging local database into initial remote database...")
            self._merge_database(TEMP_MERGE_DATABASE_FILENAME, merge_history_uuid)
            # print("Uploading initial database: '" +
            #       TEMP_MERGE_DATABASE_FILENAME + "' as '" +
            #       self.get_database_filename_without_path() + "' to connector...")
            append_merge_history_detail(self.database_filename, merge_history_uuid,
                                        "Uploading initial database: '" +
                                        TEMP_MERGE_DATABASE_FILENAME + "' as '" +
                                        self.get_database_filename_without_path() + "' to connector...")
            local_path = os.path.dirname(TEMP_MERGE_DATABASE_FILENAME)
            connector.upload_file(os.path.join(local_path, TEMP_MERGE_DATABASE_FILENAME),
                                  self.get_database_filename_without_path())
            append_merge_history(merge_history_uuid=merge_history_uuid,
                                 database_filename=self.database_filename,
                                 database_uuid_local=get_database_uuid(self.database_filename),
                                 database_name_local=get_database_name(self.database_filename),
                                 database_uuid_remote=get_database_uuid(TEMP_MERGE_DATABASE_FILENAME),
                                 database_name_remote=get_database_name(TEMP_MERGE_DATABASE_FILENAME),
                                 connector=str(connector),
                                 connector_type=connector.get_type()
                                 )
            os.remove(TEMP_MERGE_DATABASE_FILENAME)
            return
        bar = progressbar.ProgressBar(maxval=4)
        bar.start()
        bar.update(1)
        # print("Downloading database...")
        append_merge_history_detail(self.database_filename, merge_history_uuid, "Downloading database...")
        local_path = os.path.dirname(TEMP_MERGE_DATABASE_FILENAME)
        connector.download_file(self.get_database_filename_without_path(),
                                TEMP_MERGE_DATABASE_FILENAME)
        # print("Merging databases...")
        append_merge_history_detail(self.database_filename, merge_history_uuid, "Merging databases...")
        bar.update(2)
        return_code = self._merge_database(TEMP_MERGE_DATABASE_FILENAME, merge_history_uuid=merge_history_uuid)
        bar.update(3)
        if return_code > 1:
            # print("Uploading merged database...")
            append_merge_history_detail(self.database_filename, merge_history_uuid, "Uploading merged database...")
            connector.upload_file(os.path.join(local_path, TEMP_MERGE_DATABASE_FILENAME),
                                  self.get_database_filename_without_path())

        else:
            # print("No changes in remote database. Skipping upload.")
            append_merge_history_detail(self.database_filename, merge_history_uuid,
                                        "No changes in remote database. Skipping upload.")
        append_merge_history(merge_history_uuid=merge_history_uuid,
                             database_filename=self.database_filename,
                             database_uuid_local=get_database_uuid(self.database_filename),
                             database_name_local=get_database_name(self.database_filename),
                             database_uuid_remote=get_database_uuid(TEMP_MERGE_DATABASE_FILENAME),
                             database_name_remote=get_database_name(TEMP_MERGE_DATABASE_FILENAME),
                             connector=str(connector),
                             connector_type=connector.get_type(),
                             return_code=str(return_code)
                             )
        os.remove(TEMP_MERGE_DATABASE_FILENAME)
        bar.finish()


"""
database_password must be a string.encode("UTF-8")
"""


def is_valid_database_password(_database_filename: str, _database_password_bytes: bytes) -> bool:
    try:
        value = get_attribute_value_from_configuration_table(_database_filename,
                                                             CONFIGURATION_TABLE_ATTRIBUTE_PASSWORD_TEST)
        if value is None or value == "":
            print("Could not fetch a valid DATABASE_PASSWORD_TEST value from configuration table.")
            return False
        if value == CONFIGURATION_TABLE_PASSWORD_TEST_VALUE_WHEN_NOT_ENCRYPTED and _database_password_bytes == b"":
            print(colored("Warning: The account database " + _database_filename + " is NOT encrypted.", "red"))
            return True
        else:
            if _database_password_bytes == b"":
                return False
            else:
                decrypt_string_if_password_is_present_with_custom_password(value, _database_password_bytes)
    except (InvalidSignature, InvalidToken):
        return False
    return True


def decrypt_string_if_password_is_present_with_custom_password(encrypted_text: str, _database_password):
    if encrypted_text == "" or encrypted_text is None:
        return ""
    if _database_password != "":
        _fernet = _create_fernet(DEFAULT_SALT, _database_password, DEFAULT_ITERATION_COUNT)
        decrypted_string = _fernet.decrypt(bytes(encrypted_text, "UTF-8")).decode("UTF-8")
        return decrypted_string
    else:
        return encrypted_text


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
