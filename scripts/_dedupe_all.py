"""检查并去重所有 wordbank 的重复词（一次性脚本）。"""
import yaml
from pathlib import Path

for genre in ["xiuxian", "dushi", "xuanyi", "yanqing"]:
    p = Path(f"config/wordbanks/{genre}.yaml")
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    for cat, words in data.items():
        if cat == "name" or not isinstance(words, list):
            continue
        before = len(words)
        seen: set[str] = set()
        unique: list[str] = []
        for w in words:
            if w not in seen:
                seen.add(w)
                unique.append(w)
        if len(unique) != before:
            print(f"{genre}.{cat}: {before} -> {len(unique)} (去重 {before - len(unique)})")
            data[cat] = unique
    p.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
print("done")
