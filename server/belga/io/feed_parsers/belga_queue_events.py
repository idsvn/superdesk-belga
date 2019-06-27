# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2013 - 2018 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license

import logging
from copy import deepcopy
from datetime import datetime

from pytz import country_timezones

from superdesk.io.feed_parsers import FeedParser
from superdesk.io.registry import register_feed_parser
from superdesk.utc import local_to_utc

logger = logging.getLogger(__name__)


class BelgaQueueEventsParser(FeedParser):
    """Parser for events pushed from Belga Agenda through ActiveMQ
    """

    NAME = 'belgaqueueevents'

    label = 'Belga Queue Events Parser'

    REQUIRED_FIELD = [
        'eventId', 'startDate', 'endDate', 'createDate', 'url', 'contacts', 'countryCode', 'eventUploadContents'
        'mainRubric.rubricTexts', 'rubricEvent', 'eventUploadContents', 'recurrence',
        'venueInfo.venueId', 'venueInfo.street', 'venueInfo.streetNumber', 'venueInfo.country.countryTexts'
    ]
    OPTIONAL_FIELD = ['lastUpdateTime']

    def can_parse(self, data):
        for field in self.REQUIRED_FIELD:
            if not self._get(data, field):
                return False
        return True

    def _get(self, dict_item, keys):
        """Return nested item in dict via dot notation

        >> _get({'a': {'b': 'c'}}, 'a.b') == 'c'
        True
        """
        item = deepcopy(dict_item)
        for key in keys.split('.'):
            item = item.get(key, {})
            if not item:
                return item
        return item

    def parse(self, data):
        timezone = country_timezones.get(data['countryCode'])
        if not timezone:
            raise ValueError('Invalid timezone')
        timezone = timezone[0]  # pytz country timezones return list

        item = {
            'original_id': data['eventId'],
            'type': 'event',
            'dates': {
                'start': self._parse_date(timezone, data['startDate']),
                'end': self._parse_date(timezone, data['endDate']),
                'tz': timezone,
            },
            'calendars': [],
            'locations': self._parse_location(data['venueInfo']),
            'contacts': self._parse_contacts(data['contacts']),
            'links': [data['url']],
            'versioncreated': self._parse_date(timezone, data['createdDate']),
            'firstcreated': self._parse_date(timezone, data['createdDate']),
        }
        event = self._get_en_item(data['eventContents'])
        item.update({'name': event['title'], 'slugline': event['subject']})

        # update contact updated and created date:
        for c1, c2 in zip(item['contacts'], data['contacts']):
            c1["_updated"] = self._parse_date(timezone, c2['updatedDate'])
            c1["_created"] = self._parse_date(timezone, c2['createdDate'])

        if data.get('eventUploadContents'):
            item['files'] = [{
                'filename': fi['originalDocument'],
                'url': fi['downloadLink'],
                'original_id': fi['eventUploadId'],
            } for fi in data['eventUploadContents']]

        if data.get('lastUpdateTime'):
            item['_updated'] = self._parse_date(timezone, data['lastUpdateTime'])

        for rubric in [data['mainRubric']] + data.get('rubricEvent', []):
            rubric = self._get_en_item(rubric['rubricTexts'])
            item['calendars'].append({
                'is_active': True,
                'name': rubric['rubricName'],
                'qcode': rubric['rubricName'].lower()
            })
        return item

    def _get_en_item(self, list_items):
        """Return entries have EN language from a list of entries with multiple language
        """
        item = [i for i in list_items if i.get('language') == 'EN']
        return item[0]

    def _parse_date(self, timezone, time):
        """Convert string to UTC datetime object, timezone is based on country_code
        """
        return local_to_utc(timezone, datetime.strptime(time, '%d/%m/%Y %H:%M'))

    def _parse_location(self, location):
        """Parse location info from belga to superdesk format
        """
        return [{
            'name': location['venueName'],
            'address': {
                'line': [location['streetNumber'], location['street']],
                'locality': location['city'],
                'area': location['province'],
                'country': self._get_en_item(location['country']['countryTexts']),
                'postal_code': location['postCode'],
            },
            'original_id': location['venueId'],
        }]

    def _parse_contacts(self, contacts):
        phone_types = [
            'phoneGeneral', 'directPhone1', 'directPhone2', 'gsm1', 'gsm2', 'personalPhone', 'personalGsm',
            'personalMobile', 'semaphone', 'mobile247',
        ]
        email_types = ['email', 'personalEmail']
        address_types = ['professionalAddress', 'personalAddress']
        return [{
            'original_id': contact['contactId'],
            "honorific": "asdf",
            'first_name': contact['firstName'],
            'last_name': contact['lastName'],
            'organisation': contact['company'],
            'contact_email': [contact.get(email) for email in email_types if contact.get(email)],
            'contact_phone': [{
                'number': contact.get(phone),
                'public': False,
                'usage': 'Confidential',
            } for phone in phone_types if contact.get(phone)],
            "website": contact.get('url'),
            "twitter": contact.get('twitter'),
            "facebook": contact.get('facebook'),
            "contact_address": [contact.get(address) for address in address_types if contact.get(address)],
            "notes": contact.get('information'),
            "is_active": True,
            "public": contact['belgaPublic'] == 'Y',
        } for contact in contacts]

    def parse_recurence(self, item):
        return [item]


register_feed_parser(BelgaQueueEventsParser.NAME, BelgaQueueEventsParser())
