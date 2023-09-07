#
# 20230907 Jens Heine <binbash@gmx.net>
#
# webdav connector
#
from webdav4.client import Client

def webdav_file_exists()-> bool:




client = Client("https://webdav.com", auth=("username", "password"))
client.exists("Documents/Readme.md")

client.ls("Photos", detail=False)
client.upload_file("Gorilla.jpg", "Photos/Gorilla.jpg")