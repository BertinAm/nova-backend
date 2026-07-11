import importlib

from cryptography.fernet import Fernet


def test_render_style_secret_is_accepted(monkeypatch):
    from app.security import crypto

    monkeypatch.setenv("EMBEDDING_ENCRYPTION_KEY", "render-generated-secret")
    crypto = importlib.reload(crypto)

    fernet = crypto.get_fernet()
    assert isinstance(fernet, Fernet)
    token = fernet.encrypt(b"hello")
    assert crypto.decrypt_bytes(token) == b"hello"
