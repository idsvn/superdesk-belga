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

import stomp

from belga.io.feed_parsers.belga_queue_events import BelgaQueueEventsParser
import superdesk
from superdesk import get_resource_service
from superdesk.errors import SuperdeskIngestError
from superdesk.io.feeding_services import FeedingService
from superdesk.io.registry import register_feeding_service
from superdesk.media.media_operations import download_file_from_url
from flask import current_app as app

logger = logging.getLogger(__name__)


class QueueEventsBelgaError(SuperdeskIngestError):
    _codes = {
        16100: "Could not connect to host",
    }

    @classmethod
    def QueueEventsConnectionError(cls, exception=None, provider=None):
        return QueueEventsBelgaError(16100, exception, provider)


class QueueEventsFeedingService(FeedingService):
    NAME = 'queue_belga'
    ERRORS = []

    label = 'Belga Queue Events'

    fields = [
        {'id': 'host_address', 'type': 'text', 'label': 'Host address', 'required': True, 'errors': {
            16100: 'Could not connect to host',
        }},
        {'id': 'queue_name', 'type': 'text', 'label': 'Queue name', 'required': True, 'errors': {}},
        {'id': 'username', 'type': 'text', 'label': 'Username'},
        {'id': 'password', 'type': 'password', 'label': 'Password'}
    ]

    def _test(self, provider):
        config = provider.get('config', {})
        host = config.get('host_address')
        username = config.get('username')
        password = config.get('password')
        return self._connect(host, username, password)

    def _update(self, provider, update):
        config = provider.get('config', {})
        queue = config.get('queue_name')
        conn = self._test(provider)
        conn.set_listener('', QueueEventsListener(provider, queue))
        conn.subscribe(queue, id=queue)
        conn.disconnect()

    def _connect(self, host_address, username, password):
        """Connect to ActiveMQ and return connection instance
        """
        try:
            host, port = host_address.split(':', 1)
            conn = stomp.Connection11([(host, int(port))])
            conn.start()
            conn.connect(username, password, wait=True)
            return conn
        except (ValueError, ConnectionRefusedError, stomp.exception.ConnectFailedException) as e:
            raise QueueEventsBelgaError.QueueEventsConnectionError()


class QueueEventsListener(stomp.ConnectionListener):
    def __init__(self, provider, queue):
        # use for logging
        self.provider = provider
        self.queue = queue

    def on_error(self, headers, message):
        logger.error('Provider %s: Queue %s: received an error "%s"', self.provider.get('name'), self.queue, message)

    def on_message(self, headers, message):
        event_service = get_resource_service('events')
        message = json.loads(message)
        with superdesk.app.app_context():
            action = message.get('type', '').lower()
            if action not in ('delete', 'create', 'update'):
                raise ValueError('Unknown action ', action)

            if action == 'delete':
                event_service.delete({'original_id': message['eventId']})
                logger.info(
                    'Provider %s: Deleted event with original id: ',
                    self.provider.get('name'), message['eventId'])
                return

            parser = BelgaQueueEventsParser()
            parser.can_parse(message['data'])
            data = parser.parse(message['data'])
            data['event_contact_info'] = self._get_id_resource('contacts', data.pop('contacts'))
            self._get_id_resource('locations', data['locations'])
            if message['type'] == 'create':
                event_service.post([data])
                logger.info(
                    'Provider %s: Inserted new event item %s from Belga: ',
                    self.provider.get('name'), data['original_id'])
            elif message['type'] == 'update':
                old_item = event_service.find_one(original_id=data['original_id'], req=None)
                event_service.patch(old_item[superdesk.config.ID_FIELD], data)

    def _get_id_resource(self, service, items):
        """Query resource bases on original_id, create new if not exists.
        Return list of resources id, include both old and new inserted resources.
        """
        resources_service = get_resource_service(service)
        new_items = []
        list_items_id = []
        for item in items:
            _item = list(resources_service.find({'original_id': item['original_id']}))
            if not _item:
                new_items.append(item)
            else:
                list_items_id.append(_item[0][superdesk.config.ID_FIELD])
        if new_items:
            list_items_id.extend(resources_service.post(new_items))
        return list_items_id


def add_event_file(file):
    content, filename, mimetype = download_file_from_url(file['url'])
    media_id = app.media.put(
        content, filename=filename, content_type=mimetype, resource='events_files')
    event_file_service = get_resource_service('events_files')
    return event_file_service.post([{"media": media_id, "original_id": file['original_id']}])[0]


register_feeding_service(QueueEventsFeedingService)
