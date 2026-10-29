"""词库管理（新增 / 修改 / 删除 / 导入）测试 —— 需求6。

覆盖：
- GET /wordbanks/{genre}/all-words 返回全部词条
- POST /wordbanks/{genre}/words 新增（单个 / 批量 / 重复 / 未知分类）
- PATCH /wordbanks/{genre}/words 修改（改一个字）
- DELETE /wordbanks/{genre}/words 删除（单个 / 批量 / 不存在）
- POST /wordbanks/{genre}/import 导入解析
    （换行 / 逗号 / 分类前缀 / 去重 / 失败行报告）
- POST /wordbanks/{genre}/import-file 文件导入（原始 body + 大小上限）
- **板块隔离**：改修仙不影响都市
- **缓存失效**：写完立刻能随机取到新词
- 备份：每次写盘前留一份旧文件
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.services.wordbank_service import (
    WordbankNotFoundError,
    WordbankService,
    WordbankValidationError,
)

XIUXIAN_YAML = """name: 修仙
themes:
- 灵气
- 飞升
characters:
- 少年
- 师尊
plots:
- 退婚
scenes:
- 山门
items:
- 飞剑
"""

DUSHI_YAML = """name: 都市
themes:
- 逆袭
- 草根
characters:
- 总裁
plots:
- 打脸
scenes:
- 写字楼
items:
- 车钥匙
"""


@pytest.fixture
def bank(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """把词库目录指向 tmp_path，并放入两个板块。

    用环境变量 ``BOOK_SOUL_WORDBANK_DIR`` 隔离，而不是 patch 模块常量 ——
    conftest 的 ``temp_db`` 会把 ``src.*`` 从 sys.modules 里删掉重建，
    patch 某个模块副本对其它副本（API 层用的那份）不生效，
    反而会把**开发者真实的词库文件**改了。
    环境变量是进程级的，所有副本都认。
    """
    root = tmp_path / "wordbanks"
    root.mkdir()
    (root / "xiuxian.yaml").write_text(XIUXIAN_YAML, encoding="utf-8")
    (root / "dushi.yaml").write_text(DUSHI_YAML, encoding="utf-8")

    monkeypatch.setenv("BOOK_SOUL_WORDBANK_DIR", str(root))
    _clear_caches()
    yield root
    _clear_caches()


def _clear_caches() -> None:
    """清掉所有模块副本的词库缓存（``src.*`` 会被 conftest 重建，可能有多份）。"""
    import sys

    for name, module in list(sys.modules.items()):
        if name != "src.services.wordbank_service" or module is None:
            continue
        module.WordbankService.clear_cache()  # type: ignore[attr-defined]


@pytest.fixture
def service(bank: Path) -> WordbankService:
    """词库 service（依赖 bank fixture 做目录隔离）。"""
    return WordbankService()


@pytest.fixture
def client(bank: Path) -> TestClient:
    """FastAPI 测试客户端。"""
    from src.main import app

    return TestClient(app)


# ===== GET all-words =====


def test_get_all_words_returns_every_category(client: TestClient) -> None:
    """管理弹窗要一次看到该板块的全部词（按分类分组）。"""
    resp = client.get("/wordbanks/xiuxian/all-words")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "xiuxian"
    assert body["name"] == "修仙"
    assert body["categories"] == ["themes", "characters", "plots", "scenes", "items"]
    assert body["words"]["themes"] == ["灵气", "飞升"]
    assert body["words"]["items"] == ["飞剑"]
    assert body["counts"]["themes"] == 2


def test_get_all_words_unknown_genre_404(client: TestClient) -> None:
    resp = client.get("/wordbanks/not_a_genre/all-words")
    assert resp.status_code == 404


# ===== 新增 =====


def test_add_word_persists_to_yaml(service: WordbankService, bank: Path) -> None:
    result = service.add_words("xiuxian", [("themes", "顿悟")])
    assert result.added == 1
    assert result.errors == []
    text = (bank / "xiuxian.yaml").read_text(encoding="utf-8")
    assert "顿悟" in text
    assert service.get_all_words("xiuxian")["themes"] == ["灵气", "飞升", "顿悟"]


def test_add_words_batch_and_duplicate(service: WordbankService) -> None:
    """批量新增 + 重复词跳过（重复计数，不报错）。"""
    result = service.add_words(
        "xiuxian",
        [("themes", "顿悟"), ("themes", "灵气"), ("characters", "师姐")],
    )
    assert result.added == 2
    assert result.duplicates == 1
    assert service.get_all_words("xiuxian")["characters"] == ["少年", "师尊", "师姐"]


def test_add_words_unknown_category_reports_error(service: WordbankService) -> None:
    """未知分类要报出来，但不影响其它词。"""
    result = service.add_words("xiuxian", [("no_such", "词"), ("themes", "顿悟")])
    assert result.added == 1
    assert len(result.errors) == 1
    assert "no_such" in result.errors[0]


def test_add_words_unknown_genre_raises(service: WordbankService) -> None:
    with pytest.raises(WordbankNotFoundError):
        service.add_words("not_a_genre", [("themes", "词")])


def test_api_add_words(client: TestClient) -> None:
    resp = client.post(
        "/wordbanks/xiuxian/words", json={"items": [{"category": "themes", "word": "顿悟"}]}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["added"] == 1
    assert body["errors"] == []
    again = client.get("/wordbanks/xiuxian/all-words").json()
    assert "顿悟" in again["words"]["themes"]


def test_api_add_words_unknown_genre_404(client: TestClient) -> None:
    resp = client.post(
        "/wordbanks/not_a_genre/words", json={"items": [{"category": "themes", "word": "词"}]}
    )
    assert resp.status_code == 404


def test_api_add_words_unknown_category_reports_error(client: TestClient) -> None:
    resp = client.post(
        "/wordbanks/xiuxian/words",
        json={"items": [{"category": "no_such", "word": "词"}, {"category": "themes", "word": ""}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["added"] == 0
    assert len(body["errors"]) == 2


# ===== 修改 =====


def test_update_word_replaces_in_place(service: WordbankService) -> None:
    """改一个字：位置不变，词变了。"""
    result = service.update_word("xiuxian", "themes", "灵气", "真气")
    assert result.updated == 1
    assert service.get_all_words("xiuxian")["themes"] == ["真气", "飞升"]


def test_update_word_missing_raises_not_found(service: WordbankService) -> None:
    with pytest.raises(WordbankNotFoundError):
        service.update_word("xiuxian", "themes", "不存在", "新词")


def test_update_word_unknown_category_raises(service: WordbankService) -> None:
    with pytest.raises(WordbankValidationError):
        service.update_word("xiuxian", "no_such", "灵气", "真气")


def test_update_word_duplicate_target_raises(service: WordbankService) -> None:
    """改成该分类里已有的词 → 拒绝（否则会造出重复词）。"""
    with pytest.raises(WordbankValidationError):
        service.update_word("xiuxian", "themes", "灵气", "飞升")


def test_api_patch_word(client: TestClient) -> None:
    resp = client.patch(
        "/wordbanks/xiuxian/words",
        json={"category": "themes", "old": "灵气", "new": "真气"},
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 1
    assert "真气" in client.get("/wordbanks/xiuxian/all-words").json()["words"]["themes"]


def test_api_patch_missing_word_404(client: TestClient) -> None:
    resp = client.patch(
        "/wordbanks/xiuxian/words",
        json={"category": "themes", "old": "不存在", "new": "真气"},
    )
    assert resp.status_code == 404


def test_api_patch_unknown_genre_404(client: TestClient) -> None:
    resp = client.patch(
        "/wordbanks/not_a_genre/words",
        json={"category": "themes", "old": "灵气", "new": "真气"},
    )
    assert resp.status_code == 404


def test_api_patch_unknown_category_422(client: TestClient) -> None:
    resp = client.patch(
        "/wordbanks/xiuxian/words",
        json={"category": "no_such", "old": "灵气", "new": "真气"},
    )
    assert resp.status_code == 422


def test_api_patch_duplicate_target_422(client: TestClient) -> None:
    resp = client.patch(
        "/wordbanks/xiuxian/words",
        json={"category": "themes", "old": "灵气", "new": "飞升"},
    )
    assert resp.status_code == 422


# ===== 删除 =====


def test_delete_word(service: WordbankService) -> None:
    result = service.delete_words("xiuxian", [("themes", "灵气")])
    assert result.deleted == 1
    assert service.get_all_words("xiuxian")["themes"] == ["飞升"]


def test_delete_words_batch(service: WordbankService) -> None:
    result = service.delete_words(
        "xiuxian",
        [("themes", "灵气"), ("themes", "飞升"), ("characters", "少年")],
    )
    assert result.deleted == 3
    words = service.get_all_words("xiuxian")
    assert words["themes"] == []
    assert words["characters"] == ["师尊"]


def test_delete_missing_word_reported(service: WordbankService) -> None:
    result = service.delete_words("xiuxian", [("themes", "不存在")])
    assert result.deleted == 0
    assert result.missing == ["themes/不存在"]


def test_api_delete_words_batch(client: TestClient) -> None:
    resp = client.request(
        "DELETE",
        "/wordbanks/xiuxian/words",
        json={
            "items": [{"category": "themes", "word": "灵气"}, {"category": "items", "word": "飞剑"}]
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted"] == 2
    words = client.get("/wordbanks/xiuxian/all-words").json()["words"]
    assert words["themes"] == ["飞升"]
    assert words["items"] == []


def test_api_delete_words_unknown_genre_404(client: TestClient) -> None:
    resp = client.request(
        "DELETE",
        "/wordbanks/not_a_genre/words",
        json={"items": [{"category": "themes", "word": "灵气"}]},
    )
    assert resp.status_code == 404


# ===== 导入 =====


def test_import_newline_separated(service: WordbankService) -> None:
    """换行分隔。"""
    report = service.import_words("xiuxian", "顿悟\n机缘\n", default_category="themes")
    assert report.added == 2
    assert report.failed == 0
    assert service.get_all_words("xiuxian")["themes"] == ["灵气", "飞升", "顿悟", "机缘"]


def test_import_comma_separated(service: WordbankService) -> None:
    """逗号 / 顿号 / 中文逗号 分隔。"""
    report = service.import_words("xiuxian", "顿悟机缘，筑基、结丹", default_category="themes")
    assert report.added == 3
    assert service.get_all_words("xiuxian")["themes"][-3:] == ["顿悟机缘", "筑基", "结丹"]


def test_import_with_category_prefix(service: WordbankService) -> None:
    """``分类:词条`` 前缀（英文 key 与中文别名都认）。"""
    report = service.import_words(
        "xiuxian",
        "themes:顿悟\n人物：师姐\ncharacters:师弟",
        default_category="themes",
    )
    assert report.added == 3
    assert report.failed == 0
    words = service.get_all_words("xiuxian")
    assert words["themes"] == ["灵气", "飞升", "顿悟"]
    assert words["characters"] == ["少年", "师尊", "师姐", "师弟"]


def test_import_deduplicates(service: WordbankService) -> None:
    """批次内重复 + 与已有词重复，都算重复（不新增）。"""
    report = service.import_words("xiuxian", "顿悟\n顿悟\n灵气", default_category="themes")
    assert report.added == 1
    assert report.duplicates == 2
    assert service.get_all_words("xiuxian")["themes"] == ["灵气", "飞升", "顿悟"]


def test_import_reports_failed_lines(service: WordbankService) -> None:
    """解析失败的行要逐行报告原因，不能静默丢弃。"""
    report = service.import_words(
        "xiuxian", "顿悟\n未知分类:词条\n\n# 注释行", default_category="themes"
    )
    assert report.added == 1
    assert report.failed == 1
    assert len(report.errors) == 1
    assert "第 2 行" in report.errors[0]
    assert "未知分类" in report.errors[0]


def test_import_by_category_counts(service: WordbankService) -> None:
    report = service.import_words(
        "xiuxian",
        "themes:顿悟\ncharacters:师姐",
        default_category="themes",
    )
    assert report.by_category == {"themes": 1, "characters": 1}


def test_api_import_text(client: TestClient) -> None:
    resp = client.post(
        "/wordbanks/xiuxian/import",
        json={"text": "顿悟\n人物:师姐", "default_category": "themes"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["added"] == 2
    assert body["failed"] == 0


def test_api_import_unknown_genre_404(client: TestClient) -> None:
    resp = client.post("/wordbanks/not_a_genre/import", json={"text": "词"})
    assert resp.status_code == 404


def test_api_import_file_unknown_genre_404(client: TestClient) -> None:
    resp = client.post("/wordbanks/not_a_genre/import-file", content="词".encode())
    assert resp.status_code == 404


def test_api_import_file(client: TestClient) -> None:
    """文件导入：前端把文件内容当原始 body 发过来。"""
    resp = client.post(
        "/wordbanks/xiuxian/import-file",
        content="顿悟\n机缘".encode(),
        headers={"content-type": "text/plain; charset=utf-8"},
    )
    assert resp.status_code == 200
    assert resp.json()["added"] == 2


def test_api_import_file_too_large(client: TestClient) -> None:
    """超过 1 MiB → 413（不无限读进内存）。"""
    payload = ("词" * 600_000).encode("utf-8")
    resp = client.post(
        "/wordbanks/xiuxian/import-file",
        content=payload,
        headers={"content-type": "text/plain; charset=utf-8"},
    )
    assert resp.status_code == 413


def test_api_import_file_not_utf8(client: TestClient) -> None:
    """非 UTF-8 文件 → 422（报清楚原因）。"""
    resp = client.post(
        "/wordbanks/xiuxian/import-file",
        content=b"\xff\xfe\x00bad",
        headers={"content-type": "application/octet-stream"},
    )
    assert resp.status_code == 422


# ===== 板块隔离 =====


def test_updating_xiuxian_does_not_touch_dushi(service: WordbankService, bank: Path) -> None:
    """改修仙不能动都市。"""
    service.update_word("xiuxian", "themes", "灵气", "真气")
    dushi_text = (bank / "dushi.yaml").read_text(encoding="utf-8")
    assert "真气" not in dushi_text
    assert service.get_all_words("dushi")["themes"] == ["逆袭", "草根"]


def test_deleting_in_one_genre_does_not_touch_other(service: WordbankService) -> None:
    service.delete_words("dushi", [("themes", "逆袭")])
    assert service.get_all_words("xiuxian")["themes"] == ["灵气", "飞升"]
    assert service.get_all_words("dushi")["themes"] == ["草根"]


def test_import_only_writes_target_genre(service: WordbankService, bank: Path) -> None:
    service.import_words("xiuxian", "顿悟", default_category="themes")
    dushi_text = (bank / "dushi.yaml").read_text(encoding="utf-8")
    assert "顿悟" not in dushi_text


# ===== 缓存失效 =====


def test_write_invalidates_cache_new_word_is_samplable(service: WordbankService) -> None:
    """写完立刻能随机取到新词（``@cache`` 必须被清掉）。"""
    service.get_random_words("xiuxian", "themes", n=10)
    service.add_words("xiuxian", [("themes", "顿悟")])
    words = service.get_random_words("xiuxian", "themes", n=100)
    assert "顿悟" in words


def test_import_invalidates_cache_new_word_is_samplable(service: WordbankService) -> None:
    service.get_random_words("xiuxian", "themes", n=10)
    service.import_words("xiuxian", "顿悟", default_category="themes")
    words = service.get_random_words("xiuxian", "themes", n=100)
    assert "顿悟" in words


def test_delete_invalidates_cache_word_gone(service: WordbankService) -> None:
    service.get_random_words("xiuxian", "themes", n=10)
    service.delete_words("xiuxian", [("themes", "灵气")])
    words = service.get_random_words("xiuxian", "themes", n=100)
    assert "灵气" not in words


# ===== 备份 =====


def test_write_creates_backup_before_overwrite(service: WordbankService, bank: Path) -> None:
    """每次写盘前把旧文件备份到 ``.backup/``。"""
    service.add_words("xiuxian", [("themes", "顿悟")])
    backups = sorted((bank / ".backup").glob("xiuxian-*.yaml"))
    assert len(backups) == 1
    # 备份里是**旧内容**（还没有"顿悟"）
    assert "顿悟" not in backups[0].read_text(encoding="utf-8")
    assert "灵气" in backups[0].read_text(encoding="utf-8")


def test_write_leaves_no_temp_files(service: WordbankService, bank: Path) -> None:
    """原子写：临时文件用完即删（不留 ``.tmp`` 残骸）。"""
    service.add_words("xiuxian", [("themes", "顿悟")])
    assert list(bank.glob("*.tmp")) == []


def test_written_yaml_is_valid(service: WordbankService, bank: Path) -> None:
    """写出来的 YAML 仍然能被正常解析（结构没被写坏）。"""
    import yaml

    service.add_words("xiuxian", [("themes", "顿悟")])
    data = yaml.safe_load((bank / "xiuxian.yaml").read_text(encoding="utf-8"))
    assert data["name"] == "修仙"
    assert data["themes"] == ["灵气", "飞升", "顿悟"]
    # name 仍在第一个 key（顺序不能乱）
    assert list(data.keys())[0] == "name"
