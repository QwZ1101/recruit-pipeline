"""两个采集器(北森 zhiye / Moka)共用的一套口径。

为什么单独一个文件:岗位池要进同一次粗筛和同一个 top-N 窗口,打分尺子必须只有一份。
两边各写一遍的话,漂移了也没人发现 —— 精排拿到的就是两套标准量出来的岗位混排。

改这里等于改全池口径,会连带改变 shortlist.json 的内容,所以 scan_ai_jobs.py
留了 --rebuild-only:不联网、只用现有 ai_jobs.json 重建 shortlist,方便比对。
"""
import re

# 关键词三档:大模型相关的词权重最高,泛 AI 词次之,沾边的理工科词最低
TIERS = [
    (["大模型", "llm", "生成式", "agent", "rag", "多模态", "aigc", "智能体",
      "人工智能"], 30),
    (["算法", "机器学习", "深度学习", "nlp", "自然语言", "计算机视觉", "感知",
      "语音", "推荐系统", "数据挖掘", "ai"], 20),
    (["ai应用", "ai开发", "ai软件", "ai工程", "智能", "数据科学", "机器人",
      "python", "计算机"], 8),
]
MIN_SCORE = 28          # 低于这个分进不了 ai_jobs.json

CITY_RE = re.compile(r"(北京|上海|广州|深圳|杭州|成都|武汉|南京|苏州|西安|重庆|天津|"
                     r"长沙|郑州|合肥|青岛|济南|大连|宁波|厦门|福州|无锡|东莞|佛山|"
                     r"珠海|中山|惠州|芜湖|长春|沈阳|哈尔滨|石家庄|太原|南昌|昆明|"
                     r"贵阳|兰州|海口|三亚|乌鲁木齐|呼和浩特|海外|远程)")
DEGREE_RE = re.compile(r"(博士|硕士|研究生|本科|大专|专科|学历不限|不限学历)")
# 从最宽松到最严格,degree_of 按这个顺序取第一档命中的
LOOSEST_FIRST = ["学历不限", "不限学历", "大专", "专科", "本科", "研究生", "硕士", "博士"]
LOC_LINE = re.compile(r"工作地|工作地点|就业地|招聘地|常驻|地点|城市|base", re.I)

# 非开发序列:标题里有这些词就别进投递清单
EXCL = re.compile(r"设计师|产品经理|产品\b|测试|运营|项目经理|需求分析|管培|培训生|"
                  r"硬件|结构|标定|质量|采购|财务|人力|市场|供应链|法务|品牌|行政|后勤")
# 开发向标题。只用于北森那种上千条的大池子;Moka 是手动点名的少数几家,
# 标题写得不规范(「AI 搜索算法 / 架构工程师」根本不含"算法工程"连写),套这条会全被滤掉。
DEV = re.compile(r"应用研发|应用开发|Agent研发|Agent开发|agent开发|大模型应用|AI研发|"
                 r"AI软件|软件开发|工程开发|平台开发|推理工程|Infra|后端|全栈|算法工程|"
                 r"数据工程|智能体开发|AI工具")


def clean(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


MOKA_PREFIX = "moka:"


def is_moka(row):
    """tenant 带 moka: 前缀 = 从 Moka 站采来的岗位。北森的租户名是纯字母,不会撞。"""
    return str(row.get("tenant") or "").startswith(MOKA_PREFIX)


def cities_of(text):
    """"海外/远程"只在写明工作地的句子里才算工作地点,业务描述里的不算。"""
    hits = list(dict.fromkeys(CITY_RE.findall(text)))
    segs = re.split(r"[\n。;；、/]", text)
    return [c for c in hits
            if c not in ("海外", "远程") or any(c in s and LOC_LINE.search(s) for s in segs)]


def score(name, duty, require):
    """返回 (分数, 命中说明)。标题命中按双倍权重计。"""
    n = (name or "").lower()
    body = ((duty or "") + (require or "")).lower()
    s, why = 0, []
    for words, w in TIERS:
        hit = [x for x in words if x in n]
        if hit:
            s += w * 2
            why.append("标题:" + "/".join(hit[:3]))
        else:
            bh = [x for x in words if x in body]
            if bh:
                s += w
                why.append("JD:" + "/".join(bh[:3]))
    return s, ";".join(why[:2])


def degree_of(require):
    """取这份 JD 里**最宽松**的那档学历,不是第一条命中的。

    一页里写多个方向的站很常见(DeepSeek 的 Harness 团队页:研究员要硕士、
    研发工程师要"知名高校本科")。按第一条命中抽会抽成"硕士",这个岗位就被
    "本科可投"那道筛选误杀了。严格的"硕士及以上"另有 rank_jobs 的 DEG_BLOCK 拦。
    """
    hits = set(DEGREE_RE.findall(require or ""))
    for step in LOOSEST_FIRST:
        if step in hits:
            return step
    return None


def degree_line_of(require):
    """把 JD 里写明学历的那整行原样留一份,报告里要给人核对正则没抽错。"""
    return next((l.strip() for l in (require or "").split("\n") if DEGREE_RE.search(l)), None)


def shortlist_of(rows):
    """收窄成"本科可投 + 开发向"的投递候选,按分数降序、同公司同名去重。

    标题必须含开发字样这条只卡北森那种上千条的大池子。Moka 站是用户点名要看的少数
    几家,标题写得不规范(「AI 搜索算法 / 架构工程师」连"算法工程"都不连着写),
    套这条会把整家滤空。分数门槛和 EXCL 两边照旧都生效,不然法务必进清单。
    """
    cand = [r for r in rows
            if (r.get("degree") or "") in ("本科", "")
            and not EXCL.search(r["name"] or "")
            and (is_moka(r) or DEV.search(r["name"] or ""))]
    seen, out = set(), []
    for r in sorted(cand, key=lambda x: -x["score"]):
        k = (r["tenant"], clean(r["name"]).split("(")[0])
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out
