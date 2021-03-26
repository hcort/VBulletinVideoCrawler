"""
    Two threads:
    - pending videos thread: gets videos from the database and inserts them into a playlist
    - parsing thread: visits every thread looking for new videos and inserts them into the pending videos database
"""
import logging
import threading
import time
from threading import Thread

from googleapiclient.errors import HttpError

from mongo_utils import check_lists_for_updates
from parse_youtube_links import VBulletinVideoCrawler
from pending_videos import find_playlist_id
from utils import extract_thread_id_from_url, process_exception, get_error_names, fill_parser_data, \
    login_data_from_parser_data, extract_thread_modification_date, remove_videos_already_in_list, \
    convert_video_list_in_dict
from youtube_calls import playlist_insert, read_etags_from_playlists
from youtube_profile import YoutubeProfile

threads_log = logging.getLogger(__name__)

"""
    Sleep time -> quota is around 10.000 units/day. Insert operation is 50 units. So 200 videos a day
    86400 seconds/day / 200 videos/day = 432 seconds between each insert operation
    
    I try to insert up to 5 videos in each insert operation
"""
NUM_VIDEOS_INSERT_OP = 5
SLEEP_TIME_ONE_VIDEO = 450

SLEEP_TIME_PARSER = 60 * 30


def get_video_index(search_id, video_list):
    # https://www.youtube.com/watch?v=01345678901
    for idx, item in enumerate(video_list):
        item_id_from_url = item['url'][-11:]
        if item_id_from_url == search_id:
            return idx
    return -1


class PendingVideosThread(Thread):

    def __init__(self, user_profile, lock):
        Thread.__init__(self)
        self.running = True
        self.__user_profile = user_profile
        self.__database_lock = lock

    def run(self):
        while self.running:
            inserted_videos = self.insert_pending_videos_from_database()
            time.sleep(SLEEP_TIME_ONE_VIDEO * inserted_videos)

    def insert_videos(self, video_list, playlist_id):
        if not video_list:
            threads_log.debug('Video list is empty - No videos will be inserted')
        inserted_videos = []
        video_id = ''
        for video_to_insert in video_list:
            try:
                video_id = extract_thread_id_from_url(video_to_insert['url'])
                threads_log.debug("Inserting video " + video_id + ' into playlist ' + playlist_id)
                insert_result = playlist_insert(playlist_id, video_id, self.__user_profile.youtube)
                inserted_videos.append(insert_result)
                threads_log.debug("Video inserted: " + str(insert_result))
            except HttpError as err:
                process_exception(self.__user_profile, err,
                                  custom_str='Error adding video: ' + video_id + '\n' + str(err.content))
                error_names_list = get_error_names(err)
                threads_log.error('Error adding video: ' + video_id + '\n' + str(err.content))
                threads_log.error('Error list: ' + str(error_names_list))
                # remove video for some errors
                # there is no duplicate control!!!!!
                # https://stackoverflow.com/questions/39687442/how-to-disable-inserting-the-same-video-in-playlist-using-youtube-api-v3
                # apparently the limit of a playlist is 5.000 videos
                # https://webapps.stackexchange.com/questions/77790/what-is-the-maximum-youtube-playlist-length
                # threads in vBulletin go up to 2.000 posts so this limit won't be reached
                if ('videoAlreadyInPlaylist' in error_names_list) or ('videoNotFound' in error_names_list):
                    inserted_videos.append({'videoId': video_id, 'etag': ''})
                    threads_log.debug('Error adding video: ' + video_id + '. Video can be removed from pending list')
        return inserted_videos

    def update_playlist_in_database(self, playlist_id, inserted_videos):
        # I need to lock this collection as the other thread reads it to remove duplicates
        database = self.__user_profile.mongo['vBulletin']
        # update playlists_created: add videos and get new etag
        playlist_in_db = database['playlists_created'].find_one({'id': playlist_id})
        if not playlist_in_db:
            # what to do (?)
            threads_log.debug('Playlist ' + playlist_id + ' not found - Creating...')
            playlist_in_db = {
                'id': playlist_id,
                'videos': [],
                'etag': ''
            }
        etag = read_etags_from_playlists(self.__user_profile, playlist_id=playlist_id)
        playlist_in_db['etag'] = etag[0]['playlist_etag']
        # check if I need to refresh the playlist
        for inserted_video in inserted_videos:
            threads_log.debug('Adding video ' + inserted_video['videoId'] + ' to playlist ' + playlist_id)
            threads_log.debug('Adding video ' + inserted_video['videoId'] + ' with etag = ' + inserted_video['etag'])
            if inserted_video['etag']:
                playlist_in_db['videos'].append(inserted_video)
        # read etag from playlist
        database['playlists_created'].replace_one(filter={'id': playlist_id},
                                                  replacement=playlist_in_db, upsert=True)
        threads_log.debug('Collection playlists_created updated')
        threads_log.debug('Playlist ' + playlist_id + ' has ' + str(len(playlist_in_db['videos'])) + 'videos')

    def update_pending_videos_collection(self, thread_id, inserted_videos):
        # i only remove videos in inserted_videos, as there may be some video in videos_to_insert that
        # couldn't be inserted due to some error and I will need to retry later
        database = self.__user_profile.mongo['vBulletin']
        pending_videos_from_thread = database['pending_videos'].find_one({'id': thread_id})
        for inserted_video in inserted_videos:
            idx_video = get_video_index(inserted_video['videoId'], pending_videos_from_thread['videos'])
            threads_log.debug('Removing video ' + inserted_video['videoId'] + ' from pending. Index=' + str(idx_video))
            if idx_video >= 0:
                pending_videos_from_thread['videos'].pop(idx_video)
        database['pending_videos'].replace_one(filter={'id': thread_id},
                                               replacement=pending_videos_from_thread, upsert=True)
        threads_log.debug('Collection pending_videos updated')
        threads_log.debug('Thread ' + thread_id + ' has ' + str(len(pending_videos_from_thread['videos'])) +
                          'pending videos')

    def update_database(self, playlist_id, thread_id, inserted_videos):
        # I lock pending_videos so the other thread can't access it while updating
        with self.__database_lock:
            self.update_pending_videos_collection(thread_id, inserted_videos)
            self.update_playlist_in_database(playlist_id, inserted_videos)

    def process_pending_videos_from_thread(self, pending_list):
        video_list = pending_list.get('videos', [])
        threads_log.debug('Check pending video list from thread ' + pending_list['id'] +
                          ' has ' + str(len(video_list)) + 'pending videos')
        if not video_list:
            threads_log.debug('No pending videos...')
            return []
        videos_to_insert = video_list[:NUM_VIDEOS_INSERT_OP]
        updated_thread_id = pending_list['id']
        playlist_id = find_playlist_id(user_profile=self.__user_profile, thread_id=updated_thread_id)
        # the other thread may have put videos in pending list before they were uploaded
        threads_log.debug('Pending videos from playlist: ' + playlist_id)
        num_videos = len(videos_to_insert)
        for video in videos_to_insert:
            threads_log.debug('Pending videos to insert: ' + str(video))
        duplicates = remove_videos_already_in_list(self.__user_profile,
                                                   vid_dict=convert_video_list_in_dict(videos_to_insert),
                                                   playlist_id=playlist_id)
        if duplicates:
            threads_log.debug('Some videos have been deleted [duplicates] - New list')
            for duplicate in duplicates:
                threads_log.debug('Duplicates: ' + str(duplicate))
        return self.insert_videos(videos_to_insert, playlist_id)

    def insert_pending_videos_from_database(self):
        # read NUM_VIDEOS_INSERT_OP from database and try to insert them
        updated_thread_id = ''
        # no need to lock for this read operation
        pending_videos_list = self.__user_profile.mongo_pending_videos_list()
        playlist_id = ''
        inserted_videos = []
        for idx, pending_list in enumerate(pending_videos_list):
            inserted_videos = self.process_pending_videos_from_thread(pending_list)
            if inserted_videos:
                updated_thread_id = pending_list['id']
                playlist_id = find_playlist_id(user_profile=self.__user_profile, thread_id=updated_thread_id)
                break
        if not playlist_id or not inserted_videos:
            # this means pending_videos is empty
            threads_log.debug('No videos have been inserted in this iteration, exiting...')
            return 0
        self.update_database(playlist_id=playlist_id,
                             thread_id=updated_thread_id,
                             inserted_videos=inserted_videos)
        return len(inserted_videos)

    def stop(self):
        self.running = False


class VBulletinParserThread(Thread):

    def __init__(self, user_profile, lock):
        Thread.__init__(self)
        self.running = True
        self.__user_profile = user_profile
        self.__database_lock = lock
        self.__parser = VBulletinVideoCrawler(login_url=self.__user_profile.forum_login_url,
                                              login_data=login_data_from_parser_data(self.__user_profile.parser_data))

    def run(self):
        while self.running:
            self.parse_thread_list()
            time.sleep(SLEEP_TIME_PARSER)

    def stop(self):
        self.running = False

    def parse_thread_list(self):
        # no need to lock this as no other thread writes here
        # read threads from mongo
        for thread in self.__user_profile.mongo_thread_list():
            # if we can't upload all the videos because of quota we exit
            self.parse_thread_and_insert_in_db(thread)

    def parse_thread_and_insert_in_db(self, thread):
        last_post = thread.get('last_post', '')
        # upload videos found in the thread
        thread_url = self.__user_profile.forum_base + 'showthread.php?t=' + thread['id']
        # check last modification date
        last_mod_date_bd = thread.get('last_mod_date', '')
        last_mod_date = extract_thread_modification_date(self.__user_profile, thread_url)
        threads_log.debug('Parsing thread ' + thread['id'])
        threads_log.debug('Parsing thread - last_post = ' + last_post)
        threads_log.debug('Parsing thread - last_mod_date_bd' + last_mod_date_bd)
        threads_log.debug('Parsing thread - last_mod_date' + last_mod_date)
        if last_mod_date_bd == last_mod_date:
            threads_log.debug('No updates in thread')
            return
        else:
            thread['last_mod_date'] = last_mod_date
        videos_found = self.__parser.start_parsing(thread_url, last_post)
        self.insert_parsed_videos_in_db(thread=thread, videos_found=videos_found)
        self.update_thread_in_db(thread)

    def insert_parsed_videos_in_db(self, thread, videos_found):
        if not videos_found:
            threads_log.debug('No new videos found in thread ' + thread['id'])
            return
        with self.__database_lock:
            database = self.__user_profile.mongo['vBulletin']
            # check for duplicates
            # need to lock because I don't want to check while the other thread is updating
            threads_log.debug('Videos found in thread ' + thread['id'])
            for video in videos_found:
                threads_log.debug(str(videos_found[video]))
            duplicates = remove_videos_already_in_list(self.__user_profile, vid_dict=videos_found,
                                                       playlist_id=thread['playlist_id'])
            if duplicates:
                threads_log.debug('Some videos have been deleted as duplicates')
                for duplicate in duplicates:
                    threads_log.debug(str(duplicate))
            pending_videos_from_thread = database['pending_videos'].find_one({'id': thread['id']})
            if not pending_videos_from_thread:
                pending_videos_from_thread = {
                    'id': thread['id'],
                    'videos': []
                }
            for video_id in videos_found:
                pending_videos_from_thread['videos'].append(videos_found[video_id])
            database['pending_videos'].replace_one(filter={'id': thread['id']},
                                                   replacement=pending_videos_from_thread, upsert=True)
            threads_log.debug('Collection pending_videos has been updated')
            threads_log.debug('Thread ' + thread['id'] + ' has ' + str(len(pending_videos_from_thread['videos'])) +
                              'pending videos')

    def update_thread_in_db(self, thread):
        # no need to lock here, only this thread uses this collection
        database = self.__user_profile.mongo['vBulletin']
        database['video_threads'].replace_one(filter={'id': thread['id']},
                                              replacement=thread, upsert=True)
        threads_log.debug('Collection pending_videos has been updated')


def main():
    log_format = "%(asctime)s - %(levelname)s - %(threadName)s > [%(filename)s > %(funcName)s() > %(lineno)s]\t%(" \
                 "message)s "
    # logging.basicConfig(
    #     format=,
    #     level=logging.DEBUG,
    #     filename='res/threads.log')
    threads_log.setLevel(logging.DEBUG)

    file = logging.FileHandler('res/threads.log')
    file.setLevel(logging.DEBUG)
    fileformat = logging.Formatter(log_format, datefmt="%H:%M:%S")
    file.setFormatter(fileformat)
    threads_log.addHandler(file)

    stream = logging.StreamHandler()
    stream.setLevel(logging.DEBUG)
    streamformat = logging.Formatter(log_format)
    stream.setFormatter(streamformat)
    threads_log.addHandler(stream)

    threads_log.info('Log started')

    user_profile = YoutubeProfile(fill_parser_data())
    # update the playlists_created collection
    check_lists_for_updates(user_profile)

    lock = threading.Lock()
    thread_1 = PendingVideosThread(user_profile=user_profile, lock=lock)
    thread_2 = VBulletinParserThread(user_profile=user_profile, lock=lock)
    thread_1.run()
    thread_2.run()
    enter_str = input("Enter your input: ")
    thread_1.stop()
    thread_2.stop()
    thread_1.join()
    thread_2.join()
    print('done!')


# Lanzamos la función principal
if __name__ == "__main__":
    main()
