"""投递台账:记录每个岗位投没投、走到哪一步、下一步做什么。

用法(PowerShell 里先 $env:PYTHONIOENCODING="utf-8"):
  python src\\ledger.py init --from-rank      从精排结果导入(投→待投,观望→暂缓)
  python src\\ledger.py list                  看待投清单
  python src\\ledger.py list --status 已投     看某个状态
  python src\\ledger.py find 传音             按公司/岗位名搜 job_id
  python src\\ledger.py done J20209           标记已投(记时间)
  python src\\ledger.py set J20209 面试        改状态
  python src\\ledger.py note J20209 "邮件来了" 加备注
  python src\\ledger.py open J20209           打开岗位投递页
  python src\\ledger.py report                导出 投递台账.md
  python src\\ledger.py log J20209            看这条的状态变更历史
  python src\\ledger.py pull                  读北森侧真实投递记录(只读,需 Cookie)
  python src\\ledger.py sync --dry-run        看北森侧会把哪些状态往前推,不写库
  python src\\ledger.py sync                  把北森侧状态刷进台账
  python src\\ledger.py pull --tenant transsion

job_id 参数三种写法都行:前 8 位短码(如 9d05e981)、完整 UUID、岗位名或公司关键词。
"""
import argparse, json, os, sqlite3, sys, webbrowser
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "research"))
from tenants import COMPANY_CN

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.environ.get("LEDGER_DB") or os.path.join(ROOT, "data", "ledger.db")
RANK_JSON = os.path.join(ROOT, "data", "match_result.json")

STATUSES = ["待投", "暂缓", "已投", "笔试", "面试", "offer", "挂", "跳过"]
# 状态只能顺着这条链走,防止手滑把 offer 改回待投
NEXT_OK = {
    "待投": {"已投", "跳过", "暂缓"},
    "暂缓": {"待投", "已投", "跳过"},
    "已投": {"笔试", "面试", "挂", "暂缓"},
    "笔试": {"面试", "挂"},
    "面试": {"offer", "挂"},
    "offer": {"跳过"},
    "挂": {"跳过"},
    "跳过": set(STATUSES),
}

DDL = """
CREATE TABLE IF NOT EXISTS apps(
  job_id    TEXT PRIMARY KEY,
  tenant    TEXT, company TEXT, job_name TEXT, url TEXT, city TEXT,
  score     INTEGER, cos REAL, advice TEXT,
  status    TEXT NOT NULL DEFAULT '待投',
  applied_at TEXT, note TEXT,
  created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS history(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT, old_status TEXT, new_status TEXT, ts TEXT, note TEXT
);
"""


# 流程深浅,用于 sync 时"只前进不后退"的比较
STAGE_RANK = {"待投": 0, "暂缓": 0, "已投": 1, "笔试": 2, "面试": 3,
              "offer": 4, "挂": 5, "跳过": 6}


class LedgerError(Exception):
    """业务错误。CLI 打印后退出,HTTP 层翻译成 4xx,别让进程挂掉。"""


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def allowed(status):
    """某状态允许流转到的下一步,按 STATUSES 顺序给前端渲染下拉。"""
    return [s for s in STATUSES if s in NEXT_OK.get(status, set())]


def conn():
    if os.path.dirname(DB):
        os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.executescript(DDL)
    if "company" not in {r[1] for r in c.execute("PRAGMA table_info(apps)")}:
        c.execute("ALTER TABLE apps ADD COLUMN company TEXT")   # 旧库补列
    return c


def resolve(c, key):
    """把 J20209 / 岗位名关键词 解析成唯一 job_id。"""
    rows = c.execute("SELECT * FROM apps WHERE job_id=?", (key,)).fetchall()
    if not rows and len(key) >= 4:
        rows = c.execute("SELECT * FROM apps WHERE job_id LIKE ?",
                         (key + "%",)).fetchall()
    if not rows:
        like = f"%{key}%"
        rows = c.execute("SELECT * FROM apps WHERE job_name LIKE ? OR tenant LIKE ?"
                         " OR company LIKE ?", (like, like, like)).fetchall()
    if not rows:
        raise LedgerError(f"台账里没有「{key}」。先跑 init,或用 find 搜。")
    if len(rows) > 1:
        raise LedgerError(f"「{key}」匹配到 {len(rows)} 条,请改用完整 job_id:\n"
                          + fmt_rows(rows))
    return rows[0]


def fmt_rows(rows):
    lines = [f"{'短码':<9} {'状态':<4} {'分':>3}  {'公司':<8} 岗位"]
    for r in rows:
        lines.append(f"{(r['job_id'] or '')[:8]:<9} {r['status']:<4} "
                     f"{(r['score'] if r['score'] is not None else 0):>3}  "
                     f"{(r['company'] or r['tenant'] or ''):<8} {(r['job_name'] or '')[:40]}"
                     f"{('  |' + r['note']) if r['note'] else ''}")
    return "\n".join(lines)


def show(rows):
    print(fmt_rows(rows) if rows else "没有记录。")


def cmd_init(a):
    if not os.path.exists(RANK_JSON):
        raise LedgerError(f"找不到 {RANK_JSON},先跑 rank_jobs.py")
    d = json.load(open(RANK_JSON, encoding="utf-8"))
    c = conn()
    n = 0
    for j in d["jobs"]:
        v = j.get("verdict") or {}
        adv = v.get("advice")
        if not a.all and adv not in ("投", "观望"):
            continue
        status = {"投": "待投", "观望": "暂缓"}.get(adv, "暂缓")
        gid = str(j.get("id") or j.get("job_ad_id"))
        cur = c.execute("SELECT 1 FROM apps WHERE job_id=?", (gid,)).fetchone()
        if cur and not a.force:
            continue
        c.execute(
            "INSERT OR REPLACE INTO apps(job_id,tenant,company,job_name,url,city,"
            "score,cos,advice,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (gid, j.get("tenant"), COMPANY_CN.get(j.get("tenant"), j.get("tenant")),
             " ".join((j.get("name") or "").split()),
             j.get("url"), "/".join((j.get("gates") or {}).get("cities") or []),
             v.get("score"), j.get("_cos"), adv, status, now(), now()))
        if not cur:
            c.execute("INSERT INTO history(job_id,new_status,ts,note) VALUES(?,?,?,?)",
                      (gid, status, now(), "导入"))
        n += 1
    c.commit()
    total = c.execute("SELECT COUNT(*) FROM apps").fetchone()[0]
    print(f"本次处理 {n} 条,台账共 {total} 条。(已存在的不覆盖状态,--force 才重写)")


def cmd_list(a):
    c = conn()
    if a.status:
        rows = c.execute("SELECT * FROM apps WHERE status=? ORDER BY score DESC",
                         (a.status,)).fetchall()
    else:
        rows = c.execute("SELECT * FROM apps ORDER BY"
                         " CASE status WHEN '待投' THEN 0 WHEN '暂缓' THEN 1"
                         " ELSE 2 END, score DESC").fetchall()
    if not rows:
        print("没有记录。")
        return
    show(rows)
    st = {}
    for r in c.execute("SELECT status,COUNT(*) n FROM apps GROUP BY status"):
        st[r["status"]] = r["n"]
    print("\n统计:" + " · ".join(f"{k}{v}" for k, v in sorted(st.items(),
          key=lambda kv: -kv[1])))
    undone = c.execute("SELECT COUNT(*) FROM apps WHERE status='待投'").fetchone()[0]
    print(f"还剩 {undone} 个待投。链接见 report 或 open <job_id>")


def cmd_find(a):
    c = conn()
    like = f"%{a.key}%"
    show(c.execute("SELECT * FROM apps WHERE job_name LIKE ? OR tenant LIKE ?"
                   " OR company LIKE ? OR job_id LIKE ? ORDER BY score DESC",
                   (like, like, like, like)).fetchall())


def cmd_done(a):
    _set(a.key, "已投", a.note, applied=True, force=a.force)


def cmd_set(a):
    if a.status not in STATUSES:
        raise LedgerError(f"状态只能是: {'/'.join(STATUSES)}")
    _set(a.key, a.status, a.note, force=a.force)


def _set(key, status, note=None, applied=False, force=False):
    """唯一的状态写入口。CLI 和 HTTP 都走这里,规则只有一份。"""
    c = conn()
    r = resolve(c, key)
    if status not in NEXT_OK[r["status"]] and not force:
        raise LedgerError(f"不能从「{r['status']}」直接到「{status}」。"
                          f"允许:{'/'.join(allowed(r['status'])) or '(无)'}。"
                          " 确实要改就勾强制/--force")
    c.execute("UPDATE apps SET status=?, updated_at=?,"
              " applied_at=COALESCE(applied_at,?) WHERE job_id=?",
              (status, now(), now() if applied else r["applied_at"], r["job_id"]))
    c.execute("INSERT INTO history(job_id,old_status,new_status,ts,note)"
              " VALUES(?,?,?,?,?)",
              (r["job_id"], r["status"], status, now(), note))
    if note:
        c.execute("UPDATE apps SET note=? WHERE job_id=?", (note, r["job_id"]))
    c.commit()
    msg = f"{r['job_name'][:30]}  {r['status']} → {status}"
    print(msg)
    return {"job_id": r["job_id"], "from": r["status"], "to": status, "msg": msg}


def _note(key, text):
    c = conn()
    r = resolve(c, key)
    new = ((r["note"] + " | ") if r["note"] else "") + text
    c.execute("UPDATE apps SET note=?,updated_at=? WHERE job_id=?",
              (new, now(), r["job_id"]))
    c.commit()
    print("已记:", new)
    return new


def cmd_note(a):
    _note(a.key, a.text)


def cmd_open(a):
    r = resolve(conn(), a.key)
    if not r["url"]:
        raise LedgerError("这条没有链接")
    webbrowser.open(r["url"])
    print("已打开:", r["job_name"][:30])


def cmd_log(a):
    c = conn()
    r = resolve(c, a.key)
    for h in c.execute("SELECT * FROM history WHERE job_id=? ORDER BY id",
                       (r["job_id"],)):
        print(f"{h['ts']}  {h['old_status'] or '·'} → {h['new_status']}"
              f"{('  ' + h['note']) if h['note'] else ''}")


def _cookie_for(tenant):
    """环境变量优先,其次该租户专属文件,最后通用文件。"""
    ck = os.environ.get("BEISEN_COOKIE", "").strip()
    if not ck:
        for p in (f"beisen_cookie.{tenant}.txt", "beisen_cookie.txt"):
            f = os.path.join(ROOT, "data", "secrets", p)
            if os.path.exists(f):
                ck = open(f, encoding="utf-8").read().strip()
                if ck:
                    break
    if ck and "=" not in ck:
        ck = "user_v2=" + ck
    return ck


def _fetch(tenant, ck):
    """取该租户的投递记录。未登录时北森会 302 到登录页返回 HTML,一律当读不到。"""
    import urllib.request
    req = urllib.request.Request(
        f"https://{tenant}.zhiye.com/api/Submission/GetAllDeliveryRecord",
        data=b"{}", headers={"Content-Type": "application/json", "Cookie": ck})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode("utf-8", "replace")
    except Exception:
        return None
    try:
        return json.loads(body)
    except ValueError:
        return None


def _applied(d):
    """摊平成投递记录列表。Finished/UnFinished 两个桶都要读:
    这里的 Finished 指投递动作提交完成,不代表招聘流程结束。"""
    data = (d or {}).get("Data") or {}
    out = []
    for bucket in ("Finished", "UnFinished"):
        for sub in (data.get(bucket) or {}).get("Submissions") or []:
            out.extend(sub.get("Datas") or [])
    return out


def beisen_stage(rec):
    """把北森字段翻成台账状态。DeliveryStatus 在刚投完时是空的,所以要多路取信号。

    实测(传音 2026-09-23):进入笔试环节时 DeliveryStatus 形如「线上测评-进行中」,
    同时 InvitationTest.StateStr='assess'。北森把这一环节叫「测评」,台账里记作「笔试」。
    """
    if rec.get("IsCancel"):
        return "跳过"
    it = rec.get("InvitationTest") or {}
    txt = " ".join(str(rec.get(k) or "") for k in ("DeliveryStatus", "InterviewLocation"))
    txt += " " + str(it.get("StateStr") or "")
    for kw, st in (("offer", "offer"), ("录用", "offer"), ("入职", "offer"),
                   ("面试", "面试"), ("interview", "面试"),
                   ("笔试", "笔试"), ("测评", "笔试"), ("assess", "笔试"),
                   ("淘汰", "挂"), ("未通过", "挂"), ("结束", "挂")):
        if kw.lower() in txt.lower():
            return st
    return "已投"


def cmd_pull(a):
    """只读:打印北森侧投递记录与真实字段,不改台账。"""
    c = conn()
    tenants = [r[0] for r in c.execute("SELECT DISTINCT tenant FROM apps WHERE tenant IS NOT NULL")]
    if a.tenant:
        tenants = [a.tenant]
    raw = {}
    for t in tenants:
        ck = _cookie_for(t)
        if not ck:
            print(f"{t:<12} 没有 Cookie(data/secrets/beisen_cookie.{t}.txt)")
            continue
        d = _fetch(t, ck)
        if d is None:
            print(f"{t:<12} 未登录(北森 Cookie 按租户隔离,这家要单独一份)")
            continue
        raw[t] = d
        data = d.get("Data") or {}
        fin = data.get("Finished") or {}
        unf = data.get("UnFinished") or {}
        print(f"{t:<12} Code={d.get('Code')} {d.get('Message')} "
              f"已完成{fin.get('TotalCount')} 进行中{unf.get('TotalCount')}")
        recs = _applied(d)
        if recs:
            print(f"{'':<12} 投递记录字段: {sorted(recs[0].keys())}")
            for r in recs:
                print(f"{'':<12}   {r.get('JobAdTitle')} | {r.get('DeliveryDate')} "
                      f"| 状态='{r.get('DeliveryStatus')}' → {beisen_stage(r)}")
    if raw:
        out = os.path.join(ROOT, "data", "beisen_raw.json")
        json.dump(raw, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"\n原始响应已存 {out}(不含 Cookie)")


def sync(tenant=None, dry_run=False):
    """拉北森侧真实状态刷进台账:只前进不后退,本地更靠后的不会被覆盖。

    返回 {changed, missing, no_cookie, lines};lines 是给人看的行,CLI 和页面都印它。
    """
    c = conn()
    tenants = [r[0] for r in c.execute("SELECT DISTINCT tenant FROM apps WHERE tenant IS NOT NULL")]
    if tenant:
        tenants = [tenant]
    out, no_cookie = [], []
    changed = missing = 0
    for t in tenants:
        ck = _cookie_for(t)
        if not ck:
            no_cookie.append(t)
            continue
        d = _fetch(t, ck)
        if d is None or d.get("Code") != 200:
            out.append(f"{t:<12} 读不到记录(未登录或 Cookie 过期)")
            continue
        for rec in _applied(d):
            jid = str(rec.get("JobAdID") or "")
            row = c.execute("SELECT * FROM apps WHERE job_id=?", (jid,)).fetchone()
            if not row:
                missing += 1
                out.append(f"{t:<12} 台账外投递: {rec.get('JobAdTitle')} "
                           f"{rec.get('DeliveryDate')} (不在本科向岗位池里,自己记一下)")
                continue
            remote, when = beisen_stage(rec), rec.get("DeliveryDate") or ""
            if STAGE_RANK[remote] <= STAGE_RANK[row["status"]]:
                continue
            url = ((rec.get("InvitationTest") or {}).get("TestUrl") or "").strip()
            out.append(f"{t:<12} {row['job_name'][:26]:<28} {row['status']} → {remote}"
                       f"  投递时间 {when}" + (f"\n{'':<12} 待办链接: {url}" if url else ""))
            changed += 1
            if dry_run:
                continue
            c.execute("UPDATE apps SET status=?,updated_at=?,"
                      " applied_at=COALESCE(NULLIF(applied_at,''),?)"
                      " WHERE job_id=?",
                      (remote, now(), when or now(), jid))
            c.execute("INSERT INTO history(job_id,old_status,new_status,ts,note)"
                      " VALUES(?,?,?,?,?)",
                      (jid, row["status"], remote, now(), f"北森同步 {when}"))
    c.commit()
    if no_cookie:
        out.append(f"没 Cookie、本次未同步: {' '.join(no_cookie)}"
                   f"(data/secrets/beisen_cookie.<租户>.txt)")
    out.append(f"\n{'预览' if dry_run else '已更新'} {changed} 条"
               + (f",台账外投递 {missing} 条" if missing else "") + "。")
    return {"changed": changed, "missing": missing,
            "no_cookie": no_cookie, "lines": out}


def cmd_sync(a):
    for line in sync(a.tenant, a.dry_run)["lines"]:
        print(line)


def cmd_report(a):
    c = conn()
    rows = c.execute("SELECT * FROM apps ORDER BY"
                     " CASE status WHEN '待投' THEN 0 WHEN '暂缓' THEN 1 ELSE 2 END,"
                     " score DESC").fetchall()
    st = {}
    for r in rows:
        st.setdefault(r["status"], []).append(r)
    L = ["# 投递台账\n", f"更新于 {now()}\n"]
    L.append("- " + " · ".join(f"{k} **{len(v)}**" for k, v in st.items()) + "\n")
    for s in STATUSES:
        if s not in st:
            continue
        L.append(f"\n## {s}({len(st[s])})\n")
        L.append("| 公司 | 岗位 | 分 | 城市 | 投递时间 | 备注 | 链接 |")
        L.append("|---|---|---|---|---|---|---|")
        for r in st[s]:
            L.append(f"| {r['company'] or r['tenant']} | {r['job_name'][:30]} "
                     f"| {r['score']} "
                     f"| {r['city'] or '-'} | {r['applied_at'] or '-'} "
                     f"| {(r['note'] or '').replace('|', '/')} "
                     f"| [投递]({r['url']}) |")
    out = os.path.join(ROOT, "投递台账.md")
    open(out, "w", encoding="utf-8").write("\n".join(L))
    print(f"已生成 {out}")


def main():
    p = argparse.ArgumentParser(description="投递台账")
    sub = p.add_subparsers(dest="cmd", required=True)
    x = sub.add_parser("init"); x.add_argument("--from-rank", action="store_true")
    x.add_argument("--all", action="store_true"); x.add_argument("--force", action="store_true")
    x.set_defaults(f=cmd_init)
    x = sub.add_parser("list"); x.add_argument("--status"); x.set_defaults(f=cmd_list)
    x = sub.add_parser("find"); x.add_argument("key"); x.set_defaults(f=cmd_find)
    x = sub.add_parser("done"); x.add_argument("key"); x.add_argument("--note")
    x.add_argument("--force", action="store_true"); x.set_defaults(f=cmd_done)
    x = sub.add_parser("set"); x.add_argument("key"); x.add_argument("status")
    x.add_argument("--note"); x.add_argument("--force", action="store_true")
    x.set_defaults(f=cmd_set)
    x = sub.add_parser("note"); x.add_argument("key"); x.add_argument("text")
    x.set_defaults(f=cmd_note)
    x = sub.add_parser("open"); x.add_argument("key"); x.set_defaults(f=cmd_open)
    x = sub.add_parser("log"); x.add_argument("key"); x.set_defaults(f=cmd_log)
    x = sub.add_parser("pull"); x.add_argument("--tenant")
    x.set_defaults(f=cmd_pull)
    x = sub.add_parser("sync"); x.add_argument("--tenant"); x.add_argument("--dry-run",
                                                                     action="store_true")
    x.set_defaults(f=cmd_sync)
    x = sub.add_parser("report"); x.set_defaults(f=cmd_report)
    a = p.parse_args()
    if getattr(a, "cmd", None) == "init" and not a.from_rank:
        sys.exit("init 需要 --from-rank(目前只支持从精排结果导入)")
    try:
        a.f(a)
    except LedgerError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
