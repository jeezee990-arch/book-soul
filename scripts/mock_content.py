"""Mock provider 的**内容选择器**：按请求里的提示词特征挑对应的模拟输出。

为什么需要它：本地 mock provider（见 :mod:`perf_probe`）默认只吐无意义的
``"字" * N``。这对"测流式链路"够用，但**大纲**这一步后端要 ``json.loads``
解析出 ``volumes``，解析不了就抛 ``JSON parse failed`` → 向导退回第 2 步，
UI 根本走不到第 3 步。

所以这里按提示词里的特征串分流：

============  ==================================  ==========================
请求特征      场景                                 返回
============  ==================================  ==========================
basic_info    人物卡（generate_card）               YAML 块
严格 JSON 列表  抽取人物（extract_characters）        JSON 数组
volumes       大纲（outline_complete）               JSON 对象（volumes+chapters）
简要剧情大纲   剧情（plot_generation）                200-400 字剧情（3 个版本轮换）
（都没有）     其它未知场景                          "字" * N（封顶，见 perf_probe）
============  ==================================  ==========================

用法见 ``scripts/mock_provider.py``（没有 API Key 也能把"开新书"三步走完）。
"""

from __future__ import annotations

import json

# ===== 大纲（complete 模式：volumes → chapters → key_events）====================

OUTLINE_JSON: dict = {
    "volumes": [
        {
            "name": "第一卷 雨夜旧案",
            "summary": (
                "主角林晚在雨夜接到一桩看似普通的坠楼案，却在死者手机里发现自己十年前的合影。"
                "她重返当年的小城，与旧友陈默、刑警老周一起顺藤摸瓜，逐步揭开当年那场"
                "「意外」的真相。本卷以她的身世秘密为轴心，从被动卷入到主动追查，"
                "完成从旁观者到当事人的转变。"
            ),
            "chapters": [
                {
                    "title": "第一章 雨夜来电",
                    "summary": (
                        "凌晨两点的雨敲着窗，林晚被一阵急促的铃声惊醒。来电的是陌生号码，"
                        "对方只说了一句「你当年也在场」，随即挂断。第二天新闻里出现一则"
                        "坠楼案的简短通报，死者手机里那张合影让林晚彻夜难眠。"
                    ),
                    "key_events": ["深夜陌生来电", "新闻中的坠楼通报", "手机里的旧合影"],
                },
                {
                    "title": "第二章 旧城重逢",
                    "summary": (
                        "林晚回到记忆里的小城，在老宅阁楼找到一只封存的铁盒。"
                        "陈默的出现打破了她刻意维持的平静，他带来一个更坏的消息："
                        "当年经手那份笔录的刑警老周，三个月前刚刚病故。"
                    ),
                    "key_events": ["阁楼铁盒", "陈默重逢", "老周病故的消息"],
                },
                {
                    "title": "第三章 笔录的空白",
                    "summary": (
                        "林晚翻出当年的笔录复印件，发现关键时间点整整空了两页。"
                        "她找到退休的档案员，对方欲言又止，只留下一句「签收的人不是你父亲」。"
                        "第一个真正的线索浮出水面。"
                    ),
                    "key_events": ["笔录缺失两页", "档案员的欲言又止", "签名另有其人"],
                },
                {
                    "title": "第四章 旁观者",
                    "summary": (
                        "陈默劝林晚收手，理由是当年那个圈子早已散尽。她却从旧照片里"
                        "认出一张陌生面孔——那人如今就在本市，且身居要职。"
                        "她决定不再只是旁观。"
                    ),
                    "key_events": ["陈默劝退", "照片中的陌生面孔", "主角决定追查"],
                },
            ],
        },
        {
            "name": "第二卷 沉默的证人",
            "summary": (
                "追查深入，林晚发现当年还有第三个人在場——一个被所有人当成"
                "「不重要」的角色。她开始逐一接触旧案的幸存者，每接近一步，"
                "身边就越不安全。本卷节奏收紧，人物关系网逐渐收紧，主角第一次"
                "为真相付出实质代价。"
            ),
            "chapters": [
                {
                    "title": "第五章 第三个人",
                    "summary": (
                        "林晚从一份出勤表里发现第三个名字：赵屿。当年所有材料里"
                        "都没有他，像是被人为抹去。她翻出当年的合照，终于对上号。"
                    ),
                    "key_events": ["出勤表上的第三个名字", "赵屿浮出水面", "合照对号入座"],
                },
                {
                    "title": "第六章 书店夜谈",
                    "summary": (
                        "赵屿开了一家旧书店，拒绝见面。林晚在雨夜的店外等到打烊，"
                        "换来一句「你父亲是替人顶罪的」。这句话把她十年的愧疚彻底翻了过来。"
                    ),
                    "key_events": ["旧书店", "雨夜等候", "顶罪的真相"],
                },
                {
                    "title": "第七章 代价",
                    "summary": (
                        "有人撬开了林晚家的门，母亲在混乱中受了伤。林晚第一次感到"
                        "退路正在消失，但她也意识到，对方急了——这说明她查对了方向。"
                    ),
                    "key_events": ["家中闯入", "母亲受伤", "对方狗急跳墙"],
                },
                {
                    "title": "第八章 录音",
                    "summary": (
                        "赵屿交出一盘老式磁带。录音里传出的对话让林晚彻夜难眠，"
                        "也让她意识到，十年来的「意外」其实是一场精心安排的沉默。"
                    ),
                    "key_events": ["旧磁带", "关键录音", "沉默背后的安排"],
                },
            ],
        },
        {
            "name": "第三卷 雨停之前",
            "summary": (
                "林晚与陈默联手，将当年参与者的证词一一固定。她选择把证据"
                "公开而不是私下解决，哪怕这意味着亲手打碎父亲的清白想象。"
                "本卷完成情感清算，并给出一个不那么圆满、但足够诚实的结局。"
            ),
            "chapters": [
                {
                    "title": "第九章 逐一固定",
                    "summary": (
                        "林晚用十二天走访了六位当事人，把每个人的记忆固定成文字。"
                        "过程枯燥而重复，却像在给一条裂缝一寸寸打上钉子。"
                    ),
                    "key_events": ["六位当事人", "逐份笔录", "证据链成形"],
                },
                {
                    "title": "第十章 见面",
                    "summary": (
                        "当年那位如今身居要职的人提出见面，条件是林晚交出证据。"
                        "她拒绝了，并带上了录音笔。这是一场早就布好的局。"
                    ),
                    "key_events": ["对方的条件", "林晚拒绝", "录音笔"],
                },
                {
                    "title": "第十一章 公开",
                    "summary": (
                        "林晚把一切交给媒体，也交给警方。父亲的清白无法还原，"
                        "但至少那些被改写的十分钟不再属于谎言。"
                    ),
                    "key_events": ["证据公开", "警方介入", "真相落定"],
                },
                {
                    "title": "第十二章 雨停",
                    "summary": (
                        "雨停了。林晚回到老宅，把铁盒重新锁回去。新的案件已经在路上，"
                        "但这一次，她选择先让母亲好好吃一顿饭。"
                    ),
                    "key_events": ["雨停", "老宅", "新的开始"],
                },
            ],
        },
    ],
    "overall_theme": (
        "一个人如何在十年后重新学会相信自己的判断——以及迟到的正义究竟能不能还给活着的人一个交代。"
    ),
}

# ===== 人物抽取（extract_characters 的输出）===================================

CHARACTERS_JSON: list[dict[str, str]] = [
    {"name": "林晚", "role": "主角"},
    {"name": "陈默", "role": "主角团"},
    {"name": "赵屿", "role": "其他"},
    {"name": "周正", "role": "反派"},
]

# ===== 人物卡（generate_card 的输出，YAML 块）==================================

CARD_YAML: str = """```yaml
basic_info: |
  三十四岁，市局刑侦支队现任技术员，办过十一起积案。
  常年穿灰色风衣，右手虎口有一道旧刀疤。
  习惯把工牌反着挂，从不解释原因。

personality: |
  关键词：执拗、克制、护短。
  她相信证据胜过直觉，却又总被直觉推着往前走。
  对家人近乎偏执的保护，对外人一贯保持礼貌的距离感。

habits: |
  1. 思考时会把笔帽咬在嘴里，直到想起来自己在做什么。
  2. 走进任何一个房间先看出口和窗户。
  3. 说「我知道」的时候，多半已经知道结局。

thinking: |
  先找最不可能的那条路径，再回头验证所有人默认的前提。
  一旦认定方向就不会回头，宁可把所有人都当嫌疑人，也不肯在证据不足时下结论。

relationships: |
  与陈默是十年旧识，两人在警校同届，分手后仍是彼此最信任的人。
  与父亲之间隔着一份被改写的笔录，她至今不肯原谅他替人顶罪的选择。

growth_arc: |
  从只敢独自查案，到学会把后背交给别人，也从「为父亲翻案」走向「为所有被改写的人翻案」。
```"""


# ===== 剧情（plot_generation 的输出）============================================
#
# 为什么不能直接吐 "字" * N：
#   后端 ``OutlineGenerationRequest.plot_summary`` 上限 5000 字，剧情摘要超了
#   → 下一步的大纲接口直接 422 → 向导卡在第 3 步（这正是 2026-10-24 走查踩到的）。
#   真实 prompt 要求的是 200-400 字，所以 mock 也按这个量级给。
#
# 为什么给 3 个版本：
#   真实场景是"同 prompt、不同采样 → 3 个不同走向"。mock 是无状态的，
#   用一个轮换计数器近似，让三张剧情卡看起来不一样。

PLOT_VARIANTS: list[str] = [
    (
        "{genre}背景下的一场旧案把三个人的命运绑在了一起。主角{lead}是市局刑侦支队的技术员，"
        "执拗、话少、办案时只信证据。她在一桩看似普通的坠楼案现场，捡到一张不该出现的旧合影。"
        "照片背后牵出{keywords}，以及十年前被人为抹掉的那十分钟。"
        "她越靠近真相，越发现自己才是当年那场沉默的当事人。"
        "开场钩子：死者手机里最后一条未发送的消息，收件人正是她父亲。"
    ),
    (
        "{genre}故事里，{lead}是个只想安静做自己的{lead_role}，却被{keywords}推到了台前。"
        "她没有退路，也不打算退。"
        "三天前，她收到一份没有署名的信，信里只有一句话：你当年也在场。"
        "为了查清这句话背后的主使，她不得不重新走进十年前那间封存的屋子，"
        "面对那些以为她早已忘记的人。"
        "开场钩子：屋子里只多了一把椅子，灰尘上却没有任何挪动痕迹。"
    ),
    (
        "{lead}一直以为自己只是路过{genre}的局外人。直到{keywords}把她拖进来，"
        "她才发现自己是这盘棋上最关键的那颗子。"
        "她选择先不揭穿，一边配合对方演下去，一边把证据一条条藏好。"
        "这是她第一次主动走进别人的故事，也第一次不再是自己的主角。"
        "开场钩子：对方在会面时叫出了她的名字 —— 用的是十年前那个没人知道的名字。"
    ),
]

# 三个版本对应的主角设定（轮换，避免三张卡只差一个开头）
PLOT_LEADS: list[tuple[str, str]] = [
    ("林晚", "技术员"),
    ("周叙", "实习医生"),
    ("沈砚", "古董修复师"),
]


def _extract_after(request_body: str, marker: str, fallback: str = "") -> str:
    """取 prompt 里 ``marker`` 之后到行尾的文本（prompt 已在服务端渲染过）。"""
    idx = request_body.find(marker)
    if idx < 0:
        return fallback
    rest = request_body[idx + len(marker) :]
    line = rest.splitlines()[0] if rest.splitlines() else ""
    return line.strip() or fallback


def extract_prompt_text(payload: object) -> str:
    """从**已解析的请求 JSON**里取出 prompt 文本。

    ⚠️ 为什么不能直接拿原始请求体做特征匹配：请求体是 JSON，prompt 里的换行
    是转义的 ``\\n``（两个字符），不是真换行。直接在 JSON 上按行切，会把
    "题材：xxx" 后面的一整条 JSON（包括 ``"temperature":0.8``）当成题材值抠出来。

    所以要先 ``json.loads``，再从 ``messages[*].content`` 里取真文本。
    """
    if not isinstance(payload, dict):
        return ""
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return ""
    parts: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for chunk in content:
                if isinstance(chunk, dict) and isinstance(chunk.get("text"), str):
                    parts.append(chunk["text"])
    return "\n".join(parts)


def pick_content(request_body: str, fallback: str, variant: int = 0) -> str:
    """按 prompt 文本里的特征挑模拟输出。

    :param request_body: **prompt 文本**（用 :func:`extract_prompt_text` 从请求 JSON 取出）
    :param fallback: 兜底内容（"要多少给多少"的未知场景，长度由调用方封顶）
    :param variant: 剧情场景的第几个版本（0 起，用于让 3 张卡内容不同）
    :return: 该场景应该返回的正文
    """
    if "basic_info" in request_body:
        return CARD_YAML
    if "严格 JSON 列表" in request_body:
        return json.dumps(CHARACTERS_JSON, ensure_ascii=False)
    if "volumes" in request_body:
        return json.dumps(OUTLINE_JSON, ensure_ascii=False)
    if "简要剧情大纲" in request_body:
        genre = _extract_after(request_body, "- 题材：", "通用")
        keywords = _extract_after(request_body, "- 灵感词：", "未知线索")
        lead, lead_role = PLOT_LEADS[variant % len(PLOT_LEADS)]
        template = PLOT_VARIANTS[variant % len(PLOT_VARIANTS)]
        return template.format(genre=genre, keywords=keywords, lead=lead, lead_role=lead_role)
    return fallback


__all__ = [
    "CARD_YAML",
    "CHARACTERS_JSON",
    "OUTLINE_JSON",
    "PLOT_VARIANTS",
    "extract_prompt_text",
    "pick_content",
]
