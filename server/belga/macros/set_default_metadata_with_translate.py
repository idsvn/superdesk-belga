# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2013, 2014 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license
import logging
from .set_default_metadata import get_default_content_template, set_default_metadata
from superdesk import get_resource_service
from superdesk.errors import StopDuplication
from copy import deepcopy


logger = logging.getLogger(__name__)


def set_default_metadata_with_translate(item, **kwargs):
    """Replace some metadata from default content template and set translation id

    This macro is the same as "Set Default Metadata" + adding a translation
    link to original item.
    """
    archive_service = get_resource_service('archive')
    move_service = get_resource_service('move')
    original_item = archive_service.find_one(None, _id=item['_id'])

    desk_id = kwargs.get('dest_desk_id')
    if not desk_id:
        logger.warning("no destination id specified")
        return
    stage_id = kwargs.get('dest_stage_id')
    if not stage_id:
        logger.warning("no stage id specified")
        return

    # we first do the translation, we need destination language for that
    content_template = get_default_content_template(item, **kwargs)
    language = content_template['data'].get('language')
    if not language:
        logger.warning("no language set in default content template")
        return

    new_item = deepcopy(original_item)
    new_item['language'] = language

    translate_service = get_resource_service('translate')
    new_id = translate_service.create([new_item])[0]

    # translation is done, we now move the item to the new desk
    dest = {"task": {"desk": desk_id, "stage": stage_id}}
    move_service.move_content(new_id, dest)

    # and now we apply the update
    new_item = archive_service.find_one(req=None, _id=new_id)
    set_default_metadata(new_item, **kwargs)
    archive_service.put(new_id, new_item)

    # no need for further treatment, we stop here internal_destinations workflow
    raise StopDuplication


name = 'Set Default Metadata With Translate'
label = name
callback = set_default_metadata_with_translate
access_type = 'frontend'
action_type = 'direct'
