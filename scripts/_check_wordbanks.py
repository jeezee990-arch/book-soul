"""快速统计 4 个词库的词数（一次性脚本）。"""
import yaml
from pathlib import Path

for genre in ["xiuxian", "dushi", "xuanyi", "yanqing"]:
    p = Path("config/wordbanks") / f"{genre}.yaml"
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    name = data["name"]
    print(f"{genre} ({name}):")
    total = 0
    for cat, words in data.items():
        if cat == "name":
            continue
        if isinstance(words, list):
            print(f"  {cat}: {len(words)}")
            total += len(words)
    print(f"  TOTAL: {total}")
