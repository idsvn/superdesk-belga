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
from unittest.mock import MagicMock

from flask import current_app as app
from httmock import HTTMock, urlmatch

from belga.publish.auto_publish import AutoPublishService
from superdesk import get_resource_service
from superdesk.metadata.item import CONTENT_STATE
from superdesk.publish.subscribers import SUBSCRIBER_TYPES
from superdesk.tests import TestCase


@urlmatch(scheme='http', netloc='localhost', path='/api/v1/auth/superdesk', method='POST')
def auth_request(url, request):
    return json.dumps({'token': {'api_key': 'abc'}})


@urlmatch(scheme='http', netloc='localhost', path='/api/v1/organization/rules/evaluate', method='POST')
def evaluate_request(url, request):
    return json.dumps({'tenants': [{'route': '/business'}]})


class AutoPublishServiceTest(TestCase):
    def setUp(self):
        app.config['SUPERDESK_PUBLISHER_URL'] = 'http://localhost/api/v1'
        app.config['SUPERDESK_USERNAME'] = 'abc'
        app.config['SUPERDESK_PASSWORD'] = 'abc'
        self.publish_service = AutoPublishService()

    def test_auth(self):
        with HTTMock(auth_request):
            token = self.publish_service.auth()
        assert token == 'abc'

    def test_auto_publish(self):
        publish_service = AutoPublishService()
        publish_service._check_connection = MagicMock(return_value=True)
        archive_service = get_resource_service('archive')
        item = {
            'type': 'text',
            'state': CONTENT_STATE.PROGRESS,
            'unique_name': 'abc',
            'headline': '<h1>abc</h1>',
            'slugline': 'Slugline',
            'body_html': '<p>Lorem Ipsum</p>',
            '_current_version': 1,
        }

        archive_service.post([item])
        item['_type'] = 'archive'
        publish_service.get_resources = MagicMock(return_value=[item])

        get_resource_service('subscribers').post([{
            "_id": "1", "name": "sub1", "is_active": True,
            "subscriber_type": SUBSCRIBER_TYPES.WIRE,
            "media_type": "media",
            "sequence_num_settings": {"max": 10, "min": 1},
            "email": "test@test.com",
            "products": ["1"],
            "destinations": [{
                "name": "dest1", "format": "nitf",
                "delivery_type": "http_push",
                "config": {"address": "127.0.0.1", "username": "test"}
            }]
        }])

        with HTTMock(auth_request, evaluate_request):
            publish_service.run()
        item = list(get_resource_service('published').get(req=None, lookup=None))[0]
        assert item['state'] == 'published'
