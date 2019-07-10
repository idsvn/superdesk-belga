# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2013 - 2018 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license
import json
import os
from datetime import datetime, timezone

from belga.io.feed_parsers.belga_queue_events import BelgaQueueEventsParser
from superdesk.tests import TestCase
from superdesk.utc import local_to_utc


class BelgaQueueEventsTest(TestCase):
    filename = 'queue_events.json'

    def setUp(self):
        dirname = os.path.dirname(os.path.realpath(__file__))
        fixture = os.path.normpath(os.path.join(dirname, '../fixtures', self.filename))
        provider = {'name': 'test'}
        with open(fixture, 'r') as f:
            parser = BelgaQueueEventsParser()
            self.data = json.load(f)['data']
            self.item = parser.parse(self.data, provider)

    def test_can_parse(self):
        self.assertTrue(BelgaQueueEventsParser().can_parse(self.data))

    def test_content(self):
        item = self.item
        self.assertEqual(item['original_id'], 345678)
        self.assertEqual(item['name'], 'Belga event')
        self.assertEqual(item['links'][0], 'https://belga.be')
        self.assertEqual(
            item['definition_short'],
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
            "Praesent a erat vel nisl pretium vehicula. Donec vestibulum tempor accumsan.")
        self.assertEqual(item['versioncreated'], datetime(2019, 6, 30, 4, tzinfo=timezone.utc))
        self.assertListEqual(item['calendars'], [{
            'is_active': True,
            'name': 'NEWS',
            'qcode': 'news',
        }, {
            'is_active': True,
            'name': 'POLITICS',
            'qcode': 'politics',
        }])
        self.assertDictEqual(item['dates'], {
            'start': datetime(2019, 6, 30, 22, tzinfo=timezone.utc),
            'end': datetime(2019, 7, 1, 21, 59, tzinfo=timezone.utc),
            'tz': 'Europe/Brussels'
        })
        self.assertDictEqual(item['files'][0], {
            'filename': 'image.jpg',
            'url': 'http://localhost/pressagenda/agenda/event-details-document.action?id=345678&docName=image.jpg',
            'original_id': 234567,

        })
        self.assertDictEqual(item['location'][0], {
            'name': "ING Contact Centre LLN",
            'address': {
                'line': ["6", "traverse d'Esope"],
                'locality': "Louvain-la-Neuve",
                'area': "BRABANT WALLON",
                'country': "BELGIUM",
                'postal_code': "1348",
            },
            'original_id': 250250,
        })
        contact = item['contacts'][0]
        self.assertEqual(contact['original_id'], 316395)
        self.assertEqual(contact['first_name'], 'Laurent')
        self.assertEqual(contact['last_name'], 'Dery')
        self.assertEqual(contact['organisation'], 'Lorem Ipsum')
        self.assertListEqual(contact['contact_email'], ['Laurent@gmail.com', 'DLaurent@gmail.com'])
        self.assertListEqual(contact['contact_phone'], [{
            'number': '+32 2 226 13 51',
            'usage': 'Business',
            'public': True,
        }, {
            'number': '+32 495 50 25 94',
            'usage': 'Business',
            'public': True,
        }, {
            'number': '123456789',
            'usage': 'Confidential',
            'public': False,
        }])
        self.assertListEqual(contact['mobile'], [{
            'number': '012012012',
            'usage': 'Confidential',
            'public': False,
        }, {
            'number': '987654321',
            'usage': 'Business',
            'public': True,
        }])
