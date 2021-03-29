from mongo_utils import fill_thread_data_playlist_name_id
from populate_playlist import upload_video_dict_and_update_bd
from utils import convert_video_list_in_dict


def find_playlist_id_create_if_not_found(thread_id, user_profile):
    thread_data = user_profile.mongo_get_thread_info(thread_id)
    if not thread_data:
        return None
    thread_data = fill_thread_data_playlist_name_id(thread_data=thread_data, user_profile=user_profile)
    return thread_data.get('playlist_id', None)


def parse_pending_list_and_upload(user_profile):
    for thread in user_profile.mongo_pending_videos_list():
        videos_pending = thread.get('videos', None)
        if videos_pending:
            upload_video_dict_and_update_bd(user_profile=user_profile,
                                            thread=user_profile.mongo_get_thread_info(thread['id']),
                                            videos_found=convert_video_list_in_dict(videos_pending))
        if not user_profile.has_quota:
            return
