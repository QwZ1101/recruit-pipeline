"""SQLite 作为唯一数据源:apps/history 存可写状态,pool/meta 存只读岗位数据。

流水线(采集→粗筛→精排)产出 JSON 快照,ingest() 幂等灌进库,看板和后端 API
一律只从库读——不在前端再拼一遍 JSON。

用法(PowerShell 先 $env:PYTHONIOENCODING="utf-8"):
  python src\\store.py ingest     把 data/match_result.json + resume.json 灌进库
  python src\\store.py export     从库渲染静态 web/public/data.json(不启后端时用)
  python src\\store.py payload    从库里拼出看板数据并打印统计(验证用)
"""
import json, os, sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ledger
from ledger import LedgerError, conn, now

ROOT = ledger.ROOT
DATA = os.path.join(ROOT, "data")

DDL = """
CREATE TABLE IF NOT EXISTS pool(
  job_id   TEXT PRIMARY KEY,
  grp      TEXT, tenant TEXT, company TEXT, job_name TEXT, url TEXT, post TEXT,
  cities   TEXT, degree TEXT, coarse REAL, cos REAL, why TEXT,
  score    INTEGER, advice TEXT, one_line TEXT, city_note TEXT,
  matched  TEXT, gaps TEXT, risk TEXT, skills TEXT, blockers TEXT,
  duty     TEXT, require TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
"""

# 精排结论之外的岗位字段,来自 data/shortlist.json 那一批
RESUME_KEYS = ("name", "target_role", "job_type", "graduation", "school",
               "school_tier", "degree", "major", "target_cities", "links", "signals")


def db():
    c = conn()
    c.executescript(DDL)
    return c


def _read_json(path, default=None):
    if not os.path.exists(path):
        return default
    return json.load(open(path, encoding="utf-8"))


def _mts(path):
    if not os.path.exists(path):
        return None
    return datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")


def _j(v):
    return json.dumps(v if v is not None else [], ensure_ascii=False)


def ingest():
    """幂等:重跑只刷新岗位内容,绝不动 apps.status。"""
    mr = _read_json(os.path.join(DATA, "match_result.json"))
    if not mr:
        raise LedgerError(f"找不到 {os.path.join(DATA,'match_result.json')},先跑 rank_jobs.py")
    c = db()
    n = 0
    keep = []
    for grp, rows in (("ranked", mr["jobs"]), ("blocked", mr["blocked"])):
        for j in rows:
            gid = str(j.get("id") or j.get("job_ad_id"))
            keep.append(gid)
            g = j.get("gates") or {}
            v = j.get("verdict") or {}
            c.execute(
                "INSERT OR REPLACE INTO pool(job_id,grp,tenant,company,job_name,url,post,"
                "cities,degree,coarse,cos,why,score,advice,one_line,city_note,matched,gaps,"
                "risk,skills,blockers,duty,require,updated_at) VALUES(" +
                ",".join("?" * 24) + ")",
                (gid, grp, j.get("tenant"),
                 ledger.COMPANY_CN.get(j.get("tenant"), j.get("tenant")),
                 j.get("name"), j.get("url"), (j.get("post") or "")[:10],
                 # 城市以 rank_jobs 现算的 gates 为准(空数组也算结果);JSON 里那份可能是旧脚本抽的
                 _j(g["cities"] if "cities" in g else (j.get("cities") or [])),
                 j.get("degree"),
                 j.get("score"), j.get("_cos"), j.get("why"),
                 v.get("score"), v.get("advice") or "未精排", v.get("one_line") or "",
                 v.get("city_note") or "", _j(v.get("matched")), _j(v.get("gaps")),
                 _j(v.get("risk")), _j(g.get("skills_wanted")), _j(g.get("blockers")),
                 j.get("duty") or "", j.get("require") or "", now()))
            n += 1
    # 上一版有、这一版没有的岗位要清掉,否则看板会继续显示已下架的旧结论
    ph = ",".join("?" * len(keep))
    stale = [r[0] for r in c.execute(f"SELECT job_id FROM pool WHERE job_id NOT IN ({ph})",
                                     keep)]
    c.executemany("DELETE FROM pool WHERE job_id=?", [(x,) for x in stale])
    resume = _read_json(os.path.join(DATA, "resume.json")) or {}
    meta = {
        "stats": _j(mr.get("stats") or {}),
        "resume": _j({k: resume[k] for k in RESUME_KEYS if resume.get(k) is not None}),
        "pool_scanned_at": _mts(os.path.join(DATA, "ai_jobs.json")) or "",
        "resume_parsed_at": _mts(os.path.join(DATA, "resume.json")) or "",
        "ingested_at": now(),
    }
    for k, v in meta.items():
        c.execute("INSERT OR REPLACE INTO meta(k,v) VALUES(?,?)", (k, v))
    c.commit()
    c.close()
    return {"pool": n, "stats": mr.get("stats") or {}}


POOL_TEXT = ("matched", "gaps", "risk", "skills", "blockers", "cities")


def pool_row(r, apps):
    """pool 一行 + apps 的可写状态 = 看板一行。duty/require 在这里截断,库里存全文。"""
    d = dict(r)
    for k in POOL_TEXT:
        d[k] = json.loads(d.get(k) or "[]")
    a = apps.get(d["job_id"])
    d.update({
        "id": d["job_id"], "short": d["job_id"][:8], "name": d.pop("job_name"),
        "status": a["status"] if a else "未入台账",
        "applied_at": (a or {}).get("applied_at") or "",
        "note": (a or {}).get("note") or "",
        "duty": (d.get("duty") or "")[:1200],
        "require": (d.get("require") or "")[:1200],
    })
    for k in ("grp", "why", "coarse", "updated_at"):
        d.pop(k, None)
    return d


def payload():
    """看板/前端唯一的数据来源。transitions 一起给,规则不在 JS 里重写一遍。"""
    c = db()
    apps = {r["job_id"]: dict(r) for r in c.execute("SELECT * FROM apps")}
    meta = {r["k"]: json.loads(r["v"]) if r["v"].startswith(("{", "[")) else r["v"]
            for r in c.execute("SELECT k,v FROM meta")}
    ranked = [pool_row(r, apps) for r in
              c.execute("SELECT * FROM pool WHERE grp='ranked'")]
    blocked = []
    for r in c.execute("SELECT * FROM pool WHERE grp='blocked'"):
        d = pool_row(r, apps)
        blocked.append({k: d[k] for k in
                        ("id", "short", "tenant", "company", "name", "url", "degree",
                         "cities", "blockers", "score")})
    # 台账里有、岗位池里没有(init --all 导过或手工加的),别漏掉
    have = {j["id"] for j in ranked} | {j["id"] for j in blocked}
    for jid, a in apps.items():
        if jid in have:
            continue
        ranked.append({
            "id": jid, "short": jid[:8], "tenant": a["tenant"],
            "company": a["company"] or ledger.COMPANY_CN.get(a["tenant"], a["tenant"]),
            "name": a["job_name"], "url": a["url"], "post": "", "cities": [],
            "degree": None, "cos": a["cos"], "skills": [], "duty": "", "require": "",
            "score": a["score"], "advice": a["advice"] or "未精排", "matched": [],
            "gaps": [], "risk": [], "one_line": "", "city_note": "",
            "status": a["status"], "applied_at": a["applied_at"] or "",
            "note": a["note"] or "",
        })
    history = [dict(r) for r in c.execute("SELECT * FROM history ORDER BY ts, id")]
    c.close()

    by_status = {}
    for j in ranked:
        by_status[j["status"]] = by_status.get(j["status"], 0) + 1
    companies = {}
    for j in ranked:
        cmp = companies.setdefault(j["tenant"], {
            "tenant": j["tenant"], "company": j["company"],
            "jobs": 0, "tracked": 0, "applied": 0})
        cmp["jobs"] += 1
        if j["status"] != "未入台账":
            cmp["tracked"] += 1
        if j["status"] in ("已投", "笔试", "面试", "offer", "挂"):
            cmp["applied"] += 1

    return {
        "generated_at": now(),
        "resume": meta.get("resume") or {},
        "stats": dict(meta.get("stats") or {}, by_status=by_status,
                      pool_scanned_at=meta.get("pool_scanned_at"),
                      resume_parsed_at=meta.get("resume_parsed_at"),
                      ingested_at=meta.get("ingested_at")),
        "companies": sorted(companies.values(), key=lambda x: -x["jobs"]),
        "jobs": sorted(ranked, key=lambda x: -(x["score"] or 0)),
        "blocked": sorted(blocked, key=lambda x: -(x["score"] or 0)),
        "history": history,
        "statuses": ledger.STATUSES,
        "transitions": {s: ledger.allowed(s) for s in ledger.STATUSES},
        "ledger_db": os.environ.get("LEDGER_DB") or "data/ledger.db",
        # 分数是 LLM 给的,同一份代码连跑有 ±7 抖动;页面只按档位讲,别按名次
        "score_note": "精排分数由 LLM 给出,重复跑有 ±7 抖动,只信档位(85/82/78)不信名次",
    }


def export():
    """不启后端时也能分享的一份静态快照:从库渲染 data.json。"""
    out = os.path.join(ROOT, "web", "public", "data.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    p = payload()
    json.dump(p, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"已写入 {out}  {os.path.getsize(out)/1024:.0f} KB")
    return p


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "ingest"
    if cmd == "ingest":
        r = ingest()
        print(f"已灌入 pool {r['pool']} 行(只读岗位数据,未动状态)。stats={r['stats']}")
        p = payload()
        print(f"看板数据:岗位 {len(p['jobs'])} · 挡在门槛 {len(p['blocked'])} "
              f"· 状态流转 {len(p['history'])} 条")
    elif cmd == "export":
        p = export()
        print("  状态分布: " + " ".join(
            f"{k}{v}" for k, v in sorted(p["stats"]["by_status"].items())))
    elif cmd == "payload":
        p = payload()
        print("岗位 %d · 被挡 %d · 状态 %s" % (
            len(p["jobs"]), len(p["blocked"]),
            " ".join(f"{k}{v}" for k, v in sorted(p["stats"]["by_status"].items()))))
        print("已入库时间:", p["stats"].get("ingested_at"))
    else:
        sys.exit("用法: python src\\store.py ingest|payload")


if __name__ == "__main__":
    main()
