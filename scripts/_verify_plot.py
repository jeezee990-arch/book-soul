"""一次性验证 POST /inspirations/generate-plot 端点 + LLM 调用。"""
import sys
import httpx

BASE = "http://127.0.0.1:8765"


def show(name: str, r: httpx.Response) -> None:
    print(f"=== {name} ===")
    print(f"  status: {r.status_code}")
    body = r.text
    if len(body) > 1500:
        body = body[:1500] + "\n  ...(truncated)"
    print(f"  body: {body}")


with httpx.Client(base_url=BASE, timeout=120.0) as client:
    show(
        "POST /inspirations/generate-plot (修仙, 3 个词)",
        client.post(
            "/inspirations/generate-plot",
            json={
                "genre": "修仙",
                "keywords": ["废柴逆袭", "退婚打脸", "秘境"],
                "n_versions": 3,
            },
        ),
    )
    show(
        "POST /inspirations/generate-plot (空 keywords → 422)",
        client.post(
            "/inspirations/generate-plot",
            json={"genre": "都市", "keywords": [], "n_versions": 1},
        ),
    )

print("\nall done")
sys.exit(0)
