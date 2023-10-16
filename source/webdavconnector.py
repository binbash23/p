#
# 20230907 Jens Heine <binbash@gmx.net>
#
# webdav connector
#
from webdav4.client import Client

# def webdav_file_exists()-> bool:

class WebdavConnector():

    dav_client = None
    dav_login = None
    dav_password = None

    def __init__(self, dav_url=None, dav_login=None, dav_password=None):
        self.dav_login = dav_login
        self.dav_password = dav_password
        if self.dav_login is not None and self.dav_password is not None:
            self.dav_client = Client(dav_url, auth=(dav_login, dav_password))
        else:
            self.dav_client = Client(dav_url)

    def __str__(self):
        print("Webdav Connector attributes:")
        if self.dav_client is None:
            return "not initialized."
        string = "base url : " + str(self.dav_client.base_url)
        string = string + "\n" + "login    : " + str(self.dav_login)
        return string

def main():
    webdav_connector = WebdavConnector(dav_url="mm", dav_login="mm", dav_password="mm")
    print("Connector is:\n" + str(webdav_connector))
    # webdav_connector.dav_client.ls("\\")
    webdav_connector.dav_client.exists("/")
    webdav_connector.dav_client.upload_file("c:\\temp\\p.exe", "\\p\p.exe")

if __name__ == '__main__':
    main()

"""
client = Client("https://webdav.com", auth=("username", "password"))
client.exists("Documents/Readme.md")

client.ls("Photos", detail=False)
client.upload_file("Gorilla.jpg", "Photos/Gorilla.jpg")
"""