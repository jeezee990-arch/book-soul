"""去重 xiuxian items 中的重复词（一次性脚本）。"""
import yaml
from pathlib import Path

p = Path("config/wordbanks/xiuxian.yaml")
data = yaml.safe_load(p.read_text(encoding="utf-8"))

# 统计去重前
before = len(data["items"])
# 去重保序
seen: set[str] = set()
unique: list[str] = []
for w in data["items"]:
    if w not in seen:
        seen.add(w)
        unique.append(w)
data["items"] = unique
after = len(unique)

# 写回
p.write_text(
    yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
    encoding="utf-8",
)
print(f"items: {before} -> {after} (去重 {before - after})")
