import superdesk
import json

from superdesk import get_resource_service
from belga.io.feed_parsers.belga_queue_events import BelgaQueueEventsParser
import logging

logger = logging.getLogger(__name__)


def import_events_via_json_file(path_file):
    """
    Get info contacts in file and add to database
    :param path_file:
    :param unit_test:
    :return:
    """
    with open(path_file, 'rt', encoding='utf-8') as contacts_data:
        json_data = json.load(contacts_data)
        event_service = get_resource_service('events')
        contact_service = get_resource_service('contacts')
        location_service = get_resource_service('locations')
        parser = BelgaQueueEventsParser()
        for item in json_data:
            event = parser.parse(item.get('data'))
            if not event_service.find_one(req=None, original_id=event.get('original_id')):
                event['contacts'] = get_id_resource(contact_service, event['contacts'])
                get_id_resource(location_service, event['locations'])
                event_service.post([event])('events').post([event])
                logger.info("import event: " + event.get('original_id'))
        return
def download_event_file(url):
    pass

def get_id_resource(self, resources_service, items):
    """Query resource bases on original_id, create new if not exists.
    Return list of resources id, include both old and new inserted resources.
    """
    new_items = []
    list_items = []
    for item in items:
        _item = resources_service.find({'original_id': item['original_id']})
        if not _item:
            new_items.append(item)
        else:
            list_items.extend(_item)
    if new_items:
        list_items.extend(resources_service.post(new_items))
    return [item[superdesk.config.ID_FIELD] for item in list_items]


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
