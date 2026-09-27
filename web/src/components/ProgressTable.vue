<script setup>
import { computed } from 'vue'
import StatusPicker from './StatusPicker.vue'
import { FLOW, tone, shortTime } from '../fmt.js'

const props = defineProps({ rows: Array, history: Array, sync: Object })

const ORDER = ['已投', '笔试', '面试', 'offer', '挂', '待投', '暂缓', '跳过']
const sorted = computed(() =>
  [...props.rows].sort((a, b) => ORDER.indexOf(a.status) - ORDER.indexOf(b.status)))

const names = computed(() => {
  const m = {}
  for (const j of props.rows) m[j.id] = `${j.company} · ${j.name}`
  return m
})
const log = computed(() =>
  [...props.history].reverse().slice(0, 24))

function nodeClass(j, s) {
  const i = FLOW.indexOf(j.status)
  const k = FLOW.indexOf(s)
  if (i < 0) return ''
  if (k < i) return 'hit'
  return k === i ? 'now' : ''
}
</script>

<template>
  <div>
    <div class="tbl">
      <table>
        <thead>
          <tr>
            <th style="width:96px">公司</th>
            <th>职位</th>
            <th style="width:190px">进展</th>
            <th style="width:86px">状态</th>
            <th style="width:130px">投递时间</th>
            <th>备注</th>
            <th style="width:70px">链接</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="j in sorted" :key="j.id">
            <td class="nowrap">{{ j.company }}</td>
            <td><span class="strong">{{ j.name }}</span>
              <span class="hint" style="margin-left:8px">{{ j.short }}</span></td>
            <td>
              <div class="flow">
                <template v-for="(s, i) in FLOW" :key="s">
                  <span class="node" :class="nodeClass(j, s)" :title="s"></span>
                  <span v-if="i < FLOW.length - 1" class="hint" style="opacity:.35">—</span>
                </template>
                <span class="hint" style="margin-left:8px">{{ j.status }}</span>
              </div>
            </td>
            <td><StatusPicker :job="j" /></td>
            <td class="num nowrap">{{ j.applied_at || '-' }}</td>
            <td class="hint">{{ j.note || '-' }}</td>
            <td><a :href="j.url" target="_blank">投递</a></td>
          </tr>
          <tr v-if="!sorted.length"><td colspan="7" class="empty">
            台账是空的。跑 <code class="cmd">python src\ledger.py init --from-rank</code> 导入。
          </td></tr>
        </tbody>
      </table>
    </div>

    <div class="card" style="margin-top:18px" v-if="sync">
      <div class="idx">
        <template v-if="sync.running">正在拉北森…</template>
        <template v-else>北森同步结果{{ sync.changed != null ? '(前进 ' + sync.changed + ' 条)' : '' }}</template>
      </div>
      <ul class="synclog">
        <li v-if="sync.running" class="hint">正在请求北森接口,按租户逐个拉,可能要几秒…</li>
        <li v-for="(l, i) in sync.lines" :key="i">{{ l }}</li>
        <li v-if="!sync.running && !sync.lines.length" class="hint">北森侧没有可前进的状态,或租户都没 Cookie。</li>
      </ul>
    </div>

    <div class="card" style="margin-top:18px">
      <div class="idx">状态流转记录(最近 24 条)</div>
      <ul class="tl" style="margin-top:12px">
        <li v-for="h in log" :key="h.id">
          <span class="t">{{ shortTime(h.ts) }}</span>
          <span class="v">{{ names[h.job_id] || h.job_id.slice(0, 8) }}</span>
          <span class="pill" :class="tone(h.new_status)" style="margin-left:8px">
            {{ h.old_status }} → {{ h.new_status }}</span>
          <div class="hint" v-if="h.note">{{ h.note }}</div>
        </li>
        <li v-if="!log.length" class="hint">还没有状态变更历史</li>
      </ul>
      <p class="hint" style="margin-top:8px">点状态胶囊就能改流转;北森 <code class="cmd">sync</code>
        只前进不后退,有 Cookie 的租户才会自动覆盖,其余手工改。命令行改的这边 12 秒内跟上。</p>
    </div>
  </div>
</template>
