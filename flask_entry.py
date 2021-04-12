# -*- coding: utf-8 -*-

import os
import re

import flask

import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery

# https://github.com/youtube/api-samples/blob/master/python/quickstart_web.py

# The CLIENT_SECRETS_FILE variable specifies the name of a file that contains
# the OAuth 2.0 information for this application, including its client_id and
# client_secret.
from flask import request, render_template
from pymongo import MongoClient

from youtube_calls import get_flow_from_env, playlist_insert

CLIENT_SECRETS_FILE = "res/client_secret.json"

# This OAuth 2.0 access scope allows for full read/write access to the
# authenticated user's account and requires requests to use an SSL connection.
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
app = flask.Flask(__name__)
# Note: A secret key is included in the sample so that it works, but if you
# use this code in your application please replace this with a truly secret
# key. See http://flask.pocoo.org/docs/0.12/quickstart/#sessions.
app.secret_key = 'REPLACE ME - this value is here as a placeholder.'


@app.route('/clear')
def clear():
    flask.session.clear()
    return flask.redirect('/')


@app.route('/')
def index():
    if 'credentials' not in flask.session:
        return flask.redirect('authorize')

    # Load the credentials from the session.
    credentials = google.oauth2.credentials.Credentials(
        **flask.session['credentials'])

    client = googleapiclient.discovery.build(
        API_SERVICE_NAME, API_VERSION, credentials=credentials)

    return channels_list_by_username(client,
                                     part='snippet,contentDetails,statistics',
                                     # forUsername='GoogleDevelopers')
                                     mine=True)


@app.route('/authorize')
def authorize():
    callback_url = request.args.get('callback', '')
    # Create a flow instance to manage the OAuth 2.0 Authorization Grant Flow
    # steps.
    flow = get_flow_from_env()
    if callback_url:
        flow.redirect_uri = flask.url_for('oauth2callback', _external=True) + '?callback=' + callback_url
    else:
        flow.redirect_uri = flask.url_for('oauth2callback',  _external=True)
    # flow.redirect_uri = flask.url_for(callback_url, _external=True)
    authorization_url, state = flow.authorization_url(
        # This parameter enables offline access which gives your application
        # both an access and refresh token.
        access_type='offline',
        # This parameter enables incremental auth.
        include_granted_scopes='true')

    # Store the state in the session so that the callback can verify that
    # the authorization server response.
    flask.session['state'] = state

    return flask.redirect(authorization_url)


@app.route('/update_test', methods=['GET', 'POST'])
def update_test():
    if request.method == 'POST':
        mongouser = request.form['mongouser']
        mongopassword = request.form['mongopassword']
        # Load the credentials from the session.
        credentials = google.oauth2.credentials.Credentials(
            **flask.session['credentials'])
        client = googleapiclient.discovery.build(
            API_SERVICE_NAME, API_VERSION, credentials=credentials)
        atlas_conn_str = "mongodb+srv://{usr}:{pwd}@{host}/{dbname}".format(usr=mongouser,
                                                                            pwd=mongopassword,
                                                                            host='cluster0.crnjd.mongodb.net',
                                                                            dbname='test')
        atlas_mongo = MongoClient(atlas_conn_str)
        database = atlas_mongo['vBulletin']
        video_thread = database['video_threads'].find_one()
        pending_list = database['pending_videos'].find_one({'id': video_thread['id']})
        video_url = pending_list['videos'][10]['url']
        regex_id = re.compile("watch\?v=([^\"&?\\\/]{11})")
        m = regex_id.search(video_url)
        video_id = m.group(1)
        playlist_insert_response = playlist_insert(playlist_id=video_thread['playlist_id'],
                                                   video_id=video_id,
                                                   youtube=client)
        return flask.jsonify(playlist_insert_response)

    if 'credentials' not in flask.session:
        return flask.redirect('authorize?callback=update_test')
    return render_template('update_test.html')


@app.route('/oauth2callback')
def oauth2callback():
    # Specify the state when creating the flow in the callback so that it can
    # verify the authorization server response.
    state = flask.session['state']
    # flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
    #     CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
    flow = get_flow_from_env()

    callback_url = request.args.get('callback', '')
    if callback_url:
        flow.redirect_uri = flask.url_for('oauth2callback', _external=True) + '?callback=' + callback_url
        redirect_uri = flask.url_for(callback_url)
    else:
        flow.redirect_uri = flask.url_for('oauth2callback')
        redirect_uri = flask.url_for('index')

    # Use the authorization server's response to fetch the OAuth 2.0 tokens.
    authorization_response = flask.request.url
    flow.fetch_token(authorization_response=authorization_response)

    # Store the credentials in the session.
    # ACTION ITEM for developers:
    #     Store user's access and refresh tokens in your data store if
    #     incorporating this code into your real app.
    credentials = flow.credentials
    flask.session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    return flask.redirect(redirect_uri)


def channels_list_by_username(client, **kwargs):
    response = client.channels().list(
        **kwargs
    ).execute()

    return flask.jsonify(**response)


if __name__ == '__main__':
    # When running locally, disable OAuthlib's HTTPs verification. When
    # running in production *do not* leave this option enabled.
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    app.run('localhost', 8090, debug=True)
