"""密钥存储（DPAPI + SecretStore）单元测试。

覆盖：
- 加密 → 落盘 → 解密 round-trip
- 落盘内容**不含明文**
- 删除 provider
- 非 Windows / DPAPI 不可用时的降级
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ⚠️ 必须顶层导入（与 conftest 的模块重载保持同一个实例，见 test_llm_streaming_contract.py 注释）
from src.core.security import secret_store
from src.core.security.dpapi import DPAPIUnavailableError, is_supported
from src.core.security.secret_store import SecretStore

pytestmark = pytest.mark.skipif(not is_supported(), reason="DPAPI only available on Windows")


def test_set_and_get_roundtrip(tmp_path: Path) -> None:
    store = SecretStore(tmp_path)
    store.set("mimo", "sk-secret-value-123")

    assert store.get("mimo") == "sk-secret-value-123"


def test_plaintext_not_on_disk(tmp_path: Path) -> None:
    """落盘文件里不能出现明文 key。"""
    store = SecretStore(tmp_path)
    store.set("mimo", "sk-super-secret-plaintext")

    raw = store.path.read_text(encoding="utf-8")
    assert "sk-super-secret-plaintext" not in raw
    # 但要能看到 provider 名（便于排查）
    assert "mimo" in raw


def test_keys_file_is_valid_json(tmp_path: Path) -> None:
    store = SecretStore(tmp_path)
    store.set("mimo", "value-1")
    store.set("minimax", "value-2")

    data = json.loads(store.path.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert set(data["providers"].keys()) == {"mimo", "minimax"}


def test_get_missing_provider_returns_none(tmp_path: Path) -> None:
    store = SecretStore(tmp_path)
    assert store.get("never-set") is None


def test_get_when_no_file(tmp_path: Path) -> None:
    store = SecretStore(tmp_path)
    assert store.get("mimo") is None
    assert store.list_providers() == []


def test_delete_removes_provider(tmp_path: Path) -> None:
    store = SecretStore(tmp_path)
    store.set("mimo", "v")
    assert store.delete("mimo") is True
    assert store.get("mimo") is None
    # 再删一次 → False
    assert store.delete("mimo") is False


def test_set_empty_value_deletes(tmp_path: Path) -> None:
    store = SecretStore(tmp_path)
    store.set("mimo", "v")
    store.set("mimo", "")
    assert store.get("mimo") is None


def test_list_providers(tmp_path: Path) -> None:
    store = SecretStore(tmp_path)
    store.set("mimo", "a")
    store.set("openai", "b")
    assert store.list_providers() == ["mimo", "openai"]


def test_tampered_file_does_not_crash(tmp_path: Path) -> None:
    """文件损坏 → 返回 None 而不是抛异常。"""
    store = SecretStore(tmp_path)
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.path.write_text("{ not json", encoding="utf-8")

    assert store.get("mimo") is None


def test_undecryptable_ciphertext_returns_none(tmp_path: Path) -> None:
    """密文被篡改 → 返回 None，不抛异常。"""
    store = SecretStore(tmp_path)
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.path.write_text(
        json.dumps({"version": 1, "providers": {"mimo": "bm90LWEtY2lwaGVy" * 4}}),
        encoding="utf-8",
    )

    assert store.get("mimo") is None


def test_unsupported_platform_raises(tmp_path: Path, monkeypatch) -> None:
    """DPAPI 不可用时，set 应给出明确异常（而不是静默明文落盘）。"""
    monkeypatch.setattr(secret_store, "is_supported", lambda: False)
    store = SecretStore(tmp_path)
    with pytest.raises(DPAPIUnavailableError):
        store.set("mimo", "v")
