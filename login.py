import getopt
import json
import sys

from googleapiclient.errors import HttpError

from parse_youtube_links import VBulletinVideoCrawler
from populate_playlist import get_authenticated_service, add_playlist

"""

JSON input file format

- Username and password are the fields used to log into the forum (when needed).
- login_url is optional (can be extracted from thread url

Listas contains a list of threads to parse. 
- url: URL to the thread
- last_post (optional): the post number from the last video uploaded to the playlist
    The format is "page=XX#post123456789 as this is the way vBulletin constructs links to
    specific posts in a thread.
- playlist_title (optional): if not given the playlist title will be the thread title

After running this script if we have uploaded more videos to the playlist the "last_post" value
will be updated to the newest value, even if it was not present at input time

{
  "username": "",
  "password": "",
  "login_url": "",
  "listas": [
    {
      "url": "https://.../showthread.php?t=8142569",
      "last_post": "page=21#post379656634",
      "playlist_title": "lofi-vaporwave-etc"
    },
    {
      "url": "https://.../showthread.php?t=7143451",
      "last_post": "page=10#post375992420"
    },
    ...
  ]
}
"""


# vbulletinVideoCrawler >

def main():
    login_url = ''
    start_page = ''
    name_param = ''
    username = ''
    pwd = ''
    file_param = ''
    argv = sys.argv[1:]
    try:
        opts, args = getopt.getopt(argv, 'u:p:l:s:n:f:')
        for (opt, value) in opts:
            if opt == "-u":
                username = str(value)
            elif opt == "-p":
                pwd = str(value)
            elif opt == "-l":
                login_url = str(value)
            elif opt == "-s":
                start_page = str(value)
            elif opt == "-n":
                name_param = str(value)
            elif opt == "-f":
                file_param = str(value)
    except ValueError as err:
        print(str(err))
        exit(-1)

    if file_param:
        parser_data = json.load(open(file_param, 'r'))
    else:
        parser_data = {
                        'username': username,
                        'password': pwd,
                        'login_url': login_url,
                        'listas': [
                            {
                                'url': start_page,
                                'last_post': '',
                                'playlist_title': name_param
                            }
                        ]
                    }

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
    if parser_data['username'] and parser_data['password']:
        login_data['vb_login_username'] = parser_data['username']
        login_data['vb_login_password'] = parser_data['password']
    parser = VBulletinVideoCrawler(parser_data['login_url'], login_data)
    youtube = None
    for thread in parser_data['listas']:
        last_post = thread.get('last_post', '')
        videos_found = parser.start_parsing(thread['url'], last_post)
        try:
            if not youtube:
                youtube = get_authenticated_service()
            name_param = thread.get('playlist_title', '')
            last_video = add_playlist(youtube, videos_found, name=name_param, description=parser.thread_name, url=start_page)
        except HttpError as e:
            print('An HTTP error %d occurred:\n%s' % (e.resp.status, e.content))
        if last_video and file_param:
            # update last_post element in json file
            post_link = videos_found[last_video].get('post_link')
            post_page = post_link[post_link.find('&page'):]
            thread['last_post'] = post_page
    if file_param:
        with open(file_param, 'w') as outfile:
            json.dump(parser_data, outfile)


# Lanzamos la función principal
if __name__ == "__main__":
    main()
