"""词库服务（Phase 3.1 读 / 需求6 读写管理）。

职责：
- 加载 ``config/wordbanks/{genre}.yaml`` 到内存（懒加载 + lru_cache）
- 提供 list / metadata / 随机抽样
- **词库管理**：新增 / 修改 / 删除 / 导入（按板块隔离，每个板块一个 YAML）
- 业务代码不直接读文件，统一走 service

设计：
- 走 repo root 解析（参考 ``core.llm.factory`` 的模式），不依赖 settings.data_dir
  原因：词库是代码资源（随版本走），不是用户数据
- 用 lru_cache(maxsize=None) 缓存所有已加载的题材
- 抽样用 ``random.sample``（无重复），n > 词数时返回全部
- 错误：WordbankNotFoundError (404) / WordbankValidationError (422)

写盘（新增 / 修改 / 删除 / 导入）三条硬规则：
- **板块隔离**：一次写操作只动**一个板块**的 YAML，绝不合并多个板块
- **原子写 + 备份**：见 ``wordbank_writer``（先备份，再写临时文件，再 os.replace）
- **缓存失效**：写完立刻 ``_load_genre_cached.cache_clear()``，
  否则导入的词随机不出来（``@cache`` 缓存的是旧内容）
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from ..core.paths import user_wordbanks_dir, wordbanks_dir
from .wordbank_importer import parse_import_text
from .wordbank_writer import load_wordbank_file, write_wordbank


class WordbankServiceError(Exception):
    """Service 层基础异常。"""


class WordbankNotFoundError(WordbankServiceError):
    """题材 id 不存在（或该板块下没有这个词条）。"""

    def __init__(self, genre: str, detail: str = "") -> None:
        message = f"Wordbank not found for genre: {genre!r}"
        if detail:
            message = f"{message} ({detail})"
        super().__init__(message)
        self.genre = genre


class WordbankValidationError(WordbankServiceError):
    """category 不存在 / 参数非法。"""


@dataclass
class WordbankMutation:
    """一次写操作的结果（新增 / 修改 / 删除共用）。"""

    added: int = 0
    updated: int = 0
    deleted: int = 0
    duplicates: int = 0
    errors: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


@dataclass
class WordbankImportReport:
    """一次导入的结果。"""

    added: int = 0
    duplicates: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)
    by_category: dict[str, int] = field(default_factory=dict)


_WORDBANK_DIR = wordbanks_dir()


def _bundled_dir() -> Path:
    """内置（打包内置 / 开发态 config）词库目录。

    环境变量 ``BOOK_SOUL_WORDBANK_DIR`` 优先（测试隔离用），
    否则用模块常量 ``_WORDBANK_DIR``（老测试在 patch 它）。
    """
    override = os.environ.get("BOOK_SOUL_WORDBANK_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return _WORDBANK_DIR


def _user_dir() -> Path:
    """用户可写的词库目录（测试可 monkeypatch 本函数）。

    默认走 ``core.paths.user_wordbanks_dir()``：
    打包态 = ``<data_dir>/wordbanks``；开发态 = ``config/wordbanks``。
    """
    return user_wordbanks_dir()


def _genre_file(genre: str) -> Path:
    """定位某个板块的词库文件。

    优先级：**用户可写副本** → 打包内置副本（``_bundled_dir()``）。
    打包态用户改过词之后，就一直读用户那份（不会重启就丢）。
    """
    user_file = _user_dir() / f"{genre}.yaml"
    if user_file.is_file():
        return user_file
    return _bundled_dir() / f"{genre}.yaml"


def _write_target(genre: str) -> Path:
    """写盘目标（一定是用户可写目录里的那一份）。"""
    return _user_dir() / f"{genre}.yaml"


@cache
def _load_genre_cached(genre: str, path_key: str) -> dict[str, Any]:
    """加载某个题材的 YAML（失败抛 WordbankNotFoundError）。

    缓存 key 里带**文件路径**：换目录（测试隔离、用户副本切换）不会串缓存。
    写盘后必须清缓存（见 ``WordbankService._save``），
    否则刚导入的词随机不出来。

    额外校验：所有分类词条必须是 str（YAML 裸数字如 ``- 996`` 会被解析成 int）。
    发现非 str → :class:`WordbankValidationError`，避免到 API 层才 500。
    """
    path = Path(path_key)
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


def _load_genre(genre: str) -> dict[str, Any]:
    """加载某个题材的 YAML（缓存 + 路径感知）。"""
    return _load_genre_cached(genre, str(_genre_file(genre)))


def _list_genre_ids() -> list[str]:
    """扫词库目录返回所有题材 id（打包内置 + 用户副本，取并集，按文件名排序）。"""
    ids: set[str] = set()
    for directory in (_bundled_dir(), _user_dir()):
        if not directory.is_dir():
            continue
        for p in directory.glob("*.yaml"):
            ids.add(p.stem)
    return sorted(ids)


class WordbankService:
    """词库服务（读 + 写）。"""

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

    # ===== 词库管理（读）=====
    def get_all_words(self, genre: str) -> dict[str, list[str]]:
        """返回该板块**全部**词条（按分类分组）。

        题材不存在 → :class:`WordbankNotFoundError`。
        """
        data = _load_genre(genre)
        return {k: list(v) for k, v in data.items() if k != "name" and isinstance(v, list)}

    # ===== 词库管理（写）=====
    def add_words(self, genre: str, items: list[tuple[str, str]]) -> WordbankMutation:
        """新增词条（单个或批量），追加到对应分类末尾。

        - 分类不存在 / 词条为空 → 记进 ``errors``，不影响其它词
        - 同分类里已有该词 → 记 ``duplicates``，跳过
        """
        data = _load_for_write(genre)
        categories = _categories_of(data)
        result = WordbankMutation()
        changed = False
        for category, raw_word in items:
            word = raw_word.strip()
            if not word:
                result.errors.append("词条不能为空")
                continue
            if category not in categories:
                result.errors.append(f"未知分类「{category}」（可用：{', '.join(categories)}）")
                continue
            words = data[category]
            if word in words:
                result.duplicates += 1
                continue
            words.append(word)
            result.added += 1
            changed = True
        if changed:
            self._save(genre, data)
        return result

    def update_word(self, genre: str, category: str, old: str, new: str) -> WordbankMutation:
        """修改一个词（``category`` 里的 ``old`` 改成 ``new``，保留原有位置）。

        - 分类不存在 → :class:`WordbankValidationError`（→ 422）
        - 原词不存在 → :class:`WordbankNotFoundError`（→ 404）
        - 新词与该分类已有词重复 → :class:`WordbankValidationError`（→ 422）
        """
        data = _load_for_write(genre)
        categories = _categories_of(data)
        if category not in categories:
            raise WordbankValidationError(
                f"Category {category!r} not found in genre {genre!r}; available: {categories}"
            )
        old_word = old.strip()
        new_word = new.strip()
        if not new_word:
            raise WordbankValidationError("新词条不能为空")
        words = data[category]
        if old_word not in words:
            raise WordbankNotFoundError(genre, f"词条「{old_word}」不在分类 {category!r} 中")
        if new_word != old_word and new_word in words:
            raise WordbankValidationError(f"词条「{new_word}」已存在于分类 {category!r}")
        words[words.index(old_word)] = new_word
        self._save(genre, data)
        return WordbankMutation(updated=1)

    def delete_words(self, genre: str, items: list[tuple[str, str]]) -> WordbankMutation:
        """删除词条（支持批量）。

        找不到的词记进 ``missing``（不报错，其余照删）。
        """
        data = _load_for_write(genre)
        categories = _categories_of(data)
        result = WordbankMutation()
        changed = False
        for category, raw_word in items:
            word = raw_word.strip()
            if not word:
                result.errors.append("词条不能为空")
                continue
            if category not in categories:
                result.errors.append(f"未知分类「{category}」（可用：{', '.join(categories)}）")
                continue
            words = data[category]
            if word not in words:
                result.missing.append(f"{category}/{word}")
                continue
            # 同一分类里可能有重复词，一次全删掉
            data[category] = [w for w in words if w != word]
            result.deleted += 1
            changed = True
        if changed:
            self._save(genre, data)
        return result

    def import_words(
        self,
        genre: str,
        text: str,
        default_category: str = "themes",
    ) -> WordbankImportReport:
        """导入词条（粘贴文本）。

        解析失败的行**逐行报告原因**；同分类里已有的词算重复（跳过）。

        :raises WordbankValidationError: ``default_category`` 不在该板块的分类里
        """
        data = _load_for_write(genre)
        categories = _categories_of(data)
        # ⚠️ 2026-10-29 评审：以前不校验 default_category，
        #    板块里没有这个分类时 → `data[item.category]` KeyError → 500。
        #    现在提前拦下来 → 422（前端能显示原因）。
        if default_category not in categories:
            raise WordbankValidationError(
                f"Category {default_category!r} not found in genre {genre!r}; "
                f"available: {categories}"
            )
        parsed = parse_import_text(
            text, default_category=default_category, valid_categories=categories
        )

        report = WordbankImportReport(
            duplicates=parsed.duplicates,
            failed=len(parsed.issues),
            errors=[issue.describe() for issue in parsed.issues],
        )
        changed = False
        for item in parsed.words:
            words = data.get(item.category)
            if not isinstance(words, list):
                # 兜底：解析出的分类不在当前板块的 YAML 里（正常走不到，
                # 因为 parse_import_text 已用 valid_categories 过滤过）。
                # 真到了这里也不能让它变成 KeyError → 500。
                report.errors.append(
                    f"第 {item.line_no} 行「{item.word}」：分类「{item.category}」不存在"
                )
                report.failed += 1
                continue
            if item.word in words:
                report.duplicates += 1
                continue
            words.append(item.word)
            report.added += 1
            report.by_category[item.category] = report.by_category.get(item.category, 0) + 1
            changed = True
        if changed:
            self._save(genre, data)
        return report

    # ===== 内部工具 =====
    def _save(self, genre: str, data: dict[str, Any]) -> None:
        """落盘（备份 → 原子写）并让缓存失效。

        缓存失效是**必须的**：词库带 ``@cache``，
        不清的话刚导入的词立刻随机不出来（用户会以为"导入没生效"）。
        """
        path = _write_target(genre)
        backup = write_wordbank(path, data)
        _load_genre_cached.cache_clear()
        logger.info("Wordbank {} saved (backup: {})", genre, backup)

    @staticmethod
    def clear_cache() -> None:
        """测试用：清掉 lru_cache。"""
        _load_genre_cached.cache_clear()


def _categories_of(data: dict[str, Any]) -> list[str]:
    """取出词库 dict 里的分类名（排除 ``name``，只保留 list 型）。"""
    return [k for k, v in data.items() if k != "name" and isinstance(v, list)]


def _load_for_write(genre: str) -> dict[str, Any]:
    """读取**用于修改**的词库数据。

    写目标是用户可写目录；打包态下用户还没存过副本时，
    用内置副本做种子（否则会把用户原有词全部丢掉）。
    """
    target = _write_target(genre)
    if target.is_file():
        return load_wordbank_file(target)
    bundled = _bundled_dir() / f"{genre}.yaml"
    if bundled.is_file():
        return load_wordbank_file(bundled)
    raise WordbankNotFoundError(genre)
