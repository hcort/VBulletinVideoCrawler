import os

import google.oauth2.credentials
import google_auth_oauthlib
import googleapiclient
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError

from utils import process_exception

# The CLIENT_SECRETS_FILE variable specifies the name of a file that contains
# the OAuth 2.0 information for this application, including its client_id and
# client_secret. You can acquire an OAuth 2.0 client ID and client secret from
# the {{ Google Cloud Console }} at
# {{ https://cloud.google.com/console }}.
# Please ensure that you have enabled the YouTube Data API for your project.
# For more information about using OAuth2 to access the YouTube Data API, see:
#   https://developers.google.com/youtube/v3/guides/authentication
# For more information about the client_secrets.json file format, see:
#   https://developers.google.com/api-client-library/python/guide/aaa_client_secrets

CLIENT_SECRETS_FILE = 'res/client_secret.json'

# This OAuth 2.0 access scope allows for full read/write access to the
# authenticated user's account.
SCOPES = ['https://www.googleapis.com/auth/youtube']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'


def get_flow_from_file():
    return google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES)


def get_flow_from_env():
    custom_json_cfg = {
            'web': {
                'client_id': os.environ['VBULLETIN_OAUTH_CLIENT_ID'],
                'client_secret': os.environ['VBULLETIN_OAUTH_CLIENT_SECRET'],
                'redirect_uris': [],
                'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                'token_uri': 'https://accounts.google.com/o/oauth2/token'
            }
        }
    # flow =
    return google_auth_oauthlib.flow.Flow.from_client_config(custom_json_cfg, scopes=SCOPES)


# Authorize the request and store authorization credentials.
def get_authenticated_service(credentials_dict=None):
    """

    :param credentials_dict: credentials obtained via OAuth. If not present then generate url and print it
    :return: the youtube client
    """
    if os.environ.get('VBULLETIN_OAUTH_SOURCE', '') == 'env':
        flow = get_flow_from_env()
    else:
        flow = get_flow_from_file()
    if not credentials_dict:
        credentials = flow.run_console()
    else:
        credentials = google.oauth2.credentials.Credentials(
            credentials_dict["token"],
            refresh_token=credentials_dict["refresh_token"],
            token_uri=credentials_dict["token_uri"],
            client_id=credentials_dict["client_id"],
            client_secret=credentials_dict["client_secret"],
            scopes=credentials_dict["scopes"])
    return googleapiclient.discovery.build(API_SERVICE_NAME, API_VERSION, credentials=credentials)


def video_description(description='', url=''):
    return 'Playlist creada con VBulletinVideoCrawler.\n{}\n{}'.format(description, url)


def read_etags_from_playlists(user_profile, playlist_id=None):
    if not user_profile.has_quota:
        return ''
    etag_list = []
    if not playlist_id:
        playlist_ids = []
        for thread in user_profile.mongo_thread_list():
            id = thread.get('playlist_id', None)
            if id:
                playlist_ids.append(id)
        ids_as_str = ','.join(playlist_ids)
    else:
        ids_as_str = playlist_id
    try:
        mis_listas = user_profile.youtube.playlists().list(part='id,snippet,status',
                                                           id=ids_as_str).execute(num_retries=3)
        for item in mis_listas['items']:
            etag_list.append(
                {
                    'playlist_id': item['id'],
                    'playlist_etag': item['etag']
                }
            )
    except Exception as err:
        process_exception(user_profile, err, custom_str='')
    return etag_list


def get_videos_from_playlist(user_profile, playlist_id):
    whole_playlist = []
    try:
        next_page = ''
        while True:
            # iterate playlist videos to see if any pending videos is already in it and purge pending dict
            list_uploaded_videos = user_profile.youtube.playlistItems().list(playlistId=playlist_id,
                                                                             part='snippet',
                                                                             maxResults=50,
                                                                             pageToken=next_page).execute()
            next_page = list_uploaded_videos.get('nextPageToken')
            for lista_yt in list_uploaded_videos['items']:
                whole_playlist.append(
                    {
                        'videoId': lista_yt['snippet']['resourceId']['videoId'],
                        'etag': lista_yt['etag']
                    }
                )
            if not next_page:
                break
    except HttpError as err:
        process_exception(user_profile, err, custom_str='Error reading playlist ' + playlist_id)
    return whole_playlist


def search_playlist_by_name(user_profile, name=''):
    try:
        next_page = ''
        while True:
            mis_listas = user_profile.youtube.playlists().list(part='id,snippet,status',
                                                               pageToken=next_page, mine=True).execute(num_retries=3)
            next_page = mis_listas.get('nextPageToken')
            for lista_yt in mis_listas['items']:
                if lista_yt['snippet'].get('title') == name:
                    return lista_yt['id']
            if not next_page:
                break
    except HttpError as err:
        process_exception(user_profile, err, custom_str='Error searching playlist ' + name)
    return ''


def create_playlist(user_profile, name='', description='', privacy='unlisted', url=''):
    if not user_profile.has_quota:
        return ''
    if not name:
        name = description
    name = name.strip()
    body = dict(
        snippet=dict(
            title=name,
            description=video_description(description, url)
        ),
        status=dict(
            privacyStatus=privacy
        )
    )
    try:
        playlists_insert_response = user_profile.youtube.playlists().insert(part='snippet,status',
                                                                            body=body
                                                                            ).execute()
        playlist_id = playlists_insert_response['id']
        return playlist_id
    except HttpError as err:
        process_exception(user_profile, err, custom_str='Error creating playlist ' + name)
    return ''


def playlist_insert(playlist_id, video_id, youtube):
    add_video_request = youtube.playlistItems().insert(
        part="snippet",
        body={
            'snippet': {
                'playlistId': playlist_id,
                'resourceId': {
                    'kind': 'youtube#video',
                    'videoId': video_id
                }
            }
        }
    ).execute()
    return {
        'videoId': add_video_request['snippet']['resourceId']['videoId'],
        'etag': add_video_request['etag']
    }
