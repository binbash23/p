#!/bin/python3
#
# 20221016 jens heine <binbash@gmx.net>
#
# Informal interface class for MergeTargetLocation classes
#

class InformalConnectorInterface:

    def list_files(self, remote_path) -> []:
        pass

    def upload_file(self, local_path, remote_path):
        pass

    def download_file(self, remote_path, local_path):
        pass

    def delete_file(self, remote_path):
        pass

    def exists(self, remote_path) -> bool:
        pass

    def get_type(self) -> str:
        # print a type i.e. webdav, sftp, ...
        pass
