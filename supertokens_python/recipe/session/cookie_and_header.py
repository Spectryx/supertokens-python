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

from typing import TYPE_CHECKING, List, Optional
from urllib.parse import quote, unquote

from typing_extensions import Literal

from .constants import (
    ACCESS_CONTROL_EXPOSE_HEADERS,
    ACCESS_TOKEN_COOKIE_KEY,
    ACCESS_TOKEN_HEADER_KEY,
    ANTI_CSRF_HEADER_KEY,
    AUTH_MODE_HEADER_KEY,
    AUTHORIZATION_HEADER_KEY,
    FRONT_TOKEN_HEADER_SET_KEY,
    REFRESH_TOKEN_COOKIE_KEY,
    REFRESH_TOKEN_HEADER_KEY,
    RID_HEADER_KEY,
    available_token_transfer_methods,
)

if TYPE_CHECKING:
    from supertokens_python.framework.request import BaseRequest
    from supertokens_python.framework.response import BaseResponse
    from .recipe import SessionRecipe
    from .utils import TokenTransferMethod, TokenType, SessionConfig

from json import dumps
from typing import Any, Dict, Union

from supertokens_python.utils import get_header, utf_base64encode


def set_front_token_in_headers(
    response: BaseResponse,
    user_id: str,
    expires: int,
    jwt_payload: Union[None, Dict[str, Any]] = None,
):
    if jwt_payload is None:
        jwt_payload = {}
    token_info = {"uid": user_id, "ate": expires, "up": jwt_payload}
    set_header(
        response,
        FRONT_TOKEN_HEADER_SET_KEY,
        utf_base64encode(dumps(token_info, separators=(",", ":"), sort_keys=True)),
        False,
    )
    set_header(
        response, ACCESS_CONTROL_EXPOSE_HEADERS, FRONT_TOKEN_HEADER_SET_KEY, True
    )


def get_cors_allowed_headers():
    return [
        ANTI_CSRF_HEADER_KEY,
        RID_HEADER_KEY,
        AUTHORIZATION_HEADER_KEY,
        AUTH_MODE_HEADER_KEY,
    ]


def set_header(response: BaseResponse, key: str, value: str, allow_duplicate: bool):
    if allow_duplicate:
        old_value = response.get_header(key)
        if old_value is None:
            response.set_header(key, value)
        else:
            response.set_header(key, old_value + "," + value)
    else:
        response.set_header(key, value)


def get_cookie(request: BaseRequest, key: str):
    cookie_val = request.get_cookie(key)
    if cookie_val is None:
        return None
    return unquote(cookie_val)


def set_cookie(
    config: SessionConfig,
    key: str,
    value: str,
    expires: int,
    path_type: Literal["refresh_token_path", "access_token_path"],
    response: BaseResponse,
):
    domain = config.cookie_domain
    secure = config.cookie_secure
    same_site = config.cookie_same_site
    path = ""
    if path_type == "refresh_token_path":
        path = config.refresh_token_path.get_as_string_dangerous()
    elif path_type == "access_token_path":
        path = "/"
    http_only = True
    response.set_cookie(
        key=key,
        value=quote(value, encoding="utf-8"),
        expires=expires,
        path=path,
        domain=domain,
        secure=secure,
        httponly=http_only,
        samesite=same_site,
    )


def attach_anti_csrf_header(response: BaseResponse, value: str):
    set_header(response, ANTI_CSRF_HEADER_KEY, value, False)
    set_header(response, ACCESS_CONTROL_EXPOSE_HEADERS, ANTI_CSRF_HEADER_KEY, True)


def get_anti_csrf_header(request: BaseRequest):
    return get_header(request, ANTI_CSRF_HEADER_KEY)


def get_rid_header(request: BaseRequest):
    return get_header(request, RID_HEADER_KEY)


def clear_session_from_all_token_transfer_methods(
    recipe: SessionRecipe, request: BaseRequest, response: BaseResponse
):
    for transfer_method in available_token_transfer_methods:
        if get_token(request, "access", transfer_method) is not None:
            clear_session(response, recipe.config, transfer_method)


def clear_session(
    response: BaseResponse,
    config: SessionConfig,
    transfer_method: TokenTransferMethod,
):
    # If we can tell it's a cookie based session we are not clearing using headers
    token_types: List[TokenType] = ["access", "refresh"]
    for token_type in token_types:
        set_token(response, config, token_type, "", 0, transfer_method)

    set_header(response, FRONT_TOKEN_HEADER_SET_KEY, "remove", False)
    set_header(
        response, ACCESS_CONTROL_EXPOSE_HEADERS, FRONT_TOKEN_HEADER_SET_KEY, True
    )


def get_cookie_name_from_token_type(token_type: TokenType):
    if token_type == "access":
        return ACCESS_TOKEN_COOKIE_KEY
    if token_type == "refresh":
        return REFRESH_TOKEN_COOKIE_KEY
    raise Exception("Unknown token type, should never happen")


def get_response_header_name_for_token_type(token_type: TokenType):
    if token_type == "access":
        return ACCESS_TOKEN_HEADER_KEY
    if token_type == "refresh":
        return REFRESH_TOKEN_HEADER_KEY
    raise Exception("Unknown token type, should never happen")


def get_token(
    request: BaseRequest,
    token_type: TokenType,
    transfer_method: TokenTransferMethod,
) -> Optional[str]:
    if transfer_method == "cookie":
        return request.get_cookie(get_cookie_name_from_token_type(token_type))
    if transfer_method == "header":
        value = request.get_header(AUTHORIZATION_HEADER_KEY)
        if value is None or not value.startswith("Bearer "):
            return None

        return value[len("Bearer ") :].strip()

    raise Exception("Should never happen: Unknown transferMethod: " + transfer_method)


def set_token(
    response: BaseResponse,
    config: SessionConfig,
    token_type: TokenType,
    value: str,
    expires: int,
    transfer_method: TokenTransferMethod,
):
    if transfer_method == "cookie":
        set_cookie(
            config,
            get_cookie_name_from_token_type(token_type),
            value,
            expires,
            "refresh_token_path" if token_type == "refresh" else "access_token_path",
            response,
        )
    elif transfer_method == "header":
        set_token_in_header(
            response,
            get_response_header_name_for_token_type(token_type),
            value,
        )


def set_token_in_header(response: BaseResponse, name: str, value: str):
    set_header(response, name, value, allow_duplicate=False)
    set_header(response, ACCESS_CONTROL_EXPOSE_HEADERS, name, allow_duplicate=True)
