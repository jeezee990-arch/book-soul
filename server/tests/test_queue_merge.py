"""多队列合并消费的回归测试（2026-10-23 修的真实挂死 bug）。

背景
----
流式端点（生成 3 个剧情 / 人物卡 / 多版本）用"每个生产者一个队列 +
主协程合并"的方式把事件实时吐给客户端。

原来的实现每轮 ``asyncio.wait(FIRST_COMPLETED)`` 之后把没完成的
``q.get()`` 任务 ``cancel()`` 掉。**这会丢事件** —— put() 已经把事件交给
getter 了，getter 再被 cancel，事件就永远消失。

后果实测（独立版 2026-10-23）：生成 3 个剧情，3 个版本只完成 2 个，
流式端点**死循环挂死**（客户端等到超时）。

本文件的断言：合并器必须收到**全部**事件并**正常结束**（不挂死）。
"""

from __future__ import annotations

import asyncio

import pytest

from src.core.queue_merge import merge_queue_events, merge_queue_events_ordered


@pytest.mark.asyncio
async def test_merge_delivers_all_events_and_terminates():
    """两个生产者各 50 个事件 + 结束哨兵 —— 一个都不能丢，且必须正常结束。"""
    q1: asyncio.Queue = asyncio.Queue()
    q2: asyncio.Queue = asyncio.Queue()

    async def producer(q: asyncio.Queue, tag: str, n: int) -> None:
        for i in range(n):
            await q.put({"tag": tag, "i": i})
        await q.put(None)  # 结束哨兵

    tasks = [
        asyncio.create_task(producer(q1, "a", 50)),
        asyncio.create_task(producer(q2, "b", 50)),
    ]

    received: list[dict] = []

    async def consume() -> None:
        async for ev in merge_queue_events([q1, q2]):
            received.append(ev)

    # 超时保护：旧实现会在这里死循环挂死 → 失败而不是卡住整个测试进程
    await asyncio.wait_for(consume(), timeout=10)
    await asyncio.gather(*tasks, return_exceptions=True)

    assert len(received) == 100
    assert sum(1 for e in received if e["tag"] == "a") == 50
    assert sum(1 for e in received if e["tag"] == "b") == 50


@pytest.mark.asyncio
async def test_merge_sentinel_is_not_yielded():
    """结束哨兵（None）不应该被吐给调用方。"""
    q: asyncio.Queue = asyncio.Queue()

    async def producer() -> None:
        await q.put({"x": 1})
        await q.put(None)

    task = asyncio.create_task(producer())
    received: list = []
    async for ev in merge_queue_events([q]):
        received.append(ev)
    await task
    assert received == [{"x": 1}]


@pytest.mark.asyncio
async def test_merge_terminates_when_producer_puts_sentinel_immediately():
    """生产者立刻放哨兵（没有其他事件）时也要正常结束。"""
    q: asyncio.Queue = asyncio.Queue()
    await q.put(None)
    received: list = []
    async for ev in merge_queue_events([q]):
        received.append(ev)
    assert received == []


@pytest.mark.asyncio
async def test_merge_survives_interleaved_producers():
    """两个生产者交错放事件 —— 顺序不重要，但不能丢、不能挂。"""
    q1: asyncio.Queue = asyncio.Queue()
    q2: asyncio.Queue = asyncio.Queue()

    async def producer(q: asyncio.Queue, tag: str) -> None:
        for i in range(20):
            await q.put({"tag": tag, "i": i})
            await asyncio.sleep(0)
        await q.put(None)

    tasks = [
        asyncio.create_task(producer(q1, "a")),
        asyncio.create_task(producer(q2, "b")),
    ]
    received: list[dict] = []
    async for ev in merge_queue_events([q1, q2]):
        received.append(ev)
    await asyncio.gather(*tasks, return_exceptions=True)
    assert len(received) == 40


# =========================================================================
# 有序合并（2026-10-24）
# =========================================================================


@pytest.mark.asyncio
async def test_ordered_merge_emits_in_queue_order():
    """有序合并：队列 1 的事件必须**全部**先于队列 2。

    "生成 3 个剧情"用这个：用户期望看到 A → B → C 的固定顺序，
    而不是"哪个模型先回就先出哪个"（并行时顺序是随机的）。
    """
    q1: asyncio.Queue = asyncio.Queue()
    q2: asyncio.Queue = asyncio.Queue()
    q3: asyncio.Queue = asyncio.Queue()

    async def producer(q: asyncio.Queue, tag: str, n: int, delay: float) -> None:
        # q3 最快、q1 最慢 —— 如果按到达顺序合并，输出就会是 c,a,b
        await asyncio.sleep(delay)
        for i in range(n):
            await q.put({"tag": tag, "i": i})
        await q.put(None)

    tasks = [
        asyncio.create_task(producer(q1, "a", 3, 0.06)),
        asyncio.create_task(producer(q2, "b", 3, 0.03)),
        asyncio.create_task(producer(q3, "c", 3, 0.0)),
    ]

    received: list[dict] = []
    async for ev in merge_queue_events_ordered([q1, q2, q3]):
        received.append(ev)
    await asyncio.gather(*tasks, return_exceptions=True)

    tags = [e["tag"] for e in received]
    assert tags == ["a", "a", "a", "b", "b", "b", "c", "c", "c"], f"顺序不对：{tags}"


@pytest.mark.asyncio
async def test_ordered_merge_keeps_total_time_parallel():
    """有序合并**不能**让整体变慢：生产者并行跑，总耗时取最大值。

    如果实现退化成"等 A 结束再启动 B"，总耗时会变成三者之和。
    """
    q1: asyncio.Queue = asyncio.Queue()
    q2: asyncio.Queue = asyncio.Queue()

    async def producer(q: asyncio.Queue, tag: str) -> None:
        await asyncio.sleep(0.2)
        await q.put({"tag": tag})
        await q.put(None)

    tasks = [
        asyncio.create_task(producer(q1, "a")),
        asyncio.create_task(producer(q2, "b")),
    ]

    loop = asyncio.get_running_loop()
    t0 = loop.time()
    received: list[dict] = []
    async for ev in merge_queue_events_ordered([q1, q2]):
        received.append(ev)
    elapsed = loop.time() - t0
    await asyncio.gather(*tasks, return_exceptions=True)

    assert [e["tag"] for e in received] == ["a", "b"]
    assert elapsed < 0.35, f"有序合并不该串行化，耗时 {elapsed:.2f}s（串行会 ≥0.4s）"
