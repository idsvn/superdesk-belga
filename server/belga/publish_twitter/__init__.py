import json
import os

from authlib.client.oauth1_session import OAuth1Session
from flask import g, jsonify, redirect, request

import superdesk

bp = superdesk.Blueprint('twitter_publishing', __name__)


@bp.route('/twitter')
def twitter_auth():
    request_token_url = 'https://api.twitter.com/oauth/request_token'
    authenticate_url = 'https://api.twitter.com/oauth/authenticate'
    callback = os.environ.get('TWITTER_REDIRECT', 'http://localhost:5000')
    g.client.redirect_url = callback + '/twitter/callback'
    g.client.fetch_request_token(request_token_url)
    url = g.client.create_authorization_url(authenticate_url)
    return redirect(url)


@bp.route('/twitter/callback')
def twitter_callback():
    g.client.parse_authorization_response(request.url)
    access_token_url = 'https://api.twitter.com/oauth/access_token'
    try:
        token = g.client.fetch_access_token(access_token_url)
    except Exception as e:
        return jsonify({'error': e.args[0]})
    with open('token_twitter.json', 'w') as f:
        f.write(json.dumps(token))
    return jsonify({'message': 'OK'})


def init_app(app):
    superdesk.blueprint(bp, app)


@bp.before_request
def handle_request():
    key = os.environ.get('TWITTER_KEY', '')
    secret = os.environ.get('TWITTER_KEY_SECRET', '')
    client = OAuth1Session(key, secret)
    g.client = client
