import threading
import time
from typing import Callable, TypeVar

from pymongo import MongoClient

from utils import fill_parser_data
from youtube_calls import playlist_insert
from youtube_profile import YoutubeProfile


def local_mongo_to_atlas():
    parser_data = fill_parser_data()
    local_conn_str = "mongodb://{usr}:{pwd}@{host}/{dbname}".format(usr=parser_data['mongouser'],
                                                                    pwd=parser_data['mongopassword'],
                                                                    host='127.0.0.1:27017', dbname='admin')
    atlas_usr = text = input("atlas username")
    atlas_pwd = text = input("atlas password")
    atlas_host = text = input("atlas host")
    atlas_conn_str = "mongodb+srv://{usr}:{pwd}@{host}/{dbname}".format(usr=atlas_usr,
                                                                        pwd=atlas_pwd,
                                                                        host=atlas_host,
                                                                        dbname='test')
    local_mongo = MongoClient(local_conn_str)
    atlas_mongo = MongoClient(atlas_conn_str)
    local_database_names = local_mongo.list_database_names()
    atlas_database_names = atlas_mongo.list_database_names()
    if 'vBulletin' in local_database_names:
        local_vbulletin_db = local_mongo['vBulletin']
        atlas_vbulletin_db = atlas_mongo['vBulletin']
        local_collection_names = local_vbulletin_db.list_collection_names()
        for collection_name in local_collection_names:
            local_collection = list(local_vbulletin_db[collection_name].find())
            atlas_connection = atlas_vbulletin_db[collection_name]
            atlas_connection.insert_many(local_collection)


T = TypeVar('T')


def exponential_backoff_func(retried_func: Callable[[], T], *args, sleep_time=1, max_backoffs=0) -> T:
    retries = 0
    while True:
        try:
            print('Retry: ' + str(retries) + ' -> ' + retried_func.__name__)
            return retried_func(*args)
        except Exception as err:
            print(err)
            if max_backoffs > 0 and (retries == max_backoffs):
                raise
            else:
                time.sleep(sleep_time * 2 ** retries)
                retries += 1


def read_playlist_by_id(user_profile, playlist_id):
    if not user_profile.has_quota:
        return ''
    mis_listas = user_profile.youtube.playlists().list(part='id,snippet,status',
                                                       id=playlist_id).execute(num_retries=3)
    print(mis_listas)
    return mis_listas


def read_playlists_from_user(user_profile):
    if not user_profile.has_quota:
        return ''
    all_results = []
    next_page = ''
    while True:
        mis_listas = user_profile.youtube.playlists().list(part='id,snippet,status',
                                                           pageToken=next_page, mine=True).execute(
            num_retries=3)
        next_page = mis_listas.get('nextPageToken')
        for lista_yt in mis_listas['items']:
            print(lista_yt)
            all_results.append(lista_yt)
        if not next_page:
            break
    # playlist not found
    pass


def test_error_values_playlistitems_insert(user_profile):
    # duplicate video
    try:
        add_video_req = playlist_insert(playlist_id='PLDG0iEBKCgpZ5a8EbAnoLLguH0P8JVZok',
                                        # video_id='hJ_HnbPTDWc',
                                        video_id='6MVGhGdpdDI',
                                        youtube=user_profile.youtube)
    except Exception as err:
        print(err)
    pass


def test_threads(user_profile):
    # read_playlists_from_user(user_profile)
    # exponential_backoff_func(read_playlists_from_user, user_profile, sleep_time=1, max_backoffs=0)
    x = threading.Thread(target=exponential_backoff_func,
                         args=(read_playlists_from_user, user_profile),
                         kwargs={
                             'sleep_time': 1, 'max_backoffs': 0})
    y = threading.Thread(target=exponential_backoff_func,
                         args=(read_playlist_by_id, user_profile, 'PLDG0iEBKCgpZ5a8EbAnoLLguH0P8JVZok'),
                         kwargs={
                             'sleep_time': 1, 'max_backoffs': 0})
    y.run()
    x.run()
    x.join()
    y.join()


def main():
    user_profile = YoutubeProfile(fill_parser_data())
    # test_threads(user_profile)
    # test_error_values_playlistitems_insert(user_profile)
    local_mongo_to_atlas()
    pass


# Lanzamos la función principal
if __name__ == "__main__":
    main()
