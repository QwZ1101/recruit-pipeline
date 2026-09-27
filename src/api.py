"""看板后端:把 ledger.py 的能力露成 HTTP,前端就能反过来改库。

只绑 127.0.0.1——库里是手机号、邮箱和投递记录,别放到公网。
写操作全部走 ledger 的状态机,这里不复制一份规则。

用法(PowerShell 先 $env:PYTHONIOENCODING="utf-8"):
  python src\\api.py                  默认 http://127.0.0.1:8000
前端 vite 已把 /api 代理过来,不用配 CORS。
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ledger, store
from ledger import LedgerError

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

app = FastAPI(title="投递看板后端", docs_url=None, redoc_url=None)


class StatusIn(BaseModel):
    status: str
    note: str | None = None
    force: bool = False


class NoteIn(BaseModel):
    text: str


class SyncIn(BaseModel):
    tenant: str | None = None
    dry_run: bool = False


def _bad(e):
    raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/pool")
def get_pool():
    return store.payload()


@app.get("/api/apps/{key}")
def get_app(key: str):
    c = ledger.conn()
    try:
        r = ledger.resolve(c, key)
    except LedgerError as e:
        _bad(e)
    hist = [dict(h) for h in c.execute(
        "SELECT * FROM history WHERE job_id=? ORDER BY id", (r["job_id"],))]
    return {"app": dict(r), "history": hist, "next": ledger.allowed(r["status"])}


@app.patch("/api/apps/{key}")
def patch_app(key: str, body: StatusIn):
    """改状态。已投这一步顺带记投递时间,和 CLI 的 done 同一套语义。"""
    if body.status not in ledger.STATUSES:
        _bad(LedgerError(f"状态只能是:{'/'.join(ledger.STATUSES)}"))
    try:
        r = ledger._set(key, body.status, body.note,
                        applied=body.status == "已投", force=body.force)
    except LedgerError as e:
        _bad(e)
    return r | {"pool": store.payload()}


@app.post("/api/apps/{key}/note")
def post_note(key: str, body: NoteIn):
    if not body.text.strip():
        _bad(LedgerError("备注是空的,没记。"))
    try:
        note = ledger._note(key, body.text.strip())
    except LedgerError as e:
        _bad(e)
    return {"note": note, "pool": store.payload()}


@app.post("/api/sync")
def post_sync(body: SyncIn):
    """拉北森侧真实状态。没 Cookie 的租户会在 lines 里说明,不算失败。"""
    try:
        return ledger.sync(body.tenant, body.dry_run)
    except LedgerError as e:
        _bad(e)


@app.get("/api/profile")
def get_profile():
    """投递表单的答案表,文件缺失就返回空对象+提示,不报错。"""
    p = os.path.join(store.DATA, "profile.json")
    if not os.path.exists(p):
        return {"_missing": f"没有 {p},先复制一份 data/profile.json 再填"}
    return store._read_json(p) or {"_missing": "data/profile.json 解析失败,检查 JSON 语法"}


@app.get("/api/pool/moka.js")
def get_moka_js():
    """把采集器原文交给浏览器执行 —— 只此一份实现,人贴控制台和 agent 驱动跑同一段代码。

    为什么要有这条:agent 驱动时不能整段贴 JS(单次工具调用 15 秒就超时,采集要跑几十秒),
    也不能在 https 页面上用 <script src=http://127.0.0.1> 加载(混合内容会被拦),
    所以走 fetch + CORS。CORS 只认 app.mokahr.com 这一个来源,后端本来就只绑 127.0.0.1,
    返回的是仓库里的公开源码,不含任何数据。
    """
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "research", "moka_collect.js")
    if not os.path.exists(p):
        raise HTTPException(status_code=404, detail="找不到 research/moka_collect.js")
    return PlainTextResponse(open(p, encoding="utf-8").read(),
                             headers={"Access-Control-Allow-Origin": "https://app.mokahr.com"})


@app.post("/api/pool/moka")
async def post_moka(request: Request):
    """Moka 采集器(moka_collect.js)把岗位原文落进 data/moka_raw.json。

    Moka 的岗位接口返回的是密文,明文只能在渲染好的页面里抄,所以采集必须经浏览器;
    浏览器又没法替我把文件写到磁盘上(Qoder 内置浏览器的下载会被丢掉),就留这一条
    落盘口。只认这一个固定路径、只覆盖这一个文件,收到不像样的内容直接拒。
    前端用 no-cors 简单请求发,所以这里不需要 CORS。

    一家一家采,所以**按 org+siteId 覆盖、其余保留**(一家公司在 Moka 上可以有多个站点,
    同一 org 不同 siteId 的岗位不是一批)。文件形态:单个 dict 或 dict 的 list,merge_moka 都吃。
    """
    raw = await request.body()
    if len(raw) > 4_000_000:
        raise HTTPException(status_code=413, detail=f"载荷 {len(raw)} 字节,超过 4MB,不收")
    try:
        d = json.loads(raw.decode("utf-8"))
    except ValueError:
        raise HTTPException(status_code=400, detail="不是合法 JSON")
    jobs = (d or {}).get("jobs")
    if not isinstance(jobs, list) or not jobs or not all(
            isinstance(j, dict) and j.get("id") and j.get("jd") is not None for j in jobs):
        raise HTTPException(status_code=400,
                            detail="缺少 jobs[] 或条目没有 id/jd 字段,不收")
    if not d.get("org"):
        raise HTTPException(status_code=400, detail="缺 org 字段,不知道是哪家公司,不收")
    out = os.path.join(store.DATA, "moka_raw.json")
    key = (d["org"], str(d.get("siteId") or ""))
    envs = []
    if os.path.exists(out):
        try:
            prev = json.load(open(out, encoding="utf-8"))
            envs = prev if isinstance(prev, list) else [prev]
        except (ValueError, OSError):
            envs = []       # 旧文件坏了就直接以本次为准,不报错卡住采集
    kept = [e for e in envs
            if isinstance(e, dict) and (e.get("org"), str(e.get("siteId") or "")) != key]
    merged = kept + [d]
    json.dump(merged if len(merged) > 1 else merged[0],
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return {"saved": len(jobs), "org": d.get("org"), "sites": len(merged), "path": out}


@app.get("/")
def root():
    """浏览器直接开 8000 时给个指路,别只回 404 让人以为坏了。"""
    return {"这是什么": "台账后端,只提供 /api/*,页面不在这里",
            "看板地址": "http://localhost:5173(先 cd web; npm run dev)",
            "接口": ["/api/pool", "/api/apps/{key}", "/api/apps/{key}/note",
                     "/api/sync", "/api/profile", "/api/pool/moka", "/api/pool/moka.js",
                     "/api/health"]}


@app.get("/api/health")
def health():
    return {"ok": True, "db": store.DATA}


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("API_HOST") or "127.0.0.1"
    if host not in ("127.0.0.1", "localhost"):
        sys.exit(f"拒绝绑到 {host}:库里是个人信息,只允许本机。"
                 " 确实要改请自己改这行。")
    uvicorn.run(app, host=host, port=int(os.environ.get("API_PORT") or 8000))
