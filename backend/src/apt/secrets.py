"""Secret storage. Values stay out of SQLite. Amazon passwords are refused."""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path

from cryptography.fernet import Fernet

ALLOWED_SECRET_NAMES = {"keepa_api_key"}


class SecretStoreError(RuntimeError):
    pass


def reject_secret_name(name: str) -> str | None:
    """Return an error message, or None when the name may be stored."""
    lowered = name.strip().lower()
    if "password" in lowered or lowered in {"amazon_email", "credit_card", "card_number"}:
        return "Amazon passwords are never stored, and neither are card numbers."
    if lowered not in ALLOWED_SECRET_NAMES:
        return "That secret is not used by this version."
    return None


class KeychainSecretStore:
    """macOS Keychain via the security command. Not selected on other systems."""

    def __init__(self, service: str = "com.local.amazonpricetracker") -> None:
        self.service = service

    def _add_command(self, name: str, value: str) -> list[str]:
        return [
            "security",
            "add-generic-password",
            "-U",
            "-s",
            self.service,
            "-a",
            name,
            "-w",
            value,
        ]

    def _find_command(self, name: str) -> list[str]:
        return ["security", "find-generic-password", "-s", self.service, "-a", name, "-w"]

    def _delete_command(self, name: str) -> list[str]:
        return ["security", "delete-generic-password", "-s", self.service, "-a", name]

    def put(self, name: str, value: str) -> None:
        import subprocess

        completed = subprocess.run(
            self._add_command(name, value),
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise SecretStoreError("Keychain refused the secret. The value was not logged.")

    def exists(self, name: str) -> bool:
        import subprocess

        completed = subprocess.run(
            self._find_command(name),
            check=False,
            capture_output=True,
            text=True,
        )
        return completed.returncode == 0

    def delete(self, name: str) -> None:
        import subprocess

        subprocess.run(self._delete_command(name), check=False, capture_output=True, text=True)


class EncryptedFileSecretStore:
    """Fernet file used when macOS Keychain is not available. Mode 0600."""

    def __init__(self, path: Path, key_path: Path) -> None:
        self.path = path
        self.key_path = key_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        if not self.key_path.exists():
            self.key_path.write_bytes(Fernet.generate_key())
            os.chmod(self.key_path, 0o600)
        self._fernet = Fernet(self.key_path.read_bytes())

    def _read(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text())
        items = payload.get("items", {})
        if not isinstance(items, dict):
            raise SecretStoreError("Secret file is unreadable.")
        return {str(key): str(value) for key, value in items.items()}

    def _write(self, items: dict[str, str]) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"version": 1, "items": items}))
        os.chmod(temporary, 0o600)
        temporary.replace(self.path)
        os.chmod(self.path, 0o600)

    def put(self, name: str, value: str) -> None:
        items = self._read()
        items[name] = self._fernet.encrypt(value.encode()).decode()
        self._write(items)

    def exists(self, name: str) -> bool:
        return name in self._read()

    def delete(self, name: str) -> None:
        items = self._read()
        items.pop(name, None)
        self._write(items)

    def get(self, name: str) -> str | None:
        token = self._read().get(name)
        if token is None:
            return None
        return self._fernet.decrypt(token.encode()).decode()


def build_secret_store(data_dir: Path) -> KeychainSecretStore | EncryptedFileSecretStore:
    if platform.system() == "Darwin":
        return KeychainSecretStore()
    return EncryptedFileSecretStore(data_dir / "secrets.bin", data_dir / "secrets.key")
