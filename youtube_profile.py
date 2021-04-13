import json

from pymongo import MongoClient

from youtube_calls import get_authenticated_service


def build_youtube_profile(vbulletinuser='', vbulletinpwd='',
                          mongouser='', mongopwd='', mongohost='',
                          forumbase='',
                          credentials=None):
    parser_data = {
        "username": vbulletinuser,
        "password": vbulletinpwd,
        "mongouser": mongouser,
        "mongopassword": mongopwd,
        "mongohost": mongohost,
        "forum_base": forumbase
    }
    return YoutubeProfile(parser_data=parser_data, credentials=credentials)


class YoutubeProfileEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, YoutubeProfile):
            return {'parser_data': obj.parser_data,
                    'credentials': obj.credentials}
        # Let the base class default method raise a TypeError for unsupported objects.
        return json.JSONEncoder.default(self, obj)


# This object hook recognizes a Thread object dictionary created by ThreadEncoder,
# retrieves the function and arguments, and creates a Thread object.
# Note this isn't a perfect reproduction of the Thread object...it doesn't restore other
# possible parameters to the constructor like "daemon" or "name".
def json_as_youtube_profile(dct):
    # assume a 'thread' key indicates a Thread dictionary object.
    if 'parser_data' in dct:
        return YoutubeProfile(parser_data=dct['parser_data'], credentials=dct.get('credentials', None))
    return dct  # return unchanged if not a Thread.


class YoutubeProfile:

    def __init__(self, parser_data, credentials=None):
        """
            This class stores the basic data about the youtube user that is adding videos to playlists

            - parser_data
                - vBulletin login info - basic format
                    {
                        "username": "",
                        "password": "",
                        "mongouser": "",
                        "mongopassword": "",
                        "mongohost": "",
                        "forum_base": "https://www.someforum.com/forum/"
                    }

            - youtube handle
            - quota

            - local mongo db handle
        """
        self.__parser_data = parser_data
        self.__credentials = credentials
        self.__youtube = None
        self.__mongo = None
        self.__has_quota = True

    @property
    def parser_data(self):
        return self.__parser_data

    @property
    def credentials(self):
        return self.__credentials

    def set_quota_finished(self):
        self.__has_quota = False

    @property
    def has_quota(self):
        return self.__has_quota

    @property
    def youtube(self):
        if not self.__youtube:
            try:
                self.__youtube = get_authenticated_service(self.__credentials)
            except Exception as e:
                print('An unknown error occurred during youtube authentication:\n%s' % (str(e)))
        return self.__youtube

    @property
    def mongo(self):
        if not self.__mongo:
            if 'mongohost' in self.__parser_data:
                conn_str = "mongodb+srv://{usr}:{pwd}@{host}/{dbname}".format(usr=self.__parser_data['mongouser'],
                                                                              pwd=self.__parser_data['mongopassword'],
                                                                              host=self.__parser_data['mongohost'],
                                                                              dbname='test')
            else:
                conn_str = "mongodb://{usr}:{pwd}@{host}/{dbname}".format(usr=self.__parser_data['mongouser'],
                                                                          pwd=self.__parser_data['mongopassword'],
                                                                          host='127.0.0.1:27017', dbname='admin')
            self.__mongo = MongoClient(conn_str)
        return self.__mongo

    @property
    def forum_base(self):
        return self.__parser_data.get('forum_base', '')

    @property
    def forum_login_url(self):
        return self.forum_base + 'login.php'

    def mongo_thread_list(self):
        database = self.mongo['vBulletin']
        return list(database['video_threads'].find())

    def mongo_pending_videos_list(self):
        database = self.mongo['vBulletin']
        return list(database['pending_videos'].find())

    def mongo_playlists_created_list(self):
        database = self.mongo['vBulletin']
        return list(database['playlists_created'].find())

    def mongo_get_thread_info(self, thread_id):
        database = self.mongo['vBulletin']
        return database['video_threads'].find_one({'id': thread_id})

    def mongo_get_playlists_created_info(self, playlist_id):
        database = self.mongo['vBulletin']
        return database['playlists_created'].find_one({'id': playlist_id})

    def mongo_get_pending_videos_info(self, thread_id):
        database = self.mongo['vBulletin']
        return database['pending_videos'].find_one({'id': thread_id})

    def mongo_replace_playlists_created_item(self, playlist_id, replacement):
        database = self.mongo['vBulletin']
        playlists_created = database['playlists_created']
        playlists_created.replace_one(filter={'id': playlist_id}, replacement=replacement, upsert=True)

    def mongo_replace_video_threads_item(self, thread_id, replacement):
        database = self.mongo['vBulletin']
        video_threads = database['video_threads']
        video_threads.replace_one(filter={'id': thread_id}, replacement=replacement, upsert=True)

    def mongo_replace_pending_videos_item(self, thread_id, replacement):
        database = self.mongo['vBulletin']
        pending_videos = database['pending_videos']
        pending_videos.replace_one(filter={'id': thread_id}, replacement=replacement, upsert=True)
