# 北森 zhiye 租户 AI 岗位调研报告

调研时间:2026-09-22 · 目标:AI 大模型应用开发 / AI 应用开发 · 范围:2027 届校招 + 实习

## 一、接口结论(适配器地基)

| 项 | 结论 |
|---|---|
| 鉴权 | **无需登录**,无签名、无 token,普通 HTTP 即可 |
| 列表 | `POST /api/Jobad/GetJobAdPageList` body `{"category":2,"pageIndex":N,"pageSize":10}` |
| 类目 | `category` 1=社招 2=校招 3=实习 |
| 详情 | `GET /api/Jobad/GetJobAdInfo?jobAdId=<uuid>`(字段与列表相同,无额外信息) |
| 详情页 | `https://{tenant}.zhiye.com/campus/detail?jobAdId=<uuid>` |
| 投递记录 | `POST /api/Submission/GetAllDeliveryRecord`(需本人登录 Cookie)→ 台账自动更新用 |

### 两个必须写进适配器的坑

1. **`pageSize` 只能用 10。** 20/50/100 会返回不完整页甚至空 `Data`,而 `Count` 依然正确 —— 极易造成"静默漏数据"。实测 unitree:`ps=10`→10 条,`ps=20`→14 条,`ps=30`→4 条,`ps=50`→0 条。
2. **`keyWords` 服务端过滤不可用于取数。** `Count` 准确(如 chery「算法」2293→236),但 `Data`  frequently 为空。只能全量拉取后本地过滤。
   - 非限流所致:同参数连打 5 次结果稳定。

### 字段可用性

列表与详情都**只有 9 个字段有值**:`Id / JobAdId / JobAdName / OrgId / CategoryId / Duty / Require / Status / ChangeDate`。

`Station`(城市)、`Degree`(学历)、`EndTime`(截止)、`Welfare` 全部为 `null` —— 是企业在 ATS 里没填,不是接口缺陷。
**城市与学历必须从 `Require` / `JobAdName` 文本正则抽取**(本次调研即如此处理)。
好消息:`Duty` + `Require` 是**完整全文**,足够做 embedding 匹配和 LLM 精排。

## 二、存活租户(16 家,已验证接口可用)

探测 ~110 个候选子域名,16 家存活。无效租户会返回 HTTP 200 + 非 JSON(通配 DNS),需按"能否解析 JSON"判定,不能只看状态码。

| 租户 | 公司 | 校招岗位数 | AI 相关命中 |
|---|---|---|---|
| chery | 奇瑞汽车 | 2293 | 392 |
| transsion | 传音控股 | 195 | 132 |
| iflytek | 科大讯飞 | 120 | 57 |
| changan | 长安汽车 | 256 | 57 |
| mthreads | 摩尔线程 | 55 | 50 |
| aispeech | 思必驰 | 38 | 27 |
| hellobike | 哈啰 | 44 | 19 |
| sany | 三一重工 | 91 | 14 |
| unitree | 宇树科技 | 34 | 14 |
| mengniu | 蒙牛 | 95 | 14 |
| mindray | 迈瑞医疗 | 58 | 10 |
| weichai | 潍柴动力 | 31 | 5 |
| intellif | 云天励飞 | 14 | 3 |
| kingmed | 金域医学 | 35 | 2 |
| auxgroup | 奥克斯 | 67 | 1 |
| grantthornton | 致同 | 8 | 0 |

合计命中 AI 相关岗位 **797 个**(含社招误入已排除,仅校招+实习)。

> 注:`beisen.zhiye.com` 是北森自己公司门户,校招仅 22 个岗位且**无一个 AI 岗**,只适合当接口调试夹具。

## 三、关键发现:学历门槛

**797 个 AI 岗中,402 个(50%)明确写硕士及以上。**

但分层看差异极大:

| 方向 | 本科友好度 |
|---|---|
| 算法研究 / 具身智能 / 感知算法 | 差,普遍硕士起步(宇树、迈瑞、奇瑞研究院) |
| **AI 应用开发 / Agent 工程** | **好,本科为主,部分不限学历** |

→ **选「AI 应用开发」而非「算法工程师」是正确的**,这个方向的本科可投比例显著更高。

筛选后:**本科可投 + 开发向 AI 岗 = 78 个**(见 `data/shortlist.json`)。
按租户:chery 22 · transsion 20 · iflytek 12 · unitree 5 · sany 5 · changan 4 · mthreads 3 · aispeech 2 · hellobike 2 · weichai 2 · intellif 1

## 四、最贴合意向的岗位(TOP)

**1. 思必驰 · AI Agent 研发工程师-2027届**(本科)
> 计算机/软件工程/人工智能相关专业本科及以上;熟练 Python,具备后端服务开发能力;熟悉大模型 API、Prompt Engineering、Function Calling 和结构化输出;熟悉 LangChain、LangGraph、LlamaIndex
https://aispeech.zhiye.com/campus/detail?jobAdId=9d05e981-7bbd-4042-86d3-a361feb7036a

**2. 哈啰 ·【英才2027】AI应用开发-软件研发中心**(本科)
> 本科及以上,计算机相关专业;熟练 Java、JVM、Spring Boot;了解 LangChain、LlamaIndex
https://hellobike.zhiye.com/campus/detail?jobAdId=f05ebb47-fb4b-470b-b218-54ce8c68267f

**3. 科大讯飞 · AI Agent 应用研发工程师**(学历未标注,明确"专业背景不是绝对限制")
> 熟练 Python/Java/Go/C++/TS 至少一种;**真正动手完成过一个大模型应用、AI Agent、智能助手或自动化工具**
https://iflytek.zhiye.com/campus/detail?jobAdId=2ca30bc1-4bec-46f5-9dee-6b7c050fac3a

**4. 传音 · AI Agent 工程开发工程师**(本科,硕士优先)
> 精通 Python 工程开发、异步编程、FastAPI/Flask;熟悉 SQL、Redis、向量数据库(Milvus/PGVector/Faiss 任一);了解 Docker
https://transsion.zhiye.com/campus/detail?jobAdId=0703c5c3-b3b4-4e83-8f7d-e3180e52c4c5

**5. 传音 · Data Agent 研发工程师**(本科,2027届)
> 了解大模型应用开发相关技术,对 Prompt、RAG、Agent、工作流编排有学习热情
https://transsion.zhiye.com/campus/detail?jobAdId=79779d91-c142-4d59-b45b-3eaefb9562eb

**6. 长安 · 深蓝汽车-AI应用开发**(本科,2027届,需英语四级)
https://changan.zhiye.com/campus/detail?jobAdId=10a58757-9ab7-41f9-a929-0b53864ea6ea

**7. 科大讯飞 · AI全栈开发工程师**(本科)
https://iflytek.zhiye.com/campus/detail?jobAdId=b8358011-2f06-4681-8042-39a8d73ed786

## 五、能力要求聚类(78 个岗位提取)

高频技能栈高度收敛,可直接当作学习清单:

```
必选  Python(几乎所有岗位)
      大模型 API 调用 + Prompt Engineering
      RAG / Function Calling / Agent Workflow
      向量数据库(Milvus / PGVector / Faiss 任一)
常见  Agent 框架:LangChain / LangGraph / LlamaIndex
      Web 后端:FastAPI / Flask(部分要 Java + Spring Boot)
      SQL / Redis / Docker
加分   PyTorch、LoRA/微调、分布式、C++/Go/Rust
软性  "有真实项目经历,课程/竞赛/个人/开源项目均可"(讯飞原文)
```

**多个岗位明确接受"个人项目"** —— 本项目(自动投递助手)本身就正好覆盖:数据采集适配器、embedding 匹配、LLM 精排、Agent 编排。技术栈与目标岗位重合度很高。

## 六、复现方式

```bash
cd research
python scan_ai_jobs.py     # 全量扫描 → data/ai_jobs.json(797 条)
                           # 再按学历/方向过滤去重 → data/shortlist.json(78 条)
```

`tenants.py` 为存活租户清单,新增租户只需追加 alias。
