"""扫描北森 zhiye 租户校招/实习岗位,筛出 AI 大模型应用开发相关职位。

接口(公开、无需登录):
  POST /api/Jobad/GetJobAdPageList  body {"category":2|3,"pageIndex":N,"pageSize":10}
  GET  /api/Jobad/GetJobAdInfo?jobAdId=<uuid>

用法:
  python research\\scan_ai_jobs.py                   联网全量刷新
  python research\\scan_ai_jobs.py --rebuild-only    只用现有 ai_jobs.json 重建 shortlist.json

实测约束:
  - **pageIndex 从 0 开始**,不是 1。按 1 起翻每页都正常返回,只会在末尾少一页,
    所以 Count 对得上、看起来一切正常 —— 每个租户的头 10 个岗位会静默丢掉;
    Count<=10 的小租户会整家拿到 0 条。判定:实取恒等于 Count-10 即中招。
  - pageSize 必须用 10。20/50 会返回不完整页甚至空 Data(Count 仍正确)。
  - keyWords 服务端过滤 Count 准确但 Data 会丢,故不用,改为全量拉取后本地过滤。
  - 列表与详情都只有 9 个字段有值,城市/学历需从 Duty/Require 文本抽取。

打分口径不在这个文件里,统一放 jobrules.py(Moka 采集器共用同一份)。
"""
import json, os, sys, time, math, urllib.request, concurrent.futures
from tenants import TENANTS
from jobrules import (MIN_SCORE, cities_of, clean, degree_line_of,
                      degree_of, score, shortlist_of)

# 数据产物统一落 data/,research/ 只放脚本与报告
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
PAGE_SIZE = 10
CATEGORIES = {2: "校招", 3: "实习"}


def _mtime(p):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(p)))


def req(host, path, body=None, tries=5):
    url = f"https://{host}{path}"
    data = json.dumps(body).encode() if body is not None else None
    for i in range(tries):
        try:
            r = urllib.request.Request(url, data=data,
                                       method="POST" if body else "GET",
                                       headers={"Content-Type": "application/json",
                                                "User-Agent": UA,
                                                "Referer": f"https://{host}/campus/jobs",
                                                "Origin": f"https://{host}"})
            with urllib.request.urlopen(r, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8", "replace"))
        except Exception:
            time.sleep(0.4 * (i + 1))
    return None


def _page(host, cat, idx):
    d = req(host, "/api/Jobad/GetJobAdPageList",
            {"category": cat, "pageIndex": idx, "pageSize": PAGE_SIZE})
    return d


def fetch_all(tenant, cat):
    """整量拉取,逐页校验,短页重试。返回 missing=彻底没拿到的页数。

    pageIndex 从 0 开始(实测)。曾经从 1 开始,导致每个租户头 10 个岗位
    静默丢失,而且小租户(Count<=10)整家拿不到数据。
    """
    host = f"{tenant}.zhiye.com"
    first = _page(host, cat, 0)
    if not first:
        return tenant, cat, 0, [], 1
    total = first.get("Count") or 0
    jobs = list(first.get("Data") or [])
    missing = 0
    npages = math.ceil(total / PAGE_SIZE)
    for idx in range(1, min(npages, 400)):
        want = min(PAGE_SIZE, total - idx * PAGE_SIZE)
        got = []
        for _ in range(5):
            got = (_page(host, cat, idx) or {}).get("Data") or []
            if len(got) >= want:
                break
            time.sleep(0.4)
        if not got:
            missing += 1
        jobs.extend(got)
        time.sleep(0.12)
    return tenant, cat, total, jobs, missing


def _rows_from_fetch():
    """联网全量拉北森 → 打分 → 返回 (rows, incomplete)。"""
    tasks = [(t, c) for t in TENANTS for c in CATEGORIES]
    print(f"拉取任务: {len(tasks)} 个租户×类目", flush=True)

    alljobs = {}
    incomplete = []      # 有整页拿不到的租户×类目,diff 里不能把它当"下架"
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for tenant, cat, total, jobs, missing in ex.map(lambda a: fetch_all(*a), tasks):
            got = len({j["Id"] for j in jobs})
            flag = "OK " if got >= total else "缺!"
            print(f"  {flag} {tenant:<16} {CATEGORIES[cat]} Count={total:<5} 实取={got}"
                  + (f"  (缺 {missing} 页)" if missing else ""), flush=True)
            if got < total:
                incomplete.append(f"{tenant}/{CATEGORIES[cat]}")
            for j in jobs:
                j["_cat"] = CATEGORIES[cat]
                j["_tenant"] = tenant
                alljobs.setdefault((tenant, j["Id"]), j)

    print(f"\n合计去重岗位 {len(alljobs)}", flush=True)

    rows = []
    for (tenant, _), j in alljobs.items():
        s, why = score(j.get("JobAdName"), j.get("Duty"), j.get("Require"))
        if s < MIN_SCORE:
            continue
        text = (j.get("Duty") or "") + "\n" + (j.get("Require") or "")
        rows.append({
            "tenant": tenant, "type": j["_cat"], "score": s, "why": why,
            "name": j.get("JobAdName"), "cities": cities_of(
                text + (j.get("JobAdName") or ""))[:4],
            "degree": degree_of(j.get("Require")),
            "require_degree_line": degree_line_of(j.get("Require")),
            "duty": j.get("Duty"), "require": j.get("Require"),
            "post": j.get("ChangeDate"), "id": j["Id"],
            "url": f"https://{tenant}.zhiye.com/campus/detail?jobAdId={j['Id']}",
        })
    return rows, incomplete


FETCHED = "--rebuild-only" not in sys.argv
PREV = os.path.join(DATA, "ai_jobs.json")

if FETCHED:
    rows, incomplete = _rows_from_fetch()
else:
    # 不联网:沿用现有快照,只看"打分/收窄口径"改动的影响面
    rows, incomplete = json.load(open(PREV, encoding="utf-8")), []
    print(f"--rebuild-only:用现有快照 {len(rows)} 条重建 shortlist", flush=True)

rows.sort(key=lambda x: -x["score"])

# ---- 与上一版快照按 job id 做 diff:秋招期新增/下架要看得见 ----
old = {}
if FETCHED and os.path.exists(PREV):
    old = {r["id"]: r for r in json.load(open(PREV, encoding="utf-8"))}
new_ids = {r["id"] for r in rows}
added = [r for r in rows if r["id"] not in old]
# 某租户整页没抓到时会凭空少 10 条,看起来就像"下架"。这种只能标成待核实,不能报成失去。
partial = set(incomplete)
gone = [r for r in old.values()
        if r["id"] not in new_ids and f"{r['tenant']}/{r['type']}" not in partial]
unverified_gone = [r for r in old.values()
                   if r["id"] not in new_ids and f"{r['tenant']}/{r['type']}" in partial]
changed = [r for r in rows if r["id"] in old
           and (r["duty"] or "") + (r["require"] or "") !=
               (old[r["id"]]["duty"] or "") + (old[r["id"]]["require"] or "")]
if old:
    print(f"\n===== 与上一版对比(上版 {len(old)} 个)=====")
    print(f"  新增 {len(added)} · 下架 {len(gone)} · JD 正文有变 {len(changed)}"
          + (f" · 待核实 {len(unverified_gone)}" if unverified_gone else ""))
    for r in added[:15]:
        print(f"  + [{r['score']:>3}] {r['tenant']:<14} {r['name'][:40]}")
    if len(added) > 15:
        print(f"  ...另 {len(added)-15} 个新增")
    for r in gone[:10]:
        print(f"  - {r['tenant']:<14} {r['name'][:40]}")
    if partial:
        print(f"  抓取不全(这些租户的'消失'不可信):{', '.join(sorted(partial))}")
    json.dump({"prev_at": _mtime(PREV), "added": added, "gone": gone,
               "unverified_gone": unverified_gone, "partial": sorted(partial),
               "changed": [{"id": r["id"], "tenant": r["tenant"], "name": r["name"]}
                           for r in changed]},
              open(os.path.join(DATA, "pool_diff.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

if FETCHED:
    json.dump(rows, open(PREV, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

by = {}
for r in rows:
    by.setdefault(r["tenant"], []).append(r)
print(f"\n===== AI 相关岗位 {len(rows)} 个 / {len(by)} 家 =====\n")
for t, lst in sorted(by.items(), key=lambda kv: -max(x["score"] for x in kv[1])):
    print(f"■ {t}.zhiye.com — {len(lst)} 个")
    for r in lst[:10]:
        print(f"   [{r['score']:>3}] {r['type']} {r['name']}")
        print(f"         城市:{','.join(r['cities']) or '-'} | 学历:{r['degree'] or '-'} | {r['why']}")
    if len(lst) > 10:
        print(f"   ...另 {len(lst)-10} 个")
    print()


# ---- 收窄到"本科可投 + 开发向"清单 ----
shortlist = shortlist_of(rows)

json.dump(shortlist, open(os.path.join(DATA, "shortlist.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"===== 本科可投 + 开发向:{len(shortlist)} 个 → data/shortlist.json =====")
for r in shortlist[:20]:
    print(f"  [{r['score']:>3}] {r['tenant']:<12} {r['type']} {clean(r['name'])[:44]}")
