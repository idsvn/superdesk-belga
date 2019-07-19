import json
import logging
from copy import deepcopy

import superdesk
from belga.io.feed_parsers.belga_queue_events import BelgaQueueEventsParser
from belga.io.feeding_services.queue_events_belga import add_event_file
from superdesk import get_resource_service
from superdesk.metadata.item import GUID_FIELD

logger = logging.getLogger(__name__)


def import_events_via_json_file(path_file):
    """
    Get info contacts in file and add to database
    :param path_file:
    :param unit_test:
    :return:
    """
    with open(path_file, 'rt', encoding='utf-8') as events_data:
        json_data = json.load(events_data)
        event_service = get_resource_service('events')
        contact_service = get_resource_service('contacts')
        location_service = get_resource_service('locations')
        parser = BelgaQueueEventsParser()
        for item in json_data:
            if not parser.can_parse(item):
                continue
            event = parser.parse(item)
            event['files'] = [add_event_file(file) for file in event.get('files', [])]
            if not event_service.find_one(req=None, original_id=event.get('original_id')):
                if event.get('contacts'):
                    event['event_contact_info'] = get_id_resource('contacts', event.pop('contacts'))

                if event.get('location'):
                    location = event['location'][0]
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
                event_service.post([event])
                get_resource_service('events_history').on_item_created([event])
                logger.info("import event: " + str(event.get('original_id')))
        return


def get_id_resource(service, items, _id=superdesk.config.ID_FIELD):
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
            resources_service.patch(_item[0][superdesk.config.ID_FIELD], item)
            list_items_id.append(_item[0][_id])
    if new_items:
        resources_service.post(new_items)
        list_items_id.extend([item[_id] for item in new_items])
    return list_items_id


class EventImportCommand(superdesk.Command):
    """Import event from belga to Superdesk.
    This command use for inserting a large number contact from Belga to Superdesk.
    Only support for format json file.
    """

    option_list = [
        superdesk.Option('--file', '-f', dest='events_file_path',
                         default='/home/thanhnguyen/workspace/0_test/events.txt')
    ]

    def run(self, events_file_path):
        logger.info("import file: " + events_file_path)
        import_events_via_json_file(events_file_path)


superdesk.command('event:import', EventImportCommand())
