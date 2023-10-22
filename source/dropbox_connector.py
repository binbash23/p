#
# 20231018 Jens Heine <binbash@gmx.net>
#
# thanks to matt clarke
# for his example: https://practicaldatascience.co.uk/data-science/how-to-use-the-dropbox-api-with-python
#
import base64
import json
import pathlib
import webbrowser

import dropbox
import requests
from dropbox.exceptions import AuthError

from connector_interface import ConnectorInterface


class DropboxConnector(ConnectorInterface):
    _dropbox_connection = None
    _app_key = None
    _app_secret = None
    _refresh_token = None

    def __init__(self, app_key, app_secret, refresh_token):
        self._app_key = app_key
        self._app_secret = app_secret
        self._refresh_token = refresh_token
        self._dropbox_connection = dropbox.Dropbox(app_key=app_key, app_secret=app_secret,
                                                   oauth2_refresh_token=refresh_token)

    def get_type(self) -> str:
        return "dropbox"

    def list_files(self, remote_path) -> []:
        #  a Pandas dataframe of files in a given Dropbox folder path in the Apps directory.
        # dropbox_connection = dropbox_connect(access_token)
        try:
            files = self._dropbox_connection.files_list_folder(remote_path).entries
            files_list = []
            for file in files:
                if isinstance(file, dropbox.files.FileMetadata):
                    metadata = {
                        'name': file.name,
                        #'path_display': file.path_display,
                        'client_modified': file.client_modified,
                        'server_modified': file.server_modified
                    }
                    files_list.append(metadata)
                    #files_list.append(file.name)
                    # files_list.append(file.name + '\t' + str(file.server_modified))
            # df = pd.DataFrame.from_records(files_list)
            # return df.sort_values(by='server_modified', ascending=False)
            return files_list
        except Exception as e:
            print('Error getting list of files from Dropbox: ' + str(e))
            raise

    def exists(self, remote_path) -> bool:
        # path = os.path.abspath(remote_path)
        # filename = os.path.basename(remote_path)
        # dropbox_connection = dropbox_connect(access_token)
        try:
            files = self._dropbox_connection.files_list_folder("").entries
            for file in files:
                if isinstance(file, dropbox.files.FileMetadata):
                    # print("filename - " + file.name)
                    # print("search   - " + filename)
                    # if file.name == filename:
                    if file.name == remote_path:
                        return True
        except AuthError as e:
            print('Error getting list of files from Dropbox: ' + str(e))
            raise
        return False

    def download_file(self, remote_path, local_path):
        # Download a file from Dropbox to the local machine.
        remote_path = "/" + remote_path
        # print("remote_path->" + remote_path)
        # print("local_path->" + local_path)
        try:
            # dropbox_connection = dropbox_connect(access_token)
            with open(local_path, 'wb') as f:
                metadata, result = self._dropbox_connection.files_download(path=remote_path)
                f.write(result.content)
        except Exception as e:
            print('Error downloading file from Dropbox: ' + str(e))
            raise

    def upload_file(self, local_path, remote_path):
        remote_path = "/" + remote_path
        try:
            # dropbox_connection = dropbox_connect(access_token)
            # local_file_path = pathlib.Path(local_path) / local_file
            local_file = pathlib.Path(local_path)
            with local_file.open("rb") as f:
                meta = self._dropbox_connection.files_upload(f.read(), remote_path,
                                                             mode=dropbox.files.WriteMode("overwrite"))
                return meta
        except Exception as e:
            print('Error uploading file to Dropbox: ' + str(e))
            raise

    def delete_file(self, remote_path):
        remote_path = "/" + remote_path
        try:
            # dropbox_connection = dropbox_connect(access_token)
            self._dropbox_connection.files_delete_v2(remote_path)
        except Exception as e:
            print('Error deleting file from Dropbox: ' + str(e))
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
    refresh_token_str = response.text[
                        response.text.index('refresh_token": "') + 17:response.text.index('"scope": "') - 3]
    # print("->" + refresh_token_str)
    print("Result from api call:")
    print(json.dumps(json.loads(response.text), indent=2))
    print()
    return refresh_token_str
