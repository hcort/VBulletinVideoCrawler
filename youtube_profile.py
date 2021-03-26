from pymongo import MongoClient

from youtube_calls import get_authenticated_service


class YoutubeProfile:

    def __init__(self, parser_data):
        """
            This class stores the basic data about the youtube user that is adding videos to playlists

            - parser_data
                - vBulletin login info

            - youtube handle
            - quota

            - local mongo db handle
        """
        self.__parser_data = parser_data
        self.__youtube = None
        self.__mongo = None
        self.__has_quota = True

    @property
    def parser_data(self):
        return self.__parser_data

    def set_quota_finished(self):
        self.__has_quota = False

    @property
    def has_quota(self):
        return self.__has_quota

    @property
    def youtube(self):
        if not self.__youtube:
            try:
                self.__youtube = get_authenticated_service()
            except Exception as e:
                print('An unknown error occurred during youtube authentication:\n%s' % (str(e)))
        return self.__youtube

    @property
    def mongo(self):
        if not self.__mongo:
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
