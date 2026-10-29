"""词库导入的非法分类必须报 422，不能 500。

2026-10-29 评审事故：
``import_words`` 以前不校验 ``default_category``，
板块里没有这个分类时 → ``data[item.category]`` KeyError → **500**。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from src.services.wordbank_service import (
    WordbankService,
    WordbankValidationError,
)

CUSTOM_YAML = """name: 自定义
things:
- 旧物
"""


def _clear_caches() -> None:
    """清掉所有模块副本的词库缓存（``src.*`` 会被 conftest 重建，可能有多份）。"""
    for name, module in list(sys.modules.items()):
        if name != "src.services.wordbank_service" or module is None:
            continue
        module.WordbankService.clear_cache()  # type: ignore[attr-defined]


@pytest.fixture
def bank(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """把词库目录指向 tmp_path，放一个只有 things 分类的自定义板块。

    用环境变量 ``BOOK_SOUL_WORDBANK_DIR`` 隔离 ——
    patch 模块常量对 conftest 重建出来的其它副本不生效，
    反而会去改**开发者真实的词库文件**。
    """
    root = tmp_path / "wordbanks"
    root.mkdir()
    (root / "custom.yaml").write_text(CUSTOM_YAML, encoding="utf-8")

    monkeypatch.setenv("BOOK_SOUL_WORDBANK_DIR", str(root))
    _clear_caches()
    yield root
    _clear_caches()


def test_import_with_invalid_default_category_raises_validation_error(bank: Path):
    """板块里没有 themes 分类时，用 themes 当默认分类要报 422 而不是 500。"""
    service = WordbankService()

    with pytest.raises(WordbankValidationError) as exc:
        service.import_words("custom", "新词\n", default_category="themes")

    assert "themes" in str(exc.value)
    assert "things" in str(exc.value)


def test_import_with_valid_default_category_succeeds(bank: Path):
    """合法分类照常导入。"""
    service = WordbankService()

    report = service.import_words("custom", "新词\n", default_category="things")

    assert report.added == 1
    assert report.failed == 0


def test_import_does_not_write_when_category_invalid(bank: Path):
    """校验失败时不能动文件（不能写出半截状态）。"""
    service = WordbankService()
    before = (bank / "custom.yaml").read_text(encoding="utf-8")

    with pytest.raises(WordbankValidationError):
        service.import_words("custom", "新词\n", default_category="themes")

    assert (bank / "custom.yaml").read_text(encoding="utf-8") == before
