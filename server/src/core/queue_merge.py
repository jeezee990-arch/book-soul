"""多队列合并消费（流式端点共用）。

解决什么问题
------------
多个并发生成任务（"生成 3 个剧情"、人物卡、质检多维度）各自往自己的队列里
塞事件，主协程要按**到达顺序**把事件合并吐给客户端。

哨兵约定
--------
每个生产者任务结束时往自己的队列 ``put(None)`` 作为结束哨兵。
本模块消费到哨兵即认为该队列结束（哨兵本身不会 yield 出去）；
所有队列都结束后，事件流结束。

为什么不用「每轮 asyncio.wait + cancel 掉没完成的 get」
--------------------------------------------------------
那种写法功能上没错（asyncio.Queue 对"已交付给 getter 但 getter 被取消"
这种情况是安全的：事件仍留在队列里，下次 get 照样拿得到），但有两个实际问题：

1. **每个事件都要重建一批 task**。一个 3000 字章节按 token 吐字就是几千个
   delta，每次都 create + cancel 一遍 task，纯开销。
2. **"结束"的判定散落在业务代码里**。每个 service 各写一遍
   ``while finished < n`` + 哨兵计数，逻辑重复且容易写错 ——
   2026-10-23 的挂死 bug（``queues[idx]`` 越界 → 哨兵没 put → 死等）
   就是这么来的。

本模块把"每个队列常驻一个 get 任务，谁先完成就处理谁，处理完立刻补一个"
收敛到一处：**get 任务全程不被 cancel**，所以事件不会因为任务取消而丢；
且每个队列只有 1 个 get task 常驻，与事件数量无关。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from typing import Any

__all__ = ["merge_queue_events", "merge_queue_events_ordered"]


async def merge_queue_events(
    queues: Sequence[asyncio.Queue[Any]],
) -> AsyncIterator[Any]:
    """把多个队列合并成一条事件流（按事件实际到达顺序）。

    约定：每个生产者任务结束时往自己的队列 ``put(None)`` 作为结束哨兵。
    本迭代器消费到哨兵时认为该队列结束（哨兵本身不会 yield 出去），
    所有队列都结束后本迭代器结束。

    :param queues: 各生产者的事件队列
    """
    # task -> 它在等哪个队列
    pending: dict[asyncio.Task[asyncio.Queue[Any]], asyncio.Queue[Any]] = {}
    for queue in queues:
        pending[asyncio.create_task(queue.get())] = queue
    remaining = len(queues)

    try:
        while remaining > 0 and pending:
            done, _ = await asyncio.wait(set(pending), return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                payload = task.result()
                queue = pending.pop(task)
                if payload is None:
                    # 该队列的结束哨兵：不再给它挂新的 get
                    remaining -= 1
                    continue
                yield payload
                # 立刻给同一个队列补一个新的 get（不 cancel 其它队列的任务）
                pending[asyncio.create_task(queue.get())] = queue
    finally:
        # 生成器被提前关闭（客户端断开）时清理挂着的 get 任务。
        # 此时已经不再消费事件，cancel 不会造成事件丢失。
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)


async def merge_queue_events_ordered(
    queues: Sequence[asyncio.Queue[Any]],
) -> AsyncIterator[Any]:
    """把多个队列**按顺序**合并成一条事件流：队列 1 消费完，才消费队列 2。

    什么时候用
    ----------
    "生成 3 个剧情"这种**并列展示**的场景：用户期望看到的顺序是
    **A → B → C**，而不是"哪个模型先回就先出哪个"。

    并行调用时哪个先回是随机的 —— 用户会看到 C 先出字、A 还在转圈，
    像是坏了。所以这里改成"按序号排队吐事件"。

    为什么不会让整体变慢
    ------------------
    **生产者依然是并行的**：三个 LLM 调用同时在跑，事件先进各自的队列里
    等着。本函数只是**改变吐事件的顺序**，不改变任何一个调用的开始时间。

    所以总耗时 = max(三个调用的耗时)，和并行乱序时完全一样 ——
    只是屏幕上 A 先动起来。

    约定：每个生产者任务结束时往自己的队列 ``put(None)`` 作为结束哨兵。
    """
    for queue in queues:
        while True:
            payload = await queue.get()
            if payload is None:
                # 该队列的结束哨兵：换下一个队列
                break
            yield payload
