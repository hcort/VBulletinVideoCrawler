from googleapiclient.errors import HttpError
from mongo_utils import fill_thread_data_playlist_name_id, refresh_pending_videos_document, refresh_thread_data
from utils import extract_thread_modification_date, remove_videos_already_in_list, \
    process_exception, get_error_names
from youtube_calls import playlist_insert


def add_videos_to_playlist(user_profile, vid_dict=None, playlist_id=None):
    """
    :param user_profile:
    :param vid_dict:
    :param playlist_id:
    :return: True is quota has been reached, False otherwise

    vid_dict is modified in this function
    - remove_videos_already_in_list removes pending videos that were uploaded to the playlist before
    - playlist_insert removes videos

    """
    videos_inserted = 0
    if not vid_dict or not playlist_id or not user_profile.has_quota:
        return videos_inserted

    remove_videos_already_in_list(user_profile, vid_dict, playlist_id)

    video_ids = list(vid_dict.keys())
    added_videos = []

    print('Insertando ' + str(len(video_ids)) + ' videos en ' + playlist_id)

    for video_id in video_ids:
        try:
            insert_result = playlist_insert(playlist_id, video_id, user_profile.youtube)
            added_videos.append(insert_result)
            vid_dict.pop(video_id)
            print('>>>>>>>>> ' + video_id + ' insertado correctamente')
        except HttpError as err:
            process_exception(user_profile, err, custom_str='Error adding video: ' + video_id + '\n' + str(err.content))
            error_names_list = get_error_names(err)
            # remove video for some errors
            if ('duplicate' in error_names_list) or ('playlistItemsNotAccessible' in error_names_list) or \
                    ('videoNotFound' in error_names_list):
                vid_dict.pop(video_id)
        if not user_profile.has_quota:
            break
    if added_videos:
        from mongo_utils import update_playlist_uploaded_videos
        update_playlist_uploaded_videos(user_profile, added_videos, playlist_id)
    print('All videos uploaded')
    return videos_inserted


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
    videos_found = parser.start_parsing(thread_url, last_post)
    if videos_found:
        video_list = list(videos_found.keys())
        try:
            # check for playlist title and id
            # TODO if I don't have playlist_id it means is not created yet
            thread_data = fill_thread_data_playlist_name_id(thread_data=thread, user_profile=user_profile)
            name_param = thread_data.get('playlist_title')
            playlist_id = thread_data.get('playlist_id', None)
            add_videos_to_playlist(user_profile=user_profile, vid_dict=videos_found, playlist_id=playlist_id)
        except Exception as e:
            print('An unknown error occurred:\n%s' % (str(e)))
            return
        # add remaining videos in videos_found to pending database
        refresh_pending_videos_document(user_profile, thread, videos_found, append=True)
        thread['last_post'] = parser.last_parsed_message
    refresh_thread_data(user_profile, thread)



