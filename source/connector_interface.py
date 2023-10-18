#!/bin/python3
#
# 20221017 jens heine <binbash@gmx.net>
#
# Formal interface class for connector classes
#

# import abc
from abc import ABC, abstractmethod


class ConnectorInterface(ABC):
# class ConnectorInterface(metaclass=abc.ABCMeta):
    # @classmethod
    # def __subclasshook__(cls, subclass):
    #     return (callable(subclass.list_files) and
    #             callable(subclass.exists) and
    #             callable(subclass.upload_file) and
    #             callable(subclass.download_file) and
    #             callable(subclass.delete_file) and
    #             callable(subclass.get_type))

    @abstractmethod
    def list_files(self, remote_path) -> []:
        raise NotImplementedError

    @abstractmethod
    def upload_file(self, local_path, remote_path):
        raise NotImplementedError

    @abstractmethod
    def download_file(self, remote_path, local_path):
        raise NotImplementedError

    @abstractmethod
    def delete_file(self, remote_path):
        raise NotImplementedError

    @abstractmethod
    def exists(self, remote_path) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_type(self) -> str:
        # print a type i.e. webdav, sftp, ...
        raise NotImplementedError
