"""验证大纲生成 BUG 修复 — 端到端。"""
import sys
import httpx

plot = (
    "主角顾渊是灵根被夺的废材，在忘川河畔做了十二年渡魂人。"
    "一日他渡来一缕古怪的魂魄，对方自称清虚道君，是当世第一仙门青莲宗初代祖师。"
    "清虚道君的魂魄寄存于他体内，令他重拾踏上修真之路的机缘。"
    "剧情足够长，描述完整具体。"
)

r = httpx.post(
    "http://127.0.0.1:8765/novels/outlines/generate",
    json={"genre": "修仙", "plot_summary": plot, "outline_type": "complete"},
    timeout=90.0,
)
print(f"status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    name = data["novel_name"]
    oid = data["outline_id"]
    vols = len(data["structure"]["volumes"])
    print(f"novel={name}  outline_id={oid}  volumes={vols}")
elif r.status_code == 500:
    print(f"detail: {r.text[:500]}")
else:
    print(f"other: {r.text[:200]}")
sys.exit(0)
