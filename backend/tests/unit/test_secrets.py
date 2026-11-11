from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from tracker.secrets import (
    EncryptedFileSecretStore,
    EnvSecretStore,
    KeychainSecretStore,
    SecretNameRejected,
    SecretStoreError,
    SecretStoreReadOnly,
    SecretStoreUnavailable,
    keychain_add_command,
    redact_command,
    select_secret_backend,
)


SECRET = "keepa-live-key-not-for-storage-9f3a"


def test_auto_backend_is_the_encrypted_file_off_macos():
    assert select_secret_backend("auto", "linux") == "encrypted_file"


def test_auto_backend_is_keychain_on_macos():
    assert select_secret_backend("auto", "darwin") == "keychain"


def test_explicit_keychain_is_refused_off_macos():
    with pytest.raises(SecretStoreUnavailable):
        select_secret_backend("keychain", "linux")


def test_encrypted_file_round_trip_hides_the_plaintext(tmp_path):
    path = tmp_path / "secrets" / "secrets.bin"
    store = EncryptedFileSecretStore(path, Fernet.generate_key().decode())
    store.put("keepa_api_key", SECRET)
    assert store.get("keepa_api_key") == SECRET
    blob = path.read_bytes()
    assert SECRET.encode() not in blob
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700


def test_encrypted_file_overwrite_and_delete(tmp_path):
    store = EncryptedFileSecretStore(tmp_path / "secrets.bin", Fernet.generate_key().decode())
    store.put("keepa_api_key", "first-value")
    store.put("keepa_api_key", "second-value")
    assert store.get("keepa_api_key") == "second-value"
    store.delete("keepa_api_key")
    assert store.get("keepa_api_key") is None


def test_wrong_key_does_not_reveal_the_secret(tmp_path):
    path = tmp_path / "secrets.bin"
    EncryptedFileSecretStore(path, Fernet.generate_key().decode()).put("keepa_api_key", SECRET)
    store = EncryptedFileSecretStore(path, Fernet.generate_key().decode())
    with pytest.raises(SecretStoreError) as caught:
        store.get("keepa_api_key")
    assert SECRET not in str(caught.value)


def test_empty_secret_is_rejected(tmp_path):
    store = EncryptedFileSecretStore(tmp_path / "secrets.bin", Fernet.generate_key().decode())
    with pytest.raises(SecretStoreError):
        store.put("keepa_api_key", "   ")


def test_amazon_password_name_is_rejected(tmp_path):
    store = EncryptedFileSecretStore(tmp_path / "secrets.bin", Fernet.generate_key().decode())
    with pytest.raises(SecretNameRejected):
        store.put("amazon_password", SECRET)
    assert not (tmp_path / "secrets.bin").exists()


def test_env_store_is_read_only(monkeypatch):
    monkeypatch.setenv("TRACKER_SECRET_VALUE_KEEPA_API_KEY", SECRET)
    store = EnvSecretStore()
    assert store.get("keepa_api_key") == SECRET
    with pytest.raises(SecretStoreReadOnly):
        store.put("keepa_api_key", "other")
    with pytest.raises(SecretNameRejected):
        store.get("amazon_password")


def test_keychain_store_cannot_be_constructed_off_macos():
    with pytest.raises(SecretStoreUnavailable):
        KeychainSecretStore(platform_name="linux")


def test_keychain_command_redacts_the_password_in_logs():
    argv = keychain_add_command("keepa_api_key", SECRET)
    assert argv[0] == "security"
    assert SECRET in argv
    redacted = redact_command(argv)
    assert SECRET not in redacted
    assert redacted[redacted.index("-w") + 1] == "[redacted]"


def test_keychain_put_uses_the_injected_runner():
    seen: list[list[str]] = []

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def runner(argv, check, capture_output, text):
        seen.append(list(argv))
        return Result()

    store = KeychainSecretStore(runner=runner, platform_name="darwin")
    store.put("keepa_api_key", SECRET)
    assert seen[0][0] == "security"
    assert "add-generic-password" in seen[0]
    assert SECRET in seen[0]


def test_keychain_get_strips_the_cli_output():
    class Result:
        returncode = 0
        stdout = SECRET + "\n"
        stderr = ""

    store = KeychainSecretStore(runner=lambda *args, **kwargs: Result(), platform_name="darwin")
    assert store.get("keepa_api_key") == SECRET


def test_keychain_delete_of_a_missing_item_is_quiet():
    class Result:
        returncode = 44
        stdout = ""
        stderr = "The specified item could not be found in the keychain."

    store = KeychainSecretStore(runner=lambda *args, **kwargs: Result(), platform_name="darwin")
    store.delete("keepa_api_key")
