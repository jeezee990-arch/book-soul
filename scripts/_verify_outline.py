"""一次性验证 POST /novels/outlines/generate。"""
import sys
import httpx

BASE = "http://127.0.0.1:8765"


def show(name: str, r: httpx.Response) -> None:
    print(f"=== {name} ===")
    print(f"  status: {r.status_code}")
    body = r.text
    if len(body) > 800:
        body = body[:800] + "\n  ...(truncated)"
    print(f"  body: {body}")


plot = (
    "主角顾渊是灵根被夺的废材，在忘川河畔做了十二年渡魂人。一日他渡来"
    "一缕古怪的魂魄，对方自称清虚道君，是当世第一仙门青莲宗初代祖师。"
    "清虚道君的魂魄寄存于他体内，令他重拾踏上修真之路的机缘。"
)

with httpx.Client(base_url=BASE, timeout=120.0) as client:
    show(
        "POST /novels/outlines/generate (complete)",
        client.post(
            "/novels/outlines/generate",
            json={
                "genre": "修仙",
                "plot_summary": plot,
                "novel_name": "忘川渡魂人",
                "outline_type": "complete",
            },
        ),
    )
    show(
        "POST /novels/outlines/generate (freedom)",
        client.post(
            "/novels/outlines/generate",
            json={
                "genre": "修仙",
                "plot_summary": plot,
                "outline_type": "freedom",
            },
        ),
    )

print("\nall done")
sys.exit(0)
