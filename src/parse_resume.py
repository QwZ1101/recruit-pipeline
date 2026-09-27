"""简历解析:PDF → data/resume.json 结构化画像。

用 PyMuPDF 抽文本,qwen3.7-flash 抽取为固定 schema。
院校层次单独判定,后续用于卡"985/211/双一流/重点院校"这类硬门槛。
"""
import glob, json, os, sys

import pymupdf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dashscope_client import chat_json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "resume.json")

SCHEMA = """{
  "name": "姓名",
  "location": "现所在地",
  "target_role": "意向岗位",
  "target_cities": ["意向城市"],
  "job_type": "实习 | 校招 | 社招",
  "graduation": "YYYY-MM",
  "school": "学校全称",
  "school_tier": "985 | 211 | 双一流 | 普通公办本科 | 民办本科 | 专科 | 硕士 | 博士",
  "is_fresh_2027": true,
  "degree": "本科",
  "major": "专业",
  "class_rank": "专业排名,无则 null",
  "courses": ["主修相关课程"],
  "awards": [{"name": "", "year": "", "level": "省级/国家级/校级"}],
  "skills": {
    "llm_app": ["大模型应用相关技能,如 RAG/Prompt/Function Calling/Agent框架/向量库"],
    "lang_backend": ["编程语言与后端框架"],
    "data_infra": ["数据库/运维/工具"],
    "other": []
  },
  "projects": [{"name": "", "period": "", "role": "",
                "stack": ["用到的技术"], "points": ["要点原文"]}],
  "self_summary": "自我评价压缩成一句",
  "links": {"github": "仓库地址,无则 null", "demo": "可访问的在线Demo/项目集地址,无则 null",
            "blog": "技术博客地址,无则 null"},
  "signals": {
    "has_production_project": "是否有可验证的完整项目落地",
    "english": "四六级情况,无则 null",
    "weaknesses": ["客观短板,如学历层次/无实习经历/无大厂经历"]
  }
}"""

SYSTEM = (
    "你是校招简历解析器。把简历文本解析成指定 JSON 结构,只依据原文,不要编造。"
    "数组为空用 []。没提到的字段用 null。院校层次按中国高校常识客观判断,"
    "独立学院/民办院校必须归为「民办本科」,不要美化。"
    "简历中出现的 URL(GitHub 仓库、在线 Demo、项目集、技术博客)必须原样抽取到 links,"
    "一个都不能丢。项目要点保留原文技术用词(如「工作流编排」「版面分析」「全栈」),"
    "不要同义改写或省略。"
    "输出必须是单个合法 JSON 对象,不要任何解释文字。结构严格按:\n" + SCHEMA
)


def extract_text(pdf):
    doc = pymupdf.open(pdf)
    return "\n".join(p.get_text() for p in doc)


def main():
    pdf = sys.argv[1] if len(sys.argv) > 1 else \
        glob.glob(os.path.join(ROOT, "*.pdf"))[0]
    text = extract_text(pdf)
    print(f"简历: {os.path.basename(pdf)}  抽取 {len(text)} 字符")

    profile = chat_json(SYSTEM, text)
    if "_error" in profile:
        raise SystemExit(f"解析失败: {profile['_error']}")

    profile["_source_pdf"] = os.path.basename(pdf)
    profile["_raw_text"] = text
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(profile, open(OUT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"已写入 {OUT}\n")
    print(f"  姓名      : {profile.get('name')}")
    print(f"  意向      : {profile.get('target_role')} / {profile.get('job_type')}"
          f" / 城市={profile.get('target_cities')}")
    print(f"  学历      : {profile.get('school')}({profile.get('school_tier')}) "
          f"{profile.get('major')} {profile.get('degree')} "
          f"应届={profile.get('graduation')}")
    print(f"  LLM技能   : {profile.get('skills', {}).get('llm_app')}")
    print(f"  项目      : {[p.get('name') for p in profile.get('projects', [])]}")
    print(f"  短板      : {profile.get('signals', {}).get('weaknesses')}")


if __name__ == "__main__":
    main()
