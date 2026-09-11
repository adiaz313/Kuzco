"""Trusted integrations only. No LLM tool, SQLite, config or shell storage."""
import re
import sys


class CredentialError(RuntimeError):
    pass


class Secret:
    """Explicit disclosure only at the future authenticated API boundary."""
    __slots__ = ('__value',)

    def __init__(self, value):
        self.__value = value

    def __repr__(self):
        return '<Secret redacted>'

    __str__ = __repr__

    def reveal(self):
        return self.__value


class CredentialStore:
    SERVICE = 'local.kuzco.credentials.v1'

    def __init__(self):
        if sys.platform != 'darwin':
            raise CredentialError('Secure credential storage requires macOS Keychain.')
        try:
            from keyring.backends.macOS import Keyring
            self._backend = Keyring()  # Never automatic backend discovery/fallback.
        except Exception:
            raise CredentialError('macOS Keychain is unavailable.') from None

    def _name(self, name):
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_.-]{0,63}', name):
            raise CredentialError('Use a short integration credential identifier.')
        return name

    def set(self, name, value):
        name = self._name(name)
        if not isinstance(value, str) or not value or len(value) > 8192:
            raise CredentialError('Invalid credential value.')
        try:
            self._backend.set_password(self.SERVICE, name, value)
        except Exception:
            raise CredentialError('Keychain could not store the credential.') from None

    def get(self, name):
        name = self._name(name)
        try:
            value = self._backend.get_password(self.SERVICE, name)
            return Secret(value) if value is not None else None
        except Exception:
            raise CredentialError('Keychain could not retrieve the credential.') from None

    def delete(self, name):
        name = self._name(name)
        try:
            if self._backend.get_password(self.SERVICE, name) is None:
                return False
            self._backend.delete_password(self.SERVICE, name)
            return True
        except Exception:
            raise CredentialError('Keychain could not delete the credential.') from None
