#
# 20221206 Jens Heine <binbash@gmx.net>
#
# thanks to matt clarke
# for his example: https://practicaldatascience.co.uk/data-science/how-to-use-the-dropbox-api-with-python
#
import pathlib
# import pandas as pd
import dropbox
from dropbox.exceptions import AuthError
import webbrowser
import base64
import requests
import json

DROPBOX_P_DATABASE_FILENAME = "p.db"


# def create_dropbox_connection_with_access_token(access_token):
#     try:
#         dropbox_connection = dropbox.Dropbox(access_token)
#     except AuthError as e:
#         print('Error connecting to Dropbox with access token: ' + str(e))
#         return None
#         # raise
#     return dropbox_connection


def create_dropbox_connection_with_refresh_token(_app_key, _app_secret, _refresh_token) -> dropbox.Dropbox:
    try:
        dropbox_connection = dropbox.Dropbox(app_key=_app_key, app_secret=_app_secret,
                                             oauth2_refresh_token=_refresh_token)
        # execute a dummy command to raise an exception if connection is not possible
        dropbox_connection.files_list_folder('')
#     except AuthError as e:
    except Exception as e:
        print('Error connecting to Dropbox with refresh token: ' + str(e))
        return None
        # raise
    return dropbox_connection



# def dropbox_list_files(dropbox_connection, path):
#     # Return a Pandas dataframe of files in a given Dropbox folder path in the Apps directory.
#     # dropbox_connection = dropbox_connect(access_token)
#     try:
#         files = dropbox_connection.files_list_folder(path).entries
#         files_list = []
#         for file in files:
#             if isinstance(file, dropbox.files.FileMetadata):
#                 metadata = {
#                     'name': file.name,
#                     'path_display': file.path_display,
#                     'client_modified': file.client_modified,
#                     'server_modified': file.server_modified
#                 }
#                 files_list.append(metadata)
#         df = pd.DataFrame.from_records(files_list)
#         return df.sort_values(by='server_modified', ascending=False)
#     except Exception as e:
#         print('Error getting list of files from Dropbox: ' + str(e))
#         raise



def dropbox_file_exists(dropbox_connection, path, filename):
    # dropbox_connection = dropbox_connect(access_token)
    try:
        files = dropbox_connection.files_list_folder(path).entries
        for file in files:
            if isinstance(file, dropbox.files.FileMetadata):
                # print("filename - " + file.name)
                # print("search   - " + filename)
                if file.name == filename:
                    return True
    except AuthError as e:
        print('Error getting list of files from Dropbox: ' + str(e))
        raise
    return False


def dropbox_download_file(dropbox_connection, dropbox_file_path, local_file_path):
    # Download a file from Dropbox to the local machine."""
    try:
        # dropbox_connection = dropbox_connect(access_token)
        with open(local_file_path, 'wb') as f:
            metadata, result = dropbox_connection.files_download(path=dropbox_file_path)
            f.write(result.content)
    except Exception as e:
        print('Error downloading file from Dropbox: ' + str(e))
        raise


def dropbox_delete_file(dropbox_connection, dropbox_file_path):
    try:
        # dropbox_connection = dropbox_connect(access_token)
        dropbox_connection.files_delete_v2(dropbox_file_path)
    except Exception as e:
        print('Error deleting file from Dropbox: ' + str(e))
        raise


def dropbox_upload_file(dropbox_connection, local_path, local_file, dropbox_file_path):
    """Upload a file from the local machine to a path in the Dropbox app directory.
    Args:
        local_path (str): The path to the local file.
        local_file (str): The name of the local file.
        dropbox_file_path (str): The path to the file in the Dropbox app directory.

    Example:
        dropbox_upload_file('.', 'test.csv', '/stuff/test.csv')

    Returns:
        meta: The Dropbox file metadata.
    """
    try:
        # dropbox_connection = dropbox_connect(access_token)
        local_file_path = pathlib.Path(local_path) / local_file
        with local_file_path.open("rb") as f:
            meta = dropbox_connection.files_upload(f.read(), dropbox_file_path,
                                                   mode=dropbox.files.WriteMode("overwrite"))
            return meta
    except Exception as e:
        print('Error uploading file to Dropbox: ' + str(e))
        raise


def get_generated_access_code(app_key: str):
    url = f'https://www.dropbox.com/oauth2/authorize?client_id={app_key}&' \
          f'response_type=code&token_access_type=offline'
    webbrowser.open(url)


def get_refresh_access_token(app_key: str, app_secret: str, access_code_generated: str) -> str:
    basic_auth = base64.b64encode(f'{app_key}:{app_secret}'.encode())
    headers = {
        'Authorization': f"Basic {basic_auth}",
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    data = f'code={access_code_generated}&grant_type=authorization_code'
    response = requests.post('https://api.dropboxapi.com/oauth2/token',
                             data=data,
                             auth=(app_key, app_secret))
    refresh_token_str = response.text[response.text.index('refresh_token": "')+17:response.text.index('"scope": "')-3]
    #print("->" + refresh_token_str)
    print("Result from api call:")
    print(json.dumps(json.loads(response.text), indent=2))
    print()
    return refresh_token_str


def main():
    # dropbox_connect()
    # print(dropbox_list_files(""))
    # #dropbox_upload_file(".", "p.py", "/p.py")
    # print(dropbox_list_files(""))
    # token = "asdasd"
    # dropbox_delete_file(token, "/p.db")

    app_key = "qqq"
    app_secret = "qqq"
    # get_generated_access_code(app_key)
    access_code_generated = "qqq"
    # refresh_token = "qqq"
    # print("get refresh token")
    # refresh_token = get_fresh_access_token(app_key, app_secret, access_code_generated)

    refresh_token = "qqq"

    print("refresh token: " + refresh_token)
    print("get dropbox connection")
    dropbox_connection = create_dropbox_connection_with_refresh_token(app_key, app_secret, refresh_token)
    print("do thing with connection")
    # print("connection: " + dropbox_connection)
    # dropbox_list_files(dropbox_connection, "")
    print(dropbox_file_exists(dropbox_connection, "", "p.db"))
    return


if __name__ == '__main__':
    main()
