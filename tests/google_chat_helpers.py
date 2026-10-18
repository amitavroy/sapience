"""Google Chat webhook test helpers: constants, a throwaway RSA key, a fake certs endpoint."""

import copy
import json
from pathlib import Path

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

FIXTURES = Path(__file__).parent / "fixtures"
CHAT_FIXTURES = ["google-chat-incoming.json", "google-chat-incoming-ind.json"]  # space, DM
SLASH_FIXTURE = "google-slash-command.json"  # /add-knowledge hello


def load_fixture(name: str) -> dict:
    """A sanitized real Google Chat event; mutate freely, every call returns a fresh copy."""
    return copy.deepcopy(json.loads((FIXTURES / name).read_text()))


GOOGLE_AUDIENCE = "https://chat.example.test/ingest/google-chat"
GOOGLE_EMAIL = "service-123@gcp-sa-gsuiteaddons.iam.gserviceaccount.com"
GOOGLE_KID = "test-kid"


def new_rsa_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def public_jwk(key: rsa.RSAPrivateKey, kid: str = GOOGLE_KID) -> dict:
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    return {**jwk, "kid": kid, "alg": "RS256", "use": "sig"}


class JwksServer:
    """Fake Google certs endpoint. Each request pops the next key set; the last one repeats."""

    def __init__(self, key_sets: list[list[dict]]) -> None:
        self.key_sets = key_sets
        self.calls = 0
        self.status = 200
        self.max_age = 3600
        self.error: Exception | None = None
        self.transport = httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        if self.error is not None:
            raise self.error
        keys = self.key_sets[min(self.calls, len(self.key_sets)) - 1]
        return httpx.Response(
            self.status,
            json={"keys": keys},
            headers={"cache-control": f"public, max-age={self.max_age}"},
        )
