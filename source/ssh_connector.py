#
# 20231201 Jens Heine <binbash@gmx.net>
#
# ssh connector
#
# import paramiko
import os.path

import pysftp

from connector_interface import ConnectorInterface


# def webdav_file_exists()-> bool:

class SshConnector(ConnectorInterface):
    _ssh_server_url = None
    _ssh_server_hostname = None
    _ssh_login = None
    _ssh_password = None
    _ssh_connection = None
    _ssh_remote_base_path = "/"

    def __init__(self, ssh_server_url=None, ssh_login=None, ssh_password=None):
        self._ssh_server_url = ssh_server_url
        self._ssh_login = ssh_login
        self._ssh_password = ssh_password
        # tokenize eventually existing hostname and path from url
        if ":" in self._ssh_server_url:
            self._ssh_server_hostname = self._ssh_server_url.split(":")[0]
            self._ssh_remote_path = self._ssh_server_url.split(":")[1]
        else:
            self._ssh_server_hostname = self._ssh_server_url

        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None
        self._ssh_connection = pysftp.Connection(host=self._ssh_server_hostname, username=self._ssh_login,
                                                 password=self._ssh_password, cnopts=cnopts)

    def __str__(self):
        to_string: str = "SSH Connector attributes: "
        to_string = (to_string + "url: " + str(self._ssh_server_url) +
                     # ", hostname: " + self._ssh_server_hostname +
                     # ", path: " + self._ssh_remote_path +
                     ", login: " + str(self._ssh_login))
        return to_string

    def get_type(self) -> str:
        return "ssh"

    def list_files(self, remote_path="") -> []:
        remote_path = os.path.join(self._ssh_remote_path, remote_path)
        try:
            return self._ssh_connection.listdir(remote_path)
        except Exception as e:
            print("Error: " + str(e))

    def upload_file(self, local_path, remote_path=""):
        remote_path = os.path.join(self._ssh_remote_path, remote_path)
        try:
            self._ssh_connection.put(local_path, remote_path)
        except Exception as e:
            print("Error: " + str(e))

    def download_file(self, remote_path, local_path="."):
        remote_path = os.path.join(self._ssh_remote_path, remote_path)
        try:
            self._ssh_connection.get(remote_path, local_path)
        except Exception as e:
            print("Error: " + str(e))

    def delete_file(self, remote_path):
        remote_path = os.path.join(self._ssh_remote_path, remote_path)
        try:
            self._ssh_connection.remove(remote_path)
        except Exception as e:
            print("Error: " + str(e))

    def exists(self, remote_path) -> bool:
        remote_path = os.path.join(self._ssh_remote_path, remote_path)
        exists: bool = False
        try:
            exists = self._ssh_connection.exists(remote_path)
        except Exception as e:
            print("Error: " + str(e))
        return exists

    def get_remote_base_path(self) -> str:
        return self._remote_base_path


def main():
    pass


if __name__ == '__main__':
    main()
