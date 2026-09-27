"""把 Moka 站采来的岗位并进岗位池(data/ai_jobs.json),再重建投递候选(shortlist.json)。

前置:research/moka_collect.js 已经在浏览器里跑过 —— Moka 的接口返回密文,明文只能
从渲染好的页面上抄,所以这一步没有纯 Python 版本。产物落 data/moka_raw.json,
可以是单个 {"org":...,"jobs":[...]},也可以是这些 dict 组成的 list(多家一起)。

用法(PowerShell 先 $env:PYTHONIOENCODING="utf-8"):
  python research\\merge_moka.py           合并 + 重建 shortlist
  python research\\merge_moka.py --dry     只说会新增/更新/下架什么,不落盘
  python research\\merge_moka.py --rebuild 不动岗位池,只用现有 ai_jobs.json 重建 shortlist

合并完还要跑 python src\\rank_jobs.py 才会出新分数(它只读 shortlist.json)。
"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jobrules import MIN_SCORE, cities_of, clean, degree_line_of, degree_of, score
from jobrules import shortlist_of
from tenants import COMPANY_CN, MOKA_SITES

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
AI_JOBS = os.path.join(DATA, "ai_jobs.json")
RAW = os.path.join(DATA, "moka_raw.json")
SHORTLIST = os.path.join(DATA, "shortlist.json")

# 卡片尾部是页面上的按钮文字,不是 JD
TAIL = re.compile(r"\s*(立即投递|申请职位|我要应聘|分享)\s*$")
# "要求"段头的几种写法。找到就把那一段单独当 require —— 硬门槛检测只读 require 那段。
REQ_BRACKET = re.compile(r"【[^】]{0,8}(要求|任职资格)】")
REQ_PLAIN = re.compile(r"(?m)^[ \t]*(?:任职|岗位|职位|基本|招聘)?要求[ \t]*[:：]")
# 短于这个长度的"正文"不是 JD,是转链占位(DeepSeek 的 Agent Harness 三条旧岗就这样)
MIN_JD = 80
# 有的站(月之暗面)把卡片角标和发布日期塞进了同一个标题节点:
# "急\nKimi 海外创意增长实习生\n发布于 2026-09-23"。这些不是岗位名。
BADGE = re.compile(r"^(急|新|热|置顶|推荐)$")
POSTED = re.compile(r"^(发布于|更新于)\s*[0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2}")


def title_of(raw):
    lines = [l.strip() for l in re.split(r"[\r\n]+", raw or "") if l.strip()]
    keep = [l for l in lines if not BADGE.match(l) and not POSTED.match(l)]
    return clean(keep[0] if keep else (lines[0] if lines else ""))



def req_head(s):
    hits = [m.start() for m in (REQ_BRACKET.search(s), REQ_PLAIN.search(s)) if m]
    return min(hits) if hits else None


def split_jd(jd):
    """返回 (职责段, 要求段)。没找到要求段就整段算职责,要求留空。"""
    i = req_head(jd)
    if i is None:
        return TAIL.sub("", jd).strip(), ""
    return TAIL.sub("", jd[:i]).strip(), jd[i:].strip()


def load_envelopes():
    d = json.load(open(RAW, encoding="utf-8"))
    envs = d if isinstance(d, list) else [d]
    out = []
    for e in envs:
        if not isinstance(e, dict) or not e.get("jobs") or not e.get("org"):
            sys.exit(f"moka_raw.json 结构不对:缺 org/jobs —— 先看一眼文件开头")
        out.append(e)
    return out


def to_rows(env):
    org, kind = env["org"], env.get("kind") or "社招"
    tenant = f"moka:{org}"
    rows, thin = [], []
    for j in env["jobs"]:
        name = title_of(j.get("title"))
        jd = TAIL.sub("", (j.get("jd") or "").strip())
        if len(jd) < MIN_JD:
            thin.append(name[:26])
            continue
        duty, require = split_jd(jd)
        s, why = score(name, duty, require)
        if s < MIN_SCORE:
            continue
        rows.append({
            "tenant": tenant,
            "type": "校招" if kind == "校招" else ("社招/实习" if "实习" in jd else "社招"),
            "score": s, "why": why,
            "name": name,
            "cities": cities_of((j.get("info") or "") + "\n" + jd)[:4],
            "degree": degree_of(require),
            "require_degree_line": degree_line_of(require),
            "duty": duty, "require": require, "post": None,
            "id": j["id"], "url": j.get("url"),
        })
    if thin:
        print(f"  {org}:跳过 {len(thin)} 条正文几乎是空的岗位(多半是转链占位,"
              f"正文在别的岗位里) —— {' / '.join(thin[:5])}")
    return rows


def main():
    dry = "--dry" in sys.argv
    prev = json.load(open(AI_JOBS, encoding="utf-8")) if os.path.exists(AI_JOBS) else []
    by_id = {r["id"]: r for r in prev}
    beisen = [r for r in prev if not str(r["tenant"]).startswith("moka:")]
    kept_moka = [r for r in prev if str(r["tenant"]).startswith("moka:")]

    incoming = []
    if "--rebuild" not in sys.argv:
        for env in load_envelopes():
            org = env["org"]
            tenant = f"moka:{org}"
            if org not in MOKA_SITES:
                print(f"⚠ {org} 没登记在 tenants.py 的 MOKA_SITES 里,补一行才不会被忘掉")
            if tenant not in COMPANY_CN:
                print(f"⚠ {tenant} 没有中文公司名,补进 tenants.py 的 COMPANY_CN,"
                      f"不然看板上只显示这串英文别名")
            rows = to_rows(env)
            got, total = len(rows), env.get("siteTotal") or 0
            if got < total:
                print(f"⚠ {org}:页面共 {total} 条,打分后只有 {got} 条进池"
                      f"(低于 {MIN_SCORE} 分的被丢掉,这是口径不是漏采)")
            old_ids = {r["id"] for r in kept_moka if r["tenant"] == tenant}
            new_ids = {r["id"] for r in rows if r["tenant"] == tenant}
            if total and got and old_ids - new_ids:
                gone_names = [clean(by_id[i]["name"])[:36] for i in old_ids - new_ids]
                print(f"  {org} 下架 {len(gone_names)} 个:" + " / ".join(gone_names[:5]))
            kept_moka = [r for r in kept_moka if r["tenant"] != tenant]
            incoming.extend(rows)

    clash = [r["id"] for r in incoming if r["id"] in by_id
             and not str(by_id[r["id"]]["tenant"]).startswith("moka:")]
    if clash:
        sys.exit(f"岗位 id 撞上了北森的岗位({clash[:3]}…),拒绝合并 —— 别把两边的台账搅浑")

    new = [r for r in incoming if r["id"] not in by_id]
    upd = [r for r in incoming if r["id"] in by_id
           and (r["duty"] + r["require"]) != (by_id[r["id"]].get("duty", "") +
                                              by_id[r["id"]].get("require", ""))]
    print(f"\nMoka  incoming={len(incoming)}  新增={len(new)}  正文有变={len(upd)}")
    for r in sorted(new, key=lambda x: -x["score"])[:15]:
        print(f"  + [{r['score']:>3}] {r['tenant']:<20} {clean(r['name'])[:44]}")
    if len(new) > 15:
        print(f"  ...另 {len(new) - 15} 个")

    rows = sorted(beisen + kept_moka + incoming, key=lambda x: -x["score"])
    sl = shortlist_of(rows)
    moka_sl = [r for r in sl if str(r["tenant"]).startswith("moka:")]
    print(f"岗位池 {len(rows)} 条 → shortlist {len(sl)} 条(其中 Moka {len(moka_sl)} 条)")
    for r in moka_sl:
        print(f"   [{r['score']:>3}] {r['tenant']:<20} {clean(r['name'])[:40]}"
              f" | 学历:{r['degree'] or '-'} | 城市:{','.join(r['cities']) or '-'}")
    if dry:
        print("\n--dry:什么都没写。")
        return
    json.dump(rows, open(AI_JOBS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(sl, open(SHORTLIST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n已写 {os.path.basename(AI_JOBS)} 和 {os.path.basename(SHORTLIST)}。"
          f"接着跑 python src\\rank_jobs.py")


if __name__ == "__main__":
    main()
