import re

from mongo_utils import fill_thread_data_playlist_name_id, refresh_pending_videos_document
from populate_playlist import add_videos_to_playlist
from utils import convert_video_list_in_dict


def find_playlist_id(thread_id, user_profile):
    database = user_profile.mongo['vBulletin']
    all_threads_mongo = database['video_threads']
    thread_data = all_threads_mongo.find_one({'id': thread_id})
    if not thread_data:
        return None
    thread_data = fill_thread_data_playlist_name_id(thread_data=thread_data, user_profile=user_profile)
    return thread_data.get('playlist_id', None)


def parse_pending_list_and_upload(user_profile):
    for thread in user_profile.mongo_pending_videos_list():
        videos_pending = thread.get('videos', None)
        if not videos_pending:
            continue
        playlist_id = find_playlist_id(thread['id'], user_profile)
        if not playlist_id:
            continue
        try:
            pending_videos_dict = convert_video_list_in_dict(videos_pending)
            videos_inserted = add_videos_to_playlist(user_profile,
                                                     vid_dict=pending_videos_dict, playlist_id=playlist_id)
            if videos_inserted > 0:
                refresh_pending_videos_document(user_profile, thread, pending_videos_dict)
        except Exception as e:
            print('An unknown error occurred:\n%s' % (str(e)))
        if not user_profile.has_quota:
            return
