import json
import os

import requests
from authlib.client.oauth2_session import OAuth2Session
from flask import g, jsonify, redirect, request

import superdesk

bp = superdesk.Blueprint('facebook_publishing', __name__)


@bp.route('/facebook')
def facebook_auth():
    authorization_endpoint = 'https://www.facebook.com/v4.0/dialog/oauth'
    redirect_uri = os.environ.get('FACEBOOK_REDIRECT' '')
    uri, state = g.client.create_authorization_url(authorization_endpoint, redirect_uri=redirect_uri)
    return redirect(uri)


@bp.route('/facebook/callback')
def facebook_callback():
    token_endpoint = 'https://graph.facebook.com/v4.0/oauth/access_token'
    redirect_uri = os.environ.get('FACEBOOK_REDIRECT' '')
    try:
        g.client.redirect_uri = redirect_uri
        token = g.client.fetch_token(
            token_endpoint, authorization_response=request.url, method='GET'
        )
    except Exception as e:
        return jsonify({'error': e.args[0]}, response_code=500)

    # Get list pages
    response = requests.get(
        'https://graph.facebook.com/v4.0/me/accounts',
        params={'access_token': token['access_token'], 'fields': 'id,access_token, name'}
    ).json()
    if response['data']:
        token['pages'] = response['data']
    with open('token_facebook.json', 'w') as f:
        f.write(json.dumps(token))
    return jsonify({'message': 'OK'})


def init_app(app):
    superdesk.blueprint(bp, app)


@bp.before_request
def handle_request():
    key = os.environ.get('FACEBOOK_KEY', '')
    secret = os.environ.get('FACEBOOK_KEY_SECRET', '')
    scope = 'manage_pages'
    client = OAuth2Session(key, secret, scope=scope)
    g.client = client
