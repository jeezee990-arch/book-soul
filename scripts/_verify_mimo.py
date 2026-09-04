"""端到端测 MiMo LLM（应该秒回，国内节点）。"""
import sys
import httpx
import time

BASE = "http://127.0.0.1:8765"

# 1) /llm/test 直接调 MiMo
t0 = time.time()
r = httpx.post(
    f"{BASE}/llm/test",
    json={"prompt": "用一句话介绍你自己", "max_tokens": 200},
    timeout=60.0,
)
print(f"=== /llm/test ===")
print(f"  status: {r.status_code}  ({time.time()-t0:.1f}s)")
if r.status_code == 200:
    d = r.json()
    print(f"  provider: {d.get('provider')}")
    print(f"  model: {d.get('model')}")
    print(f"  content: {d.get('content')[:200]}")
else:
    print(f"  body: {r.text[:300]}")

# 2) 完整 plot 生成
t0 = time.time()
r = httpx.post(
    f"{BASE}/inspirations/generate-plot",
    json={
        "genre": "修仙",
        "keywords": ["废柴逆袭", "退婚打脸"],
        "n_versions": 3,
    },
    timeout=120.0,
)
print(f"\n=== /inspirations/generate-plot ===")
print(f"  status: {r.status_code}  ({time.time()-t0:.1f}s)")
if r.status_code == 200:
    d = r.json()
    print(f"  provider: {d.get('provider')}")
    print(f"  versions: {len(d.get('versions', []))}")
    for v in d.get("versions", []):
        print(f"    v{v['index']}: {v['summary'][:80]}...")
else:
    print(f"  body: {r.text[:400]}")
sys.exit(0)
