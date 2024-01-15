"""
20240115 jens heine
pshell - p the password manager

The connector manager is responsible for all the stuff that has to do with connectors. A connector can be
a file connector or a dropbox connector. These objects are used to merge p databases to different locations.
"""

import pdatabase
import ssh_connector
import dropbox_connector
import file_connector
from termcolor import colored


def get_dropbox_connector(p_database: pdatabase, dropbox_account_uuid: str = None) -> dropbox_connector:
    if dropbox_account_uuid is None:
        dropbox_account_uuid = pdatabase.get_attribute_value_from_configuration_table(p_database.database_filename,
                                                                                      pdatabase.CONFIGURATION_TABLE_ATTRIBUTE_DROPBOX_ACCOUNT_UUID)
    if dropbox_account_uuid is None or str(dropbox_account_uuid).strip() == "":
        raise Exception("Error: no default dropbox account uuid in configuration found.")
    dropbox_account = p_database.get_account_by_uuid_and_decrypt(dropbox_account_uuid)
    if dropbox_account is None:
        raise Exception("Error: Account uuid " + dropbox_account_uuid + " not found.")

    dropbox_application_key = dropbox_account.url.strip()
    if dropbox_application_key == "":
        raise Exception("Dropbox application key not found in dropbox account in column URL.")
    dropbox_application_secret = dropbox_account.loginname.strip()
    if dropbox_application_secret == "":
        raise Exception("Dropbox application secret not found in dropbox account in column LOGIN.")
    access_token = dropbox_account.password.strip()
    if access_token == "":
        raise Exception("Dropbox access token not found in dropbox account in column PASSWORD.")
    connector = dropbox_connector.DropboxConnector(dropbox_application_key, dropbox_application_secret, access_token)
    return connector
