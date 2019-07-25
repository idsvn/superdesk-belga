# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2013, 2014 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license


import superdesk
from apps.auth import AuthResource

from apps.auth.service import AuthService
from superdesk import get_resource_service

from flask import g
from flask_oidc import OpenIDConnect
from superdesk.resource import Resource


class AuthResource(Resource):
    schema = {
        'token': {
            'type': 'string'
        },
        'user': Resource.rel('users', True)
    }
    resource_methods = ['POST']
    item_methods = ['GET', 'DELETE']
    public_methods = ['POST', 'DELETE']
    extra_response_fields = ['user', 'token', 'username']
    datasource = {'source': 'auth'}
    mongo_indexes = {'token': ([('token', 1)], {'background': True})}

def init_app(app):
    oidc = OpenIDConnect(app)
    oidc.client_secrets = app.config['OIDC_CLIENT_SECRETS_DATA']
    endpoint_name = 'oidcauth'

    class OIDCAuthService(AuthService):
        @oidc.accept_token(require_token=True, scopes_required=['openid'])
        def authenticate(self, credentials, ignore_expire=False):
            user = get_resource_service('auth_users').find_one(req=None,
                                                               username=g.oidc_token_info.get('sub'))
            if not user:
                role = get_resource_service('roles').find_one(req=None,
                                                              name=g.oidc_token_info.get('role'))
                new_user = {
                    "email": g.oidc_token_info.get('email'),
                    "first_name": g.oidc_token_info.get('given_name'),
                    "last_name": g.oidc_token_info.get('family_name'),
                    "needs_activation": False,
                    "password": 'xxxxx',
                    "user_type": g.oidc_token_info.get('user_type'),
                    "username": g.oidc_token_info.get('sub'),
                    "role": role.get('_id'),
                    "display_name": g.oidc_token_info.get('name'),
                }
                users_service = get_resource_service('users')
                user_id = users_service.post([new_user])[0]
                user = get_resource_service('auth_users').find_one(req=None,
                                                                   _id=user_id)

            user["oidc"] = g.oidc_token_info

            return user

    service = OIDCAuthService('auth', backend=superdesk.get_backend())
    AuthResource(endpoint_name, app=app, service=service)


