"""Google Chat webhook test helpers: constants, a throwaway RSA key, a fake certs endpoint."""

import copy
import json
from pathlib import Path

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
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


# --- Google Chat outbound (Chat API): fake service-account key + fake token/Chat endpoints ---

TOKEN_URI = "https://oauth2.example.test/token"
SA_EMAIL = "bot@project.iam.gserviceaccount.com"
SA_KEY_ID = "sa-key-id"
CHAT_TOKEN = "ya29.minted-token"


def write_service_account_file(path: Path, key: rsa.RSAPrivateKey) -> str:
    """A service-account JSON key backed by the throwaway RSA key; returns its path."""
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    path.write_text(
        json.dumps(
            {
                "client_email": SA_EMAIL,
                "private_key": pem,
                "private_key_id": SA_KEY_ID,
                "token_uri": TOKEN_URI,
            }
        )
    )
    return str(path)


class ChatApiServer:
    """Fake token endpoint + Chat API. Records every request; the Chat reply is scriptable."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.token_status = 200
        self.chat_status = 200
        self.message_name = "spaces/AAA/messages/M1"
        self.transport = httpx.MockTransport(self._handle)

    @property
    def token_requests(self) -> list[httpx.Request]:
        return [r for r in self.requests if str(r.url) == TOKEN_URI]

    @property
    def chat_requests(self) -> list[httpx.Request]:
        return [r for r in self.requests if r.url.host == "chat.googleapis.com"]

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if str(request.url) == TOKEN_URI:
            return httpx.Response(
                self.token_status, json={"access_token": CHAT_TOKEN, "expires_in": 3600}
            )
        return httpx.Response(self.chat_status, json={"name": self.message_name})
