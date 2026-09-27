"""批量探 Moka 招聘站:哪些公司在 app.mokahr.com 上有自己的站点,siteId 是多少。

原理(实测,2026-09-27):
  GET https://app.mokahr.com/<social|campus>-recruitment/<org>/        ← 不给 siteId
    · 组织存在 → 302,Location 里就是它**默认站点**的 siteId
    · 不存在   → 200(SPA 外壳,任何路径都给),所以只能看 Location,不能看状态码
  拿到 siteId 才能拼出采集器要用的列表页 URL。

为什么不逆向接口:Moka 的 jobs/v2 返回 necromancer 密文,见 moka_collect.js 顶部说明。
这里只探"这个 URL 存不存在",和一个人手敲地址栏等价。

用法:  python research\\probe_moka.py              # 探 SLUGS 里预置的一批
        python research\\probe_moka.py a b c        # 探命令行给的别名
结果写 data/moka_sites_probe.json,人挑值得登记的抄进 tenants.py 的 MOKA_SITES。
"""
import concurrent.futures
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

BASE = "https://app.mokahr.com"
KINDS = ("social", "campus")
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# 别名是公司在 Moka 后台自己起的,没有规律:英文品牌名、拼音、缩写都有。
# 这一批是"本科可投的 AI 应用/Agent 开发岗"这个目标下值得先试的公司。
SLUGS = [
    # AI 大模型公司
    "moonshot", "kimi", "high-flyer", "deepseek", "zhipu", "zhipuai", "zph",
    "minimax", "xinxi", "stepfun", "jieyue", "01ai", "lingyi", "wanwu",
    "baichuan", "shengshu", "pixverse", "siliconflow", "wutong", "infinigence",
    "agibot", "galbot", "robotera", "spirit-ai", "galaxea", "flexiv", "jaka",
    "fourier", "limxdynamics", "noematrix", "booster", "dptech", "isc",
    # 机器人/智能硬件(部分已在北森池里,双站点的情况存在)
    "unitree", "ubt", "xiaopeng", "lixiang", "nio", "zeekr", "chery", "iflytek",
    "momenta", "horizon", "sensetime", "megvii", "dagurobot", "tuyoda",
    # 互联网/消费电子里出了名用 Moka 的
    "zuoyebang", "keep", "yuanqisenlin", "miniso", "popmart", "instas", "anker",
    "tuya", "agora", "youzan", "gitee", "jd", "sogou", "sohu", "huya", "douyu",
    "miHoYo", "yostar", "ligtechnology", "infinix", "transsion", "haier",
    # 具身/芯片/AI Infra 初创
    "mthreads", "iluvatar", "enflame", "horizonrobotics", "intellif",
    "aispeech", "banma", "dahua", "realsense", "united Imaging",
]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None      # 返回 None ⇒ urlopen 抛 HTTPError,302 本身就是要读的东西


_opener = urllib.request.build_opener(_NoRedirect)


def probe(org, kind):
    """返回 (org, kind, siteId 或 None)。None = 这个别名在 Moka 上没有站点。"""
    url = f"{BASE}/{kind}-recruitment/{org}/"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with _opener.open(req, timeout=15) as r:
            loc = r.geturl()                     # 200 是 SPA 外壳,路径不会多出 siteId
    except urllib.error.HTTPError as e:          # 302:Location 里就是默认站点 id
        loc = e.headers.get("Location") or ""
    except Exception:
        return org, kind, None
    tail = loc.rstrip("/").split("/")[-1]
    return org, kind, (tail if tail.isdigit() and len(tail) >= 3 else None)


def main():
    slugs = sys.argv[1:] or SLUGS
    jobs = [(o, k) for o in slugs for k in KINDS]
    found = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        for org, kind, sid in ex.map(lambda a: probe(*a), jobs):
            if sid:
                found.setdefault(org, {})[kind] = int(sid)
                print(f"  ✓ {org:<20} {kind:<7} siteId={sid}", flush=True)
    miss = [o for o in slugs if o not in found]
    print(f"\n探完 {len(slugs)} 个别名:命中 {len(found)} 家,无站点 {len(miss)} 家")
    if miss:
        print("  未命中(不代表公司不用 Moka,只是这个别名不对):" + ", ".join(miss))
    out = os.path.join(DATA, "moka_sites_probe.json")
    old = json.load(open(out, encoding="utf-8")) if os.path.exists(out) else {}
    old.update({o: v for o, v in found.items() if v})
    old["_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    json.dump(old, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"已合并写入 {out}(累计 {len([k for k in old if not k.startswith('_')])} 家)")
    print("下一步:挑出与 AI 应用开发相关的,抄进 research/tenants.py 的 MOKA_SITES,再用浏览器采集")


if __name__ == "__main__":
    main()
