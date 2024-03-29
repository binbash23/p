#
# 20230907 Jens Heine <binbash@gmx.net>
#
# webdav connector
#
from webdav4.client import Client

from connector_interface import ConnectorInterface


class WebdavConnector(ConnectorInterface):
    _dav_client = None
    _dav_login = None
    _dav_password = None
    _remote_base_path = "/"

    def __init__(self, dav_url=None, dav_login=None, dav_password=None):
        self._dav_login = dav_login
        self._dav_password = dav_password
        if self._dav_login is not None and self._dav_password is not None:
            self._dav_client = Client(dav_url, auth=(dav_login, dav_password))
        else:
            self._dav_client = Client(dav_url)
        # check connection
        self._dav_client.ls(path="/")

    def __str__(self):
        to_string: str = "Webdav Connector attributes: "
        if self._dav_client is None:
            return to_string + "not initialized."
        to_string = to_string + "base url: " + str(self._dav_client.base_url) + ", login: " + str(self._dav_login)
        return to_string

    def get_type(self) -> str:
        return "webdav"

    def list_files(self, remote_path) -> []:
        try:
            return self._dav_client.ls(path=remote_path)
        except Exception as e:
            print("Error: " + str(e))

    def upload_file(self, local_path, remote_path):
        try:
            self._dav_client.upload_file(local_path, remote_path, overwrite=True)
        except Exception as e:
            print("Error: " + str(e))

    def download_file(self, remote_path, local_path):
        try:
            self._dav_client.download_file(remote_path, local_path)
        except Exception as e:
            print("Error: " + str(e))

    def delete_file(self, remote_path):
        try:
            self._dav_client.remove(remote_path)
        except Exception as e:
            print("Error: " + str(e))

    def exists(self, remote_path) -> bool:
        exists: bool = False
        try:
            exists = self._dav_client.exists(remote_path)
        except Exception as e:
            print("Error: " + str(e))
        return exists
        # return self._dav_client.exists(remote_path)

    def get_remote_base_path(self) -> str:
        return self._remote_base_path


def main():
    webdav_connector = WebdavConnector(dav_url="xyz", dav_login="xyz",
                                       dav_password="xyz")
    print("Connector is:\n" + str(webdav_connector))
    files = webdav_connector.list_files("\\p\\")
    for file in files:
        print(str(file))
    print("uploading...")

    print("uploading...")
    webdav_connector.delete_file("\\p\\p")
    files = webdav_connector.list_files("\\p\\")
    for file in files:
        print(str(file))


if __name__ == '__main__':
    main()
