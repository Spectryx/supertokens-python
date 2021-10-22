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
from __future__ import annotations
from typing import TYPE_CHECKING

from supertokens_python.utils import find_first_occurrence_in_list

if TYPE_CHECKING:
    from supertokens_python.recipe.thirdparty.interfaces import APIOptions, APIInterface
    from supertokens_python.recipe.thirdparty.provider import Provider
from supertokens_python.exceptions import raise_bad_input_exception


async def handle_sign_in_up_api(api_implementation: APIInterface, api_options: APIOptions):
    if api_implementation.disable_sign_in_up_post:
        return None
    body = await api_options.request.json()

    if 'thirdPartyId' not in body or not isinstance(body['thirdPartyId'], str):
        raise_bad_input_exception(
            'Please provide the thirdPartyId in request body')

    if 'code' not in body or not isinstance(body['code'], str):
        raise_bad_input_exception('Please provide the code in request body')

    if 'redirectURI' not in body or not isinstance(body['redirectURI'], str):
        raise_bad_input_exception(
            'Please provide the redirectURI in request body')

    third_party_id = body['thirdPartyId']
    provider: Provider = find_first_occurrence_in_list(
        lambda x: x.id == third_party_id, api_options.providers)
    if provider is None:
        raise_bad_input_exception('The third party provider ' + third_party_id + ' seems to not be configured '
                                                                                 'on the backend. Please '
                                                                                 'check your frontend and '
                                                                                 'backend configs.')

    result = await api_implementation.sign_in_up_post(provider, body['code'], body['redirectURI'], api_options)
    api_options.response.set_content(result.to_json())

    return api_options.response
