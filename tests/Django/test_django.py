# Copyright (c) 2021, VRAI Labs and/or its affiliates. All rights reserved.
#
# This software is licensed under the Apache License, Version 2.0 (the
# "License") as published by the Apache Software Foundation.
#
# You may not use this file except in compliance with the License. You may
# obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import json
from typing import Any, Dict

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.test import RequestFactory, TestCase
from supertokens_python import InputAppInfo, SupertokensConfig, init
from supertokens_python.framework.django import middleware
from supertokens_python.recipe import emailpassword, session
from supertokens_python.recipe.session.asyncio import (create_new_session,
                                                       get_session,
                                                       refresh_session)
from tests.utils import clean_st, reset, setup_st, start_st


def get_cookies(response: HttpResponse) -> Dict[str, Any]:
    cookies: Dict[str, Any] = dict()
    for key, morsel in response.cookies.items():
        cookies[key] = {
            'value': morsel.value,
            'name': key
        }
        for k, v in morsel.items():
            if (k == 'secure' or k == 'httponly') and v == '':
                cookies[key][k] = None
            elif k == 'samesite':
                if len(v) > 0 and v[-1] == ',':
                    v = v[:-1]
                cookies[key][k] = v
            else:
                cookies[key][k] = v
    return cookies


async def create_new_session_view(request: HttpRequest):
    await create_new_session(request, 'user_id')
    return JsonResponse({'foo': 'bar'})


async def refresh_view(request: HttpRequest):
    await refresh_session(request)
    return JsonResponse({'foo': 'bar'})


async def custom_response_view(request: HttpRequest):
    pass

from typing import Union

from supertokens_python.recipe.emailpassword.interfaces import (APIInterface,
                                                                APIOptions)
from supertokens_python.recipe.session import SessionContainer


async def logout_view(request: HttpRequest):
    session: Union[None, SessionContainer] = await get_session(request, True)
    if session is None:
        raise Exception("Should never come here")
    await session.revoke_session()
    return JsonResponse({'foo': 'bar'})


async def handle_view(request: HttpRequest):
    session: Union[None, SessionContainer] = await get_session(request, True)
    if session is None:
        raise Exception("Should never come here")
    return JsonResponse({'s': session.get_handle()})


class SupertokensTest(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        reset()
        clean_st()
        setup_st()

    def tearDown(self):
        reset()
        clean_st()

    async def test_login_refresh(self):
        init(
            supertokens_config=SupertokensConfig('http://localhost:3567'),
            app_info=InputAppInfo(
                app_name="SuperTokens Demo",
                api_domain="http://api.supertokens.io",
                website_domain="http://supertokens.io",
                api_base_path="/auth"
            ),
            framework='django',
            mode='asgi',
            recipe_list=[session.init(
                anti_csrf='VIA_TOKEN',
                cookie_domain='supertokens.io'
            )]
        )

        start_st()

        my_middleware = middleware(create_new_session_view)
        request = self.factory.get('/login', {'user_id': 'user_id'})
        response = await my_middleware(request)

        my_middleware = middleware(refresh_view)
        request = self.factory.get('/refresh', {'user_id': 'user_id'})
        cookies = get_cookies(response)

        assert len(cookies['sAccessToken']['value']) > 0
        assert len(cookies['sIdRefreshToken']['value']) > 0
        assert len(cookies['sRefreshToken']['value']) > 0

        request.COOKIES["sRefreshToken"] = cookies['sRefreshToken']['value']
        request.COOKIES["sIdRefreshToken"] = cookies['sIdRefreshToken']['value']
        request.META['HTTP_ANTI_CSRF'] = response.headers['anti-csrf']
        response = await my_middleware(request)
        refreshed_cookies = get_cookies(response)

        assert refreshed_cookies['sAccessToken']['value'] != cookies['sAccessToken']['value']
        assert refreshed_cookies['sIdRefreshToken']['value'] != cookies['sIdRefreshToken']['value']
        assert refreshed_cookies['sRefreshToken']['value'] != cookies['sRefreshToken']['value']
        assert response.headers['anti-csrf'] is not None
        assert refreshed_cookies['sAccessToken']['domain'] == cookies['sAccessToken']['domain']
        assert refreshed_cookies['sIdRefreshToken']['domain'] == cookies['sIdRefreshToken']['domain']
        assert refreshed_cookies['sRefreshToken']['domain'] == cookies['sRefreshToken']['domain']
        assert refreshed_cookies['sAccessToken']['secure'] == cookies['sAccessToken']['secure']
        assert refreshed_cookies['sIdRefreshToken']['secure'] == cookies['sIdRefreshToken']['secure']
        assert refreshed_cookies['sRefreshToken']['secure'] == cookies['sRefreshToken']['secure']

    async def test_login_logout(self):
        init(
            supertokens_config=SupertokensConfig('http://localhost:3567'),
            app_info=InputAppInfo(
                app_name="SuperTokens Demo",
                api_domain="http://api.supertokens.io",
                website_domain="http://supertokens.io",
                api_base_path="/auth"
            ),
            framework='django',
            mode='asgi',
            recipe_list=[session.init(
                anti_csrf='VIA_TOKEN',
                cookie_domain='supertokens.io'
            )]
        )

        start_st()

        my_middleware = middleware(create_new_session_view)
        request = self.factory.get('/login', {'user_id': 'user_id'})
        response = await my_middleware(request)
        cookies = get_cookies(response)

        assert len(cookies['sAccessToken']['value']) > 0
        assert len(cookies['sIdRefreshToken']['value']) > 0
        assert len(cookies['sRefreshToken']['value']) > 0

        my_middleware = middleware(logout_view)
        request = self.factory.post('/logout', {'user_id': 'user_id'})

        request.COOKIES["sAccessToken"] = cookies['sAccessToken']['value']
        request.COOKIES["sIdRefreshToken"] = cookies['sIdRefreshToken']['value']
        request.META['HTTP_ANTI_CSRF'] = response.headers['anti-csrf']
        response = await my_middleware(request)
        logout_cookies = get_cookies(response)
        assert response.headers.get('anti-csrf') is None # type: ignore
        assert logout_cookies['sAccessToken']['value'] == ''
        assert logout_cookies['sRefreshToken']['value'] == ''
        assert logout_cookies['sIdRefreshToken']['value'] == ''

    async def test_login_handle(self):
        init(
            supertokens_config=SupertokensConfig('http://localhost:3567'),
            app_info=InputAppInfo(
                app_name="SuperTokens Demo",
                api_domain="http://api.supertokens.io",
                website_domain="http://supertokens.io",
                api_base_path="/auth"
            ),
            framework='django',
            mode='asgi',
            recipe_list=[session.init(
                anti_csrf='VIA_TOKEN',
                cookie_domain='supertokens.io'
            )]
        )

        start_st()

        my_middleware = middleware(create_new_session_view)
        request = self.factory.get('/login', {'user_id': 'user_id'})
        response = await my_middleware(request)
        cookies = get_cookies(response)

        assert len(cookies['sAccessToken']['value']) > 0
        assert len(cookies['sIdRefreshToken']['value']) > 0
        assert len(cookies['sRefreshToken']['value']) > 0

        my_middleware = middleware(handle_view)
        request = self.factory.get('/handle', {'user_id': 'user_id'})

        request.COOKIES["sAccessToken"] = cookies['sAccessToken']['value']
        request.COOKIES["sIdRefreshToken"] = cookies['sIdRefreshToken']['value']
        request.META['HTTP_ANTI_CSRF'] = response.headers['anti-csrf']
        response = await my_middleware(request)
        assert "s" in json.loads(response.content)
        handle_cookies = get_cookies(response)

        assert handle_cookies == {}

    async def test_login_refresh_error_handler(self):
        init(
            supertokens_config=SupertokensConfig('http://localhost:3567'),
            app_info=InputAppInfo(
                app_name="SuperTokens Demo",
                api_domain="http://api.supertokens.io",
                website_domain="http://supertokens.io",
                api_base_path="/auth"
            ),
            framework='django',
            mode='asgi',
            recipe_list=[session.init(
                anti_csrf='VIA_TOKEN',
                cookie_domain='supertokens.io'
            )]
        )

        start_st()

        my_middleware = middleware(create_new_session_view)
        request = self.factory.get('/login', {'user_id': 'user_id'})
        response = await my_middleware(request)

        my_middleware = middleware(refresh_view)
        request = self.factory.get('/refresh', {'user_id': 'user_id'})
        cookies = get_cookies(response)

        assert len(cookies['sAccessToken']['value']) > 0
        assert len(cookies['sIdRefreshToken']['value']) > 0
        assert len(cookies['sRefreshToken']['value']) > 0

        response = await my_middleware(request)
        # not authorized because no access refresh token
        assert response.status_code == 401

    async def test_custom_response(self):
        def override_email_password_apis(original_implementation: APIInterface):

            original_func = original_implementation.email_exists_get

            async def email_exists_get(email: str, api_options: APIOptions, user_context: Dict[str, Any]):
                response_dict = {'custom': True}
                api_options.response.set_status_code(203)
                api_options.response.set_json_content(response_dict)
                return await original_func(email, api_options, user_context)

            original_implementation.email_exists_get = email_exists_get
            return original_implementation

        init(
            supertokens_config=SupertokensConfig('http://localhost:3567'),
            app_info=InputAppInfo(
                app_name="SuperTokens Demo",
                api_domain="http://api.supertokens.io",
                website_domain="http://supertokens.io",
                api_base_path="/auth"
            ),
            framework='django',
            mode='asgi',
            recipe_list=[emailpassword.init(
                override=emailpassword.InputOverrideConfig(
                    apis=override_email_password_apis
                )
            )]
        )

        start_st()

        my_middleware = middleware(custom_response_view)
        request = self.factory.get(
            '/auth/signup/email/exists?email=test@example.com')
        response = await my_middleware(request)

        assert response.status_code == 203
        dict_response = json.loads(response.content)
        assert dict_response["custom"]
