from collections.abc import Callable
from types import SimpleNamespace

import httpx
import pytest

from app.core.google_auth import GoogleTokenVerifier, InvalidGoogleTokenError
from tests.google_chat_helpers import GOOGLE_EMAIL, JwksServer, new_rsa_key, public_jwk

Sign = Callable[..., str]


async def test_valid_token_returns_claims(
    google_verifier: GoogleTokenVerifier, google_settings: SimpleNamespace, sign_google_token: Sign
) -> None:
    claims = await google_verifier.verify(
        sign_google_token(), audience=google_settings.audience, email=google_settings.email
    )

    assert claims["email"] == GOOGLE_EMAIL
    assert claims["iss"] == "https://accounts.google.com"


@pytest.mark.parametrize(
    "overrides",
    [
        {"key": new_rsa_key()},  # signed with a different key, same kid
        {"aud": "https://evil.example.test/ingest/google-chat"},
        {"iss": "https://evil.example.test"},
        {"exp": 1},
        {"exp": None},
        {"email": "service-999@gcp-sa-gsuiteaddons.iam.gserviceaccount.com"},
        {"email_verified": False},
        {"kid": None},
    ],
    ids=[
        "bad-signature",
        "wrong-aud",
        "wrong-iss",
        "expired",
        "missing-exp",
        "wrong-email",
        "email-not-verified",
        "missing-kid",
    ],
)
async def test_invalid_token_is_rejected(
    google_verifier: GoogleTokenVerifier,
    google_settings: SimpleNamespace,
    sign_google_token: Sign,
    overrides: dict,
) -> None:
    token = sign_google_token(**overrides)

    with pytest.raises(InvalidGoogleTokenError):
        await google_verifier.verify(
            token, audience=google_settings.audience, email=google_settings.email
        )


async def test_garbage_token_is_rejected(
    google_verifier: GoogleTokenVerifier, google_settings: SimpleNamespace
) -> None:
    with pytest.raises(InvalidGoogleTokenError):
        await google_verifier.verify(
            "not-a-jwt", audience=google_settings.audience, email=google_settings.email
        )


async def test_missing_kid_does_not_fetch_keys(
    google_verifier: GoogleTokenVerifier,
    google_settings: SimpleNamespace,
    sign_google_token: Sign,
    jwks: JwksServer,
) -> None:
    with pytest.raises(InvalidGoogleTokenError):
        await google_verifier.verify(
            sign_google_token(kid=None),
            audience=google_settings.audience,
            email=google_settings.email,
        )

    assert jwks.calls == 0


async def test_unknown_kid_refetches_once_then_rejects(
    google_verifier: GoogleTokenVerifier,
    google_settings: SimpleNamespace,
    sign_google_token: Sign,
    jwks: JwksServer,
) -> None:
    with pytest.raises(InvalidGoogleTokenError):
        await google_verifier.verify(
            sign_google_token(kid="unknown"),
            audience=google_settings.audience,
            email=google_settings.email,
        )

    assert jwks.calls == 2  # the initial load plus one forced refetch


async def test_rotated_key_is_picked_up_by_refetch(
    google_settings: SimpleNamespace, sign_google_token: Sign, rsa_key
) -> None:
    new_key = new_rsa_key()
    jwks = JwksServer(
        [
            [public_jwk(rsa_key)],  # first fetch: only the old key
            [public_jwk(rsa_key), public_jwk(new_key, kid="rotated")],  # after rotation
        ]
    )
    async with httpx.AsyncClient(transport=jwks.transport) as http:
        verifier = GoogleTokenVerifier(http)
        await verifier.verify(
            sign_google_token(), audience=google_settings.audience, email=google_settings.email
        )

        claims = await verifier.verify(
            sign_google_token(key=new_key, kid="rotated"),
            audience=google_settings.audience,
            email=google_settings.email,
        )

    assert claims["email"] == GOOGLE_EMAIL
    assert jwks.calls == 2


async def test_keys_are_cached_within_max_age(
    google_verifier: GoogleTokenVerifier,
    google_settings: SimpleNamespace,
    sign_google_token: Sign,
    jwks: JwksServer,
) -> None:
    for _ in range(3):
        await google_verifier.verify(
            sign_google_token(), audience=google_settings.audience, email=google_settings.email
        )

    assert jwks.calls == 1


@pytest.mark.parametrize(
    "failure",
    [
        {"status": 500},
        {"error": httpx.ReadTimeout("slow")},
    ],
    ids=["http-500", "timeout"],
)
async def test_jwks_fetch_failure_is_rejected(
    google_verifier: GoogleTokenVerifier,
    google_settings: SimpleNamespace,
    sign_google_token: Sign,
    jwks: JwksServer,
    failure: dict,
) -> None:
    for name, value in failure.items():
        setattr(jwks, name, value)

    with pytest.raises(InvalidGoogleTokenError):
        await google_verifier.verify(
            sign_google_token(), audience=google_settings.audience, email=google_settings.email
        )


@pytest.mark.parametrize(
    ("audience", "email"),
    [("", GOOGLE_EMAIL), ("https://chat.example.test/ingest/google-chat", "")],
    ids=["empty-audience", "empty-email"],
)
async def test_unconfigured_verifier_rejects_everything(
    google_verifier: GoogleTokenVerifier,
    sign_google_token: Sign,
    jwks: JwksServer,
    audience: str,
    email: str,
) -> None:
    with pytest.raises(InvalidGoogleTokenError):
        await google_verifier.verify(sign_google_token(), audience=audience, email=email)

    assert jwks.calls == 0
