import getopt
import json
import re
import sys

from parse_youtube_links import VBulletinVideoCrawler


def convert_video_list_in_dict(video_list):
    video_dict = {}
    regex_id = re.compile("watch\?v=([^\"&?\\\/]{11})")
    for item in video_list:
        m = regex_id.search(item['url'])
        if m:
            video_id = m.group(1)
            video_dict[video_id] = item
    return video_dict


def convert_video_list_in_dict_etags(video_list):
    video_dict = {}
    for item in video_list:
        video_dict[item['videoId']] = item['etag']
    return video_dict


def process_exception(user_profile, err, custom_str=''):
    if custom_str:
        print(custom_str)
    print(err)
    error_names_list = get_error_names(err)
    if is_quota_error(error_names_list):
        user_profile.set_quota_finished()


def fill_parser_data():
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
    parser_data['file_param'] = file_param
    return parser_data


def extract_thread_id_from_url(thread_url):
    regex_id = re.compile("watch\?v=([^\"&?\\\/]{11})")
    m = regex_id.search(thread_url)
    if m:
        return m.group(1)
    return ''


def find_playlist_from_thread_id(user_profile, thread_id):
    thread_data = user_profile.mongo_get_thread_info(thread_id)
    if not thread_data:
        return None
    return thread_data.get('playlist_id', None)


def extract_thread_name(user_profile, thread_url):
    parser = VBulletinVideoCrawler(login_url=user_profile.forum_login_url,
                                   login_data=login_data_from_parser_data(user_profile.parser_data))
    return parser.get_thread_name_from_url(thread_url)


def extract_thread_modification_date(user_profile, thread_url):
    parser = VBulletinVideoCrawler(login_url=user_profile.forum_login_url,
                                   login_data=login_data_from_parser_data(user_profile.parser_data))
    return parser.get_last_modification_date(thread_url)


def get_error_names(err):
    err_as_json = json.loads(err.content)
    error_list = err_as_json['error'].get('errors')
    error_name_list = []
    if error_list:
        for insert_err in error_list:
            error_name_list.append(insert_err['reason'])
    return error_name_list


def is_quota_error(error_name_list):
    return 'quotaExceeded' in error_name_list


def remove_videos_already_in_list(user_profile, vid_dict=None, playlist_id=''):
    duplicates = []
    if not playlist_id:
        return duplicates
    # don't check duplicates from youtube account, use mongodb to avoid wasting quota
    playlist = user_profile.mongo_get_playlists_created_info(playlist_id)
    if playlist:
        vid_dict_playlist = convert_video_list_in_dict_etags(playlist['videos'])
        # playlist['videos'] is a list
        video_keys = list(vid_dict.keys())
        for video_key in video_keys:
            popped_video = vid_dict_playlist.get(video_key, None)
            if popped_video:
                duplicates.append(popped_video)
                vid_dict.pop(video_key)
    return duplicates


def login_data_from_parser_data(parser_data):
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
    return login_data
