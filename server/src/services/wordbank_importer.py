"""种子词导入文本解析（纯逻辑，无 IO）。

支持的写法
----------
1. **换行分隔** —— 每行一个词。
2. **分隔符** —— 逗号 ``,`` / 中文逗号 ``，`` / 顿号 ``、`` / 分号 ``;`` ``；``
   / 竖线 ``|`` / 制表符。空格**不**当分隔符（英文词可能带空格）。
3. **分类前缀** —— ``分类:词条`` 或 ``分类：词条``：

   - 前缀可以用英文 key（``themes``）或中文别名（``主题`` / ``题材`` …）
   - 前缀出现在行首 → 该行**所有**词都归这个分类
   - 前缀出现在某个词前面 → 只有那个词归这个分类
   - 前缀认不出来 → **整行报错**（不静默丢弃）
4. **注释** —— 以 ``#`` 或 ``//`` 开头的行忽略。

失败处理
--------
解析不了的行**逐行报告原因**（行号 + 原文 + 原因），
不让整批导入静默丢词。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

__all__ = [
    "CATEGORY_ALIASES",
    "ParsedWord",
    "ParseIssue",
    "ParseResult",
    "parse_import_text",
    "resolve_category",
]

# 分类 key → 中文标签（前端展示用；这里给出英文 key → 中文别名的映射）
CATEGORY_LABELS: dict[str, str] = {
    "themes": "主题",
    "characters": "人物",
    "plots": "情节",
    "scenes": "场景",
    "items": "物品",
}

# 别名 → 规范分类 key。键统一小写（匹配时会把输入转小写）。
CATEGORY_ALIASES: dict[str, str] = {
    # 英文
    "themes": "themes",
    "theme": "themes",
    "characters": "characters",
    "character": "characters",
    "plots": "plots",
    "plot": "plots",
    "scenes": "scenes",
    "scene": "scenes",
    "items": "items",
    "item": "items",
    # 中文
    "主题": "themes",
    "主题词": "themes",
    "题材": "themes",
    "人物": "characters",
    "人物卡": "characters",
    "角色": "characters",
    "情节": "plots",
    "剧情": "plots",
    "桥段": "plots",
    "场景": "scenes",
    "环境": "scenes",
    "物品": "items",
    "道具": "items",
    "法宝": "items",
}

# 词条最长长度（超了大概率是误粘了一整段话）
MAX_WORD_LENGTH = 60

# 分隔符（不含换行 —— 换行在切行时处理）
_DELIMITER_RE = re.compile(r"[,，、;；|\t]+")

# 行首分类前缀：`分类:词条` / `分类：词条`
# 前缀里**不允许**出现分隔符 —— 否则 "逆袭,瞎写:词" 会被整行当成前缀行。
_LEADING_PREFIX_RE = re.compile(r"^(?P<prefix>[^:：,，、;；|\t]{1,20})[:：]\s*(?P<rest>.*)$")

# 词条自身的分类前缀（出现在分隔符之后）
_TOKEN_PREFIX_RE = re.compile(r"^(?P<prefix>[^:：]{1,20})[:：]\s*(?P<rest>.+)$")


@dataclass(frozen=True)
class ParsedWord:
    """解析出来的一条词（分类 + 文本 + 所在行号）。"""

    category: str
    word: str
    line_no: int


@dataclass(frozen=True)
class ParseIssue:
    """一行解析失败的原因。"""

    line_no: int
    raw: str
    reason: str

    def describe(self) -> str:
        """人类可读的一行描述（前端直接展示）。"""
        return f"第 {self.line_no} 行「{self.raw}」：{self.reason}"


@dataclass
class ParseResult:
    """一次解析的结果。"""

    words: list[ParsedWord] = field(default_factory=list)
    issues: list[ParseIssue] = field(default_factory=list)
    duplicates: int = 0
    """批次内重复（同一个分类里同一个词出现多次）的条数。"""


def resolve_category(raw: str, valid_categories: list[str] | None = None) -> str | None:
    """把用户写的分类前缀解析成规范分类 key。

    :param raw: 前缀原文（``themes`` / ``主题`` / ``THEMES``）
    :param valid_categories: 当前板块实际有的分类；给了就只认这几个（+ 别名）
    :return: 规范分类 key；认不出来返回 None
    """
    key = raw.strip().lower()
    if not key:
        return None
    if valid_categories is not None and key in valid_categories:
        return key
    mapped = CATEGORY_ALIASES.get(key)
    if mapped is None:
        return None
    if valid_categories is not None and mapped not in valid_categories:
        return None
    return mapped


def _strip_comment(line: str) -> str:
    """去掉整行注释（``#`` / ``//`` 开头）。"""
    stripped = line.strip()
    if stripped.startswith("#") or stripped.startswith("//"):
        return ""
    return stripped


def parse_import_text(
    text: str,
    default_category: str = "themes",
    valid_categories: list[str] | None = None,
) -> ParseResult:
    """解析导入文本，返回词条 + 失败行。

    :param text: 用户粘贴 / 上传的原始文本
    :param default_category: 没写分类前缀的词归到哪个分类
    :param valid_categories: 当前板块实际有的分类（决定前缀能不能被识别）
    """
    result = ParseResult()
    seen: set[tuple[str, str]] = set()

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = _strip_comment(raw_line)
        if not line:
            continue

        # 行首分类前缀（作用于整行）
        line_category: str | None = None
        body = line
        lead = _LEADING_PREFIX_RE.match(line)
        if lead:
            prefix = lead.group("prefix").strip()
            resolved = resolve_category(prefix, valid_categories)
            if resolved is None:
                result.issues.append(
                    ParseIssue(
                        line_no=line_no,
                        raw=raw_line.strip(),
                        reason=f"无法识别的分类「{prefix}」",
                    )
                )
                continue
            line_category = resolved
            body = lead.group("rest")

        for token in _DELIMITER_RE.split(body):
            token = token.strip()
            if not token:
                continue

            # 词条自带分类前缀（覆盖行首前缀）
            category = line_category or default_category
            token_prefix = _TOKEN_PREFIX_RE.match(token)
            if token_prefix:
                prefix = token_prefix.group("prefix").strip()
                resolved = resolve_category(prefix, valid_categories)
                if resolved is None:
                    result.issues.append(
                        ParseIssue(
                            line_no=line_no,
                            raw=raw_line.strip(),
                            reason=f"无法识别的分类「{prefix}」",
                        )
                    )
                    continue
                category = resolved
                token = token_prefix.group("rest").strip()

            if not token:
                result.issues.append(
                    ParseIssue(line_no=line_no, raw=raw_line.strip(), reason="词条为空")
                )
                continue
            if len(token) > MAX_WORD_LENGTH:
                result.issues.append(
                    ParseIssue(
                        line_no=line_no,
                        raw=raw_line.strip(),
                        reason=f"词条过长（{len(token)} 字，上限 {MAX_WORD_LENGTH}）",
                    )
                )
                continue

            key = (category, token)
            if key in seen:
                result.duplicates += 1
                continue
            seen.add(key)
            result.words.append(ParsedWord(category=category, word=token, line_no=line_no))

    return result
