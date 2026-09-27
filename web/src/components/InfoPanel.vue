<script setup>
const props = defineProps({ data: Object })
const r = props.data.resume
const s = props.data.stats
const links = Object.entries(r.links || {}).filter(([, v]) => v && v !== 'null')
</script>

<template>
  <div class="meta">
    <div class="card">
      <div class="idx">简历画像 / data/resume.json</div>
      <h3>{{ r.name }} · {{ r.target_role }}</h3>
      <div class="kv"><span>学历</span><b>{{ r.school }}({{ r.school_tier }}){{ r.degree }} · {{ r.major }}</b></div>
      <div class="kv"><span>批次</span><b>{{ r.job_type }} · {{ r.graduation }} 届</b></div>
      <div class="kv"><span>意向城市</span><b>{{ (r.target_cities || []).join('/') || '简历已删除该行(接受异地)' }}</b></div>
      <div class="kv" v-for="[k, v] in links" :key="k"><span>{{ k }}</span><b><a :href="v" target="_blank">{{ v }}</a></b></div>
      <div class="kv"><span>自认短板</span><b>{{ (r.signals?.weaknesses || []).join(' / ') || '-' }}</b></div>
    </div>

    <div class="card">
      <div class="idx">管线与命令</div>
      <h3>数据单向进库,状态双向可写</h3>
      <p>
        <code class="cmd">python src\parse_resume.py "新版PDF路径"</code> 简历 → 画像<br />
        <code class="cmd">python src\rank_jobs.py</code> 门槛过滤 → embedding 粗筛 → LLM 精排<br />
        <code class="cmd">python src\store.py ingest</code> 把精排结果灌进 SQLite(不动状态)<br />
        <code class="cmd">python src\api.py</code> 起后端,本页读写都走它<br />
        <code class="cmd">python src\ledger.py init --from-rank</code> 新岗位入台账
      </p>
      <p class="hint">页面上点状态胶囊 = 后端 <code class="cmd">ledger.py</code> 的
        <code class="cmd">_set()</code>,和命令行同一条写路径、同一个状态机。</p>
    </div>

    <div class="card">
      <div class="idx">顶栏三个按钮</div>
      <h3>同步北森 / 同步预览 / 重载,各自干嘛</h3>
      <div class="kv"><span>同步北森</span><b>真写库。遍历台账里有 tenant 的公司,按 Cookie
        调 <code class="cmd">https://&lt;租户&gt;.zhiye.com/api/Submission/GetAllDeliveryRecord</code>,
        把北森侧真实投递记录(测评/笔试/面试邀请)翻成台账状态,<b>只往前往推、不后退</b>,
        本地更靠后的不覆盖。</b></div>
      <div class="kv"><span>同步预览</span><b>干跑(dry-run)。拉同样的数据但不写库,只列出
        "会把哪几条从 X 推到 Y"。先点这个确认 Cookie 没过期、不会误推,再点真同步。</b></div>
      <div class="kv"><span>重载</span><b>立刻 <code class="cmd">GET /api/pool</code>。
        页面平时每 12 秒自动静默刷一次(切到后台不刷),这个按钮是手动马上刷——
        命令行改了库、或刚同步完想立刻看到结果时用。</b></div>
      <p class="hint">同步结果会自动跳到"投递进展"tab 顶部的卡片里。Cookie 按租户隔离,
        存在 <code class="cmd">data/secrets/beisen_cookie.&lt;租户&gt;.txt</code>;
        过期了要重新登北森导一份,没有 Cookie 的租户这一步会在结果里说明,不算失败。</p>
    </div>

    <div class="card">
      <div class="idx">数据新鲜度</div>
      <h3>这一页读的是库,12 秒自动刷一次</h3>
      <div class="kv"><span>岗位池扫描</span><b>{{ s.pool_scanned_at || '-' }}</b></div>
      <div class="kv"><span>简历解析</span><b>{{ s.resume_parsed_at || '-' }}</b></div>
      <div class="kv"><span>岗位入 SQLite</span><b>{{ s.ingested_at || '-' }}</b></div>
      <div class="kv"><span>本次渲染</span><b>{{ data.generated_at }}</b></div>
      <div class="kv"><span>台账库</span><b>{{ data.ledger_db }}</b></div>
      <p class="hint">命令行改了库、或页面改了库,另一边下一刷就跟上。
        精排重跑后要 <code class="cmd">store.py ingest</code> 才看得到新岗位内容。</p>
    </div>

    <div class="card">
      <div class="idx">已知局限(别把页面数字当绝对)</div>
      <h3>三处口径要心里有数</h3>
      <ul>
        <li>分数是 LLM 给的,<b>同代码连跑 ±7 抖动</b>,只信档位不信名次</li>
        <li>北森接口 <b>不返回城市/学历</b>,这两个字段是从 JD 正文正则抽的,大量为空属正常</li>
        <li>状态自动同步只覆盖有 Cookie 的租户,当前 <b>2 / 6</b> 家;其余点状态胶囊手工流转</li>
      </ul>
      <p class="hint">本页含手机号/邮箱等个人信息与投递记录,后端<b>只绑 127.0.0.1</b>,
        不要部署到公网、不要提交进 git(.db / data.json / secrets 都已排除)。</p>
    </div>
  </div>
</template>
