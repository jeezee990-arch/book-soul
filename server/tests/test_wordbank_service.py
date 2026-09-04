"""词库 service 单元测试（Phase 3.1）。

覆盖：
- list_genres 返回 4 个题材（基于 repo 真实 config/wordbanks/）
- get_metadata 返回 categories + counts
- get_metadata 未知题材 → NotFound
- get_random_words 抽样数 + 不重复
- get_random_words n 超出 → 返回全部
- get_random_words 未知分类 → ValidationError
- get_random_words_multi 多类一次拿
- clear_cache 不抛异常
- 路径解析：找不到目录时 list_genres 返回 []
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.services.wordbank_service import (
    WordbankNotFoundError,
    WordbankService,
    WordbankValidationError,
    _list_genre_ids,
    _load_genre,
)


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """每个测试前后清缓存，避免 module-level lru_cache 跨测试影响。"""
    WordbankService.clear_cache()
    yield
    WordbankService.clear_cache()


@pytest.fixture
def service() -> WordbankService:
    return WordbankService()


# ===== 题材列表 =====


def test_list_genre_ids_finds_four_genres() -> None:
    """repo 真实 config/wordbanks/ 下应有 4 个题材。"""
    ids = _list_genre_ids()
    assert set(ids) == {"xiuxian", "dushi", "xuanyi", "yanqing"}


def test_list_genres_returns_four_with_totals(service: WordbankService) -> None:
    genres = service.list_genres()
    assert len(genres) == 4
    by_id = {g["id"]: g for g in genres}
    # 修仙总词数应 >= 800（PROJECT_PLAN 要求）
    assert by_id["xiuxian"]["total"] >= 800
    # 名字来自 YAML 的 name 字段
    assert by_id["xiuxian"]["name"] == "修仙"
    assert by_id["dushi"]["name"] == "都市"
    assert by_id["xuanyi"]["name"] == "悬疑"
    assert by_id["yanqing"]["name"] == "言情"


# ===== 元数据 =====


def test_get_metadata_xiuxian_has_five_categories(service: WordbankService) -> None:
    meta = service.get_metadata("xiuxian")
    assert meta["id"] == "xiuxian"
    assert meta["name"] == "修仙"
    # 5 个分类
    assert set(meta["categories"]) == {"themes", "characters", "plots", "scenes", "items"}
    # counts 与列表长度一致
    for cat in meta["categories"]:
        assert meta["counts"][cat] == len(_load_genre("xiuxian")[cat])


def test_get_metadata_unknown_genre_raises(service: WordbankService) -> None:
    with pytest.raises(WordbankNotFoundError) as exc_info:
        service.get_metadata("not_a_genre")
    assert "not_a_genre" in str(exc_info.value)


# ===== 随机抽样 =====


def test_get_random_words_returns_n_items(service: WordbankService) -> None:
    words = service.get_random_words("xiuxian", "themes", n=10)
    assert isinstance(words, list)
    assert len(words) == 10
    # 全部来自 themes 分类
    all_themes = _load_genre("xiuxian")["themes"]
    for w in words:
        assert w in all_themes


def test_get_random_words_no_duplicates_when_pool_is_unique(service: WordbankService) -> None:
    """当分类内部无重复词时，抽样结果也唯一。

    注意：``random.sample`` 只保证选不重复的下标，不去重 population。
    如果原列表本身有重复词，sample 可能选到相同词。
    这里选一个去重后词数大、明显无重复的分类（xiuxian items 270 词）。
    """
    all_items = _load_genre("xiuxian")["items"]
    assert len(all_items) == len(set(all_items)), "测试前提：items 内部需去重"
    words = service.get_random_words("xiuxian", "items", n=50)
    assert len(words) == 50
    assert len(words) == len(set(words))  # 抽样结果唯一


def test_get_random_words_n_exceeds_pool_returns_all(service: WordbankService) -> None:
    """n 超过分类词数时，random.sample 自动截断到 len(pool)。"""
    all_chars = _load_genre("dushi")["characters"]
    n_huge = len(all_chars) + 100
    words = service.get_random_words("dushi", "characters", n=n_huge)
    assert len(words) == len(all_chars)
    assert set(words) == set(all_chars)


def test_get_random_words_n_zero_raises(service: WordbankService) -> None:
    with pytest.raises(WordbankValidationError):
        service.get_random_words("xiuxian", "themes", n=0)


def test_get_random_words_unknown_category_raises(service: WordbankService) -> None:
    with pytest.raises(WordbankValidationError) as exc_info:
        service.get_random_words("xiuxian", "no_such_category", n=5)
    assert "no_such_category" in str(exc_info.value)


def test_get_random_words_unknown_genre_raises(service: WordbankService) -> None:
    with pytest.raises(WordbankNotFoundError):
        service.get_random_words("unknown", "themes", n=5)


def test_get_random_words_multi_returns_per_category(service: WordbankService) -> None:
    result = service.get_random_words_multi(
        "xuanyi",
        {"themes": 5, "scenes": 3},
    )
    assert set(result.keys()) == {"themes", "scenes"}
    assert len(result["themes"]) == 5
    assert len(result["scenes"]) == 3
    all_themes = _load_genre("xuanyi")["themes"]
    for w in result["themes"]:
        assert w in all_themes


# ===== 缓存 =====


def test_clear_cache_does_not_raise(service: WordbankService) -> None:
    # 先触发一次加载
    service.get_metadata("xiuxian")
    # 再清缓存不应抛
    service.clear_cache()
    # 重新加载仍正常
    meta = service.get_metadata("xiuxian")
    assert meta["name"] == "修仙"


# ===== 数据完整性（YAML 解析保护）=====


def test_load_genre_rejects_non_str_word(tmp_path: Path) -> None:
    """YAML 裸数字（如 ``- 996``）解析成 int，service 层必须拦截。

    修过 BUG：dushi.yaml themes 里有 ``- 996``，5-category 接口返回 list[str | int]
    触发 Pydantic ResponseValidationError → 500。service 层应提前抛
    WordbankValidationError（→ API 层转 422）。

    关键：测试内 ``importlib.reload`` 确保拿到最新 module 对象——
    conftest 的 ``temp_db`` fixture 会卸载 ``src.*`` 子模块，
    测试模块顶部 ``from src.services.wordbank_service import _load_genre``
    拿到的是旧引用；reload 后所有引用同步。
    """
    import importlib

    import src.services.wordbank_service as _ws

    importlib.reload(_ws)

    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text(
        "name: 测试\nthemes:\n  - 灵气\n  - 996\n  - 飞升\n",
        encoding="utf-8",
    )
    _ws._WORDBANK_DIR = tmp_path
    _ws.WordbankService.clear_cache()
    try:
        with pytest.raises(_ws.WordbankValidationError) as exc_info:
            _ws._load_genre("bad")
        assert "must be str" in str(exc_info.value)
        assert "int" in str(exc_info.value)
    finally:
        _ws.WordbankService.clear_cache()


def test_load_genre_accepts_all_str() -> None:
    """回归测试：所有词库现在都是 str，不应抛 ValidationError。"""
    for genre in ("xiuxian", "dushi", "xuanyi", "yanqing"):
        data = _load_genre(genre)
        for cat, words in data.items():
            if cat == "name" or not isinstance(words, list):
                continue
            for w in words:
                assert isinstance(w, str), f"{genre}.{cat} 含非 str: {w!r}"
