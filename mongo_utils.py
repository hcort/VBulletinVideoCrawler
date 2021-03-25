from utils import extract_thread_name
from youtube_calls import get_videos_from_playlist, read_etags_from_playlists, create_playlist


def update_playlist_uploaded_videos(user_profile, added_videos, playlist_id):
    # check for new etag
    etag = read_etags_from_playlists(user_profile, playlist_id)
    if not etag:
        return
    # playlist_etag
    database = user_profile.mongo['vBulletin']
    created_lists = database['playlists_created']
    playlist_in_db = created_lists.find_one({'id': playlist_id})
    playlist_in_db['eTag'] = etag[0]['playlist_etag']
    for video in added_videos:
        playlist_in_db['videos'].append({
            'videoId': video['id'],
            'etag': ''
        })
    created_lists.replace_one(filter={'id': playlist_id}, replacement=playlist_in_db, upsert=True)


def refresh_thread_data(user_profile, thread):
    database = user_profile.mongo['vBulletin']
    video_thread = database['video_threads']
    video_thread.replace_one(filter={'id': thread['id']}, replacement=thread, upsert=True)


def check_lists_for_updates(user_profile):
    """
    :param user_profile:
    :return:
        To avoid wasting quota when looking for duplicates I store the videos from the playlist in mongodb

        Each playlist is stored with an eTag. If the retrieved eTags are different that means the playlists
        have been edited since the last run so the data in the database is outdated
    """
    etags = read_etags_from_playlists(user_profile)
    database = user_profile.mongo['vBulletin']
    for playlist in etags:
        playlist_in_db = database['playlists_created'].find_one({'id': playlist['playlist_id']})
        if (not playlist_in_db) or (playlist_in_db.get('etag', '') != playlist['playlist_etag']):
            # update playlist in db
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
    # replace playlist in database
    database = user_profile.mongo['vBulletin']
    all_threads_mongo = database['playlists_created']
    all_threads_mongo.replace_one(filter={'id': playlist['playlist_id']}, replacement=json_object, upsert=True)


def refresh_pending_videos_document(user_profile, thread, videos_found, append=False):
    # two kinds of "updates"
    #   -> after processing pending list, I can ignore the previous list
    #   -> after parsing a thread, I should append the new pending videos to the existing list
    database = user_profile.mongo['vBulletin']
    pending_videos = database['pending_videos']
    if append:
        previous_list = pending_videos.find_one({'id': thread['id']})
        pending_videos_doc = {
            'id': thread['id'],
            'videos': (previous_list['videos'] if previous_list else []) + list(videos_found.values())
        }
    else:
        pending_videos_doc = {
            'id': thread['id'],
            'videos': list(videos_found.values())
        }
    pending_videos.replace_one(filter={'id': thread['id']}, replacement=pending_videos_doc, upsert=True)


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
        database = user_profile.mongo['vBulletin']
        all_threads_mongo = database['video_threads']
        all_threads_mongo.replace_one(filter={'id': thread_data['id']}, replacement=thread_data)
    return thread_data

