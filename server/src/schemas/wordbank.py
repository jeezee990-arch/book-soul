"""词库 Pydantic schema（输入/输出契约）。

端点：
- GET /wordbanks                              → WordbankList
- GET /wordbanks/{genre}                      → WordbankMeta
- GET /wordbanks/{genre}/words?category=...   → list[str] | dict
- GET /wordbanks/{genre}/all-words            → WordbankAllWords
- POST/PATCH/DELETE /wordbanks/{genre}/words  → WordbankMutationResult
- POST /wordbanks/{genre}/import              → WordbankImportResult
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WordbankMeta(BaseModel):
    """单个题材的词库元数据。"""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="题材 id（与文件名同名，如 xiuxian）")
    name: str = Field(description="题材中文名（来自 YAML）")
    categories: list[str] = Field(description="所有分类名")
    counts: dict[str, int] = Field(description="每个分类的词数")


class WordbankListEntry(BaseModel):
    """``GET /wordbanks`` 返回的单个题材摘要。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    total: int = Field(description="该题材总词数")


class WordbankList(BaseModel):
    """``GET /wordbanks`` 返回。"""

    genres: list[WordbankListEntry]


class WordbankAllWords(BaseModel):
    """``GET /wordbanks/{genre}/all-words`` 返回：该板块的全部词条。"""

    id: str = Field(description="题材 id")
    name: str = Field(description="题材中文名")
    categories: list[str] = Field(description="分类顺序（与 YAML 一致）")
    words: dict[str, list[str]] = Field(description="分类 → 全部词条")
    counts: dict[str, int] = Field(description="分类 → 词数")


class WordItem(BaseModel):
    """一条词条（分类 + 文本）。"""

    category: str = Field(description="分类 key（themes/characters/plots/scenes/items）")
    word: str = Field(description="词条文本")


class WordsAddRequest(BaseModel):
    """新增词条（单个或批量）。"""

    items: list[WordItem] = Field(description="待新增的词条列表")


class WordUpdateRequest(BaseModel):
    """修改词条：把 ``category`` 里的 ``old`` 改成 ``new``。"""

    category: str = Field(description="词条所在分类")
    old: str = Field(description="原词条")
    new: str = Field(description="新词条")


class WordsDeleteRequest(BaseModel):
    """删除词条（支持批量）。"""

    items: list[WordItem] = Field(description="待删除的词条列表")


class WordbankMutationResult(BaseModel):
    """写操作结果。"""

    added: int = Field(default=0, description="新增条数")
    updated: int = Field(default=0, description="修改条数")
    deleted: int = Field(default=0, description="删除条数")
    duplicates: int = Field(default=0, description="重复（已存在，跳过）条数")
    errors: list[str] = Field(default_factory=list, description="逐条错误说明")
    missing: list[str] = Field(default_factory=list, description="没找到的词条（分类/词条）")


class WordbankImportRequest(BaseModel):
    """粘贴文本导入。"""

    text: str = Field(description="待导入的原始文本")
    default_category: str = Field(default="themes", description="没写分类前缀的词归到哪类")


class WordbankImportResult(BaseModel):
    """导入结果。"""

    added: int = Field(default=0, description="新增条数")
    duplicates: int = Field(default=0, description="重复条数")
    failed: int = Field(default=0, description="解析失败行数")
    errors: list[str] = Field(default_factory=list, description="逐行失败原因")
    by_category: dict[str, int] = Field(default_factory=dict, description="各分类新增条数")
