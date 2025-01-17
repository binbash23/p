#
# 20240104 Jens Heine <binbash@gmx.net>
#
# file connector
#
import os.path
import shutil
from pathlib import Path

# from informal_connector_interface import InformalConnectorInterface
from connector_interface import ConnectorInterface


class FileConnector(ConnectorInterface):
    _base_path = None

    def __init__(self, file_path=None):
        # self._file_path = str(file_path).replace("\\", "\\\\")
        self._base_path = file_path
        # if not os.path.isdir(self._file_path):
        if not os.path.exists(self._base_path):
            os.makedirs(self._base_path)
        if not Path(self._base_path).is_dir():
            raise Exception("Error: Path exists but is a file, not a folder: " + self._base_path)
        # if not os.path.exists(self._file_path):
        #     os.makedirs(self._file_path)
        #     return

    def __str__(self):
        return "File Connector attributes: Path: " + self._base_path

    def get_type(self) -> str:
        return "file"

    def list_files(self, remote_path="") -> []:
        return os.listdir(os.path.join(remote_path, self._base_path))
        # return os.listdir(self._file_path)

    def upload_file(self, local_path, remote_path=""):
        # remote_path = os.path.join(self._base_path, remote_path)
        # local_filename = os.path.basename(local_path)
        remote_filename = os.path.basename(remote_path)
        try:
            # shutil.copyfile(local_path, os.path.join(remote_path, local_filename))
            shutil.copyfile(local_path, os.path.join(self._base_path, remote_filename))
        except Exception as e:
            print("Error: " + str(e))

    def download_file(self, remote_path, local_path="."):
        # remote_path = os.path.join(self._base_path, remote_path)
        # remote_filename = os.path.basename(remote_path)
        connector_file = os.path.join(self._base_path, os.path.basename(remote_path))
        try:
            shutil.copyfile(connector_file, local_path)
        except Exception as e:
            print("Error: " + str(e))

    def delete_file(self, remote_path):
        remote_path = os.path.join(self._base_path, remote_path)
        try:
            os.remove(remote_path)
        except Exception as e:
            print("Error: " + str(e))

    def exists(self, remote_path) -> bool:
        remote_path = os.path.join(self._base_path, remote_path)
        exists: bool = False
        try:
            exists = os.path.exists(remote_path)
        except Exception as e:
            print("Error: " + str(e))
        return exists

    def get_remote_base_path(self) -> str:
        return self._base_path


def main():
    fc = FileConnector(file_path="/home/melvin/tmp/testdir")
    print("exists: " + str(fc.exists("testfile")))
    fc.upload_file("/home/melvin/tmp/d_1")
    print("exists: " + str(fc.exists("d_1")))
    fc.delete_file("d_1")
    print("exists: " + str(fc.exists("d_1")))


if __name__ == '__main__':
    main()
