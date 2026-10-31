"""正文排版归一化（2026-10-30 新增，用户实测触发）。

用户实测反馈（2026-10-30）
--------------------------
「生成的小说文本多出大量空余字符，没有分段分行，不同人物的对话无法区分」。

真实数据取证（用户库里《骨仙传》第 1 章）
------------------------------------------
原始内容 ``repr``::

    '山\\n\\n门前的\\n\\n铜\\n\\n钟连\\n\\n响三\\n\\n声，雾便从青石\\n\\n阶\\n\\n下退了\\n\\n。\\n\\n...'

统计：``len(content)=5338``，其中 **2024 个字符是 ``\\n``**（1012 组 ``\\n\\n``），
真实正文只有 **3314 字**（Word 统计的 3309 字是对的，界面显示的 5338 是虚高假数字）。

两个叠加的病因
--------------
1. **前端编辑器把流式批次当成段落**（``NovelEditor.flushAppend`` 在**文档末尾**
   ``insertText``，ProseMirror 会**新建一个段落**）。于是每 16ms 一个 flush =
   一个新段落，Tiptap 的 ``getText()`` 又用 ``"\\n\\n"`` 拼块 → 满篇假换行。
2. **模型可能不输出段落**（本次实测：模型输出里**一个换行都没有**），
   纯文本喂给 Tiptap 会被当成 HTML 解析成一个大段落 → 整章挤成一行。

本模块解决第 2 个问题（并为第 1 个问题提供**旧数据修复**所需的能力）：

- :class:`ProseFormatter` —— **增量**排版器：把 LLM 流水正文整理成规范段落。
  - 去掉**汉字之间的多余空格**（模型常见毛病："山 门 前 的"）
  - 模型给的 ``\\n`` / ``\\n\\n`` → 统一成段落分隔
  - 模型不给段落时，**兜底按句末标点自动断段**（每段 30-120 字）
  - 对白收尾后另起一段（多人对话可区分）
- :func:`count_prose_words` —— **真实字数**口径：**非空白字符数**（含中文标点，
  不含空格/换行）—— 与 Word 的「字数」统计一致，也是网文平台的通行口径。

⚠️ 为什么不用 ``len(text)`` 当字数
----------------------------------
``len(text)`` 把换行符、空格全算进去 → 界面显示的字数虚高，
和 Word 统计对不上（用户实测 5338 vs 3309）。字数必须是**读者眼中的字数**。
"""

from __future__ import annotations

import re
from typing import Final

__all__ = [
    "count_prose_words",
    "normalize_whitespace",
    "split_paragraphs",
    "split_consecutive_dialogue",
    "ProseFormatter",
]

# 句末标点 —— 可作为断段点
_SENTENCE_END: Final = "。！？!?…"

# 收尾引号 / 括号 —— 跟在句末标点后面时要和标点一起留在段末
# （中文习惯：`……了。」` 是一句，不能把 `」` 甩到下一段）
#
# ⚠️ 用拼接写法而不是直接写在字符串里 —— 里面含 ASCII 双引号 `"`，
#    直接写会把 Python 字符串提前截断（写出来的源码直接 SyntaxError）。
_CLOSERS: Final = "」』”" + '"' + "）)》〉】"

# 弱断点 —— 只有段落已经过长时才在这里断（避免把长句切碎）
_WEAK_BREAK: Final = "，、；：,;:"

# 对白引号（开 / 闭）
#
# ⚠️ 模型写小说最常用的是**弯引号** “ ”（不是直角引号「」），
#    两种都要认，否则"换人说话"分不开。
_DIALOG_OPEN: Final = "“‘「"
_DIALOG_CLOSE: Final = "”’」"

# 汉字（含扩展 A）与常见中文标点 —— 这些字符之间不该出现空格
_CJK: Final = re.compile(
    r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff"
    r"\u3000-\u303f\uff00-\uffef]"
)

# 单个汉字
_HANZI: Final = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")

# 汉字之间的多余空格（固定宽度的前后查找，Python re 要求 lookbehind 定长）
_CJK_SPACE: Final = re.compile(
    r"(?<=[\u4e00-\u9fff\u3400-\u4dbf\u3000-\u303f\uff00-\uffef])"
    r"[ \t\u3000]+"
    r"(?=[\u4e00-\u9fff\u3400-\u4dbf\u3000-\u303f\uff00-\uffef])"
)


def _is_cjk(ch: str) -> bool:
    """判断字符是否属于"中文语境"（汉字或中文标点）。"""
    return bool(_CJK.match(ch))


def count_prose_words(text: str) -> int:
    """真实字数：**非空白字符数**（含中文标点，不含空格与换行）。

    口径与 Word 的「字数」统计一致，也是网文平台（起点/番茄等）的通行算法。
    - 汉字、中文标点、英文单词、数字：**都算**
    - 空格、制表符、换行符：**不算**

    用户实测对照（2026-10-30，《骨仙传》第 1 章）：
    坏数据 ``len=5338``（含 2024 个换行）→ 本函数算 **3314**，
    而 Word 导出统计是 **3309** —— 一致（差 5 个是 Word 对个别标点的处理差异）。

    :param text: 待统计文本
    :return: 字数
    """
    if not text:
        return 0
    return sum(1 for c in text if not c.isspace())


def normalize_whitespace(text: str) -> str:
    """去掉汉字之间的多余空格（英文单词之间的空格保留）。

    模型经常输出 "山 门 前 的 铜 钟" 这种**汉字被空格拆开**的正文 ——
    读者看到的是"多出大量空余字符"。这里把它们收回去。

    :param text: 原始文本
    :return: 清理后的文本
    """
    if not text:
        return ""
    return _CJK_SPACE.sub("", text)


def split_paragraphs(text: str) -> list[str]:
    """把纯文本按段落切开。

    段落分隔符是空行（``\\n\\n``）；单个 ``\\n`` 也当段落分隔
    （模型有时只给一个换行）。空段会被丢弃。

    :param text: 纯文本
    :return: 段落列表（每段已去首尾空白）
    """
    if not text:
        return []
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    raw = re.split(r"\n\s*\n|\n", normalized)
    return [p.strip() for p in raw if p.strip()]


# 连续对白之间的切分点：引号收尾 后紧跟 引号开头
_DIALOG_SPLIT: Final = re.compile(r"(?<=[。！？][”’」])(?=[“‘「])")


def split_consecutive_dialogue(text: str) -> str:
    """在**保留原有段落边界**的前提下，把挤在一起的连续对白拆开。

    与 :class:`ProseFormatter` 的区别：那个是生成时**从零排版**（段落边界由
    兜底断段规则决定）；这个是给**已经排好版的正文**做二次修整 ——
    段落划分不动，只把 ``“甲？”“乙。”`` 这种换人说话拆成独立段落。

    用于修复「历史章节的段落划分是对的，但连续对白还挤在一段」的情况。

    :param text: 纯文本正文
    :return: 拆分后的正文（段落之间用空行分隔）
    """
    if not text:
        return ""
    out: list[str] = []
    for para in split_paragraphs(text):
        pieces = [p.strip() for p in _DIALOG_SPLIT.split(para) if p.strip()]
        out.extend(pieces)
    return "\n\n".join(out)


class ProseFormatter:
    """**增量**正文排版器：把 LLM 流水正文整理成规范段落。

    用法::

        fmt = ProseFormatter()
        for delta in llm_stream:
            out = fmt.feed(delta)   # 可能返回 ""（还在等断句）
            if out:
                yield out
        tail = fmt.finish()        # 收尾
        if tail:
            yield tail

    规则
    ----
    1. **汉字之间的空格删掉**，英文单词之间的空格保留。
    2. 模型给的 ``\\n`` → 段落分隔（统一成 ``\\n\\n``）。
    3. **兜底断段**：段落达到 ``min_para_chars`` 字后，遇到句末标点
       （``。！？…``）就断段 —— 模型不输出段落时靠这条兜底。
    4. 段落超过 ``max_para_chars`` 字时，允许在逗号/分号处断（弱断点）。
    5. 对白以 ``”`` / ``」`` 收尾且段落已够长时，另起一段（多人对话可区分）。
    6. **连续对白强制断段**：上一句对白以引号收尾、紧接着又出现引号开头
       （``“甲？”“乙。”``）→ 直接断成两段。这是"换人说话"最可靠的信号，
       不受段落长度限制。

    :param min_para_chars: 段落最短字数（低于它不断段，避免碎成一行行）
    :param max_para_chars: 段落最长字数（超过它允许在弱断点断开）
    """

    def __init__(
        self,
        *,
        min_para_chars: int = 30,
        max_para_chars: int = 120,
    ) -> None:
        self._min = max(1, min_para_chars)
        self._max = max(self._min, max_para_chars)
        self._pending = ""  # 待定的段末候选（如 "。" 或 "。」"）
        self._para_len = 0  # 当前段落已确定输出的字数
        self._pending_space = False  # 有一个空格等着看下一个字符再决定去留
        self._last_char = ""  # 上一个非空白字符（判断汉字间空格用）
        self._prev_nonspace = ""  # 上一个非空白**输入**字符（判断连续对白用）
        self._prev2_nonspace = ""  # 上上个非空白**输入**字符（判断对白是否收尾）

    # ===== 对外接口 =====

    def feed(self, delta: str) -> str:
        """喂入一段增量文本，返回**已排版好**的增量输出。

        :param delta: LLM 原始增量
        :return: 排版后的增量（可能为空串 —— 说明还在等断句）
        """
        if not delta:
            return ""
        out: list[str] = []
        for ch in delta:
            piece = self._feed_char(ch)
            if piece:
                out.append(piece)
        return "".join(out)

    def finish(self) -> str:
        """流结束时收尾（把待定的段末/空格冲掉）。

        :return: 收尾输出
        """
        out = ""
        if self._pending:
            # 收尾不再断段（不能留尾部空行）
            out += self._emit(self._pending)
            self._pending = ""
        # 结尾的空格一律丢掉
        self._pending_space = False
        return out

    # ===== 内部 =====

    def _push_prev(self, ch: str) -> None:
        """记录最近的非空白输入字符（保留前一个，供对白判据用）。

        :param ch: 刚读到的非空白字符
        """
        self._prev2_nonspace = self._prev_nonspace
        self._prev_nonspace = ch

    def _feed_char(self, ch: str) -> str:
        # 1) 换行 —— 模型给的段落分隔
        if ch == "\n" or ch == "\r":
            out = ""
            if self._pending:
                out += self._emit_sentence_end(self._pending)
                self._pending = ""
            # 段落末尾的空格丢掉
            self._pending_space = False
            if self._para_len > 0:
                self._para_len = 0
                out += "\n\n"
            return out

        # 2) 空白 —— 可能是汉字间的多余空格，先挂起
        if ch in " \t\u3000":
            if self._pending:
                # 挂起的段末候选后面跟空格 → 先把候选定下来
                flushed = self._emit(self._pending)
                self._pending = ""
                self._pending_space = True
                return flushed
            self._pending_space = True
            return ""

        # 3) 普通字符
        prefix = self._resolve_space(ch)

        if self._pending:
            if ch in _SENTENCE_END:
                self._pending += ch
                self._push_prev(ch)
                return prefix
            if ch in _CLOSERS:
                self._pending += ch
                self._push_prev(ch)
                return prefix
            # 候选后面跟了别的字符 → 段落到此结束
            out = prefix + self._emit_sentence_end(self._pending)
            self._pending = ""
            if _starts_new_dialogue(ch, self._prev_nonspace, self._prev2_nonspace):
                self._para_len = 0
                out += "\n\n"
            out += self._emit(ch)
            self._last_char = ch
            self._push_prev(ch)
            return out

        if ch in _SENTENCE_END:
            self._pending = ch
            self._last_char = ch
            self._push_prev(ch)
            return prefix

        if ch in _CLOSERS:
            # 没有挂起的句末标点，但可能刚好结束一段对白
            out = prefix + self._emit(ch)
            self._last_char = ch
            self._push_prev(ch)
            if self._para_len >= self._min:
                self._para_len = 0
                out += "\n\n"
            return out

        # 连续对白 —— 上一句以引号收尾，紧接着又冒出引号开头：
        # 这是**换人说话**，必须另起一段，否则不同人物的对话糊在一起。
        #
        # 例：`“沈砚？”“沈家村，沈砚。”“供药旧户？”“是。”`
        #      → 四段，每句对白独立成段
        #
        # 判据用「上一个非空白**输入**字符」而不是「上一个输出字符」——
        # 闭引号常常挂在待定段末里（`？”`），那时它还没被输出。
        if _starts_new_dialogue(ch, self._prev_nonspace, self._prev2_nonspace):
            self._para_len = 0
            out = prefix + "\n\n" + self._emit(ch)
            self._last_char = ch
            self._push_prev(ch)
            return out

        out = prefix + self._emit(ch)
        self._last_char = ch
        self._push_prev(ch)
        return out

    def _resolve_space(self, ch: str) -> str:
        """决定挂起的空格去留。

        汉字之间的空格删掉；其它情况（英文单词之间、行首）保留。
        """
        if not self._pending_space:
            return ""
        self._pending_space = False
        if self._last_char and _is_cjk(self._last_char) and _is_cjk(ch):
            return ""  # 汉字之间 → 删
        return " "

    def _emit_sentence_end(self, text: str) -> str:
        """输出"段末候选"（含句末标点），并按规则决定要不要断段。

        规则：段落已达 ``min_para_chars`` 字 → 在此断段（输出 ``\\n\\n``）。
        这就是"模型不给段落"时的**兜底断段**。
        """
        out = self._emit(text)
        if any(c in _SENTENCE_END for c in text) and self._para_len >= self._min:
            self._para_len = 0
            out += "\n\n"
        return out

    def _emit(self, text: str) -> str:
        """输出已确定的文本，并更新段落长度。"""
        if not text:
            return ""
        # 弱断点：段落太长时在逗号/分号处断开
        out = text
        extra = ""
        if self._para_len >= self._max and any(c in _WEAK_BREAK for c in text):
            # 在最后一个弱断点处切开
            idx = max(text.rfind(c) for c in _WEAK_BREAK)
            if idx >= 0:
                out = text[: idx + 1]
                extra = text[idx + 1 :]
        self._para_len += _count_nonspace(out)
        if extra:
            # 剩余部分另起一段
            self._para_len = _count_nonspace(extra)
            return out + "\n\n" + extra
        return out


def _count_nonspace(text: str) -> int:
    """段落长度按"非空白字符数"算。"""
    return sum(1 for c in text if not c.isspace())


def _starts_new_dialogue(ch: str, prev: str, prev2: str = "") -> bool:
    """判断当前字符是否开启**新的一段对白**。

    判据（三条同时成立）：
    1. 当前是引号开头（``“`` / ``‘`` / ``「``）
    2. 上一个非空白字符是引号收尾（``”`` / ``’`` / ``」``）
    3. 收尾引号**前面是句末标点**（``。`` / ``！`` / ``？``）

    第 3 条是关键：只有**以句末标点收尾**的引号才是"一句话说完了"，
    才可能是换人说话。而 ``将“沈”“砚”二字`` 这种**引用**里的引号
    内部没有句末标点 —— 不能拆，否则会把词组拆断。

    :param ch: 当前字符
    :param prev: 上一个非空白字符
    :param prev2: 上上个非空白字符
    :return: True 表示要另起一段
    """
    if not prev or not ch:
        return False
    if ch not in _DIALOG_OPEN or prev not in _DIALOG_CLOSE:
        return False
    return prev2 in _SENTENCE_END
