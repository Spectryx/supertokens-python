from typing import List, Any, Dict, Union
from unittest.mock import patch

from fastapi import FastAPI, Depends
from pytest import fixture, mark
from starlette.requests import Request
from starlette.testclient import TestClient

from supertokens_python import init
from supertokens_python.framework.fastapi import get_middleware
from supertokens_python.recipe import session
from supertokens_python.recipe.session.asyncio import create_new_session
from supertokens_python.recipe.session.exceptions import (
    raise_invalid_claims_exception,
    ClaimValidationError,
)
from supertokens_python.recipe.session.framework.fastapi import verify_session
from supertokens_python.recipe.session.interfaces import (
    RecipeInterface,
    SessionClaimValidator,
    JSONObject,
    ClaimValidationResult,
    SessionContainer,
)
from supertokens_python.recipe.session.session_class import Session
from tests.sessions.claims.utils import st_init_common_args, TrueClaim, NoneClaim
from tests.utils import setup_function, teardown_function, start_st, AsyncMock

_ = setup_function  # type:ignore
_ = teardown_function  # type:ignore
_ = start_st  # type:ignore

pytestmark = mark.asyncio


def st_init_generator_with_overriden_global_validators(
    validators: List[SessionClaimValidator],
):
    def session_function_override(oi: RecipeInterface) -> RecipeInterface:
        async def new_get_global_claim_validators(
            _user_id: str,
            _claim_validators_added_by_other_recipes: List[SessionClaimValidator],
            _user_context: Dict[str, Any],
        ):
            return validators

        oi.get_global_claim_validators = new_get_global_claim_validators
        return oi

    return {
        **st_init_common_args,
        "recipe_list": [
            session.init(
                anti_csrf="VIA_TOKEN",
                override=session.InputOverrideConfig(
                    functions=session_function_override
                ),
            )
        ],
    }


def st_init_generator_with_claim_validator(claim_validator: SessionClaimValidator):
    def session_function_override(oi: RecipeInterface) -> RecipeInterface:
        async def new_get_global_claim_validators(
            _user_id: str,
            claim_validators_added_by_other_recipes: List[SessionClaimValidator],
            _user_context: Dict[str, Any],
        ):
            return [*claim_validators_added_by_other_recipes, claim_validator]

        oi.get_global_claim_validators = new_get_global_claim_validators
        return oi

    return {
        **st_init_common_args,
        "recipe_list": [
            session.init(
                anti_csrf="VIA_TOKEN",
                override=session.InputOverrideConfig(
                    functions=session_function_override
                ),
            )
        ],
    }


class AlwaysValidValidator(SessionClaimValidator):
    def __init__(self):
        super().__init__("always-valid-validator")

    async def validate(
        self, payload: JSONObject, user_context: Union[Dict[str, Any], None] = None
    ) -> ClaimValidationResult:
        return {"isValid": True}


class AlwaysInvalidValidator(SessionClaimValidator):
    def __init__(self):
        super().__init__("always-invalid-validator")

    async def validate(
        self, payload: JSONObject, user_context: Union[Dict[str, Any], None] = None
    ) -> ClaimValidationResult:
        return {"isValid": False, "reason": "foo"}


@fixture(scope="function")
async def fastapi_client():
    app = FastAPI()
    app.add_middleware(get_middleware())

    @app.post("/login")
    async def _login(request: Request):  # type: ignore
        user_id = "userId"
        await create_new_session(request, user_id, {}, {})
        return {"userId": user_id}

    @app.post("/create-with-claim")
    async def _create_with_claim(request: Request):  # type: ignore
        user_id = "userId"
        _ = await create_new_session(request, user_id, {}, {})
        key: str = (await request.json())["key"]
        # PrimitiveClaim(key, fetch_value="Value").add_to_session(session, "value")
        return {"userId": key}

    @app.get("/default-claims")
    async def default_claims(s: SessionContainer = Depends(verify_session())):  # type: ignore
        return {"handle": s.get_handle()}

    no_claims_verify_session = verify_session(
        override_global_claim_validators=lambda _, __, ___: []  # type: ignore
    )

    @app.get("/no-claims")
    async def no_claims(s: SessionContainer = Depends(no_claims_verify_session)):  # type: ignore
        return {"handle": s.get_handle()}

    refetched_claims_verify_session = verify_session(
        override_global_claim_validators=lambda _, __, ___: [  # type: ignore
            TrueClaim.validators.has_value(True)
        ]
    )

    @app.get("/refetched-claim")
    async def refetched_claim(  # type: ignore
        s: SessionContainer = Depends(refetched_claims_verify_session),
    ):
        return {"handle": s.get_handle()}

    refetched_claims_false_verify_session = verify_session(
        override_global_claim_validators=lambda _, __, ___: [  # type: ignore
            TrueClaim.validators.has_value(False)
        ]
    )

    @app.get("/refetched-claim-false")
    async def refetched_claim2(  # type: ignore
        s: SessionContainer = Depends(refetched_claims_false_verify_session),
    ):
        return {"handle": s.get_handle()}

    class CustomValidator(SessionClaimValidator):
        def __init__(self, is_valid: bool):
            super().__init__("test_id")
            self.is_valid = is_valid

        async def validate(
            self, payload: JSONObject, user_context: Union[Dict[str, Any], None] = None
        ) -> ClaimValidationResult:
            if self.is_valid:
                return {"isValid": True}
            return {"isValid": False, "reason": "test_reason"}

    refetched_claims_verify_session_is_valid_false = verify_session(
        override_global_claim_validators=lambda _, __, ___: [  # type: ignore
            CustomValidator(is_valid=False)
        ]
    )

    @app.get("/refetched-claim-isvalid-false")
    async def refetched_claim3(  # type: ignore
        s: SessionContainer = Depends(refetched_claims_verify_session_is_valid_false),
    ):
        return {"handle": s.get_handle()}

    refetched_claims_verify_session_is_valid_true = verify_session(
        override_global_claim_validators=lambda _, __, ___: [  # type: ignore
            CustomValidator(is_valid=True)
        ]
    )

    @app.get("/refetched-claim-isvalid-true")
    async def refetched_claim4(  # type: ignore
        s: SessionContainer = Depends(refetched_claims_verify_session_is_valid_true),
    ):
        return {"handle": s.get_handle()}

    return TestClient(app)


def create_session(fastapi_client: TestClient):
    res = fastapi_client.post("create-with-claim", json={"key": "something"})
    return res


async def test_should_allow_without_claims_required_or_present(
    fastapi_client: TestClient,
):
    st_init_args = {
        **st_init_common_args,
        "recipe_list": [session.init(anti_csrf="VIA_TOKEN")],
    }
    init(**st_init_args)  # type: ignore
    start_st()

    create_session(fastapi_client)

    res = fastapi_client.get("/default-claims")
    assert res.status_code == 200
    assert "-" in res.json()["handle"]


async def test_should_allow_with_claim_valid_after_refetching(
    fastapi_client: TestClient,
):
    st_init_args = st_init_generator_with_claim_validator(
        TrueClaim.validators.has_value(True)
    )
    init(**st_init_args)  # type: ignore
    start_st()

    create_session(fastapi_client)

    response = fastapi_client.get("/default-claims")
    assert response.status_code == 200


async def test_should_reject_with_claim_required_but_not_added(
    fastapi_client: TestClient,
):
    st_init_args = st_init_generator_with_claim_validator(
        NoneClaim.validators.has_value(True)  # type: ignore
    )
    init(**st_init_args)  # type: ignore
    start_st()

    create_session(fastapi_client)

    response = fastapi_client.get("/default-claims")
    assert response.status_code == 403
    assert response.json() == {
        "message": "invalid claim",
        "claimValidationErrors": [
            {
                "id": "st-none",
                "reason": {
                    "message": "wrong value",
                    "expectedValue": True,
                    "actualValue": None,  # TODO: Do we want to return actualValue or not?
                },
            }
        ],
    }


async def test_should_allow_with_custom_validator_returning_true(
    fastapi_client: TestClient,
):
    custom_validator = AlwaysValidValidator()

    st_init_args = st_init_generator_with_claim_validator(custom_validator)
    init(**st_init_args)  # type: ignore
    start_st()

    create_session(fastapi_client)
    res = fastapi_client.get("/default-claims")
    assert res.status_code == 200
    assert "-" in res.json()["handle"]


async def test_should_reject_with_custom_validator_returning_false(
    fastapi_client: TestClient,
):
    custom_validator = AlwaysInvalidValidator()

    st_init_args = st_init_generator_with_claim_validator(custom_validator)
    init(**st_init_args)  # type: ignore
    start_st()

    create_session(fastapi_client)
    response = fastapi_client.get("/default-claims")
    assert response.status_code == 403
    assert response.json() == {
        "message": "invalid claim",
        "claimValidationErrors": [{"id": "always-invalid-validator", "reason": "foo"}],
    }


# should reject with validator returning false with reason (Leaving this. It's exactly same as prev.)


async def test_should_reject_if_assert_claims_returns_an_error(
    fastapi_client: TestClient,
):
    validator = AlwaysValidValidator()
    st_init_args = st_init_generator_with_overriden_global_validators([validator])
    init(**st_init_args)  # type: ignore
    start_st()

    recipe_implementation_mock = AsyncMock()
    s = Session(
        recipe_implementation_mock,
        "test_access_token",
        "test_session_handle",
        "test_user_id",
        {},
    )

    with patch.object(Session, "assert_claims", wraps=s.assert_claims) as mock:
        mock.side_effect = lambda _, __: raise_invalid_claims_exception(  # type: ignore
            "INVALID_CLAIM",
            [
                ClaimValidationError(
                    "test_id",
                    {"msg": "test_reason"},
                )
            ],
        )
        create_session(fastapi_client)
        response = fastapi_client.get("/default-claims")
        assert response.status_code == 403
        assert response.json() == {
            "message": "invalid claim",
            "claimValidationErrors": [{"id": "test_id", "reason": "test_reason"}],
        }


async def test_should_allow_if_assert_claims_returns_none(fastapi_client: TestClient):
    validator = AlwaysValidValidator()
    st_init_args = st_init_generator_with_overriden_global_validators([validator])
    init(**st_init_args)  # type: ignore
    start_st()

    recipe_implementation_mock = AsyncMock()
    s = Session(
        recipe_implementation_mock,
        "test_access_token",
        "test_session_handle",
        "test_user_id",
        {},
    )

    with patch.object(Session, "assert_claims", wraps=s.assert_claims) as mock:
        mock.return_value = None
        create_session(fastapi_client)
        response = fastapi_client.get("/default-claims")
        assert response.status_code == 200
        assert "-" in response.json()["handle"]


# With override_global_claim_validators:


async def test_should_allow_with_empty_list_as_override(fastapi_client: TestClient):
    # Despite providing a SessionClaimValidator, the validator should not be called
    # because in the endpoint "no-claims" we remove all the validators
    # by passing override_global_claim_validators to verify_session()
    st_init_args = st_init_generator_with_claim_validator(
        NoneClaim.validators.has_value(True)
    )
    init(**st_init_args)  # type: ignore
    start_st()

    create_session(fastapi_client)
    res = fastapi_client.get("/no-claims")
    assert res.status_code == 200


async def test_should_allow_with_refetched_claim(fastapi_client: TestClient):
    # This gets overriden by TrueClaim.validators.has_value(True)
    # in refetched-claim-false via override_global_claim_validators param
    # passed to verify_session()
    st_init_args = st_init_generator_with_claim_validator(
        NoneClaim.validators.has_value(True)
    )
    init(**st_init_args)  # type: ignore
    start_st()

    create_session(fastapi_client)
    res = fastapi_client.get("/refetched-claim")
    assert res.status_code == 200


async def test_should_reject_with_invalid_refetched_claim(fastapi_client: TestClient):
    # This gets overriden by TrueClaim.validators.has_value(False)
    # in refetched-claim-false via override_global_claim_validators param
    # passed to verify_session()
    st_init_args = st_init_generator_with_claim_validator(
        NoneClaim.validators.has_value(True)
    )
    init(**st_init_args)  # type: ignore
    start_st()

    create_session(fastapi_client)
    res = fastapi_client.get("/refetched-claim-false")
    assert res.status_code == 403
    assert res.json() == {
        "message": "invalid claim",
        "claimValidationErrors": [
            {
                "id": "st-true",
                "reason": {
                    "message": "wrong value",
                    "expectedValue": False,
                    "actualValue": True,
                },
            }
        ],
    }


async def test_should_reject_with_custom_claim_returning_false(
    fastapi_client: TestClient,
):
    # This gets overriden by override_global_claim_validators passed to verify_session()
    # in "/refetched-claim-isvalid-false" api
    cv = AlwaysInvalidValidator()
    st_init_args = st_init_generator_with_claim_validator(cv)
    init(**st_init_args)  # type: ignore
    start_st()

    create_session(fastapi_client)
    res = fastapi_client.get("/refetched-claim-isvalid-false")
    assert res.status_code == 403
    assert res.json() == {
        "message": "invalid claim",
        "claimValidationErrors": [{"id": "test_id", "reason": "test_reason"}],
    }


async def test_should_allow_with_custom_claim_returning_true(
    fastapi_client: TestClient,
):
    # This gets overriden by override_global_claim_validators passed to verify_session()
    # in "/refetched-claim-isvalid-true" api
    cv = AlwaysValidValidator()
    st_init_args = st_init_generator_with_claim_validator(cv)
    init(**st_init_args)  # type: ignore
    start_st()

    create_session(fastapi_client)
    res = fastapi_client.get("/refetched-claim-isvalid-true")
    assert res.status_code == 200
    assert "-" in res.json()["handle"]
