"""DashScope 调用封装:embedding + JSON 模式对话。"""
import json, os, time, urllib.request

KEY = os.environ.get("DASHSCOPE_API_KEY")
BASE = "https://ws-hqr7fpy8nvk4r1d3.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
EMBED_MODEL = "qwen3.7-text-embedding"
CHAT_MODEL = "qwen3.8-max-0902"


def _post(path, payload, tries=4):
    for i in range(tries):
        try:
            r = urllib.request.Request(BASE + path,
                                       data=json.dumps(payload).encode(),
                                       headers={"Authorization": f"Bearer {KEY}",
                                              "Content-Type": "application/json"})
            # qwen3.8-max-0902 是思考模型,1900 字的简历解析实测 >90s 才回,超时给到 300
            with urllib.request.urlopen(r, timeout=300) as resp:
                return json.loads(resp.read().decode("utf-8", "replace"))
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(1.5 * (i + 1))


def embed(texts):
    """返回与输入等长的向量列表。DashScope 单次上限 10 条,内部自动分批。"""
    out = []
    for i in range(0, len(texts), 10):
        d = _post("/embeddings", {"model": EMBED_MODEL,
                                  "input": [t[:2000] for t in texts[i:i + 10]]})
        out.extend(x["embedding"] for x in sorted(d["data"], key=lambda x: x["index"]))
        time.sleep(0.15)
    return out


def chat_json(system, user, tries=3):
    for i in range(tries):
        try:
            d = _post("/chat/completions", {
                "model": CHAT_MODEL,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": user}],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                # 该模型带 reasoning_content,额度给足否则截断
                "max_tokens": 3000,
            }, tries=1)
            return json.loads(d["choices"][0]["message"]["content"])
        except Exception as e:
            if i == tries - 1:
                return {"_error": str(e)[:120]}
            time.sleep(1.2 * (i + 1))
