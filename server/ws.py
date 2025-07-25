#!/usr/bin/env python
# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2013, 2014, 2015 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license

from app import get_app
from superdesk.ws import create_server

if __name__ == "__main__":
    app = get_app()
    config = {
        "WS_HOST": app.config["WS_HOST"],
        "WS_PORT": app.config["WS_PORT"],
        "BROKER_URL": app.config["BROKER_URL"],
    }
    create_server(config)
