import os
from pathlib import Path

import keyring
from cryptography.fernet import Fernet, InvalidToken
from keyring.backends.fail import Keyring as NoKeyring
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from nexus.core.config import Settings
from nexus.secrets.models import Secret

KEYCHAIN_SERVICE = "nexus-studio"
KEYCHAIN_ACCOUNT = "master-key"
KEY_FILE = "master.key"


class SecretUnavailable(Exception):
    pass


def _key_from_file(path: Path) -> bytes:
    if path.exists():
        return path.read_bytes()
    key = Fernet.generate_key()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as file:
        file.write(key)
    return key


def _key_from_keychain() -> bytes:
    stored = keyring.get_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT)
    if stored:
        return stored.encode()
    key = Fernet.generate_key()
    keyring.set_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT, key.decode())
    return key


def load_master_key(settings: Settings) -> tuple[bytes, str]:
    """The key stays out of the database: in the OS keychain, or a private file without one."""
    use_keychain = settings.secret_backend == "keychain" or (
        settings.secret_backend == "auto" and not isinstance(keyring.get_keyring(), NoKeyring)
    )
    if use_keychain:
        return _key_from_keychain(), "keychain"
    return _key_from_file(settings.data_dir / KEY_FILE), "file"


class SecretService:
    """The only code that handles secret values. No route ever returns one."""

    def __init__(self, factory: sessionmaker[Session], key: bytes, backend: str) -> None:
        self.factory = factory
        self.cipher = Fernet(key)
        self.backend = backend

    def names(self) -> list[Secret]:
        with self.factory() as session:
            rows = list(session.scalars(select(Secret).order_by(Secret.name)))
            session.expunge_all()
            return rows

    def exists(self, name: str) -> bool:
        with self.factory() as session:
            return session.get(Secret, name) is not None

    def store(self, name: str, value: str) -> None:
        ciphertext = self.cipher.encrypt(value.encode())
        with self.factory() as session, session.begin():
            session.merge(Secret(name=name, ciphertext=ciphertext))

    def delete(self, name: str) -> bool:
        with self.factory() as session, session.begin():
            row = session.get(Secret, name)
            if row is None:
                return False
            session.delete(row)
            return True

    def resolve(self, name: str) -> str:
        with self.factory() as session:
            row = session.get(Secret, name)
        if row is None:
            raise SecretUnavailable(f"Secret {name} does not exist")
        try:
            return self.cipher.decrypt(row.ciphertext).decode()
        except InvalidToken as error:
            raise SecretUnavailable(
                f"Secret {name} cannot be decrypted; the master key has changed"
            ) from error
