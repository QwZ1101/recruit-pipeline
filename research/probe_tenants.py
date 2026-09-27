"""探活北森 zhiye 租户:找出还有哪些公司用 {别名}.zhiye.com 收校招简历。

判活只看能不能解析出 JSON —— 无效租户会返回 HTTP 200 + 一段 HTML(通配 DNS),
所以不能看状态码。

用法(PowerShell 先 $env:PYTHONIOENCODING="utf-8"):
  python research\\probe_tenants.py                 探内置候选清单
  python research\\probe_tenants.py --harvest URL   先从这些页面抓 *.zhiye.com 别名再探
  python research\\probe_tenants.py --only a,b,c    只探指定别名
结果打印到终端,并写 data/tenants_probe.json。确认要收编的再手工补进 tenants.py。
"""
import argparse, json, os, re, sys, urllib.request, concurrent.futures

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tenants import TENANTS

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

ALIAS_RE = re.compile(r"([a-z0-9][a-z0-9-]{2,30})\.zhiye\.com")
# 这些是子域前缀或平台自身,不是公司租户
NOT_TENANT = {"www", "campus", "m", "api", "static", "cdn", "job", "jobs", "hr",
              "recruit", "career", "test", "pre", "dev", "beisen", "cloud", "app"}

# 候选别名:中大型制造/医药/AI/软件公司,北森的主力客群
CANDIDATES = """
faw gac greatwall saic hongqi deepal voyah zeekr lynkco wanxiang banma
ubtrobot agibot galbot robotera dobot aubo jaka estun siasun sunplus rockchip
megvii sensetime faceplus paradigmtongdun tongdun belark bonc adlink
hikvision dahua dahuatech smic willsemi ehang goke hoperain sitoday 3peak
fii sunwoda atlb mclen lgcchem wistron quanta
goldwind tgood longi trinasolar jinkosolar sungrow calb easion greatpower
farasis hithium chinamoly crisovale enjsolar
yonyou kingdee digiwin inspur h3c lenovo tcl hisense konka changhong skyworth
yuyue acrobiosystem sinocare biocare wuxi aosa sansin mindraya
yili shuanghui guming luhav babytree chinaresources
zoomlion xcmg sunward liugong dovor crrc crrcgz sannio
kuayue junle bestex sto yto zto
hellobike2 aux chigo chando seeyon seiyu iu5
"""


def get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def harvest(urls):
    """从高校就业网/招聘聚合页里正则捞真实租户别名。"""
    found = set()
    for u in urls:
        try:
            html = get(u)
        except Exception as e:
            print(f"  抓不到 {u}:{type(e).__name__}", flush=True)
            continue
        hits = {m for m in ALIAS_RE.findall(html) if m not in NOT_TENANT}
        print(f"  {u} → {' '.join(sorted(hits)) or '(无)'}", flush=True)
        found |= hits
    return found


def probe(alias, cat=2):
    """返回 (alias, 校招数, 实习数, 是否存活)。解析不出 JSON 就算不存活。"""
    host = f"{alias}.zhiye.com"
    counts = {}
    for c in (cat, 3):
        # pageIndex 从 0 开始。这里只读 Count 判活,用 1 也不会错,但别照抄给采集脚本用
        body = json.dumps({"category": c, "pageIndex": 0, "pageSize": 10}).encode()
        req = urllib.request.Request(
            f"https://{host}/api/Jobad/GetJobAdPageList", data=body, method="POST",
            headers={"Content-Type": "application/json", "User-Agent": UA,
                     "Referer": f"https://{host}/campus/jobs",
                     "Origin": f"https://{host}"})
        try:
            with urllib.request.urlopen(req, timeout=12) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
            counts[c] = int(d.get("Count") or 0)
        except Exception:
            counts[c] = None
    alive = counts.get(2) is not None or counts.get(3) is not None
    return alias, counts.get(2), counts.get(3), alive


def main():
    ap = argparse.ArgumentParser(description="zhiye 租户探活")
    ap.add_argument("--harvest", nargs="*", default=[], help="从这些页面捞别名")
    ap.add_argument("--only", help="逗号分隔,只探这些")
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()

    if a.only:
        cands = [x.strip() for x in a.only.split(",") if x.strip()]
    else:
        cands = set(CANDIDATES.split()) | harvest(a.harvest)
        cands = sorted(cands - set(TENANTS) - NOT_TENANT)
    print(f"待探别名 {len(cands)} 个(已排除 {len(TENANTS)} 个在册租户)\n", flush=True)

    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for alias, xj, sx, alive in ex.map(probe, cands):
            rows.append({"tenant": alias, "campus": xj, "intern": sx, "alive": alive})
            mark = "活" if alive else "× "
            print(f"  {mark} {alias:<18} 校招={str(xj):<6} 实习={str(sx):<6}", flush=True)

    ok = sorted([r for r in rows if r["alive"]],
                key=lambda r: -(r["campus"] or 0) - (r["intern"] or 0))
    print(f"\n===== 存活 {len(ok)} / 探 {len(rows)} =====")
    for r in ok:
        print(f"  {r['tenant']:<18} 校招 {r['campus']:<5} 实习 {r['intern']}")
    dead = [r["tenant"] for r in rows if not r["alive"]]
    print(f"\n不通 {len(dead)} 个:" + " ".join(dead[:40]) + (" …" if len(dead) > 40 else ""))
    out = os.path.join(DATA, "tenants_probe.json")
    json.dump({"probed": len(rows), "alive": ok, "dead": dead},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n已写 {out}")
    print("把要收编的别名和中文名补进 research/tenants.py 的 TENANTS / COMPANY_CN。")


if __name__ == "__main__":
    main()
