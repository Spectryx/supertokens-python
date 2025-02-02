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

from os import environ
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set, Union

from typing_extensions import Literal

from supertokens_python.logger import get_maybe_none_as_str, log_debug_message
from supertokens_python.types import SupportedFrameworks
from .constants import FDI_KEY_HEADER, RID_KEY_HEADER, USER_COUNT, USER_DELETE, USERS
from .exceptions import SuperTokensError
from .interfaces import (
    CreateUserIdMappingOkResult,
    DeleteUserIdMappingOkResult,
    GetUserIdMappingOkResult,
    UnknownMappingError,
    UnknownSupertokensUserIDError,
    UpdateOrDeleteUserIdMappingInfoOkResult,
    UserIdMappingAlreadyExistsError,
    UserIDTypes,
)
from .normalised_url_domain import NormalisedURLDomain
from .normalised_url_path import NormalisedURLPath
from .post_init_callbacks import PostSTInitCallbacks
from .querier import Querier
from .types import ThirdPartyInfo, User, UsersResponse
from .utils import (
    get_rid_from_header,
    get_top_level_domain_for_same_site_resolution,
    is_version_gte,
    normalise_http_method,
    send_non_200_response_with_message,
)

if TYPE_CHECKING:
    from .recipe_module import RecipeModule
    from supertokens_python.framework.request import BaseRequest
    from supertokens_python.framework.response import BaseResponse
    from supertokens_python.recipe.session import SessionContainer

import json

from .exceptions import BadInputError, GeneralError, raise_general_exception


class SupertokensConfig:
    def __init__(
        self, connection_uri: str, api_key: Union[str, None] = None
    ):  # We keep this = None here because this is directly used by the user.
        self.connection_uri = connection_uri
        self.api_key = api_key


class Host:
    def __init__(self, domain: NormalisedURLDomain, base_path: NormalisedURLPath):
        self.domain = domain
        self.base_path = base_path


class InputAppInfo:
    def __init__(
        self,
        app_name: str,
        api_domain: str,
        website_domain: str,
        api_gateway_path: str = "",
        api_base_path: str = "/auth",
        website_base_path: str = "/auth",
    ):
        self.app_name = app_name
        self.api_gateway_path = api_gateway_path
        self.api_domain = api_domain
        self.website_domain = website_domain
        self.api_base_path = api_base_path
        self.website_base_path = website_base_path


class AppInfo:
    def __init__(
        self,
        app_name: str,
        api_domain: str,
        website_domain: str,
        framework: SupportedFrameworks,
        api_gateway_path: str,
        api_base_path: str,
        website_base_path: str,
        mode: Union[Literal["asgi", "wsgi"], None],
    ):
        self.app_name = app_name
        self.api_gateway_path = NormalisedURLPath(api_gateway_path)
        self.api_domain = NormalisedURLDomain(api_domain)
        self.website_domain = NormalisedURLDomain(website_domain)
        self.top_level_api_domain = get_top_level_domain_for_same_site_resolution(
            self.api_domain.get_as_string_dangerous()
        )
        self.top_level_website_domain = get_top_level_domain_for_same_site_resolution(
            self.website_domain.get_as_string_dangerous()
        )
        self.api_base_path = self.api_gateway_path.append(
            NormalisedURLPath(api_base_path)
        )
        self.website_base_path = NormalisedURLPath(website_base_path)
        if mode is not None:
            self.mode = mode
        elif framework in ("fastapi", "litestar"):
            mode = "asgi"
        else:
            mode = "wsgi"
        self.framework = framework
        self.mode = mode

    def toJSON(self):
        def defaultImpl(o: Any):
            if isinstance(o, (NormalisedURLDomain, NormalisedURLPath)):
                return o.get_as_string_dangerous()
            return o.__dict__

        return json.dumps(self, default=defaultImpl, sort_keys=True, indent=4)


def manage_session_post_response(session: SessionContainer, response: BaseResponse):
    # Something similar happens in handle_error of session/recipe.py
    for mutator in session.response_mutators:
        mutator(response=response)  # type: ignore


class Supertokens:
    __instance = None

    def __init__(
        self,
        app_info: InputAppInfo,
        framework: SupportedFrameworks,
        supertokens_config: SupertokensConfig,
        recipe_list: List[Callable[[AppInfo], RecipeModule]],
        mode: Union[Literal["asgi", "wsgi"], None],
        telemetry: Union[bool, None],
    ):
        if not isinstance(app_info, InputAppInfo):  # type: ignore
            raise ValueError("app_info must be an instance of InputAppInfo")

        self.app_info = AppInfo(
            app_info.app_name,
            app_info.api_domain,
            app_info.website_domain,
            framework,
            app_info.api_gateway_path,
            app_info.api_base_path,
            app_info.website_base_path,
            mode,
        )
        self.supertokens_config = supertokens_config
        self._telemetry_status: str = "NONE"
        log_debug_message(
            "Started SuperTokens with debug logging (supertokens.init called)"
        )
        log_debug_message("app_info: %s", self.app_info.toJSON())
        log_debug_message("framework: %s", framework)
        hosts = list(
            map(
                lambda h: Host(
                    NormalisedURLDomain(h.strip()), NormalisedURLPath(h.strip())
                ),
                filter(lambda x: x != "", supertokens_config.connection_uri.split(";")),
            )
        )
        Querier.init(hosts, supertokens_config.api_key)

        if len(recipe_list) == 0:
            raise_general_exception(
                "Please provide at least one recipe to the supertokens.init function call"
            )

        self.recipe_modules: List[RecipeModule] = list(
            map(lambda func: func(self.app_info), recipe_list)
        )

        self.telemetry = (
            telemetry
            if telemetry is not None
            else (environ.get("TEST_MODE") != "testing")
        )

    @staticmethod
    def init(
        app_info: InputAppInfo,
        framework: SupportedFrameworks,
        supertokens_config: SupertokensConfig,
        recipe_list: List[Callable[[AppInfo], RecipeModule]],
        mode: Union[Literal["asgi", "wsgi"], None],
        telemetry: Union[bool, None],
    ):
        if Supertokens.__instance is None:
            Supertokens.__instance = Supertokens(
                app_info, framework, supertokens_config, recipe_list, mode, telemetry
            )
            PostSTInitCallbacks.run_post_init_callbacks()

    @staticmethod
    def reset():
        if ("SUPERTOKENS_ENV" not in environ) or (
            environ["SUPERTOKENS_ENV"] != "testing"
        ):
            raise_general_exception("calling testing function in non testing env")
        Querier.reset()
        Supertokens.__instance = None

    @staticmethod
    def get_instance() -> Supertokens:
        if Supertokens.__instance is not None:
            return Supertokens.__instance
        raise_general_exception(
            "Initialisation not done. Did you forget to call the SuperTokens.init function?"
        )

    def get_all_cors_headers(self) -> List[str]:
        headers_set: Set[str] = set()
        headers_set.add(RID_KEY_HEADER)
        headers_set.add(FDI_KEY_HEADER)
        for recipe in self.recipe_modules:
            headers = recipe.get_all_cors_headers()
            for header in headers:
                headers_set.add(header)

        return list(headers_set)

    async def get_user_count(  # pylint: disable=no-self-use
        self, include_recipe_ids: Union[None, List[str]]
    ) -> int:
        querier = Querier.get_instance(None)
        include_recipe_ids_str = None
        if include_recipe_ids is not None:
            include_recipe_ids_str = ",".join(include_recipe_ids)

        response = await querier.send_get_request(
            NormalisedURLPath(USER_COUNT), {"includeRecipeIds": include_recipe_ids_str}
        )

        return int(response["count"])

    async def delete_user(self, user_id: str) -> None:  # pylint: disable=no-self-use
        querier = Querier.get_instance(None)

        cdi_version = await querier.get_api_version()

        if is_version_gte(cdi_version, "2.10"):
            await querier.send_post_request(
                NormalisedURLPath(USER_DELETE), {"userId": user_id}
            )

            return None
        raise_general_exception("Please upgrade the SuperTokens core to >= 3.7.0")

    async def get_users(  # pylint: disable=no-self-use
        self,
        time_joined_order: Literal["ASC", "DESC"],
        limit: Union[int, None],
        pagination_token: Union[str, None],
        include_recipe_ids: Union[None, List[str]],
        query: Union[Dict[str, str], None] = None,
    ) -> UsersResponse:
        querier = Querier.get_instance(None)
        params = {"timeJoinedOrder": time_joined_order}
        if limit is not None:
            params = {"limit": limit, **params}
        if pagination_token is not None:
            params = {"paginationToken": pagination_token, **params}

        include_recipe_ids_str = None
        if include_recipe_ids is not None:
            include_recipe_ids_str = ",".join(include_recipe_ids)
            params = {"includeRecipeIds": include_recipe_ids_str, **params}

        if query is not None:
            params = {**params, **query}

        response = await querier.send_get_request(NormalisedURLPath(USERS), params)
        next_pagination_token = None
        if "nextPaginationToken" in response:
            next_pagination_token = response["nextPaginationToken"]
        users_list = response["users"]
        users: List[User] = []
        for user in users_list:
            recipe_id = user["recipeId"]
            user_obj = user["user"]
            third_party = None
            if "thirdParty" in user_obj:
                third_party = ThirdPartyInfo(
                    user_obj["thirdParty"]["userId"], user_obj["thirdParty"]["id"]
                )
            email = None
            if "email" in user_obj:
                email = user_obj["email"]
            phone_number = None
            if "phoneNumber" in user_obj:
                phone_number = user_obj["phoneNumber"]
            users.append(
                User(
                    recipe_id,
                    user_obj["id"],
                    user_obj["timeJoined"],
                    email,
                    phone_number,
                    third_party,
                )
            )

        return UsersResponse(users, next_pagination_token)

    async def create_user_id_mapping(  # pylint: disable=no-self-use
        self,
        supertokens_user_id: str,
        external_user_id: str,
        external_user_id_info: Optional[str] = None,
        force: Optional[bool] = None,
    ) -> Union[
        CreateUserIdMappingOkResult,
        UnknownSupertokensUserIDError,
        UserIdMappingAlreadyExistsError,
    ]:
        querier = Querier.get_instance(None)

        cdi_version = await querier.get_api_version()

        if is_version_gte(cdi_version, "2.15"):
            body: Dict[str, Any] = {
                "superTokensUserId": supertokens_user_id,
                "externalUserId": external_user_id,
                "externalUserIdInfo": external_user_id_info,
            }
            if force:
                body["force"] = force

            res = await querier.send_post_request(
                NormalisedURLPath("/recipe/userid/map"), body
            )
            if res["status"] == "OK":
                return CreateUserIdMappingOkResult()
            if res["status"] == "UNKNOWN_SUPERTOKENS_USER_ID_ERROR":
                return UnknownSupertokensUserIDError()
            if res["status"] == "USER_ID_MAPPING_ALREADY_EXISTS_ERROR":
                return UserIdMappingAlreadyExistsError(
                    does_super_tokens_user_id_exist=res["doesSuperTokensUserIdExist"],
                    does_external_user_id_exist=res["does_external_user_id_exist"],
                )

            raise_general_exception("Unknown response")

        raise_general_exception("Please upgrade the SuperTokens core to >= 3.15.0")

    async def get_user_id_mapping(  # pylint: disable=no-self-use
        self,
        user_id: str,
        user_id_type: Optional[UserIDTypes] = None,
    ) -> Union[GetUserIdMappingOkResult, UnknownMappingError]:
        querier = Querier.get_instance(None)

        cdi_version = await querier.get_api_version()

        if is_version_gte(cdi_version, "2.15"):
            body = {
                "userId": user_id,
            }
            if user_id_type:
                body["userIdType"] = user_id_type
            res = await querier.send_get_request(
                NormalisedURLPath("/recipe/userid/map"),
                body,
            )
            if res["status"] == "OK":
                return GetUserIdMappingOkResult(
                    supertokens_user_id=res["superTokensUserId"],
                    external_user_id=res["externalUserId"],
                    external_user_info=res.get("externalUserIdInfo"),
                )
            if res["status"] == "UNKNOWN_MAPPING_ERROR":
                return UnknownMappingError()

            raise_general_exception("Unknown response")

        raise_general_exception("Please upgrade the SuperTokens core to >= 3.15.0")

    async def delete_user_id_mapping(  # pylint: disable=no-self-use
        self,
        user_id: str,
        user_id_type: Optional[UserIDTypes] = None,
        force: Optional[bool] = None,
    ) -> DeleteUserIdMappingOkResult:
        querier = Querier.get_instance(None)

        cdi_version = await querier.get_api_version()

        if is_version_gte(cdi_version, "2.15"):
            body: Dict[str, Any] = {
                "userId": user_id,
                "userIdType": user_id_type,
            }
            if force:
                body["force"] = force
            res = await querier.send_post_request(
                NormalisedURLPath("/recipe/userid/map/remove"), body
            )
            if res["status"] == "OK":
                return DeleteUserIdMappingOkResult(
                    did_mapping_exist=res["didMappingExist"]
                )

            raise_general_exception("Unknown response")

        raise_general_exception("Please upgrade the SuperTokens core to >= 3.15.0")

    async def update_or_delete_user_id_mapping_info(  # pylint: disable=no-self-use
        self,
        user_id: str,
        user_id_type: Optional[UserIDTypes] = None,
        external_user_id_info: Optional[str] = None,
    ) -> Union[UpdateOrDeleteUserIdMappingInfoOkResult, UnknownMappingError]:
        querier = Querier.get_instance(None)

        cdi_version = await querier.get_api_version()

        if is_version_gte(cdi_version, "2.15"):
            res = await querier.send_post_request(
                NormalisedURLPath("/recipe/userid/external-user-id-info"),
                {
                    "userId": user_id,
                    "userIdType": user_id_type,
                    "externalUserIdInfo": external_user_id_info,
                },
            )
            if res["status"] == "OK":
                return UpdateOrDeleteUserIdMappingInfoOkResult()
            if res["status"] == "UNKNOWN_MAPPING_ERROR":
                return UnknownMappingError()

            raise_general_exception("Unknown response")

        raise_general_exception("Please upgrade the SuperTokens core to >= 3.15.0")

    async def middleware(  # pylint: disable=no-self-use
        self, request: BaseRequest, response: BaseResponse
    ) -> Union[BaseResponse, None]:
        log_debug_message("middleware: Started")
        path = Supertokens.get_instance().app_info.api_gateway_path.append(
            NormalisedURLPath(request.get_path())
        )
        method = normalise_http_method(request.method())

        if not path.startswith(Supertokens.get_instance().app_info.api_base_path):
            log_debug_message(
                "middleware: Not handling because request path did not start with api base path. Request path: %s",
                path.get_as_string_dangerous(),
            )
            return None
        request_rid = get_rid_from_header(request)
        log_debug_message(
            "middleware: requestRID is: %s", get_maybe_none_as_str(request_rid)
        )
        if request_rid is not None and request_rid == "anti-csrf":
            # see
            # https://github.com/supertokens/supertokens-python/issues/54
            request_rid = None
        request_id = None
        matched_recipe = None
        if request_rid is not None:
            for recipe in Supertokens.get_instance().recipe_modules:
                log_debug_message(
                    "middleware: Checking recipe ID for match: %s",
                    recipe.get_recipe_id(),
                )
                if recipe.get_recipe_id() == request_rid:
                    matched_recipe = recipe
                    break
            if matched_recipe is not None:
                request_id = matched_recipe.return_api_id_if_can_handle_request(
                    path, method
                )
        else:
            for recipe in Supertokens.get_instance().recipe_modules:
                log_debug_message(
                    "middleware: Checking recipe ID for match: %s",
                    recipe.get_recipe_id(),
                )
                request_id = recipe.return_api_id_if_can_handle_request(path, method)
                if request_id is not None:
                    matched_recipe = recipe
                    break
        if matched_recipe is not None:
            log_debug_message(
                "middleware: Matched with recipe ID: %s", matched_recipe.get_recipe_id()
            )
        else:
            log_debug_message("middleware: Not handling because no recipe matched")
        if matched_recipe is not None and request_id is None:
            log_debug_message(
                "middleware: Not handling because recipe doesn't handle request path or method. Request path: %s, request method: %s",
                path.get_as_string_dangerous(),
                method,
            )
        if request_id is not None and matched_recipe is not None:
            log_debug_message(
                "middleware: Request being handled by recipe. ID is: %s", request_id
            )
            api_resp = await matched_recipe.handle_api_request(
                request_id, request, path, method, response
            )
            if api_resp is None:
                log_debug_message("middleware: Not handled because API returned None")
            else:
                log_debug_message("middleware: Ended")
            return api_resp
        return None

    async def handle_supertokens_error(
        self, request: BaseRequest, err: Exception, response: BaseResponse
    ):
        log_debug_message("errorHandler: Started")
        log_debug_message(
            "errorHandler: Error is from SuperTokens recipe. Message: %s", str(err)
        )
        if isinstance(err, GeneralError):
            raise err

        if isinstance(err, BadInputError):
            log_debug_message("errorHandler: Sending 400 status code response")
            return send_non_200_response_with_message(str(err), 400, response)

        for recipe in self.recipe_modules:
            log_debug_message(
                "errorHandler: Checking recipe for match: %s", recipe.get_recipe_id()
            )
            if recipe.is_error_from_this_recipe_based_on_instance(err) and isinstance(
                err, SuperTokensError
            ):
                log_debug_message(
                    "errorHandler: Matched with recipeID: %s", recipe.get_recipe_id()
                )
                return await recipe.handle_error(request, err, response)
        raise err
