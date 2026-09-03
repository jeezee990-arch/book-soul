"""测试加密服务（Phase 1.6）。

覆盖：
- KeyManager：fake backend 读/写；backend 异常 → None
- EncryptionService：默认 disabled（no-op）；enabled 正常加解密；key 不可用降级；
  decrypt 拿到非密文透传；空入参透传；None 入参透传
"""

from __future__ import annotations

from src.core.security.encryption import EncryptionService
from src.core.security.keyring_manager import (
    KEY_USERNAME,
    SERVICE_NAME,
    get_or_create_key,
)

# ===== Test helpers =====


class FakeKeyring:
    """内存 keyring backend（用于测试，不污染系统 keyring）。"""

    def __init__(self, *, fail_get: bool = False, fail_set: bool = False) -> None:
        self.store: dict[tuple[str, str], str] = {}
        self.fail_get = fail_get
        self.fail_set = fail_set
        self.set_calls = 0
        self.get_calls = 0

    def get_password(self, service: str, username: str) -> str | None:
        self.get_calls += 1
        if self.fail_get:
            raise RuntimeError("simulated keyring get failure")
        return self.store.get((service, username))

    def set_password(self, service: str, username: str, value: str) -> None:
        self.set_calls += 1
        if self.fail_set:
            raise RuntimeError("simulated keyring set failure")
        self.store[(service, username)] = value


# ===== KeyManager 测试 =====


def test_get_or_create_key_creates_new_when_empty():
    """空 store → 生成新 key 并写入。"""
    backend = FakeKeyring()
    key1 = get_or_create_key(backend=backend)
    assert key1 is not None
    assert len(key1) > 0
    # 应写到了 backend
    assert backend.store[(SERVICE_NAME, KEY_USERNAME)] is not None
    assert backend.set_calls == 1
    assert backend.get_calls == 1


def test_get_or_create_key_returns_existing():
    """已有 key → 读出来不重写。"""
    backend = FakeKeyring()
    # 先写一个
    key1 = get_or_create_key(backend=backend)
    # 第二次读
    key2 = get_or_create_key(backend=backend)
    assert key1 == key2
    # 第二次不应再 set
    assert backend.set_calls == 1  # 只有第一次的


def test_get_or_create_key_returns_none_on_get_failure():
    """get 异常 → 返回 None（降级）。"""
    backend = FakeKeyring(fail_get=True)
    key = get_or_create_key(backend=backend)
    assert key is None


def test_get_or_create_key_returns_none_on_set_failure():
    """set 异常 → 返回 None。"""
    backend = FakeKeyring(fail_set=True)
    key = get_or_create_key(backend=backend)
    assert key is None


# ===== EncryptionService 测试 =====


def test_disabled_service_is_noop():
    """默认 disabled，encrypt/decrypt 直接透传。"""
    svc = EncryptionService(enabled=False)
    assert svc.is_active is False
    assert svc.encrypt("hello") == "hello"
    assert svc.decrypt("anything") == "anything"


def test_disabled_service_default():
    """不传 enabled = 默认 False。"""
    svc = EncryptionService()
    assert svc.is_active is False
    assert svc.encrypt("hello") == "hello"


def test_enabled_service_encrypt_decrypt_roundtrip():
    """enabled 时 encrypt → decrypt 还原。"""
    backend = FakeKeyring()
    svc = EncryptionService(enabled=True, backend=backend)
    assert svc.is_active is True

    plaintext = "凡人修仙的热血与孤独"
    ct = svc.encrypt(plaintext)
    assert ct is not None
    assert ct != plaintext  # 确实加密了
    assert svc.decrypt(ct) == plaintext


def test_enabled_service_persists_key():
    """两次构造同 backend 共享同一 key（解密互通）。"""
    backend = FakeKeyring()
    svc1 = EncryptionService(enabled=True, backend=backend)
    ct = svc1.encrypt("secret1")

    svc2 = EncryptionService(enabled=True, backend=backend)
    assert svc2.decrypt(ct) == "secret1"


def test_enabled_service_downgrades_on_key_unavailable():
    """enabled 但 key 拿不到 → 自动降级为 no-op，不抛错。"""
    backend = FakeKeyring(fail_get=True)
    svc = EncryptionService(enabled=True, backend=backend)
    assert svc.is_active is False
    # 透传
    assert svc.encrypt("x") == "x"
    assert svc.decrypt("x") == "x"


def test_decrypt_plaintext_passes_through():
    """decrypt 收到非 Fernet 密文（明文）应直接返回，不抛错。"""
    backend = FakeKeyring()
    svc = EncryptionService(enabled=True, backend=backend)
    # 这看起来像密文但不是合法的 Fernet token
    plain = "this is just a regular string"
    assert svc.decrypt(plain) == plain


def test_decrypt_empty_string():
    """decrypt 空字符串 → 空。"""
    backend = FakeKeyring()
    svc = EncryptionService(enabled=True, backend=backend)
    assert svc.decrypt("") == ""


def test_decrypt_none():
    """decrypt None → None。"""
    backend = FakeKeyring()
    svc = EncryptionService(enabled=True, backend=backend)
    assert svc.decrypt(None) is None


def test_encrypt_none():
    """encrypt None → None。"""
    backend = FakeKeyring()
    svc = EncryptionService(enabled=True, backend=backend)
    assert svc.encrypt(None) is None


def test_disabled_service_handles_none():
    """disabled 状态 None 入参也安全。"""
    svc = EncryptionService(enabled=False)
    assert svc.encrypt(None) is None
    assert svc.decrypt(None) is None
    assert svc.decrypt("") == ""


def test_encode_decode_aliases():
    """encode/decode 是 encrypt/decrypt 的别名。"""
    backend = FakeKeyring()
    svc = EncryptionService(enabled=True, backend=backend)
    ct = svc.encode("hello")
    assert svc.decode(ct) == "hello"


def test_ciphertext_format_is_fernet_token():
    """加密结果应符合 Fernet token 格式（gAAAAA...）。"""
    backend = FakeKeyring()
    svc = EncryptionService(enabled=True, backend=backend)
    ct = svc.encrypt("hello")
    # Fernet 密文以版本字节开头（base64 of 0x80 = "gAAA"）
    assert ct.startswith("gAAAAA")


def test_two_encryptions_of_same_text_differ():
    """Fernet 每次随机 IV，同明文两次密文不同（防确定性泄漏）。"""
    backend = FakeKeyring()
    svc = EncryptionService(enabled=True, backend=backend)
    ct1 = svc.encrypt("same text")
    ct2 = svc.encrypt("same text")
    assert ct1 != ct2
    assert svc.decrypt(ct1) == svc.decrypt(ct2) == "same text"


def test_different_keys_cant_decrypt():
    """用不同 key 构造的 service 不能解密对方的密文。"""
    backend1 = FakeKeyring()
    backend2 = FakeKeyring()
    svc1 = EncryptionService(enabled=True, backend=backend1)
    svc2 = EncryptionService(enabled=True, backend=backend2)
    ct = svc1.encrypt("secret")
    # svc2 用自己的 key 解 svc1 的密文 → 失败 → 透传原值
    assert svc2.decrypt(ct) == ct  # 透传


# ===== 集成：disabled 时全程不调 keyring =====


def test_disabled_never_touches_backend():
    """disabled service 不应触发任何 backend 调用。"""
    backend = FakeKeyring()
    EncryptionService(enabled=False, backend=backend)
    assert backend.get_calls == 0
    assert backend.set_calls == 0
