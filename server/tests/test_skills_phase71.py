"""Phase 7.1 剩余 9 个 Skill 测试。"""

from __future__ import annotations

import pytest

# ===== chapter_summarizer =====


@pytest.mark.asyncio
async def test_chapter_summarizer_basic() -> None:
    from src.core.skills import run_skill

    text = "开头内容" + "x" * 300 + "中间内容" + "y" * 300 + "结尾"
    r = await run_skill("chapter_summarizer", text=text, head_chars=50, tail_chars=50)
    assert r.success is True
    assert r.data["summary_chars"] > 0
    assert "开头内容" in r.data["summary"]
    assert "结尾" in r.data["summary"]


@pytest.mark.asyncio
async def test_chapter_summarizer_short_text() -> None:
    from src.core.skills import run_skill

    r = await run_skill("chapter_summarizer", text="短文", head_chars=200, tail_chars=200)
    assert r.success is True


# ===== character_extractor =====


@pytest.mark.asyncio
async def test_character_extractor_basic() -> None:
    from src.core.skills import run_skill

    text = "韩立说道：我要修仙。韩立心想：得努力。韩立望着远方。墨大夫冷笑。"
    r = await run_skill("character_extractor", text=text, top_n=5)
    assert r.success is True
    names = [c["name"] for c in r.data["characters"]]
    assert "韩立" in names


@pytest.mark.asyncio
async def test_character_extractor_empty() -> None:
    from src.core.skills import run_skill

    r = await run_skill("character_extractor", text="")
    assert r.success is True
    assert r.data["characters"] == []


# ===== plot_analyzer =====


@pytest.mark.asyncio
async def test_plot_analyzer_basic() -> None:
    from src.core.skills import run_skill

    text = "他突然转身，发现了危险，决定战斗。最终胜利。"
    r = await run_skill("plot_analyzer", text=text)
    assert r.success is True
    groups = r.data["groups"]
    assert "突转" in groups
    assert "发现" in groups
    assert "决定" in groups
    assert "胜利" in groups


# ===== web_search =====


@pytest.mark.asyncio
async def test_web_search_placeholder() -> None:
    from src.core.skills import run_skill

    r = await run_skill("web_search", query="test")
    assert r.success is False
    assert "未启用" in (r.error or "")


# ===== read_local_file =====


@pytest.mark.asyncio
async def test_read_local_file_success(tmp_path) -> None:
    from src.core.skills import run_skill

    f = tmp_path / "test.md"
    f.write_text("# Hello", encoding="utf-8")
    r = await run_skill("read_local_file", path=str(f))
    assert r.success is True
    assert r.data["content"] == "# Hello"
    assert r.data["size"] == 7


@pytest.mark.asyncio
async def test_read_local_file_disallowed_suffix(tmp_path) -> None:
    from src.core.skills import run_skill

    f = tmp_path / "test.exe"
    f.write_text("x", encoding="utf-8")
    r = await run_skill("read_local_file", path=str(f))
    assert r.success is False
    assert "Disallowed" in (r.error or "")


@pytest.mark.asyncio
async def test_read_local_file_nonexistent() -> None:
    from src.core.skills import run_skill

    r = await run_skill("read_local_file", path="/nope/a.md")
    assert r.success is False


# ===== consistency_checker =====


@pytest.mark.asyncio
async def test_consistency_checker_alias_variation() -> None:
    from src.core.skills import run_skill

    text = "师父说：好好修炼。师傅教我如何御剑。师尊满意地点头。"
    r = await run_skill("consistency_checker", text=text)
    assert r.success is True
    issues = r.data["issues"]
    assert any(i["type"] == "alias_variation" and i["canonical"] == "师父" for i in issues)


@pytest.mark.asyncio
async def test_consistency_checker_clean() -> None:
    from src.core.skills import run_skill

    text = "普通文本，无别名问题。"
    r = await run_skill("consistency_checker", text=text)
    assert r.success is True
    # 没有别名都出现时 issues 为空（除非"普通"恰好命中）
    # "普通" 不在任何 alias
    # 但 "文本" "无" 也不在 alias
    assert r.data["issues"] == [] or not any(
        i["type"] == "alias_variation" for i in r.data["issues"]
    )


# ===== style_analyzer =====


@pytest.mark.asyncio
async def test_style_analyzer_basic() -> None:
    from src.core.skills import run_skill

    text = "这是第一句。这是第二句！这是第三句？他大喊：「什么？」"
    r = await run_skill("style_analyzer", text=text)
    assert r.success is True
    assert r.data["sentence_count"] >= 3
    assert r.data["exclamation_density"] > 0
    assert r.data["dialog_ratio"] > 0


@pytest.mark.asyncio
async def test_style_analyzer_empty() -> None:
    from src.core.skills import run_skill

    r = await run_skill("style_analyzer", text="")
    assert r.success is True
    assert r.data["char_count"] == 0


# ===== pacing_visualizer =====


@pytest.mark.asyncio
async def test_pacing_visualizer_basic() -> None:
    from src.core.skills import run_skill

    text = "段一短。\n\n段二稍长一些内容。\n\n段三。\n\n段四有更多内容更多内容更多内容更多。"
    r = await run_skill("pacing_visualizer", text=text)
    assert r.success is True
    assert r.data["total_segments"] == 4
    assert r.data["max_chars"] > r.data["min_chars"]


# ===== outline_structurer =====


@pytest.mark.asyncio
async def test_outline_structurer_complete() -> None:
    from src.core.skills import run_skill

    text = """
第一卷：开端
第一章 起点
- 主角觉醒
- 拜入宗门
第二章 成长
- 第一次试炼
- 结识伙伴
第二卷：高潮
第一章 决战
- 大战反派
"""
    r = await run_skill("outline_structurer", text=text)
    assert r.success is True
    assert r.data["total_volumes"] == 2
    assert r.data["total_chapters"] == 3


@pytest.mark.asyncio
async def test_outline_structurer_chapter_only() -> None:
    from src.core.skills import run_skill

    text = "第一章 开篇\n- 介绍主角\n第二章 发展\n- 加入战斗"
    r = await run_skill("outline_structurer", text=text)
    assert r.success is True
    assert r.data["total_volumes"] == 0
    assert r.data["total_chapters"] == 2
    assert len(r.data["orphan_chapters"]) == 2


# ===== genre_classifier =====


@pytest.mark.asyncio
async def test_genre_classifier_xianxia() -> None:
    from src.core.skills import run_skill

    text = "韩立修仙，灵气充裕，灵根觉醒，筑基成功，飞升在望。"
    r = await run_skill("genre_classifier", text=text, top_n=2)
    assert r.success is True
    candidates = r.data["candidates"]
    assert candidates[0]["genre"] == "修仙"


@pytest.mark.asyncio
async def test_genre_classifier_dushi() -> None:
    from src.core.skills import run_skill

    text = "他在公司里当总裁，开着豪车，与豪门千金在写字楼相遇。"
    r = await run_skill("genre_classifier", text=text, top_n=2)
    assert r.success is True
    assert r.data["candidates"][0]["genre"] == "都市"


@pytest.mark.asyncio
async def test_genre_classifier_empty() -> None:
    from src.core.skills import run_skill

    r = await run_skill("genre_classifier", text="")
    assert r.success is True
    assert r.data["candidates"] == []


# ===== 总览：所有 11 个 builtin skill 都在 registry =====


def test_all_11_builtin_registered() -> None:
    from src.core.skills import list_skills

    names = {s.name for s in list_skills()}
    expected = {
        "word_counter",
        "sensitive_word",
        "chapter_summarizer",
        "character_extractor",
        "plot_analyzer",
        "web_search",
        "read_local_file",
        "consistency_checker",
        "style_analyzer",
        "pacing_visualizer",
        "outline_structurer",
        "genre_classifier",
    }
    assert names == expected
