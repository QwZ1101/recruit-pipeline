<script setup>
import { computed, onBeforeUnmount, onMounted, provide, ref } from 'vue'
import StatBar from './components/StatBar.vue'
import { tier } from './fmt.js'
import { api } from './api.js'
import FilterBar from './components/FilterBar.vue'
import JobTable from './components/JobTable.vue'
import ProgressTable from './components/ProgressTable.vue'
import BlockedTable from './components/BlockedTable.vue'
import InfoPanel from './components/InfoPanel.vue'

const data = ref(null)
const err = ref('')
const tab = ref('jobs')
const filters = ref({ company: '', status: '', advice: '', tier: '', q: '' })
const busy = ref(false)
const toast = ref(null)
const syncing = ref(null)
const agoSec = ref(999)          // 距上次成功 load 的秒数,顶栏显示用
let timer = null
let tipTimer = null
let agoTimer = null

function onVisible() {
  if (!document.hidden) load()
}

function say(text, kind = 'good') {
  toast.value = { text, kind }
  clearTimeout(tipTimer)
  tipTimer = setTimeout(() => (toast.value = null), 3200)
}

async function load(quiet = true) {
  try {
    data.value = await api.pool()
    err.value = ''
    agoSec.value = 0
  } catch (e) {
    // 轮询失败通常是后端停了,已经渲染的数据就别清掉
    if (!quiet || !data.value) {
      err.value = '连不上后端:' + (e.message || e) +
        '。在项目根跑 python src\\api.py(只听 127.0.0.1:8000)'
    }
  }
}

// 手动重载:给个明确反馈,别让用户点了不知道刷没刷成
async function reload() {
  await load(false)
  if (!err.value) say('已刷新')
}

const agoText = computed(() => {
  const s = agoSec.value
  if (s >= 999) return ''
  if (s < 4) return '刚刚'
  if (s < 60) return s + 's 前'
  const m = Math.floor(s / 60)
  return m + 'm' + (s % 60) + 's 前'
})

async function setStatus(job, p) {
  busy.value = true
  try {
    const r = await api.setStatus(job.id, p)
    data.value = r.pool
    say(r.msg)
    return true
  } catch (e) {
    say('没改成:' + (e.message || e), 'bad')
    return false
  } finally {
    busy.value = false
  }
}

async function addNote(job, text) {
  busy.value = true
  try {
    const r = await api.note(job.id, text)
    data.value = r.pool
    say('已记备注')
    return true
  } catch (e) {
    say('没记下:' + (e.message || e), 'bad')
    return false
  } finally {
    busy.value = false
  }
}

async function runSync(dryRun) {
  busy.value = true
  syncing.value = { running: true, lines: [] }
  try {
    const r = await api.sync({ dry_run: !!dryRun })
    syncing.value = { running: false, lines: r.lines, changed: r.changed }
    tab.value = 'progress'   // 结果卡片在进展页,不跳过去就看不到
    await load()
    say(dryRun ? `预览:可前进 ${r.changed} 条` : `北森同步完成,前进 ${r.changed} 条`)
  } catch (e) {
    syncing.value = { running: false, lines: ['同步失败:' + (e.message || e)], changed: 0 }
  } finally {
    busy.value = false
  }
}

// 状态机规则只在后端一份,前端从这里取着渲染,不自己判
provide('ledger', {
  get transitions() { return data.value?.transitions || {} },
  get statuses() { return data.value?.statuses || [] },
  get busy() { return busy.value },
  setStatus, addNote, runSync,
})

onMounted(() => {
  load(false)
  // CLI 那边改了库,页面 12s 内跟上;切到别的窗口就不刷,省得抢 SQLite 写锁
  timer = setInterval(() => { if (!document.hidden && !busy.value) load() }, 12000)
  agoTimer = setInterval(() => { if (!document.hidden) agoSec.value++ }, 1000)
  document.addEventListener('visibilitychange', onVisible)
})
onBeforeUnmount(() => {
  clearInterval(timer)
  clearTimeout(tipTimer)
  clearInterval(agoTimer)
  document.removeEventListener('visibilitychange', onVisible)
})

const jobs = computed(() => data.value?.jobs || [])
const tracked = computed(() => jobs.value.filter(j => j.status !== '未入台账'))
const blocked = computed(() => data.value?.blocked || [])

const visible = computed(() => {
  const f = filters.value
  const q = f.q.trim().toLowerCase()
  return jobs.value.filter((j) => {
    if (f.company && j.company !== f.company) return false
    if (f.status && j.status !== f.status) return false
    if (f.advice && j.advice !== f.advice) return false
    if (f.tier && tier(j.score) !== f.tier) return false
    if (q) {
      const hay = [j.name, j.company, j.one_line, (j.skills || []).join(' '), j.require]
        .join(' ').toLowerCase()
      if (!hay.includes(q)) return false
    }
    return true
  })
})
</script>

<template>
  <header class="topbar">
    <div class="topbar-inner">
      <div class="brand">
        <h1>智能投递看板 · 2027 届校招</h1>
        <p>{{ data?.resume?.name || '' }} · {{ data?.resume?.target_role || '' }} ·
          {{ data?.resume?.school || '' }}({{ data?.resume?.school_tier || '' }}) ·
          {{ data?.resume?.graduation || '' }} 届</p>
      </div>
      <div class="top-stats" v-if="data">
        <div class="top-stat"><b>{{ data.stats.pool }}</b><span>本科可投池</span></div>
        <div class="top-stat"><b>{{ data.stats.ranked }}</b><span>进入精排</span></div>
        <div class="top-stat"><b>{{ tracked.filter(j => ['已投','笔试','面试','offer'].includes(j.status)).length }}</b><span>已投出</span></div>
        <div class="top-stat"><b>{{ tracked.filter(j => j.status === '待投').length }}</b><span>待投</span></div>
        <div class="top-stat"><b style="font-size:14px;color:var(--muted)">{{ data.generated_at }}</b><span>库最近写入</span></div>
        <div class="top-stat"><b style="font-size:14px;color:var(--muted)">{{ agoText || '—' }}</b><span>页面刷新</span></div>
      </div>
      <div class="topbtn">
        <button class="btn" :disabled="busy" @click="runSync(false)"
                title="遍历台账里有 Cookie 的租户,拉北森侧真实投递记录,把状态只往前往推(写库,本地更靠后的不覆盖)">
          {{ syncing?.running ? '同步中…' : '同步北森' }}
        </button>
        <button class="btn ghost" :disabled="busy" @click="runSync(true)"
                title="和「同步北森」拉同样的数据,但不写库,只预览会把哪几条从 X 推到 Y">
          同步预览
        </button>
        <button class="btn ghost" @click="reload"
                title="立刻重拉 /api/pool(页面平时每 12s 自动静默刷一次,切到后台不刷)">
          重载
        </button>
      </div>
    </div>
  </header>

  <div v-if="toast" class="toast" :class="toast.kind">{{ toast.text }}</div>

  <main class="wrap">
    <p v-if="err" class="pill red banner">{{ err }}</p>
    <template v-else-if="data">
      <StatBar :stats="data.stats" :tracked="tracked" />

      <nav class="tabs">
        <button class="tab" :class="{ on: tab === 'jobs' }" @click="tab = 'jobs'">
          推荐岗位<i>{{ jobs.length }}</i></button>
        <button class="tab" :class="{ on: tab === 'progress' }" @click="tab = 'progress'">
          投递进展<i>{{ tracked.length }}</i></button>
        <button class="tab" :class="{ on: tab === 'blocked' }" @click="tab = 'blocked'">
          被硬门槛挡住<i>{{ blocked.length }}</i></button>
        <button class="tab" :class="{ on: tab === 'info' }" @click="tab = 'info'">
          数据说明</button>
      </nav>

      <template v-if="tab === 'jobs'">
        <FilterBar v-model="filters" :jobs="jobs" />
        <p class="hint" style="margin:-8px 0 10px">筛出 {{ visible.length }} / {{ jobs.length }} 条 ·
          点行展开看 JD · 点状态胶囊直接改流转 · {{ data.score_note }}</p>
        <JobTable :rows="visible" />
      </template>

      <ProgressTable v-else-if="tab === 'progress'" :rows="tracked"
                     :history="data.history" :sync="syncing" />
      <BlockedTable v-else-if="tab === 'blocked'" :rows="blocked" />
      <InfoPanel v-else :data="data" />

      <footer class="foot">
        <span>读写都走 <code class="cmd">python src\api.py</code> + <code class="cmd">data/ledger.db</code>,
          页面改的东西立刻进库</span>
        <span>命令行同样能改:<code class="cmd">python src\ledger.py done &lt;短码&gt;</code>,两边 12 秒内互相同步</span>
        <span v-if="data.stats.pool_scanned_at">岗位池扫描于 {{ data.stats.pool_scanned_at }}</span>
      </footer>
    </template>
  </main>
</template>
