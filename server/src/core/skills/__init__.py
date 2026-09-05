"""Skills subpackage (Phase 6.4 + 7.1).

Auto-registers built-in skills on import.
"""

from __future__ import annotations

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

register(word_counter.WordCounterSkill())
register(sensitive_word.SensitiveWordSkill())
register(chapter_summarizer.ChapterSummarizerSkill())
register(character_extractor.CharacterExtractorSkill())
register(plot_analyzer.PlotAnalyzerSkill())
register(web_search.WebSearchSkill())
register(read_local_file.ReadLocalFileSkill())
register(consistency_checker.ConsistencyCheckerSkill())
register(style_analyzer.StyleAnalyzerSkill())
register(pacing_visualizer.PacingVisualizerSkill())
register(outline_structurer.OutlineStructurerSkill())
register(genre_classifier.GenreClassifierSkill())

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
