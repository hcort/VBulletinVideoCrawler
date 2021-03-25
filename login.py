from parse_youtube_links import VBulletinVideoCrawler
from pending_videos import parse_pending_list_and_upload
from populate_playlist import parse_thread_and_upload
from mongo_utils import check_lists_for_updates
from utils import fill_parser_data, login_data_from_parser_data
from youtube_profile import YoutubeProfile

"""

JSON input file format
    {
        "username": "...",
        "password": "...",
        "mongouser": "...",
        "mongopassword": "...",
        "forum_base": "https://www.someforum.com/forum/"
    }

- Username and password are the fields used to log into the forum (when needed).
- Mongouser and mongopassword are used to connect to local MongoDB
- forum_base is the base URL of the forum
"""


def main():
    user_profile = YoutubeProfile(fill_parser_data())
    check_lists_for_updates(user_profile)
    parse_pending_list_and_upload(user_profile)

    parser = VBulletinVideoCrawler(login_url=user_profile.forum_login_url,
                                   login_data=login_data_from_parser_data(user_profile.parser_data))
    # read threads from mongo
    for thread in user_profile.mongo_thread_list():
        # if we can't upload all the videos because of quota we exit
        parse_thread_and_upload(user_profile, thread, parser)


# Lanzamos la función principal
if __name__ == "__main__":
    main()
