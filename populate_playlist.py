from googleapiclient.errors import HttpError
from mongo_utils import fill_thread_data_playlist_name_id, refresh_pending_videos_document, replace_video_threads_item
from utils import extract_thread_modification_date, remove_videos_already_in_list, \
    process_exception, get_error_names
from youtube_calls import playlist_insert


def iterate_video_dict_and_insert(user_profile, playlist_id, vid_dict):
    added_videos = []
    video_ids = list(vid_dict.keys())
    # print('Insertando ' + str(len(video_ids)) + ' videos en ' + playlist_id)
    for video_id in video_ids:
        try:
            insert_result = playlist_insert(playlist_id, video_id, user_profile.youtube)
            added_videos.append(insert_result)
            vid_dict.pop(video_id)
        except HttpError as err:
            process_exception(user_profile, err, custom_str='Error adding video: ' + video_id + '\n' + str(err.content))
            error_names_list = get_error_names(err)
            # remove video for some errors
            if ('duplicate' in error_names_list) or ('playlistItemsNotAccessible' in error_names_list) or \
                    ('videoNotFound' in error_names_list):
                vid_dict.pop(video_id)
        except Exception as err:
            # another kind of error I can't solve
            process_exception(user_profile, err, custom_str='Error adding video: ' + video_id + '\n' + str(err.content))
            break
        if not user_profile.has_quota:
            break
    return added_videos


def add_videos_to_playlist_and_update_db(user_profile, thread, vid_dict=None, playlist_id=None,
                                         append_pending_list=False):
    added_videos = add_videos_to_playlist(user_profile,
                                          vid_dict=vid_dict,
                                          playlist_id=playlist_id)
    if added_videos:
        from mongo_utils import add_uploaded_videos_to_playlists_created
        add_uploaded_videos_to_playlists_created(user_profile, added_videos, playlist_id)
        refresh_pending_videos_document(user_profile, thread, vid_dict, append=append_pending_list)


def add_videos_to_playlist(user_profile, vid_dict=None, playlist_id=None, append_pending_list=False):
    """
    :param user_profile:
    :param vid_dict:
    :param playlist_id:
    :return: a list of videos added to the playlist

    vid_dict is modified in this function
    - remove_videos_already_in_list removes pending videos that were uploaded to the playlist before
    - playlist_insert removes videos
    After execution only pending videos remain in vid_dict

    """
    if not vid_dict or not playlist_id or not user_profile.has_quota:
        return []

    remove_videos_already_in_list(user_profile, vid_dict, playlist_id)

    added_videos = iterate_video_dict_and_insert(user_profile=user_profile,
                                                 playlist_id=playlist_id,
                                                 vid_dict=vid_dict)
    print('All videos uploaded')
    return added_videos


def parse_thread_and_upload(user_profile, thread, parser):
    if not user_profile.youtube:
        return
    last_post = thread.get('last_post', '')
    # upload videos found in the thread
    thread_url = user_profile.forum_base + 'showthread.php?t=' + thread['id']
    # check last modification date
    last_mod_date_bd = thread.get('last_mod_date', '')
    last_mod_date = extract_thread_modification_date(user_profile, thread_url)
    if last_mod_date_bd == last_mod_date:
        return
    else:
        thread['last_mod_date'] = last_mod_date
    thread_data = thread
    videos_found = parser.start_parsing(thread_url, last_post)
    if videos_found:
        video_list = list(videos_found.keys())
        try:
            thread_data = fill_thread_data_playlist_name_id(thread_data=thread, user_profile=user_profile)
            playlist_id = thread_data.get('playlist_id', None)
            add_videos_to_playlist_and_update_db(user_profile=user_profile,
                                                 thread=thread_data,
                                                 vid_dict=videos_found,
                                                 playlist_id=playlist_id,
                                                 append_pending_list=True)
        except Exception as e:
            print('An unknown error occurred:\n%s' % (str(e)))
        thread['last_post'] = parser.last_parsed_message
    user_profile.mongo_replace_video_threads_item(thread_id=thread_data['id'], replacement=thread_data)
