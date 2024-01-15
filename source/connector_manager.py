"""
20240115 jens heine
pshell - p the password manager

The connector manager is responsible for all the stuff that has to do with connectors. A connector can be
a file connector or a dropbox connector. These objects are used to merge p databases to different locations.
"""

import pdatabase
import ssh_connector
import dropbox_connector
import webdav_connector
import file_connector
# from termcolor import colored
import connector_interface


def get_dropbox_connector(p_database: pdatabase, account_uuid: str = None) -> dropbox_connector.DropboxConnector:
    if account_uuid is None:
        account_uuid = pdatabase.get_attribute_value_from_configuration_table(p_database.database_filename,
                                                                              pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_CONNECTOR_DEFAULT_DROPBOX_ACCOUNT_UUID)
    if account_uuid is None or str(account_uuid).strip() == "":
        raise Exception("Error: no default dropbox account uuid in configuration found.")
    account = p_database.get_account_by_uuid_and_decrypt(account_uuid)
    if account is None:
        raise Exception("Error: Account uuid " + account_uuid + " not found.")

    if account.connector_type != "dropbox":
        raise Exception("Error: expected connector type dropbox but got: " + account.connector_type)

    dropbox_application_key = account.url.strip()
    if dropbox_application_key == "":
        raise Exception("Dropbox application key not found in dropbox account in column URL.")
    dropbox_application_secret = account.loginname.strip()
    if dropbox_application_secret == "":
        raise Exception("Dropbox application secret not found in dropbox account in column LOGIN.")
    access_token = account.password.strip()
    if access_token == "":
        raise Exception("Dropbox access token not found in dropbox account in column PASSWORD.")
    connector = dropbox_connector.DropboxConnector(dropbox_application_key, dropbox_application_secret, access_token)
    return connector


def get_ssh_connector(p_database: pdatabase, account_uuid: str = None) -> ssh_connector.SshConnector:
    if account_uuid is None:
        account_uuid = pdatabase.get_attribute_value_from_configuration_table(p_database.database_filename,
                                                                              pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_CONNECTOR_DEFAULT_SSH_ACCOUNT_UUID)
    if account_uuid is None or str(account_uuid).strip() == "":
        raise Exception("Error: no default ssh account uuid in configuration found.")
    account = p_database.get_account_by_uuid_and_decrypt(account_uuid)
    if account is None:
        raise Exception("Error: Account uuid " + account_uuid + " not found.")

    if account.connector_type != "ssh":
        raise Exception("Error: expected connector type ssh but got: " + account.connector_type)

    ssh_server_url = account.url.strip()
    if ssh_server_url == "":
        raise Exception("SSH server url not found in ssh account in column URL.")
    ssh_login = account.loginname.strip()
    if ssh_login == "":
        raise Exception("SSH login name not found in ssh account in column LOGIN.")
    ssh_password = account.password.strip()
    if ssh_password == "":
        raise Exception("SSH password not found in ssh account in column PASSWORD.")
    connector = ssh_connector.SshConnector(ssh_server_url, ssh_login, ssh_password)
    return connector


def get_webdav_connector(p_database: pdatabase, account_uuid: str = None) -> webdav_connector.WebdavConnector:
    if account_uuid is None:
        account_uuid = pdatabase.get_attribute_value_from_configuration_table(p_database.database_filename,
                                                                              pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_CONNECTOR_DEFAULT_WEBDAV_ACCOUNT_UUID)
    if account_uuid is None or str(account_uuid).strip() == "":
        raise Exception("Error: no default webdav account uuid in configuration found.")
    account = p_database.get_account_by_uuid_and_decrypt(account_uuid)
    if account is None:
        raise Exception("Error: Account uuid " + account_uuid + " not found.")

    if account.connector_type != "webdav":
        raise Exception("Error: expected connector type webdav but got: " + account.connector_type)

    dav_url = account.url.strip()
    if dav_url == "":
        raise Exception("Webdav server url not found in webdav account in column URL.")
    dav_login = account.loginname.strip()
    if dav_login == "":
        raise Exception("Webdav login name not found in webdav account in column LOGIN.")
    dav_password = account.password.strip()
    if dav_password == "":
        raise Exception("Webdav password not found in webdav account in column PASSWORD.")
    connector = webdav_connector.WebdavConnector(dav_url, dav_login, dav_password)
    return connector


def get_file_connector(p_database: pdatabase, account_uuid: str = None) -> file_connector.FileConnector:
    if account_uuid is None:
        account_uuid = pdatabase.get_attribute_value_from_configuration_table(p_database.database_filename,
                                                                              pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_CONNECTOR_DEFAULT_FILE_ACCOUNT_UUID)
    if account_uuid is None or str(account_uuid).strip() == "":
        raise Exception("Error: no default webdav account uuid in configuration found.")
    account = p_database.get_account_by_uuid_and_decrypt(account_uuid)
    if account is None:
        raise Exception("Error: Account uuid " + account_uuid + " not found.")

    if account.connector_type != "file":
        raise Exception("Error: expected connector type file but got: " + account.connector_type)

    url = account.url.strip()
    if url == "":
        raise Exception("File url not found in file account in column URL.")
    connector = file_connector.FileConnector(url)
    return connector


def get_connector(p_database: pdatabase, account_uuid: str = None) -> connector_interface.ConnectorInterface:
    if account_uuid is None:
        raise Exception("Error: Account UUID is not set.")
    account = p_database.get_account_by_uuid_and_decrypt(account_uuid)
    if account is None:
        raise Exception("Error: Account uuid " + account_uuid + " not found.")
    if account.connector_type == "dropbox":
        return get_dropbox_connector(p_database, account_uuid)
    if account.connector_type == "ssh":
        return get_ssh_connector(p_database, account_uuid)
    if account.connector_type == "webdav":
        return get_webdav_connector(p_database, account_uuid)
    if account.connector_type == "file":
        return get_file_connector(p_database, account_uuid)
    raise Exception("Error: unknown connector type: " + account.connector_type)
