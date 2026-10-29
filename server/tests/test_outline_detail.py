"""大纲阶段二「分批 / 重试 / 兜底」单元测试（2026-10-29 新增）。

背景：用户实测（图7）大纲生成后 CH01~CH14 **只有标题**、没有概要。
根因：一卷 20 章一次调用，推理模型思考把正文额度吃光 → "返回空内容" → 整卷只剩标题。

覆盖：
- ``split_batches``：按章数切批，顺序不变
- ``detail_budget``：有下限有上限
- ``align_detail``：与批次对齐、缺失补占位
- ``placeholder_chapter``：诚实标注"待细化"，不编剧情
"""

from __future__ import annotations

from src.services.outline_detail import (
    DETAIL_BATCH_SIZE,
    DETAIL_MAX_BUDGET,
    align_detail,
    chapters_skeleton_text,
    detail_budget,
    placeholder_chapter,
    split_batches,
)


def _chapters(n: int) -> list[dict[str, object]]:
    return [{"title": f"第{i + 1}章"} for i in range(n)]


# ===== split_batches =====


def test_split_batches_keeps_order_and_size() -> None:
    batches = split_batches(_chapters(20))
    assert len(batches) == 4  # 20 章 / 每批 6 章 → 4 批
    assert all(len(b) <= DETAIL_BATCH_SIZE for b in batches)
    flat = [c["title"] for b in batches for c in b]
    assert flat == [f"第{i + 1}章" for i in range(20)]


def test_split_batches_exact_multiple() -> None:
    batches = split_batches(_chapters(12))
    assert [len(b) for b in batches] == [6, 6]


def test_split_batches_empty() -> None:
    assert split_batches([]) == []


def test_split_batches_size_guard() -> None:
    """size 传 0 / 负数不能死循环。"""
    batches = split_batches(_chapters(3), size=0)
    assert len(batches) == 3


# ===== detail_budget =====


def test_detail_budget_has_floor() -> None:
    """章很少时也不能给太小的预算 —— 推理模型思考会吃掉一部分。"""
    assert detail_budget(1) >= 4000
    assert detail_budget(6) >= 4000


def test_detail_budget_grows_with_chapters() -> None:
    assert detail_budget(6) < detail_budget(12)


def test_detail_budget_capped() -> None:
    assert detail_budget(1000) <= DETAIL_MAX_BUDGET


# ===== chapters_skeleton_text =====


def test_chapters_skeleton_text_numbered_from_one() -> None:
    text = chapters_skeleton_text(_chapters(3))
    assert text.splitlines() == ["1. 第1章", "2. 第2章", "3. 第3章"]


# ===== placeholder_chapter =====


def test_placeholder_is_marked_pending() -> None:
    """占位概要必须诚实标注"待细化"，不能编剧情。"""
    out = placeholder_chapter({"title": "剑冢深处"}, {"name": "第一卷", "summary": "初入宗门"})
    assert "待细化" in out["summary"]
    assert "剑冢深处" in out["summary"]
    assert "初入宗门" in out["summary"]
    assert out["key_events"] == []


def test_placeholder_without_volume_context() -> None:
    out = placeholder_chapter({"title": "无题"}, {})
    assert "待细化" in out["summary"]
    assert "无题" in out["summary"]


# ===== align_detail =====


def test_align_detail_matches_batch_length_and_order() -> None:
    batch = _chapters(3)
    detail = [
        {"summary": "概要一", "key_events": ["事件一"]},
        {"summary": "概要二", "key_events": []},
        {"summary": "概要三", "key_events": ["事件三"]},
    ]
    out = align_detail(detail, batch, {"name": "第一卷"})
    assert len(out) == 3
    assert out[0]["summary"] == "概要一"
    assert out[2]["key_events"] == ["事件三"]


def test_align_detail_fills_missing_with_placeholder() -> None:
    """模型少给 → 用占位补齐，**绝不**留空章节。"""
    batch = _chapters(3)
    detail = [{"summary": "概要一", "key_events": []}]
    out = align_detail(detail, batch, {"name": "第一卷"})
    assert len(out) == 3
    assert out[0]["summary"] == "概要一"
    assert "待细化" in out[1]["summary"]
    assert "待细化" in out[2]["summary"]


def test_align_detail_ignores_extra_items() -> None:
    batch = _chapters(2)
    detail = [
        {"summary": "一", "key_events": []},
        {"summary": "二", "key_events": []},
        {"summary": "三", "key_events": []},
    ]
    out = align_detail(detail, batch, {})
    assert len(out) == 2


def test_align_detail_handles_non_dict_items() -> None:
    batch = _chapters(2)
    out = align_detail(["不是字典", None], batch, {"name": "第一卷"})
    assert len(out) == 2
    assert "待细化" in out[0]["summary"]


def test_align_detail_keeps_events_when_summary_missing() -> None:
    batch = _chapters(1)
    out = align_detail([{"summary": "", "key_events": ["事件"]}], batch, {})
    assert out[0]["key_events"] == ["事件"]
    assert out[0]["summary"] == ""
