import json

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

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

CLIENT_SECRETS_FILE = 'client_secret.json'

# This OAuth 2.0 access scope allows for full read/write access to the
# authenticated user's account.
SCOPES = ['https://www.googleapis.com/auth/youtube']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'


# Authorize the request and store authorization credentials.
def get_authenticated_service():
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    credentials = flow.run_console()
    return build(API_SERVICE_NAME, API_VERSION, credentials=credentials)


def add_video_to_playlist(youtube, videoID, playlistID):
    add_video_request = youtube.playlistItem().insert(
        part="snippet",
        body={
            'snippet': {
                'playlistId': playlistID,
                'resourceId': {
                    'kind': 'youtube#video',
                    'videoId': videoID
                }
                # 'position': 0
            }
        }
    ).execute()


def add_playlist(youtube, vid_dict, name='', description='', url='', privacy='unlisted'):
    if not vid_dict:
        return ''

    if not name:
        name = description
    name = name.strip()
    body = dict(
        snippet=dict(
            title=name,
            description='Playlist creada con VBulletinVideoCrawler.\n{}\n{}'.format(description, url)
        ),
        status=dict(
            privacyStatus=privacy
        )
    )

    try:
        next_page = ''
        create_list = True
        while True:
            mis_listas = youtube.playlists().list(part='id,snippet,status',
                                                  pageToken=next_page, mine=True).execute()
            next_page = mis_listas.get('nextPageToken')
            for lista_yt in mis_listas['items']:
                if lista_yt['snippet'].get('title') == name:
                    create_list = False
                    playlist_id = lista_yt['id']
                    break
            if not next_page:
                break
        if create_list:
            playlists_insert_response = youtube.playlists().insert(
                part='snippet,status',
                body=body
            ).execute()

            playlist_id = playlists_insert_response['id']
    except HttpError as err:
        print('Error creating playlist ' + name + '\n' + str(err) + '\n\n')
        return ''

    try:
        next_page = ''
        while True:
            list_uploaded_videos = youtube.playlistItems().list(playlistId=playlist_id, part='snippet', pageToken=next_page).execute()
            next_page = list_uploaded_videos.get('nextPageToken')
            for lista_yt in list_uploaded_videos['items']:
                # using part=snippet
                video_id = lista_yt['snippet']['resourceId']['videoId']
                popped_elem = vid_dict.pop(video_id, None)
                if popped_elem:
                    print('Video already in list: ' + video_id)
            if not next_page:
                break
    except HttpError as err:
        print('Error reading playlist ' + name + '\n' + str(err) + '\n\n')
        return ''

    for video_id in vid_dict:
        # add_video_to_playlist(youtube, video_id, playlist_id)
        try:
            add_video_request = youtube.playlistItems().insert(
                part="snippet",
                body={
                    'snippet': {
                        'playlistId': playlist_id,
                        'resourceId': {
                            'kind': 'youtube#video',
                            'videoId': video_id
                        }
                        # 'position': 0
                    }
                }
            ).execute()
            print(add_video_request)
        except HttpError as err:
            print('Error adding video: ' + video_id + '\n' + str(err) + '\n\n')
            err_as_json = json.loads(err.content)
            error_list = err_as_json['error'].get('errors')
            if error_list:
                for insert_err in error_list:
                    quota_error = (insert_err['reason'] == 'quotaExceeded')
                    if quota_error:
                        print('Daily quota exceeded - Finishing uploads')
                        return video_id

    print('All videos uploaded')
    return list(vid_dict.keys())[-1]
