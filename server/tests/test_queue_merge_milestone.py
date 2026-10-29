"""``merge_queue_events_milestone_ordered`` 的单元测试（2026-10-25 新增）。

背景
----
旧实现 :func:`merge_queue_events_ordered` 是"队列 1 消费完才消费队列 2"——
**后面版本的内容事件会憋在队列里**，等前一个版本彻底结束才一次性涌出。

2026-10-25 真机实测（MiniMax-M3.1-Flash，"生成 3 个剧情"）::

    [39.80s] delta index=1 ...
    [45.89s] delta index=1 ...
    [46.10s] delta index=2 ...    ← 几十块同一毫秒全到
    [46.10s] delta index=2 ...

用户反馈的原话是"生成的时候像是先生成但不输出，阻塞到一整个剧情生成完毕
后才一口气很快地流式输出"—— **这就是那次"一口气"的直接来源**。

新实现：内容事件实时透传，只有 ``version_done`` 这类里程碑保序。
本文件锁住这个行为。
"""

from __future__ import annotations

import asyncio

import pytest

from src.core.queue_merge import merge_queue_events_milestone_ordered


@pytest.mark.asyncio
async def test_content_events_are_not_held_back_by_slower_sibling():
    """快队列的内容事件**不能**等慢队列结束（这就是"一口气输出"的成因）。"""
    q1: asyncio.Queue = asyncio.Queue()
    q2: asyncio.Queue = asyncio.Queue()

    async def slow() -> None:
        await asyncio.sleep(0.2)
        await q1.put({"event": "delta", "index": 1, "text": "A"})
        await q1.put({"event": "version_done", "index": 1})
        await q1.put(None)

    async def fast() -> None:
        await asyncio.sleep(0.02)
        await q2.put({"event": "delta", "index": 2, "text": "B"})
        await q2.put({"event": "version_done", "index": 2})
        await q2.put(None)

    tasks = [asyncio.create_task(slow()), asyncio.create_task(fast())]
    seen: list[dict] = []
    async for ev in merge_queue_events_milestone_ordered([q1, q2]):
        seen.append(ev)
        if len(seen) == 1:
            # 第一条必须是快队列的 delta —— 旧实现这里会是慢队列的
            assert ev == {"event": "delta", "index": 2, "text": "B"}, (
                "快队列的内容被慢队列憋住了 —— 这就是用户说的'先生成但不输出，憋到最后才一口气输出'"
            )
    await asyncio.gather(*tasks)

    # 里程碑仍然保序
    done_idx = [e["index"] for e in seen if e["event"] == "version_done"]
    assert done_idx == [1, 2]


@pytest.mark.asyncio
async def test_milestones_are_emitted_in_index_order_even_when_out_of_order():
    """乱序到达的 version_done 会被缓冲，等前面的完成后再按序吐出。"""
    q1: asyncio.Queue = asyncio.Queue()
    q2: asyncio.Queue = asyncio.Queue()

    async def slow() -> None:
        await asyncio.sleep(0.2)
        await q1.put({"event": "version_done", "index": 1})
        await q1.put(None)

    async def fast() -> None:
        await asyncio.sleep(0.02)
        await q2.put({"event": "version_done", "index": 2})
        await q2.put(None)

    tasks = [asyncio.create_task(slow()), asyncio.create_task(fast())]
    seen: list[dict] = []
    async for ev in merge_queue_events_milestone_ordered([q1, q2]):
        seen.append(ev)
    await asyncio.gather(*tasks)

    done_idx = [e["index"] for e in seen if e["event"] == "version_done"]
    assert done_idx == [1, 2], "里程碑必须按 index 排序（出场顺序 A→B→C）"


@pytest.mark.asyncio
async def test_buffered_milestones_are_flushed_when_stream_ends():
    """流结束时，缓冲里没轮到的里程碑必须被吐出去（不能永远卡住）。"""
    q1: asyncio.Queue = asyncio.Queue()

    async def only_version2() -> None:
        await q1.put({"event": "version_done", "index": 2})
        await q1.put(None)

    task = asyncio.create_task(only_version2())
    seen: list[dict] = []
    async for ev in merge_queue_events_milestone_ordered([q1]):
        seen.append(ev)
    await task

    assert [e["index"] for e in seen] == [2], "缓冲的里程碑必须在流结束时被吐出"


@pytest.mark.asyncio
async def test_non_milestone_events_pass_through_untouched():
    """非里程碑事件（thinking / delta / version_start）原样透传。"""
    q1: asyncio.Queue = asyncio.Queue()

    async def producer() -> None:
        await q1.put({"event": "version_start", "index": 1})
        await q1.put({"event": "thinking", "index": 1, "text": "想想"})
        await q1.put({"event": "delta", "index": 1, "text": "正文"})
        await q1.put(None)

    task = asyncio.create_task(producer())
    seen: list[dict] = []
    async for ev in merge_queue_events_milestone_ordered([q1]):
        seen.append(ev)
    await task

    assert [e["event"] for e in seen] == ["version_start", "thinking", "delta"]


@pytest.mark.asyncio
async def test_milestone_without_index_passes_through():
    """没有 index 的里程碑事件直接透传，不参与排序（不能被吞掉）。"""
    q1: asyncio.Queue = asyncio.Queue()

    async def producer() -> None:
        await q1.put({"event": "version_done"})
        await q1.put(None)

    task = asyncio.create_task(producer())
    seen: list[dict] = []
    async for ev in merge_queue_events_milestone_ordered([q1]):
        seen.append(ev)
    await task

    assert seen == [{"event": "version_done"}]


@pytest.mark.asyncio
async def test_failed_version_does_not_block_later_milestones():
    """版本 1 失败时，版本 2/3 的完成事件**不能**被压到流结束才吐。

    失败的生产者发的是 ``error`` 事件（不会发 ``version_done``）。
    早先的实现只把 ``version_done`` 当里程碑，于是保序指针卡在版本 1：
    版本 2/3 的完成事件一直缓冲着，用户看到"另外两张卡明明写完了却一直转圈"。
    """
    q1: asyncio.Queue = asyncio.Queue()
    q2: asyncio.Queue = asyncio.Queue()
    q3: asyncio.Queue = asyncio.Queue()

    async def failed() -> None:
        await asyncio.sleep(0.02)
        await q1.put({"event": "error", "index": 1, "message": "模型炸了"})
        await q1.put(None)

    async def ok2() -> None:
        await asyncio.sleep(0.04)
        await q2.put({"event": "version_done", "index": 2})
        await q2.put(None)

    async def ok3() -> None:
        await asyncio.sleep(0.06)
        await q3.put({"event": "version_done", "index": 3})
        await q3.put(None)

    tasks = [asyncio.create_task(f()) for f in (failed, ok2, ok3)]
    seen: list[dict] = []
    async for ev in merge_queue_events_milestone_ordered([q1, q2, q3]):
        seen.append(ev)
    await asyncio.gather(*tasks)

    # 版本 2/3 的完成事件必须在流结束前就已经吐出来（而不是被压到最后）
    done_idx = [e["index"] for e in seen if e["event"] == "version_done"]
    assert done_idx == [2, 3], f"版本 2/3 的完成事件被压到流末了：{seen}"


@pytest.mark.asyncio
async def test_error_event_still_reaches_the_consumer():
    """error 事件参与保序，但它本身**必须**原样透传给前端（不能被吞）。"""
    q1: asyncio.Queue = asyncio.Queue()

    async def producer() -> None:
        await q1.put({"event": "error", "index": 1, "message": "boom"})
        await q1.put(None)

    task = asyncio.create_task(producer())
    seen: list[dict] = []
    async for ev in merge_queue_events_milestone_ordered([q1]):
        seen.append(ev)
    await task

    assert seen == [{"event": "error", "index": 1, "message": "boom"}]


@pytest.mark.asyncio
async def test_terminal_events_can_be_configured():
    """``terminal_events`` 可以覆盖默认的 error 集合。"""
    q1: asyncio.Queue = asyncio.Queue()
    q2: asyncio.Queue = asyncio.Queue()

    async def failed() -> None:
        await asyncio.sleep(0.02)
        await q1.put({"event": "error", "index": 1, "message": "boom"})
        await q1.put(None)

    async def ok2() -> None:
        await asyncio.sleep(0.04)
        await q2.put({"event": "version_done", "index": 2})
        await q2.put(None)

    tasks = [asyncio.create_task(failed()), asyncio.create_task(ok2())]
    seen: list[dict] = []
    # 不把 error 当终态 → 版本 2 的里程碑会被压到流末（这正是"覆盖默认"的语义）
    async for ev in merge_queue_events_milestone_ordered([q1, q2], terminal_events=()):
        seen.append(ev)
    await asyncio.gather(*tasks)

    # 事件都到了，但 version_done 是最后才吐的
    assert [e["event"] for e in seen] == ["error", "version_done"]
