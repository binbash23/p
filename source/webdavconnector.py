#
# 20230907 Jens Heine <binbash@gmx.net>
#
# webdav connector
#
import webdav.client as wc


options = {
 'webdav_hostname': "https://webdav.server.ru",
 'webdav_login':    "login",
 'webdav_password': "password"
}

client = wc.Client(options)