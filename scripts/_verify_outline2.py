"""直连后端测试 /novels/outlines/generate，确认 LLM 真能跑。"""
import sys
import httpx

BASE = "http://127.0.0.1:8765"
plot = (
    "主角顾渊是灵根被夺的废材，在忘川河畔做了十二年渡魂人。一日他渡来"
    "一缕古怪的魂魄，对方自称清虚道君，是当世第一仙门青莲宗初代祖师。"
    "清虚道君的魂魄寄存于他体内，令他重拾踏上修真之路的机缘。"
    "剧情足够长，描述完整具体。"
)

with httpx.Client(base_url=BASE, timeout=180.0) as client:
    r = client.post(
        "/novels/outlines/generate",
        json={"genre": "修仙", "plot_summary": plot, "outline_type": "complete"},
    )
    print(f"status: {r.status_code}")
    body = r.text
    if len(body) > 600:
        body = body[:600] + "..."
    print(f"body: {body}")
sys.exit(0)
