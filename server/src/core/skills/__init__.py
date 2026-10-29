"""Skills subpackage (Phase 6.4 + 7.1).

Auto-registers built-in skills on import.
"""

from __future__ import annotations

from typing import cast

from .base import Skill, SkillResult

# 导入 builtin skills 触发自动注册
from .builtin import (  # noqa: F401
    chapter_summarizer,
    character_extractor,
    consistency_checker,
    genre_classifier,
    outline_structurer,
    pacing_visualizer,
    plot_analyzer,
    read_local_file,
    sensitive_word,
    style_analyzer,
    web_search,
    word_counter,
)
from .registry import (
    SkillNotFoundError,
    SkillRegistry,
    get,
    list_skills,
    register,
    registry,
    run_skill,
)

# ⚠️ 下面统一用 ``cast(Skill, ...)`` 显式声明内置 skill 满足 Skill 协议：
#    Protocol 声明的是 ``execute(self, **kwargs: Any)``，而内置 skill 的形参更具体
#    （如 ``execute(self, text: str)``），mypy 的结构化子类型检查因此判定为不兼容。
#    运行时注册表始终按关键字传参调用（``registry.run`` → ``skill.execute(**kwargs)``），
#    实际调用方式与 Protocol 约定一致，故此处做显式类型断言而非忽略错误。
register(cast(Skill, word_counter.WordCounterSkill()))
register(cast(Skill, sensitive_word.SensitiveWordSkill()))
register(cast(Skill, chapter_summarizer.ChapterSummarizerSkill()))
register(cast(Skill, character_extractor.CharacterExtractorSkill()))
register(cast(Skill, plot_analyzer.PlotAnalyzerSkill()))
register(cast(Skill, web_search.WebSearchSkill()))
register(cast(Skill, read_local_file.ReadLocalFileSkill()))
register(cast(Skill, consistency_checker.ConsistencyCheckerSkill()))
register(cast(Skill, style_analyzer.StyleAnalyzerSkill()))
register(cast(Skill, pacing_visualizer.PacingVisualizerSkill()))
register(cast(Skill, outline_structurer.OutlineStructurerSkill()))
register(cast(Skill, genre_classifier.GenreClassifierSkill()))

__all__ = [
    "Skill",
    "SkillResult",
    "SkillRegistry",
    "SkillNotFoundError",
    "registry",
    "register",
    "get",
    "list_skills",
    "run_skill",
]
