"""词库服务（Phase 3.1）。

职责：
- 加载 ``config/wordbanks/{genre}.yaml`` 到内存（懒加载 + lru_cache）
- 提供 list / metadata / 随机抽样
- 业务代码不直接读文件，统一走 service

设计：
- 走 repo root 解析（参考 ``core.llm.factory`` 的模式），不依赖 settings.data_dir
  原因：词库是代码资源（随版本走），不是用户数据
- 用 lru_cache(maxsize=None) 缓存所有已加载的题材
- 抽样用 ``random.sample``（无重复），n > 词数时返回全部
- 错误：WordbankNotFoundError (404) / WordbankValidationError (422)
"""

from __future__ import annotations

import random
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from loguru import logger


class WordbankServiceError(Exception):
    """Service 层基础异常。"""


class WordbankNotFoundError(WordbankServiceError):
    """题材 id 不存在。"""

    def __init__(self, genre: str) -> None:
        super().__init__(f"Wordbank not found for genre: {genre!r}")
        self.genre = genre


class WordbankValidationError(WordbankServiceError):
    """category 不存在 / 参数非法。"""


def _find_repo_root() -> Path:
    """向上找项目根：包含 ``config/`` + ``pyproject.toml``。"""
    p = Path(__file__).resolve().parent
    for _ in range(8):
        if (p / "config").is_dir() and (p / "pyproject.toml").is_file():
            return p
        p = p.parent
    return Path(__file__).resolve().parents[4]


_WORDBANK_DIR = _find_repo_root() / "config" / "wordbanks"


@cache
def _load_genre(genre: str) -> dict[str, Any]:
    """加载某个题材的 YAML。失败抛 WordbankNotFoundError。

    缓存到 lru_cache；测试可用 ``_load_genre.cache_clear()`` 清除。

    额外校验：所有分类词条必须是 str（YAML 裸数字如 ``- 996`` 会被解析成 int）。
    发现非 str → :class:`WordbankValidationError`，避免到 API 层才 500。
    """
    path = _WORDBANK_DIR / f"{genre}.yaml"
    if not path.is_file():
        raise WordbankNotFoundError(genre)
    try:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to load wordbank {}: {}", path, e)
        raise WordbankNotFoundError(genre) from e
    if not isinstance(data, dict):
        raise WordbankValidationError(
            f"Wordbank {genre!r} root must be a dict, got {type(data).__name__}"
        )
    for cat, words in data.items():
        if cat == "name" or not isinstance(words, list):
            continue
        for i, w in enumerate(words):
            if not isinstance(w, str):
                raise WordbankValidationError(
                    f"Wordbank {genre!r}.{cat}[{i}] must be str, got {type(w).__name__}: {w!r}"
                )
    return data


def _list_genre_ids() -> list[str]:
    """扫 ``config/wordbanks/*.yaml`` 返回所有题材 id（按文件名排序）。"""
    if not _WORDBANK_DIR.is_dir():
        return []
    return sorted(p.stem for p in _WORDBANK_DIR.glob("*.yaml"))


class WordbankService:
    """词库查询服务（无状态）。"""

    # ===== 题材列表 =====
    def list_genres(self) -> list[dict[str, Any]]:
        """返回所有题材摘要 ``[{"id", "name", "total"}, ...]``。"""
        result: list[dict[str, Any]] = []
        for gid in _list_genre_ids():
            try:
                data = _load_genre(gid)
            except WordbankServiceError:
                continue
            name = data.get("name") or gid
            total = sum(len(v) for k, v in data.items() if k != "name" and isinstance(v, list))
            result.append({"id": gid, "name": name, "total": total})
        return result

    # ===== 元数据 =====
    def get_metadata(self, genre: str) -> dict[str, Any]:
        """返回 ``{id, name, categories, counts}``。

        题材不存在 → :class:`WordbankNotFoundError`。
        """
        data = _load_genre(genre)
        name = data.get("name") or genre
        categories: list[str] = []
        counts: dict[str, int] = {}
        for k, v in data.items():
            if k == "name":
                continue
            if isinstance(v, list):
                categories.append(k)
                counts[k] = len(v)
        return {
            "id": genre,
            "name": name,
            "categories": categories,
            "counts": counts,
        }

    # ===== 随机抽样 =====
    def get_random_words(
        self,
        genre: str,
        category: str,
        n: int = 10,
    ) -> list[str]:
        """从某题材某分类抽 ``n`` 个词（无重复）。"""
        if n < 1:
            raise WordbankValidationError(f"n must be >= 1, got {n}")
        data = _load_genre(genre)
        words = data.get(category)
        if not isinstance(words, list):
            raise WordbankValidationError(
                f"Category {category!r} not found in genre {genre!r}; "
                f"available: {[k for k in data if k != 'name']}"
            )
        if not words:
            return []
        return random.sample(words, min(n, len(words)))

    def get_random_words_multi(
        self,
        genre: str,
        per_category: dict[str, int],
    ) -> dict[str, list[str]]:
        """一次抽多类，返回 ``{category: [words]}``。"""
        return {cat: self.get_random_words(genre, cat, n) for cat, n in per_category.items()}

    # ===== 内部工具 =====
    @staticmethod
    def clear_cache() -> None:
        """测试用：清掉 lru_cache。"""
        _load_genre.cache_clear()
