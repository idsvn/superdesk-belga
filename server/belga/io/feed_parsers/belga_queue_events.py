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

    NAME = 'belga_queue_events'

    label = 'Belga Queue Events Parser'

    REQUIRED_FIELD = [
        'eventId', 'startDate', 'endDate', 'createdDate', 'countryCode', 'mainRubric.rubricTexts', 'rubricEvent',
        'venueInfo.venueId', 'venueInfo.street', 'venueInfo.streetNumber', 'venueInfo.country.countryTexts'
    ]
    OPTIONAL_FIELD = ['lastUpdateTime']

    def can_parse(self, data):
        if not data:
            return False

        for field in self.REQUIRED_FIELD:
            if not self._get(data, field):
                return False
        return True

    def _get(self, dict_item, keys):
        """Return nested item in dict via dot notation

        >>> _get({'a': {'b': 'c'}}, 'a.b')
        c
        """
        item = deepcopy(dict_item)
        for key in keys.split('.'):
            item = item.get(key, {})
            if not item:
                return item
        return item

    def parse(self, data, provider=None):
        try:
            timezone = country_timezones.get(data['countryCode'])
            if not timezone:
                raise ValueError('Invalid timezone')
            timezone = timezone[0]  # pytz country timezones are list

            item = {
                'original_id': data['eventId'],
                'type': 'event',
                'dates': {
                    'start': self._parse_date(timezone, data['startDate']),
                    'end': self._parse_date(timezone, data['endDate']),
                    'tz': timezone,
                },
                'calendars': [],
                'location': self._parse_location(data['venueInfo']),
                'links': [data.get('url')] if data.get('url') else [],  # avoid display empty link
                'versioncreated': self._parse_date(timezone, data['createdDate']),
                'firstcreated': self._parse_date(timezone, data['createdDate']),
            }
            event = self._get_en_item(data['eventContents'])
            item.update({'name': event['title'], 'definition_short': event['subject']})

            if data.get('contacts'):
                item['contacts'] = self._parse_contacts(data['contacts'])
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
        except KeyError as e:
            logger.error('Provider %s. Item ID %s. Key %s is not exist',
                         provider.get('name'), data.get('eventId'), e.args)

    def _get_en_item(self, list_items):
        """Return entries have EN language from a list of entries with multiple language
        """
        item = [i for i in list_items if i.get('language') == 'EN']
        return item[0]

    def _parse_date(self, timezone, time):
        """Convert string to UTC datetime object, timezone is based on country_code
        """
        try:
            return local_to_utc(timezone, datetime.strptime(time, '%d/%m/%Y %H:%M'))
        except ValueError:
            return None

    def _parse_location(self, location):
        """Parse location info from belga to superdesk format
        """
        return [{
            'name': location['venueName'],
            'address': {
                'line': [location['streetNumber'], location['street']],
                'locality': location['city'],
                'area': location['province'],
                'country': self._get_en_item(location['country']['countryTexts'])['name'],
                'postal_code': location['postCode'],
            },
            'original_id': location['venueId'],
        }]

    def _parse_contacts(self, contacts):
        def _get_contact_values(contact, types):
            return [contact.get(_type) for _type in types if contact.get(_type)]

        phone_types = [
            'phoneGeneral', 'directPhone1', 'directPhone2', 'gsm1', 'gsm2', 'semaphone',
        ]
        phone_confidential_types = ['personalPhone', 'personalGsm']
        return [{
            'original_id': contact.get('contactId'),
            'honorific': None,
            'first_name': contact.get('firstName'),
            'last_name': contact.get('lastName'),
            'organisation': contact.get('company'),
            'job_title': contact.get('function'),
            'contact_email': _get_contact_values(contact, ['email', 'personalEmail']),
            'contact_phone': [{
                'number': contact.get(phone),
                'usage': 'Confidential' if phone in phone_confidential_types else 'Business',
                'public': phone not in phone_confidential_types,
            } for phone in phone_types + phone_confidential_types if contact.get(phone)],
            'mobile': [{
                'number': contact.get(phone),
                'usage': 'Confidential' if phone == 'personalMobile' else 'Business',
                'public': phone != 'personalMobile',
            } for phone in ['personalMobile', 'mobile247'] if contact.get(phone)],
            'website': contact.get('url'),
            'twitter': contact.get('twitter'),
            'facebook': contact.get('facebook'),
            'fax': contact.get('fax'),
            "contact_address": _get_contact_values(contact, ['professionalAddress', 'personalAddress']),
            'notes': contact.get('information'),
            "is_active": True,
            'public': contact.get('belgaPublic') == 'Y',
        } for contact in contacts]


register_feed_parser(BelgaQueueEventsParser.NAME, BelgaQueueEventsParser())
