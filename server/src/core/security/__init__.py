"""Security 子包：加密服务（Phase 1.6）。

加密默认关闭（配置项 ``encryption_enabled: bool = False``）。
开启时通过 Fernet 对称加密，密钥存系统 Keyring。
"""
