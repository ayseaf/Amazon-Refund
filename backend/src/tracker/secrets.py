from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

ALLOWED_SECRET_NAMES = frozenset({"keepa_api_key"})
_REJECTED_NAME_PARTS = ("password", "card", "cvv", "pan", "secret")
KEYCHAIN_SERVICE = "com.local.amazonpricetracker"


class SecretStoreError(Exception):
    pass


class SecretStoreUnavailable(SecretStoreError):
    pass


class SecretStoreLocked(SecretStoreError):
    pass


class SecretStoreReadOnly(SecretStoreError):
    pass


class SecretNameRejected(SecretStoreError):
    pass


def validate_secret_name(name: str) -> str:
    lowered = name.strip().lower()
    if lowered in {"amazon_password", "password", "card_number"} or any(
        part in lowered for part in _REJECTED_NAME_PARTS
    ):
        raise SecretNameRejected(
            "This application never stores Amazon passwords, payment cards, or arbitrary secrets."
        )
    if lowered not in ALLOWED_SECRET_NAMES:
        raise SecretNameRejected("That secret is not used in this version. The only name is keepa_api_key.")
    if not name or name != lowered:
        raise SecretNameRejected("Secret names must be lowercase identifiers.")
    return lowered


def select_secret_backend(requested: str, platform_name: str) -> str:
    if requested == "auto":
        return "keychain" if platform_name == "darwin" else "encrypted_file"
    if requested == "keychain" and platform_name != "darwin":
        raise SecretStoreUnavailable(
            "macOS Keychain is unavailable on this system. "
            "Use TRACKER_SECRET_BACKEND=encrypted_file or TRACKER_SECRET_BACKEND=env."
        )
    if requested not in {"keychain", "encrypted_file", "env"}:
        raise SecretStoreError(f"Unknown secret backend: {requested}")
    return requested


def _protect_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved = path.parent.resolve()
    if resolved == Path.cwd().resolve() or resolved == Path("/"):
        return
    os.chmod(resolved, 0o700)


class EncryptedFileSecretStore:
    backend_name = "encrypted_file"
    writable = True

    def __init__(self, path: Path, key: str):
        self.path = path
        try:
            self._fernet = Fernet(key.encode("ascii"))
        except (ValueError, TypeError) as exc:
            raise SecretStoreError("TRACKER_SECRET_KEY is not a valid Fernet key") from exc

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self._fernet.decrypt(self.path.read_bytes()))
        except InvalidToken as exc:
            raise SecretStoreError("The secret file could not be decrypted with TRACKER_SECRET_KEY") from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise SecretStoreError("The secret file is corrupt") from exc
        if not isinstance(payload, dict):
            raise SecretStoreError("The secret file is corrupt")
        return {str(key): str(value) for key, value in payload.items()}

    def _save(self, payload: dict[str, str]) -> None:
        _protect_parent(self.path)
        token = self._fernet.encrypt(json.dumps(payload, sort_keys=True).encode("utf-8"))
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_bytes(token)
        os.chmod(temporary, 0o600)
        temporary.replace(self.path)
        os.chmod(self.path, 0o600)

    def get(self, name: str) -> str | None:
        validated = validate_secret_name(name)
        return self._load().get(validated)

    def put(self, name: str, value: str) -> None:
        validated = validate_secret_name(name)
        if not value or not value.strip():
            raise SecretStoreError("A secret value cannot be empty")
        payload = self._load() if self.path.exists() else {}
        payload[validated] = value
        self._save(payload)

    def delete(self, name: str) -> None:
        validated = validate_secret_name(name)
        payload = self._load() if self.path.exists() else {}
        payload.pop(validated, None)
        self._save(payload)


class EnvSecretStore:
    """Read-only secrets injected by the environment. Writes are refused."""

    backend_name = "env"
    writable = False
    prefix = "TRACKER_SECRET_VALUE_"

    def __init__(self, environ: Mapping[str, str] | None = None):
        self._environ = os.environ if environ is None else environ

    def _env_name(self, name: str) -> str:
        return f"{self.prefix}{validate_secret_name(name).upper()}"

    def get(self, name: str) -> str | None:
        value = self._environ.get(self._env_name(name))
        if value is None or value == "":
            return None
        return value

    def put(self, name: str, value: str) -> None:
        validate_secret_name(name)
        raise SecretStoreReadOnly(
            "The env secret store is read-only. Set TRACKER_SECRET_VALUE_KEEPA_API_KEY "
            "in the environment, or use the encrypted file store."
        )

    def delete(self, name: str) -> None:
        validate_secret_name(name)
        raise SecretStoreReadOnly("The env secret store is read-only.")


class LockedSecretStore:
    backend_name = "encrypted_file"
    writable = False

    def __init__(self, backend_name: str = "encrypted_file"):
        self.backend_name = backend_name

    def get(self, name: str) -> str | None:
        validate_secret_name(name)
        raise SecretStoreLocked(
            "The secret store is locked. Set TRACKER_SECRET_KEY to a Fernet key, "
            "or on a Mac set TRACKER_SECRET_BACKEND=keychain."
        )

    def put(self, name: str, value: str) -> None:
        self.get(name)

    def delete(self, name: str) -> None:
        self.get(name)


def keychain_add_command(name: str, value: str, service: str = KEYCHAIN_SERVICE) -> list[str]:
    validated = validate_secret_name(name)
    if not value:
        raise SecretStoreError("A secret value cannot be empty")
    return [
        "security",
        "add-generic-password",
        "-U",
        "-s",
        service,
        "-a",
        validated,
        "-w",
        value,
    ]


def keychain_find_command(name: str, service: str = KEYCHAIN_SERVICE) -> list[str]:
    validated = validate_secret_name(name)
    return ["security", "find-generic-password", "-s", service, "-a", validated, "-w"]


def keychain_delete_command(name: str, service: str = KEYCHAIN_SERVICE) -> list[str]:
    validated = validate_secret_name(name)
    return ["security", "delete-generic-password", "-s", service, "-a", validated]


def redact_command(argv: Sequence[str]) -> list[str]:
    redacted: list[str] = []
    skip_next = False
    for part in argv:
        if skip_next:
            redacted.append("[redacted]")
            skip_next = False
            continue
        redacted.append(part)
        if part == "-w":
            skip_next = True
    return redacted


class KeychainSecretStore:
    """macOS Keychain via the `security` CLI.

    The password is passed as an argument because that is what `security` accepts.
    A local user can see it briefly in the process list. Logs use redact_command
    and never include the value. Phase 5 can replace this with the Security framework.
    """

    backend_name = "keychain"
    writable = True

    def __init__(self, runner=subprocess.run, platform_name: str | None = None):
        current = sys.platform if platform_name is None else platform_name
        if current != "darwin":
            raise SecretStoreUnavailable(
                "macOS Keychain is only available on Darwin. "
                "This environment uses the encrypted file store instead."
            )
        self._runner = runner

    def _run(self, argv: list[str]) -> subprocess.CompletedProcess:
        completed = self._runner(argv, check=False, capture_output=True, text=True)
        if completed.returncode != 0:
            raise SecretStoreError("Keychain rejected the request")
        return completed

    def put(self, name: str, value: str) -> None:
        self._run(keychain_add_command(name, value))

    def get(self, name: str) -> str | None:
        argv = keychain_find_command(name)
        completed = self._runner(argv, check=False, capture_output=True, text=True)
        if completed.returncode != 0:
            return None
        value = (completed.stdout or "").strip()
        return value or None

    def delete(self, name: str) -> None:
        argv = keychain_delete_command(name)
        completed = self._runner(argv, check=False, capture_output=True, text=True)
        if completed.returncode != 0:
            stderr = completed.stderr or ""
            if "could not be found" in stderr.lower():
                return
            raise SecretStoreError("Keychain rejected the request")


def store_status(store: EncryptedFileSecretStore | EnvSecretStore | LockedSecretStore | KeychainSecretStore) -> str:
    if isinstance(store, LockedSecretStore):
        return "locked"
    if not store.writable:
        return "read_only"
    return "ready"


def open_secret_store(backend: str, secret_file: Path, secret_key: str, platform_name: str):
    selected = select_secret_backend(backend, platform_name)
    if selected == "keychain":
        return KeychainSecretStore(platform_name=platform_name)
    if selected == "env":
        return EnvSecretStore()
    if not secret_key:
        return LockedSecretStore("encrypted_file")
    return EncryptedFileSecretStore(secret_file, secret_key)
