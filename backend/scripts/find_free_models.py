import httpx

def get_free_models():
    res = httpx.get("https://openrouter.ai/api/v1/models")
    data = res.json()["data"]
    free_models = [m["id"] for m in data if m["id"].endswith(":free") or ":free" in m["id"] or "free" in m.get("pricing", {}).get("prompt", "1")]
    print(f"Total OpenRouter Models Available: {len(data)}")
    print(f"Free Models Found ({len(free_models)}):")
    for m in free_models:
        print(f"  - {m}")

if __name__ == "__main__":
    get_free_models()
