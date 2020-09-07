import getopt
import sys

from googleapiclient.errors import HttpError

from parse_youtube_links import VBulletinVideoCrawler
from populate_playlist import get_authenticated_service, add_playlist

"""
<form name="log2" action="login.php" method="post" onsubmit="return l2check();">
<input type="hidden" name="do" value="login">
<input type="hidden" name="forceredirect" value="1">
<input type="hidden" name="url" value="/">
<input type="hidden" name="vb_login_md5password">
<input type="hidden" name="vb_login_md5password_utf">
<input type="hidden" name="s" value="">
<input type="hidden" name="securitytoken" value="guest">


do=login
forceredirect=1
url="%"2F
vb_login_md5password=
vb_login_md5password_utf=
s=
securitytoken=guest
vb_login_username=...
vb_login_password=...
cookieuser=1
logb2=Acceder
"""


# vbulletinVideoCrawler >


def main():
    argv = sys.argv[1:]
    try:
        opts, args = getopt.getopt(argv, 'u:p:l:s:')
        for (opt, value) in opts:
            if opt == "-u":
                username = str(value)
            elif opt == "-p":
                pwd = str(value)
            elif opt == "-l":
                login_url = str(value)
            elif opt == "-s":
                start_page = str(value)
    except ValueError as err:
        print(str(err))
        exit(-1)

    # This is the form data that the page sends when logging in
    # TODO get securitytoken value from the HTML document
    # <input type="hidden" name="securitytoken" value="guest">
    login_data = {
        'do': 'login',
        'forceredirect': '0',
        'url': '',
        'vb_login_md5password': '',
        'vb_login_md5password_utf': '',
        's': '',
        'securitytoken': 'guest',
        'vb_login_username': '',
        'vb_login_password': '',
        'cookieuser': '1',
        'logb2': 'Acceder'
    }
    if username and pwd:
        login_data['vb_login_username'] = username
        login_data['vb_login_password'] = pwd
    parser = VBulletinVideoCrawler(login_url, login_data)
    q = parser.start_parsing(start_page)

    youtube = get_authenticated_service()
    try:
        add_playlist(youtube, q)
    except HttpError as e:
        print('An HTTP error %d occurred:\n%s' % (e.resp.status, e.content))


# Lanzamos la función principal
if __name__ == "__main__":
    main()
