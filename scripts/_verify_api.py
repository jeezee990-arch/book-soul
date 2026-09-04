"""一次性验证 3 个新 wordbank 端点（用 httpx + utf-8 JSON）。"""
import json
import sys
import httpx

BASE = "http://127.0.0.1:8765"


def show(name: str, r: httpx.Response) -> None:
    print(f"=== {name} ===")
    print(f"  status: {r.status_code}")
    try:
        data = r.json()
        body = json.dumps(data, ensure_ascii=False, indent=2)
        if len(body) > 600:
            body = body[:600] + "\n  ...(truncated)"
        print(f"  body:\n  {body}")
    except Exception:
        print(f"  body: {r.text[:200]}")


with httpx.Client(base_url=BASE, timeout=10.0) as client:
    show("GET /wordbanks", client.get("/wordbanks"))
    show("GET /wordbanks/xiuxian", client.get("/wordbanks/xiuxian"))
    show(
        "GET /wordbanks/xiuxian/words?category=themes&n=5",
        client.get("/wordbanks/xiuxian/words", params={"category": "themes", "n": 5}),
    )
    show(
        "GET /wordbanks/xiuxian/words?category=themes&category=plots&n=3",
        client.get(
            "/wordbanks/xiuxian/words",
            params=[("category", "themes"), ("category", "plots"), ("n", "3")],
        ),
    )
    show(
        "GET /wordbanks/unknown (should 404)",
        client.get("/wordbanks/unknown_genre"),
    )
    show(
        "GET /wordbanks/xiuxian/words?category=bogus&n=5 (should 422)",
        client.get("/wordbanks/xiuxian/words", params={"category": "bogus", "n": 5}),
    )

print("\nall done")
sys.exit(0)
