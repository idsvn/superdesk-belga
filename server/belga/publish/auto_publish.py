# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2013, 2014 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license

import json
import logging
import os
import socket
from base64 import b64encode
from urllib.parse import urlparse

import requests
import twitter
from eve.utils import ParsedRequest
from flask import current_app as app
from lxml import etree

from apps.auth.errors import CredentialsAuthError
from apps.content_types import apply_schema
from superdesk import get_resource_service
from superdesk.metadata.item import CONTENT_STATE, ITEM_STATE
from superdesk.publish.formatters import get_formatter

logger = logging.getLogger(__name__)


class AutoPublishService():
    def __init__(self):
        self.query = {
            'query': {
                'filtered': {
                    'filter': {
                        "and": [
                            {"not": {"term": {"state": "spiked"}}},
                            {"term": {"type": "text"}},
                        ]
                    }
                }
            }
        }
        self.repo = 'archive,ingest'
        self.url = app.config['SUPERDESK_PUBLISHER_URL']

    def _check_connection(self):
        if not self.url:
            return
        parse = urlparse(self.url)
        host = parse.hostname
        port = parse.port if parse.port else 80
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0

    def auth(self):
        session_id = self._get_session_id(app.config['SUPERDESK_USERNAME'], app.config['SUPERDESK_PASSWORD'])
        token = self._get_token(session_id)
        try:
            response = requests.post(
                self.url + '/auth/superdesk/',
                json={
                    'session_id': session_id,
                    'token': token,
                }).json()
            token = response['token']['api_key']
            return token
        except (ValueError, KeyError):
            return ''

    def run(self):
        resources = self.get_resources()
        subscribers = list(get_resource_service('subscribers').get(req=None, lookup=None))
        if not subscribers:
            return
        subscriber = subscribers[0]

        if not self._check_connection():
            logger.error('belga:publish:autopublish: Publisher server is not available.')
            return

        token = self.auth()
        if not token:
            return

        for item in list(resources):
            if item.get('_type') == 'ingest':
                continue
            doc = get_resource_service('archive').find_one(req=None, _id=item['_id'])
            formatter = get_formatter('ninjs', item)
            formatted_docs = formatter.format(article=apply_schema(doc),
                                              subscriber=subscriber,
                                              codes=None)
            doc = formatted_docs[0][1]
            response = requests.post(
                self.url + '/organization/rules/evaluate',
                data=doc,
                headers={'Authorization': token})

            tenants = response.json().get('tenants')
            # no matching rules available
            if not tenants or not tenants[0].get('route'):
                continue
            try:
                # avoid packages item
                if any([item.get('fields_meta'), item.get('body_html')]):
                    # twitter publishing
                    with open('token_twitter.json') as f:
                        try:
                            twitter_token = json.load(f)
                            twitter_api = twitter.Api(
                                os.environ.get('TWITTER_KEY', ''),
                                os.environ.get('TWITTER_KEY_SECRET', ''),
                                twitter_token.get('oauth_token', ''),
                                twitter_token.get('oauth_token_secret', '')
                            )
                            updates = item['headline']
                            # twitter increase limit to 280 but the library still use 140 char limit
                            if len(updates) > 130:
                                updates = updates[:130]
                            twitter_api.PostUpdate(updates)
                        except Exception as e:
                            logger.error(e.args[0])
                    # facebook publishing
                    with open('token_facebook.json') as f:
                        try:
                            facebook_token = json.load(f)
                            url = 'https://graph.facebook.com/v4.0/'
                            pages = facebook_token.get('pages', '')
                            content = item['headline'] + '\r\n\r\n' + etree.fromstring(item['body_html']).text
                            for page in pages:
                                request = requests.post(
                                    url + page['id'] + '/feed',
                                    params={'access_token': page['access_token']},
                                    data={'message': content}
                                )
                                if request.status_code != 200:
                                    logger.error(request.text)
                        except Exception as e:
                            logger.error(e.args[0])
                get_resource_service('archive_publish').patch(
                    id=item['_id'],
                    updates={ITEM_STATE: CONTENT_STATE.PUBLISHED}
                )
                logger.info('belga:publish:autopublish: Published item %s' % item.get('guid'))
            # invalid item raise outside app context
            except RuntimeError:
                pass

    def get_resources(self):
        req = ParsedRequest()
        req.args = {'repo': self.repo, 'source': json.dumps(self.query)}
        return get_resource_service('search').get(req=req, lookup=None)

    def _get_session_id(self, username, password):
        credentials = {
            'username': username,
            'password': password
        }
        service = get_resource_service('auth_db')
        try:
            session_id = str(service.post([credentials])[0])
            return session_id
        except CredentialsAuthError:
            logger.error('belga:publish:autopublish: Invalid username/password')
            return

    def _get_token(self, session_id):
        service = get_resource_service('auth_db')
        creds = service.find_one(req=None, _id=session_id)
        if not creds:
            return
        token = creds.get('token').encode('ascii')
        encoded_token = b'basic ' + b64encode(token + b':')
        return encoded_token
