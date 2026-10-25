"""大纲规模参数化（2026-10-25 新增）。

为什么要有这个模块
------------------
旧的大纲 prompt 把规模**写死**在模板里："3-5 卷（每卷 6-10 章），总章节 20-40"。
作者在想法里写"全书 100 章、每章 3000 字、完本 30 万字"，模型面对
"硬性要求"和"作者想法"两个冲突的指令，只能挑一个 —— 多数情况下按 prompt 走，
作者的要求被**静默丢弃**（用户实测反馈："添加想法录入后大纲生成部分未按照要求进行生成"）。

现在规模变成**显式参数**：

====================  ==========================================
字段                   含义
====================  ==========================================
``total_chapters``     全书总章数
``chapters_per_volume`` 每卷章数（目标值）
``words_per_chapter``   每章字数
====================  ==========================================

并提供 :func:`parse_scale_from_text`，从作者的自然语言里把这三个数抽出来
（"100 章"、"30 万字"、"每章 3000 字"、"每卷 10 章"）。

分卷规则
--------
``total_chapters`` 不一定能被 ``chapters_per_volume`` 整除。为了让
"章数总和严格等于用户要求的总数"这条硬指标成立，本模块按**均分 + 前几卷多一章**
分配（见 :attr:`OutlineScale.volume_chapter_counts`）：

- 100 章 / 每卷 10 章 → 10 卷 × 10 章
- 25 章 / 每卷 10 章 → 3 卷（10 + 10 + 5）
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "OutlineScale",
    "DEFAULT_TOTAL_CHAPTERS",
    "DEFAULT_CHAPTERS_PER_VOLUME",
    "DEFAULT_WORDS_PER_CHAPTER",
    "MIN_TOTAL_CHAPTERS",
    "MAX_TOTAL_CHAPTERS",
    "MIN_CHAPTERS_PER_VOLUME",
    "MAX_CHAPTERS_PER_VOLUME",
    "MIN_WORDS_PER_CHAPTER",
    "MAX_WORDS_PER_CHAPTER",
    "normalize_scale",
    "parse_scale_from_text",
]

# ===== 默认值与取值范围 =====

DEFAULT_TOTAL_CHAPTERS = 30
DEFAULT_CHAPTERS_PER_VOLUME = 10
DEFAULT_WORDS_PER_CHAPTER = 3000

MIN_TOTAL_CHAPTERS = 1
MAX_TOTAL_CHAPTERS = 500
MIN_CHAPTERS_PER_VOLUME = 1
MAX_CHAPTERS_PER_VOLUME = 100
MIN_WORDS_PER_CHAPTER = 500
MAX_WORDS_PER_CHAPTER = 20_000


def _clamp(value: int, lo: int, hi: int) -> int:
    """把数值夹到 ``[lo, hi]`` 区间。"""
    return max(lo, min(hi, value))


@dataclass(frozen=True)
class OutlineScale:
    """大纲规模（三元组）。

    用 ``frozen=True`` + 不可变语义：规模一旦定下来就不该被就地改，
    需要变更就重新构造（避免"生成到一半规模变了"这种诡异状态）。
    """

    total_chapters: int
    chapters_per_volume: int
    words_per_chapter: int

    @property
    def volume_count(self) -> int:
        """总卷数（向上取整）。"""
        cpv = max(1, self.chapters_per_volume)
        return max(1, -(-self.total_chapters // cpv))

    @property
    def volume_chapter_counts(self) -> list[int]:
        """各卷章数；总和**严格等于** ``total_chapters``。

        均分，余数分给前几卷（每卷最多多 1 章）。
        """
        n = self.volume_count
        base, rem = divmod(self.total_chapters, n)
        return [base + 1] * rem + [base] * (n - rem)

    @property
    def total_words(self) -> int:
        """全书预计总字数。"""
        return self.total_chapters * self.words_per_chapter

    @property
    def volume_plan(self) -> str:
        """给 prompt 用的分卷计划文本。

        例："第1卷 10 章；第2卷 10 章；第3卷 10 章"
        """
        return "；".join(
            f"第{i}卷 {c} 章" for i, c in enumerate(self.volume_chapter_counts, start=1)
        )


def normalize_scale(
    total_chapters: int | None = None,
    chapters_per_volume: int | None = None,
    words_per_chapter: int | None = None,
) -> OutlineScale:
    """把任意（可能为 None / 越界）的规模参数规整成合法值。

    - ``total_chapters`` 缺省 :data:`DEFAULT_TOTAL_CHAPTERS`
    - ``chapters_per_volume`` 缺省 :data:`DEFAULT_CHAPTERS_PER_VOLUME`；
      且不能超过总章数（否则会算出 0 章的卷）
    - ``words_per_chapter`` 缺省 :data:`DEFAULT_WORDS_PER_CHAPTER`
    """
    total = _clamp(
        int(total_chapters) if total_chapters is not None else DEFAULT_TOTAL_CHAPTERS,
        MIN_TOTAL_CHAPTERS,
        MAX_TOTAL_CHAPTERS,
    )
    cpv = (
        int(chapters_per_volume) if chapters_per_volume is not None else DEFAULT_CHAPTERS_PER_VOLUME
    )
    cpv = _clamp(cpv, MIN_CHAPTERS_PER_VOLUME, MAX_CHAPTERS_PER_VOLUME)
    cpv = min(cpv, total)
    wpc = int(words_per_chapter) if words_per_chapter is not None else DEFAULT_WORDS_PER_CHAPTER
    wpc = _clamp(wpc, MIN_WORDS_PER_CHAPTER, MAX_WORDS_PER_CHAPTER)
    return OutlineScale(
        total_chapters=total,
        chapters_per_volume=cpv,
        words_per_chapter=wpc,
    )


# ===== 自然语言解析 =====

_CN_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000, "万": 10000}


def _cn_to_int(text: str) -> int | None:
    """把中文数字转成整数（支持到"万"级，如"一百二十三"→123、"三十"→30）。

    解析不了返回 None（调用方会退回正则里的阿拉伯数字分支）。
    """
    if not text:
        return None
    if not all(ch in _CN_DIGITS or ch in _CN_UNITS for ch in text):
        return None
    total = 0
    section = 0
    number = 0
    for ch in text:
        if ch in _CN_DIGITS:
            number = _CN_DIGITS[ch]
        else:
            unit = _CN_UNITS[ch]
            if unit == 10000:
                section = (section + number) * unit
                total += section
                section = 0
            else:
                if number == 0:
                    number = 1  # "十五" → 15
                section += number * unit
            number = 0
    return total + section + number


_NUM = r"(?:\d+(?:\.\d+)?|[零〇一二两三四五六七八九十百千万]+)"

# 每章字数："每章3000字" / "每回 3 千字" / "3000字/章"
_RE_PER_CHAPTER_WORDS = re.compile(
    rf"(?:每章|每回|单章)\s*({_NUM})\s*[kK千]?\s*字"
    rf"|({_NUM})\s*[kK千]?\s*字\s*[／/]\s*[章回]"
)
# 每卷章数："每卷10章"
_RE_PER_VOLUME_CHAPTERS = re.compile(rf"每卷\s*({_NUM})\s*[章回]")
# 总章数："共100章" / "全书 100 章" / "100章"
_RE_TOTAL_CHAPTERS = re.compile(rf"({_NUM})\s*[章回]")
# 总字数："30万字" / "30w字" / "共30万字"
_RE_TOTAL_WORDS_WAN = re.compile(rf"({_NUM})\s*[wW万]\s*字")
_RE_TOTAL_WORDS_QIAN = re.compile(rf"({_NUM})\s*[kK千]\s*字")
_RE_TOTAL_WORDS_PLAIN = re.compile(rf"(?:共|全书|总字|总计|完本|整本|大约|约)\s*({_NUM})\s*字")

# 出现在数字**紧前面**的这些词，说明这个数字**不是**总量
# （"每卷 10 章"里的 10 是每卷章数，"第 10 章"里的 10 是章节序号）
_NEGATIVE_SUFFIXES = (
    "每卷",
    "每回",
    "每章",
    "每",
    "第",
    "单",
    "上",
    "下",
    "另",
    "其余",
)


def _to_number(raw: str) -> float | None:
    """把正则捕获到的数字文本转成 float（支持中文数字）。"""
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        pass
    cn = _cn_to_int(raw)
    return float(cn) if cn is not None else None


def _is_negative_context(text: str, start: int) -> bool:
    """判断 ``text[start:]`` 处的数字是不是"每卷 10 章"这类**局部**数字。"""
    prefix = text[max(0, start - 4) : start]
    for token in _NEGATIVE_SUFFIXES:
        if prefix.endswith(token):
            return True
    # 前一个字符是数字的一部分（"100章"里的 "00"）→ 不是新数字
    if prefix and prefix[-1].isdigit():
        return True
    return False


def parse_scale_from_text(text: str) -> OutlineScale | None:
    """从作者的自然语言想法里解析规模参数。

    支持的写法（可组合出现）：

    - 总章数：``共100章`` / ``全书100章`` / ``100章``
    - 每卷章数：``每卷10章``
    - 每章字数：``每章3000字`` / ``3000字/章``
    - 总字数：``30万字`` / ``30w字`` / ``共30万字``

    :param text: 作者想法原文（多个想法拼成的多行文本）
    :return: 解析出的规模；**一个数都没识别出来时返回 None**
        （调用方应保留默认值，而不是把规模改成 0）
    """
    if not text or not text.strip():
        return None

    per_chapter_words: int | None = None
    m = _RE_PER_CHAPTER_WORDS.search(text)
    if m:
        raw = m.group(1) or m.group(2)
        value = _to_number(raw)
        if value:
            mult = 1000 if re.search(r"[kK千]", m.group(0)) else 1
            per_chapter_words = int(value * mult)

    per_volume_chapters: int | None = None
    m = _RE_PER_VOLUME_CHAPTERS.search(text)
    if m:
        value = _to_number(m.group(1))
        if value:
            per_volume_chapters = int(value)

    total_chapters: int | None = None
    for m in _RE_TOTAL_CHAPTERS.finditer(text):
        if _is_negative_context(text, m.start(1)):
            continue
        value = _to_number(m.group(1))
        if value:
            total_chapters = int(value)
            break

    total_words: int | None = None
    for pattern, mult in (
        (_RE_TOTAL_WORDS_WAN, 10000),
        (_RE_TOTAL_WORDS_QIAN, 1000),
        (_RE_TOTAL_WORDS_PLAIN, 1),
    ):
        m = pattern.search(text)
        if m:
            value = _to_number(m.group(1))
            if value:
                total_words = int(value * mult)
                break

    # 只有总字数 → 按每章字数折算章数
    if total_chapters is None and total_words is not None:
        wpc = per_chapter_words or DEFAULT_WORDS_PER_CHAPTER
        total_chapters = max(1, round(total_words / wpc))
    # 只有总章数 + 总字数 → 反推每章字数
    if per_chapter_words is None and total_words is not None and total_chapters:
        per_chapter_words = max(1, round(total_words / total_chapters))

    if total_chapters is None and per_volume_chapters is None and per_chapter_words is None:
        return None

    scale = normalize_scale(
        total_chapters=total_chapters,
        chapters_per_volume=per_volume_chapters,
        words_per_chapter=per_chapter_words,
    )
    return scale
