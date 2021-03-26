from mongo_utils import fill_thread_data_playlist_name_id
from populate_playlist import add_videos_to_playlist_and_update_db
from utils import convert_video_list_in_dict


def find_playlist_id(thread_id, user_profile):
    thread_data = user_profile.mongo_get_thread_info(thread_id)
    if not thread_data:
        return None
    thread_data = fill_thread_data_playlist_name_id(thread_data=thread_data, user_profile=user_profile)
    return thread_data.get('playlist_id', None)


def parse_pending_list_and_upload(user_profile):
    for thread in user_profile.mongo_pending_videos_list():
        videos_pending = thread.get('videos', None)
        if not videos_pending:
            continue
        thread_db = fill_thread_data_playlist_name_id(thread_data=user_profile.mongo_get_thread_info(thread['id']),
                                                      user_profile=user_profile)
        playlist_id = thread_db['playlist_id']
        if not playlist_id:
            continue
        try:
            pending_videos_dict = convert_video_list_in_dict(videos_pending)
            add_videos_to_playlist_and_update_db(user_profile=user_profile,
                                                 thread=thread_db,
                                                 vid_dict=pending_videos_dict,
                                                 playlist_id=playlist_id)
        except Exception as e:
            print('An unknown error occurred:\n%s' % (str(e)))
        if not user_profile.has_quota:
            return
