"""加密服务（Phase 1.6 简化版）。

设计：
- ``EncryptionService`` 是无状态的轻包装（每次调用查一次 keyring，缓存 cipher）
- 默认 disabled（``enabled=False``）；开启时尝试拿 key，失败 → 降级为 disabled + 日志告警
- ``encrypt`` / ``decrypt`` 都是单参/双参；空入参直接返回入参
- decrypt 拿到非加密数据（明文/空）也直接返回，**不抛错**（graceful）

使用场景：
- 后续可能加密 chapter.content、inspiration.content、novel.description 等敏感字段
- 调用方读 settings.encryption_enabled 决定是否实例化 enabled=True 的 service
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken
from loguru import logger

from .keyring_manager import _KeyringLike, get_or_create_key


class EncryptionService:
    """Fernet 对称加密服务。

    用法::

        svc = EncryptionService(enabled=True)
        ct = svc.encrypt("secret text")
        pt = svc.decrypt(ct)  # 还原
    """

    def __init__(
        self,
        enabled: bool = False,
        backend: _KeyringLike | None = None,
    ) -> None:
        self.enabled = enabled
        self.cipher: Fernet | None = None
        if not enabled:
            return
        key = get_or_create_key(backend=backend)
        if key is None:
            # Keyring 不可用 → 降级为 disabled
            logger.warning(
                "encryption enabled but key unavailable; "
                "service will be a no-op (data written in plaintext)"
            )
            self.enabled = False
            return
        self.cipher = Fernet(key)

    @property
    def is_active(self) -> bool:
        """服务是否真的能加解密（enabled 且 cipher 已建好）。"""
        return self.enabled and self.cipher is not None

    def encrypt(self, plaintext: str | None) -> str | None:
        """加密；None 透传；服务未激活时返回原值。"""
        if plaintext is None:
            return None
        if not self.is_active:
            return plaintext
        return self.cipher.encrypt(plaintext.encode()).decode()  # type: ignore[union-attr]

    def decrypt(self, ciphertext: str | None) -> str | None:
        """解密；None/空 透传；服务未激活时返回原值；解密失败（明文/格式错）也返回原值。"""
        if ciphertext is None or ciphertext == "":
            return ciphertext
        if not self.is_active:
            return ciphertext
        try:
            return self.cipher.decrypt(ciphertext.encode()).decode()  # type: ignore[union-attr]
        except (InvalidToken, ValueError):
            # 不是 Fernet 密文（可能是旧明文数据）→ 透传
            return ciphertext

    # 兼容旧 API 命名（plan 里用 encrypt/decrypt 但可能别处叫 encode/decode）
    def encode(self, plaintext: str | None) -> str | None:
        return self.encrypt(plaintext)

    def decode(self, ciphertext: str | None) -> str | None:
        return self.decrypt(ciphertext)
