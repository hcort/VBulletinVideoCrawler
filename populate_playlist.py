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
        return

    if not name:
        name = description
    body = dict(
        snippet=dict(
            title=name,
            description='Playlist creada con VBulletinVideoCrawler.\n{}\n{}'.format(description, url)
        ),
        status=dict(
            privacyStatus=privacy
        )
    )

    # TODO check if playlist already exists
    next_page = ''
    create_list = True
    while True:
        mis_listas = youtube.playlists().list(part='id,snippet,status',
                                              pageToken=next_page, mine=True).execute()
        next_page = mis_listas.get('nextPageToken')
        for lista_yt in mis_listas['items']:
            if lista_yt['snippet'].get('title') == name:
                create_list = False
                playlist_id = lista_yt['snippet'].get('id')
                break
        if not next_page:
            break
    if create_list:
        playlists_insert_response = youtube.playlists().insert(
            part='snippet,status',
            body=body
        ).execute()

        playlist_id = playlists_insert_response['id']


    # TODO read playlist and check for videos already uploaded?
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
            print('Error al añadir ' + video_id + '\n' + str(err) + '\n\n')

    print('New playlist ID: %s' % playlists_insert_response['id'])


if __name__ == '__main__':

    # parser = argparse.ArgumentParser()
    # parser.add_argument('--title',
    #                     default='Test Playlist',
    #                     help='The title of the new playlist.')
    # parser.add_argument('--description',
    #                     default='A private playlist created with the YouTube Data API.',
    #                     help='The description of the new playlist.')
    #
    # args = parser.parse_args()

    youtube = get_authenticated_service()
    try:
        add_playlist(youtube)
    except HttpError as e:
        print('An HTTP error %d occurred:\n%s' % (e.resp.status, e.content))
