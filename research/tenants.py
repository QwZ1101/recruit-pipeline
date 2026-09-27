TENANTS = [
    # 2026-09-22 首批 16 家
    "unitree", "iflytek", "intellif", "aispeech", "mthreads", "hellobike",
    "transsion", "auxgroup", "grantthornton", "mengniu", "changan", "chery",
    "sany", "weichai", "mindray", "kingmed",
    # 2026-09-25 用 probe_tenants.py 探活新增(括号内为当时校招+实习岗位数)
    "dahua",        # 195
    "h3c",          # 83
    "ubtrobot",     # 85
    "goldwind",     # 73
    "yzkgbdagroup",  # 73
    "tgood",        # 46
    "goke",         # 42
    "dobot",        # 39
    "siasun",       # 22
    "cscihk",       # 22
    "digiwin",      # 20
    "shuanghui",    # 18
    "ccdc",         # 12
    "banma",        # 3
    "sunwoda",      # 2
]

# 租户别名 → 公司中文名。接口返回里没有公司名,台账和报告要靠这张表让人看懂。
# 新增的中文名是抓各家门户 <title> 得到的,不要凭别名猜(tgood 是特锐德,不是特变电工)。
COMPANY_CN = {
    "chery": "奇瑞汽车", "transsion": "传音控股", "iflytek": "科大讯飞",
    "changan": "长安汽车", "mthreads": "摩尔线程", "aispeech": "思必驰",
    "hellobike": "哈啰", "sany": "三一重工", "unitree": "宇树科技",
    "mengniu": "蒙牛", "mindray": "迈瑞医疗", "weichai": "潍柴动力",
    "intellif": "云天励飞", "kingmed": "金域医学", "auxgroup": "奥克斯",
    "grantthornton": "致同", "beisen": "北森云计算",
    "dahua": "浙江大华", "h3c": "新华三", "ubtrobot": "优必选",
    "goldwind": "金风科技", "yzkgbdagroup": "亦庄控股", "tgood": "特锐德",
    "goke": "国科微", "dobot": "越疆机器人", "siasun": "新松机器人",
    "cscihk": "建投国际", "digiwin": "鼎捷数智", "shuanghui": "双汇发展",
    "ccdc": "中债登", "banma": "斑马网络", "sunwoda": "欣旺达",
    # Moka 站的键带 moka: 前缀,和北森租户分开,免得别名撞车
    "moka:high-flyer": "深度求索 DeepSeek",
    # 中文名一律抄自页面 <title>,不凭别名猜(见 MOKA_SITES 下面那段)
    "moka:moonshot": "月之暗面 Kimi", "moka:zuoyebang": "作业帮",
    "moka:tuya": "涂鸦智能", "moka:enflame": "燧原科技",
    "moka:zphz": "智谱", "moka:step": "阶跃 StepFun",
    "moka:dji": "大疆 DJI", "moka:yinhetongyong": "银河通用机器人",
    "moka:robotera": "星动纪元", "moka:iluvatar": "天数智芯",
}

# Moka 招聘站清单。它和北森不是一套系统:岗位接口一律返回密文,拿 curl 复现只能得到
# 一坨 base64,所以采集走 research/moka_collect.js(在浏览器里抄渲染好的页面),
# 合并走 research/merge_moka.py。org 就是 URL 里 /social-recruitment/<org>/<siteId>/ 那一段。
MOKA_SITES = {
    # 深度求索。注意:别名探到的默认站点 4604/4605 是**空站**(0 条),真正在招的是这个
    "high-flyer": {"siteId": 140576, "kind": "social"},   # 37 条在招(含实习)
    "moonshot": {"siteId": 148507, "kind": "campus"},     # 月之暗面 Kimi,93 条校招/实习
    "zuoyebang": {"siteId": 39595, "kind": "campus"},     # 作业帮,64 条 27 届秋招(卡片无 JD)
    "tuya": {"siteId": 147434, "kind": "campus"},         # 涂鸦智能,29 条(含 AI 开发实习生)
    "enflame": {"siteId": 168420, "kind": "campus"},      # 燧原科技,48 条(多为芯片,含运维 Agent 研发)
    "zphz": {"siteId": 148984, "kind": "campus"},         # 智谱,24 条(27 届校招 + 实习,Agent/应用开发方向)
    "step": {"siteId": 94905, "kind": "campus"},          # 阶跃 StepFun,127 条(Stepstar 计划 + 终端/安全工程)
    "dji": {"siteId": 143359, "kind": "campus"},          # 大疆,140 条(硬件为主,含大模型推理部署/AI 测开)
    "yinhetongyong": {"siteId": 165930, "kind": "campus"},  # 银河通用机器人,58 条(具身向,硕士居多)
    "iluvatar": {"siteId": 44785, "kind": "campus"},      # 天数智芯,9 条全是 IC/编译器/固件 → 0 条进池
    "robotera": {"siteId": 163878, "kind": "campus"},     # 星动纪元,4 条具身算法(硕士起步,由门槛层拦)
}
# 别名会撞车:agibot 探到的是「敏捷医疗」不是智元;公司中文名一律从页面 <title> 抄。
# 看过但不值得登记进来的:hncjjt(海南省财金集团)11 条全是社招管理岗,最轻的一条也要
# 硕士 + 10 年经验;海外 Lever 站(Palantir 等)则要工签,不在这个项目的能力范围内。
# 探活结果在 data/moka_sites_probe.json(18 家有站),这几家没登记的原因记在这:
#   jd / agora / agibot(是「敏捷医疗」不是智元) / moonshot 社招站默认站点 → 站点空或别名不对
#   iluvatar(天数智芯 9 条全是 IC/编译器/固件)、robotera(星动纪元 4 条全是具身算法,硕士起步)
#   xiaopeng 的 67918/150393 是**汇天**(飞行汽车)子站点,不是小鹏汽车主站,337 条几乎全是航空硬件
# 2026-09-27 晚又探了一批别名(证据清单在 probe 输出里),这些**页面能打开但校招站是空的**
# (标题正常、列表 0 条 —— 说明 org 对、siteId 是别的类目或压根没开放),别再重复采:
#   4paradigm 58145 / cloudwalk 4872 / keenon 24673 / hytera 182194 / tuhu 28398
# 这几家有站但和「AI 应用开发 + 本科」不搭,采了也是白采:
#   tal 好未来 164593(150 条,首屏 60 个标题零个技术岗)、shopee 150780(只剩 3 条管培)、
#   nbdeli 得力 70019(38 条,只有 1 条带 AI 字样的管培生)
