"""岗位匹配排序:硬门槛过滤 → embedding 粗筛 → LLM 精排 → 投递优先级报告。

输入: data/resume.json, data/shortlist.json
输出: data/match_result.json, data/verdict_cache.json, 投递优先级.md

精排结论按 (简历+提示词口径, JD 正文) 双指纹缓存,重跑只为新岗位花钱。
加 --fresh 忽略缓存全量重排。
"""
import json, os, re, sys, math, hashlib, concurrent.futures
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dashscope_client import embed, chat_json, CHAT_MODEL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "research"))     # 公司中文名表和采集端共用一份
from tenants import COMPANY_CN                         # noqa: E402
RESUME = json.load(open(os.path.join(ROOT, "data", "resume.json"), encoding="utf-8"))
JOBS = json.load(open(os.path.join(ROOT, "data", "shortlist.json"), encoding="utf-8"))

TOP_N = 30            # 粗筛保留数
# 新版简历刻意删掉了「意向城市」(8 个目标岗全在异地)。本地仍按南昌量化提醒。
TARGET_CITIES = [c for c in (RESUME.get("target_cities") or [])] or ["江西南昌"]
# 简历 PDF 里没有英语等级,这个事实只能由本人声明。改这一行即可切换门槛口径。
CET4_PASSED = False

# ---------- 任务2:硬门槛检测 ----------
DEG_BLOCK = re.compile(r"硕士及以上|硕士研究生及以上|博士|学历要求[:：]?\s*(硕士|博士)"
                       r"|统招硕士|211及以上.*硕士|硕士优先.*必须")
SCHOOL_BLOCK = re.compile(r"985|211|双一流|重点院校|C9|一本|QS\s*前"
                          r"|海外(?:留学|硕士)|老八所")
# "知名高校"这类没有名单的说法。只在 require 段里认它 —— 同一句写在 duty 里
# 常常是"与知名高校合作"这种业务描述,当成门槛就会误杀(海外/远程 已经踩过一次)。
SCHOOL_SOFT = re.compile(r"知名高校|名牌大学|顶尖院校|头部高校")
CET = re.compile(r"(?:通过|持有)?\s*(?:国家)?四级|CET-?4|大学英语四级")
CET6 = re.compile(r"六级|CET-?6")
YEAR27 = re.compile(r"2027届|27届")
YEAR26_ONLY = re.compile(r"2026届|26届")
CITY_RE = re.compile(r"(南昌|北京|上海|广州|深圳|杭州|成都|武汉|南京|苏州|西安|重庆|天津|"
                     r"长沙|郑州|合肥|青岛|济南|大连|宁波|厦门|福州|无锡|东莞|佛山|珠海|"
                     r"芜湖|长春|沈阳|哈尔滨|石家庄|太原|昆明|贵阳|兰州|海口|海外|远程)")
SKILL_RE = re.compile(r"(LangChain|LangGraph|LlamaIndex|RAG|Prompt|Function Calling|"
                      r"Agent|向量|Milvus|PGVector|Faiss|FAISS|Redis|Docker|FastAPI|"
                      r"PyTorch|大模型|LLM|Java|Spring|Python|Go|C\+\+|SQL|K8S|Kubernetes)")


def clean(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def site_of(job):
    """岗位来源站。北森租户是纯别名 → <alias>.zhiye.com;Moka 采来的带 moka: 前缀。"""
    t = job.get("tenant") or ""
    return f"app.mokahr.com/{t[5:]}" if t.startswith("moka:") else f"{t}.zhiye.com"


def COMPANY(alias):
    return COMPANY_CN.get(alias, alias)


LOC_LINE = re.compile(r"工作地|工作地点|就业地|招聘地|常驻|地点|城市|base", re.I)


def cities_of(text):
    """"海外/远程"只有出现在写明工作地的句子里才算工作地点。
    JD 里的「与海外开发者交流」「负责传音海外内容营销」是业务描述,
    当成城市会把岗位标成海外岗(实测误判过 2 个)。"""
    hits = set(CITY_RE.findall(text))
    segs = re.split(r"[\n。;；、/]", text)
    for amb in ("海外", "远程"):
        if amb in hits and not any(amb in s and LOC_LINE.search(s) for s in segs):
            hits.discard(amb)
    return sorted(hits)


def detect_gates(job):
    """从 JD 正文抽门槛。城市/学历字段接口里是 null,只能读文本。"""
    req = job.get("require") or ""
    duty = job.get("duty") or ""
    full = duty + "\n" + req + "\n" + (job.get("name") or "")
    school = SCHOOL_BLOCK.search(full) or SCHOOL_SOFT.search(req)
    g = {
        "blocked_degree": bool(DEG_BLOCK.search(req)),
        "blocked_school": bool(school),
        "need_cet4": bool(CET.search(req)),
        "need_cet6": bool(CET6.search(req)),
        "year_ok": bool(YEAR27.search(full)) or not YEAR26_ONLY.search(full),
        "cities": cities_of(full)[:6],
        "skills_wanted": sorted(set(SKILL_RE.findall(full)))[:14],
    }
    reasons = []
    if g["blocked_degree"]:
        reasons.append("明确要硕士及以上")
    if g["blocked_school"]:
        reasons.append(f"卡院校层次({school.group(0)})")
    if not g["year_ok"]:
        reasons.append("仅招2026届")
    if g["need_cet4"] and not CET4_PASSED:
        reasons.append("要求通过四级(未过线)")
    g["blockers"] = reasons
    g["eligible"] = not reasons
    return g


# ---------- 任务3:embedding 粗筛 ----------
def portfolio_links():
    lk = RESUME.get("links") or {}
    return "/".join(str(v) for v in lk.values() if v and v != "null")


def resume_card():
    s = RESUME["skills"]
    pj = RESUME.get("projects") or []
    main = pj[0] if pj else {}
    return " | ".join([
        f"求职意向:{RESUME.get('target_role')}({RESUME.get('job_type')})",
        f"学历:{RESUME.get('school_tier')}{RESUME.get('degree')}"
        f"{RESUME.get('major')},{RESUME.get('graduation')}届",
        "技能:" + "/".join(s.get("llm_app", []) + s.get("lang_backend", [])
                          + s.get("data_infra", [])),
        f"主项目:{main.get('name')} 技术栈={'/'.join(main.get('stack') or [])}",
        "项目成果:" + " ;".join((main.get("points") or [])[:3]),
        "可验证作品:" + (portfolio_links() or "无"),
        "课程:" + "/".join(RESUME.get("courses") or []),
    ])


def job_text(job):
    return " | ".join([
        f"岗位:{clean(job.get('name'))}",
        f"公司:{job.get('tenant')}",
        "职责:" + clean(job.get("duty"))[:700],
        "要求:" + clean(job.get("require"))[:700],
    ])


def cosine(a, b):
    d = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1
    nb = math.sqrt(sum(x * x for x in b)) or 1
    return d / (na * nb)


# ---------- 任务4:LLM 精排 ----------
SYSTEM = """你是严格的校招简历-岗位匹配评估器。候选人背景已在画像中给出,请诚实评估"这位候选人投这个岗位的通过概率",不要给鼓励性高分。

判定要求:
1. score 为 0-100 的综合匹配分。技能重合度权重最高,其次项目相关性,再次学历/院校门槛。
2. matched: 候选人确实具备且 JD 明确要求的技能点(必须两边都对得上,不能靠联想)。
3. gaps: 候选人缺失但 JD 要求的能力,按影响大小排列。
4. risk: 学历/院校/届别/英语等硬性风险,如果已不可绕过要明确说清。
5. advice 只能取 "投" | "观望" | "不投"。有不可绕过硬门槛时一律"不投"。
6. city_note: 若工作城市与候选人意向城市不一致,一句话说明。

以下三条是已经人工核对过的事实,必须遵守,违反即为错误评估:
A. 届别:候选人 2027-06 毕业,2026 年秋季正在招的 2027 届就是他的应届批次。
   不得以"大二/大三""非应届时间窗口""需确认是否实习转正"为由扣分。
B. 英语:候选人四级未过线。只在 JD 明确要求四级/六级/英语工作时计为风险;
   JD 未提英语时,**不要**用"大厂隐性英语门槛"这种推测扣分。
C. 编程语言:JD 写"Java/Python/Go 等至少一种"时,候选人会 Python 即视为完全满足,
   不得因缺 Java/Go 扣分;只有 JD 把某语言写成必备要求时才算 gap。
D. 作品可验证性:画像里"作品集链接"非空即代表有公网可访问的 Demo。若该 JD 把
   "可访问的 Demo / GitHub / 开源 / 技术博客"写成要求或加分项,必须计入 matched,
   并相应上调分数;链接缺失时不要假设候选人有作品仓库。

只输出一个合法 JSON 对象:
{"score":0,"matched":["..."],"gaps":["..."],"risk":["..."],"advice":"投","city_note":"","one_line":"一句话理由"}"""


def rerank(job):
    user = f"""【候选人画像】
学校/学历: {RESUME.get('school')}({RESUME.get('school_tier')}) {RESUME.get('degree')} {RESUME.get('major')}, {RESUME.get('graduation')} 届
意向: {RESUME.get('target_role')} / {RESUME.get('job_type')} / 意向城市 {TARGET_CITIES}
专业排名: {RESUME.get('class_rank')}
英语水平: {'已过四级' if CET4_PASSED else '四级未过线'}
大模型技能: {RESUME['skills'].get('llm_app')}
编程/后端: {RESUME['skills'].get('lang_backend')}
数据/工具: {RESUME['skills'].get('data_infra')}
主项目: {json.dumps(RESUME['projects'][0], ensure_ascii=False)[:1200]}
证书: {json.dumps(RESUME.get('awards'), ensure_ascii=False)[:300]}
作品集链接: {portfolio_links() or '无'}
已检测硬门槛: {json.dumps(job['gates'], ensure_ascii=False)}

【岗位 JD】
{job_text(job)}
"""
    r = chat_json(SYSTEM, user)
    return r if "_error" not in r else {"score": job.get("_cos", 0), "advice": "观望",
                                        "one_line": "LLM 调用失败,回退相似度",
                                        "matched": [], "gaps": [], "risk": [],
                                        "_error": r["_error"]}


CACHE = os.path.join(ROOT, "data", "verdict_cache.json")


def _dig(*parts):
    return hashlib.md5("␟".join(parts).encode("utf-8")).hexdigest()[:12]


def jd_key(j):
    return _dig(clean(j.get("name")), j.get("duty") or "", j.get("require") or "")


def rubric_key():
    """简历/提示词/英语口径/评判模型 一改,旧结论就不作数了——不然改了还在吃老分数。
    模型名必须算进来:换模型后不复用,否则缓存会让切换看起来"没生效"。"""
    return _dig(resume_card(), SYSTEM, str(CET4_PASSED), CHAT_MODEL)


def load_cache():
    if "--fresh" in sys.argv or not os.path.exists(CACHE):
        return {}
    try:
        return json.load(open(CACHE, encoding="utf-8"))
    except ValueError:
        return {}


def reusable(cache, j):
    e = cache.get(j["id"]) or {}
    return bool(e.get("v")) and e.get("k") == rubric_key() and e.get("h") == jd_key(j)


def main():
    print(f"岗位池 {len(JOBS)} 个(来自 data/shortlist.json)\n")

    # 任务2
    for j in JOBS:
        j["gates"] = detect_gates(j)
    elig = [j for j in JOBS if j["gates"]["eligible"]]
    blocked = [j for j in JOBS if not j["gates"]["eligible"]]
    print(f"[硬门槛] 可投 {len(elig)} / 被门槛卡掉 {len(blocked)}")
    for j in blocked:
        print(f"   ✗ {j['tenant']:<12} {clean(j['name'])[:40]:<42} {j['gates']['blockers']}")

    # 任务3
    vecs = embed([resume_card()] + [job_text(j) for j in elig])
    rv, jv = vecs[0], vecs[1:]
    for j, v in zip(elig, jv):
        j["_cos"] = round(cosine(rv, v), 4)
    elig.sort(key=lambda x: -x["_cos"])
    picked = elig[:TOP_N]
    print(f"\n[粗筛] embedding 相似度 top {TOP_N}:")
    for j in picked[:12]:
        print(f"   {j['_cos']:.4f}  {j['tenant']:<12} {clean(j['name'])[:46]}")

    # 任务4
    cache = load_cache()
    todo = [j for j in picked if not reusable(cache, j)]
    for j in picked:
        if reusable(cache, j):
            j["verdict"] = cache[j["id"]]["v"]
    print(f"\n[精排] 候选 {len(picked)} 个:复用旧结论 {len(picked) - len(todo)} 个,"
          f"调用 LLM {len(todo)} 个(--fresh 强制全量重排)")
    if "--plan" in sys.argv:
        # 池子一大,最先要回答的是"这次要付几次调用",所以留个只看不动的挡
        for j in todo:
            print(f"   待精排 {j['tenant']:<18} {clean(j['name'])[:44]}"
                  f"  cos={j['_cos']:.4f}")
        print(f"\n--plan:就到这里,一次 LLM 都没调,match_result.json 还是旧的。")
        return
    if todo:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            res = list(ex.map(rerank, todo))
        for j, r in zip(todo, res):
            j["verdict"] = r
            if "_error" not in r:      # 调用失败的兜底分不进缓存,否则永远不再重算
                cache[j["id"]] = {"k": rubric_key(), "h": jd_key(j), "v": r,
                                  "at": datetime.now().strftime("%Y-%m-%d")}
        json.dump(cache, open(CACHE, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

    ranked = sorted(picked, key=lambda x: -(x["verdict"].get("score") or 0))
    stats = {"pool": len(JOBS), "eligible": len(elig), "blocked": len(blocked),
             "ranked": len(ranked),
             "cet4_excluded": sum(1 for j in blocked if j["gates"]["need_cet4"])}
    json.dump({"resume_card": resume_card(), "jobs": ranked,
               "blocked": blocked, "stats": stats},
              open(os.path.join(ROOT, "data", "match_result.json"), "w",
                   encoding="utf-8"), ensure_ascii=False, indent=1)

    write_report(ranked, blocked, stats)
    print(f"\n已生成 data/match_result.json 与 投递优先级.md")
    # 顺手灌进 SQLite:看板/后端只读库,不再让人多跑一步
    import store
    print("已灌入台账库:", store.ingest()["pool"], "行岗位数据")
    return ranked


def write_report(ranked, blocked, stats):
    L = []
    A = L.append
    A("# 投递优先级清单\n")
    A(f"- 候选人:{RESUME['name']} · {RESUME['school']}({RESUME['school_tier']})"
      f" · {RESUME['graduation']} 届 · 意向 {RESUME['target_role']}\n")
    A(f"- 岗位池:{stats['pool']} 个本科向 AI 岗 → 过完硬门槛 **{stats['eligible']}** 个可投"
      f"({stats['blocked']} 个被门槛卡掉)→ 精排取前 {stats['ranked']}\n")

    city_hit = [j for j in ranked if "南昌" in (j["gates"]["cities"] or [])]
    A("## 一、两个必须先解决的门槛\n")
    if stats.get("cet4_excluded"):
        A(f"1. **英语四级**:已确认未过线。池中有 **{stats['cet4_excluded']}** 个岗位"
          f"在 JD 中明确要求「通过国家四级」,已在第四节整体排除,长安系集中于此。"
          f"结论:不要在长安系上花时间;若之后补过四级,可回来重投。\n")
    A(f"2. **意向城市**:意向 {TARGET_CITIES},精排池里落在南昌的 **{len(city_hit)}** 个。"
      f"北森多数岗位不在 JD 里写城市(下表「未标注」即此),需逐个点开链接确认;"
      f"若不接受异地,可投范围会大幅收缩。\n")
    ct = {}
    for j in ranked:
        for c in (j["gates"]["cities"] or ["未标注"]):
            ct[c] = ct.get(c, 0) + 1
    top_city = sorted(ct.items(), key=lambda kv: -kv[1])[:8]
    A("   - 实际城市分布:" + " · ".join(f"{c}{n}" for c, n in top_city) + "\n")

    A("\n## 二、建议投递顺序\n")
    A("| # | 匹配分 | 结论 | 公司 | 岗位 | 城市 | 说明 |")
    A("|---|---|---|---|---|---|---|")
    for i, j in enumerate(ranked, 1):
        v = j["verdict"]
        A(f"| {i} | {v.get('score')} | **{v.get('advice')}** | {j['tenant']} "
          f"| {clean(j['name'])[:34]} | {'/'.join(j['gates']['cities']) or '-'} "
          f"| {clean(v.get('one_line'))[:60]} |")

    A("\n## 三、逐岗位详情\n")
    for i, j in enumerate(ranked, 1):
        v = j["verdict"]
        A(f"### {i}. {clean(j['name'])}")
        A(f"- 公司:`{COMPANY(j['tenant'])}` · `{site_of(j)}` · {j['type']} · "
          f"匹配分 **{v.get('score')}** · 结论 **{v.get('advice')}**")
        A(f"- 城市:{'/'.join(j['gates']['cities']) or 'JD 未标注'}"
          f" · 需四级:{'是' if j['gates']['need_cet4'] else '否'}")
        A(f"- 岗位链接:{j['url']}")
        if v.get("matched"):
            A(f"- **匹配点**:" + ";".join(v["matched"][:5]))
        if v.get("gaps"):
            A(f"- **能力差距**:" + ";".join(v["gaps"][:5]))
        if v.get("risk"):
            A(f"- **风险**:" + ";".join(v["risk"][:4]))
        if v.get("city_note"):
            A(f"- **城市**:{clean(v['city_note'])}")
        A(f"- **一句话**:{clean(v.get('one_line') or '')}\n")

    if blocked:
        A("\n## 四、因硬门槛被排除(不必浪费投递)\n")
        A("| 公司 | 岗位 | 卡在哪 |")
        A("|---|---|---|")
        for j in blocked:
            A(f"| {j['tenant']} | {clean(j['name'])[:38]} "
              f"| {';'.join(j['gates']['blockers'])} |")

    A("\n> 说明:北森接口不返回城市/学历字段(企业未填),以上门槛与城市均由 "
      "JD 正文正则抽取,可能有漏判;投递前请点开链接核对原文。\n")

    open(os.path.join(ROOT, "投递优先级.md"), "w", encoding="utf-8").write("\n".join(L))


def report_only():
    """改报告文案/门槛口径时用:门槛是纯正则可确定性重算,只复用已存的 LLM 精排结果。"""
    d = json.load(open(os.path.join(ROOT, "data", "match_result.json"),
                       encoding="utf-8"))
    verdicts = {j["id"]: j["verdict"] for j in d["jobs"]}
    for j in JOBS:
        j["gates"] = detect_gates(j)
    elig = [j for j in JOBS if j["gates"]["eligible"]]
    blocked = [j for j in JOBS if not j["gates"]["eligible"]]
    ranked = []
    for j in elig:
        if j["id"] in verdicts:
            j["verdict"] = verdicts[j["id"]]
            ranked.append(j)
    ranked.sort(key=lambda x: -(x["verdict"].get("score") or 0))
    stats = {"pool": len(JOBS), "eligible": len(elig), "blocked": len(blocked),
             "ranked": len(ranked),
             "cet4_excluded": sum(1 for j in blocked if j["gates"]["need_cet4"])}
    write_report(ranked, blocked, stats)
    print(f"已重渲染 投递优先级.md(未调用 LLM):可投 {len(elig)},"
          f"其中 {stats['ranked']} 个已有精排结论,被排除 {len(blocked)}")


if __name__ == "__main__":
    if "--report-only" in sys.argv:
        report_only()
    else:
        main()
