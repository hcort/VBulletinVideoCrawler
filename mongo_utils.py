from utils import extract_thread_name
from youtube_calls import get_videos_from_playlist, read_etags_from_playlists, create_playlist


def add_uploaded_videos_to_playlists_created(user_profile, added_videos, playlist_id):
    # check for new etag
    etag = read_etags_from_playlists(user_profile, playlist_id)
    if not etag:
        return
    playlist_in_db = user_profile.mongo_get_playlists_created_info(playlist_id)
    playlist_in_db['eTag'] = etag[0]['playlist_etag']
    for video in added_videos:
        playlist_in_db['videos'].append({
            'videoId': video['id'],
            'etag': ''
        })
    user_profile.mongo_replace_playlists_created_item(playlist_id, playlist_in_db)


def get_playlist_id_from_thread_id(user_profile, thread_id):
    thread = user_profile.mongo_get_thread_info(thread_id)
    if thread:
        return thread['playlist_id']
    return ''


def check_lists_for_updates(user_profile):
    """
    :param user_profile:
    :return:
        To avoid wasting quota when looking for duplicates I store the videos from the playlist in mongodb

        Each playlist is stored with an eTag. If the retrieved eTags are different that means the playlists
        have been edited since the last run so the data in the database is outdated
    """
    etags = read_etags_from_playlists(user_profile)
    for playlist in etags:
        playlist_in_db = user_profile.mongo_get_playlists_created_info(playlist['playlist_id'])
        if (not playlist_in_db) or (playlist_in_db.get('etag', '') != playlist['playlist_etag']):
            read_playlist_items_and_update_db(user_profile, playlist)


def read_playlist_items_and_update_db(user_profile, playlist):
    if not user_profile.has_quota:
        return
    whole_playlist = get_videos_from_playlist(user_profile, playlist['playlist_id'])
    json_object = {
        'id': playlist['playlist_id'],
        'etag': playlist['playlist_etag'],
        'videos': whole_playlist
    }
    user_profile.mongo_replace_playlists_created_item(playlist_id=playlist['playlist_id'], replacement=json_object)


def refresh_pending_videos_document(user_profile, thread, videos_found, append=False):
    # two kinds of "updates"
    #   -> after processing pending list, I can ignore the previous list
    #   -> after parsing a thread, I should append the new pending videos to the existing list
    if append:
        previous_list = user_profile.mongo_get_pending_videos_info(thread['id'])
        pending_videos_doc = {
            'id': thread['id'],
            'videos': (previous_list['videos'] if previous_list else []) + list(videos_found.values())
        }
    else:
        pending_videos_doc = {
            'id': thread['id'],
            'videos': list(videos_found.values())
        }
    user_profile.mongo_replace_pending_videos_item(thread_id=thread['id'], replacement=pending_videos_doc)


def create_thread_in_pending_videos(user_profile, thread_data, force_creation=False):
    if force_creation or (not user_profile.mongo_get_pending_videos_info(thread_data['id'])):
        user_profile.mongo_replace_pending_videos_item(
            thread_id=thread_data['id'],
            replacement={
                'id': thread_data['id'],
                'videos': []
            })


def create_playlist_in_created_playlists(user_profile, thread_data, force_creation=False):
    if not thread_data['playlist_id']:
        return
    if force_creation or (not user_profile.mongo_get_playlists_created_info(thread_data['playlist_id'])):
        user_profile.mongo_replace_playlists_created_item(playlist_id=thread_data['playlist_id'],
                                                          replacement={
                                                              'id': thread_data['playlist_id'],
                                                              'etag': '',
                                                              # FIXME maybe get etag from create_playlist (?
                                                              'videos': []
                                                          })


def fill_thread_data_playlist_name_id(thread_data, user_profile):
    # check if thread data misses playlist name or playlist id
    update_mongo = False
    if not thread_data.get('playlist_title', ''):
        thread_url = user_profile.forum_base + '/showthread.php?t=' + thread_data['id']
        thread_data['playlist_title'] = extract_thread_name(user_profile, thread_url)
        update_mongo = (thread_data['playlist_title'] != '')
    if not thread_data.get('playlist_id', ''):
        # user_profile.youtube.playlists().list is returning backendError frequently
        #  so I won't search the lists in the channel. If playlist_id is empty it means it doesn't
        #  exist yet so I will create it
        thread_data['playlist_id'] = create_playlist(user_profile,
                                                     name=thread_data.get('playlist_title', ''), description='',
                                                     privacy='unlisted', url='')
        update_mongo = update_mongo or (thread_data['playlist_title'] != '')
    if update_mongo:
        user_profile.mongo_replace_video_threads_item(thread_id=thread_data['id'], replacement=thread_data)
        # check if the playlist exists in playlists_created and pending_videos. if not, create them
        create_thread_in_pending_videos(user_profile=user_profile, thread_data=thread_data)
        create_playlist_in_created_playlists(user_profile=user_profile, thread_data=thread_data)
    return thread_data
