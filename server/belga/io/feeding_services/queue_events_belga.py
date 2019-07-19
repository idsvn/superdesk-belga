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
from copy import deepcopy

import stomp

from belga.io.feed_parsers.belga_queue_events import BelgaQueueEventsParser
import superdesk
from superdesk import get_resource_service
from superdesk.errors import SuperdeskIngestError
from superdesk.io.feeding_services import FeedingService
from superdesk.io.registry import register_feeding_service
from superdesk.media.media_operations import download_file_from_url
from superdesk.metadata.item import GUID_FIELD

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
            if data.get('contacts'):
                data['event_contact_info'] = self._get_id_resource('contacts', data.pop('contacts'))

            location_service = get_resource_service('locations')
            if data.get('location'):
                location = data['location'][0]
                saved_location = list(location_service.find({
                    'name': location['name'],
                    'address.line': location['address']['line'],
                    'address.country': location['address']['country'],
                }))
                if saved_location:
                    location_service.patch(saved_location[0][superdesk.config.ID_FIELD], location)
                    location['qcode'] = saved_location[0][GUID_FIELD]
                else:
                    _location = deepcopy(location)
                    location_service.post([_location])
                    location['qcode'] = _location[GUID_FIELD]

            history_service = get_resource_service('events_history')
            if message['type'] == 'update':
                old_item = event_service.find_one(original_id=data['original_id'], req=None)
                if old_item:
                    # lookup files to avoid adding new file each time update
                    list_files_id = []
                    for fi in data.get('files', []):
                        efile = get_resource_service('events_files').find_one(original_id=fi['original_id'], req=None)
                        if efile:
                            list_files_id.append(efile[superdesk.config.ID_FIELD])
                        else:
                            list_files_id.append(add_event_file(fi))
                    if list_files_id:
                        data['files'] = list_files_id

                    event_service.patch(old_item[superdesk.config.ID_FIELD], data)
                    non_history_fields = ['original_id', 'versioncreated']
                    updates = {
                        k: data[k] for k in data
                        if data[k] != old_item.get(k) and not k.startswith('_') and k not in non_history_fields
                    }
                    history_service._save_history(old_item, updates, 'edited')
                    return

            data['files'] = [add_event_file(fi) for fi in data.get('files', [])]
            event_service.post([data])
            history_service.on_item_created([data])
            logger.info(
                'Provider %s: Inserted new event item %s from Belga: ',
                self.provider.get('name'), data['original_id'])

    def _get_id_resource(self, service, items, _id=superdesk.config.ID_FIELD):
        """Query resource bases on original_id, create new if not exists.
        Return list of resources _id, include both old and new inserted resources.
        """
        resources_service = get_resource_service(service)
        new_items = []
        list_items_id = []
        for item in items:
            _item = list(resources_service.find({'original_id': item['original_id']}))
            if not _item:
                new_items.append(item)
            else:
                resources_service.patch(_item[0][superdesk.config.ID_FIELD], item)
                list_items_id.append(_item[0][_id])
        if new_items:
            resources_service.post(new_items)
            list_items_id.extend([item[_id] for item in new_items])
        return list_items_id


def add_event_file(file):
    content, filename, mimetype = download_file_from_url(file['url'])
    media_id = app.media.put(
        content, filename=filename, content_type=mimetype, resource='events_files')
    event_file_service = get_resource_service('events_files')
    return event_file_service.post([{"media": media_id, "original_id": file['original_id']}])[0]


register_feeding_service(QueueEventsFeedingService)
