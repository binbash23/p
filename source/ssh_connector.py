#
# 20231201 Jens Heine <binbash@gmx.net>
#
# ssh connector
#
# import paramiko
import pysftp

# from informal_connector_interface import InformalConnectorInterface
from connector_interface import ConnectorInterface


# def webdav_file_exists()-> bool:

class WebdavConnector(ConnectorInterface):
    _ssh_server_url = None
    _ssh_login = None
    _ssh_password = None
    _ssh_connection = None

    def __init__(self, ssh_server_url=None, ssh_login=None, ssh_password=None):
        self._ssh_server_url = ssh_server_url
        self._ssh_login = ssh_login
        self._ssh_password = ssh_password
        # self._ssh_connection = paramiko.SSHClient()
        # self._ssh_connection.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        # self._ssh_connection.connect(self._ssh_server_url, username=self._ssh_login, password=self._ssh_password)
        self._ssh_connection = pysftp.Connection(host=self._ssh_server_url, username=self._ssh_login,
                                                 password=self._ssh_password)
        current_dir = self._ssh_connection.pwd
        print("Current ssh dir: " + current_dir)
        # self._ssh_connection.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        # self._ssh_connection.connect(self._ssh_server_url, username=self._ssh_login, password=self._ssh_password)

    def __str__(self):
        to_string: str = "SSH Connector attributes: "
        to_string = to_string + "base url : " + str(self._ssh_server_url) + ", login    : " + str(self._ssh_login)
        return to_string

    def get_type(self) -> str:
        return "ssh"

    def list_files(self, remote_path) -> []:
        try:
            # files = self._dav_client.ls(path=remote_path)
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


def main():
    ssh_connector =

    webdav_connector = WebdavConnector(dav_url="xyz", dav_login="xyz",
                                       dav_password="xyz")
    print("Connector is:\n" + str(webdav_connector))
    # files = webdav_connector._dav_client.ls("\\p")
    files = webdav_connector.list_files("\\p\\")
    for file in files:
        print(str(file))
    # webdav_connector._dav_client.exists("/")
    print("uploading...")
    # webdav_connector.upload_file("/home/melvin/tmp/p", "\\p\\p")
    # print("downloading...")
    # webdav_connector.download_file("/p/p", "/home/melvin/tmp/p")

    print("uploading...")
    webdav_connector.delete_file("\\p\\p")
    files = webdav_connector.list_files("\\p\\")
    for file in files:
        print(str(file))


if __name__ == '__main__':
    main()
