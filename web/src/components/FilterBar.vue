<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { STATUSES, tier } from '../fmt.js'

const props = defineProps({ modelValue: Object, jobs: Array })
const emit = defineEmits(['update:modelValue'])

const f = computed(() => props.modelValue)
function set(key, val) {
  emit('update:modelValue', { ...f.value, [key]: f.value[key] === val ? '' : val })
}
function count(key, val) {
  return props.jobs.filter(j => j[key] === val).length
}
function tierCount(t) {
  return props.jobs.filter(j => tier(j.score) === t).length
}

const companies = computed(() => {
  const m = new Map()
  for (const j of props.jobs) m.set(j.company, (m.get(j.company) || 0) + 1)
  return [...m].sort((a, b) => b[1] - a[1])
})
const q = computed({
  get: () => f.value.q,
  set: (v) => emit('update:modelValue', { ...f.value, q: v }),
})
const statuses = computed(() =>
  STATUSES.filter(s => props.jobs.some(j => j.status === s)))

const searchInput = ref(null)
function onKey(e) {
  // 输入框/浮层里敲键别劫持
  const tag = e.target.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || e.target.isContentEditable) return
  if (e.key === '/') {
    e.preventDefault()
    searchInput.value && searchInput.value.focus()
  }
}
onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
</script>

<template>
  <section class="filters">
    <div class="frow">
      <label>公司</label>
      <button v-for="[c, n] in companies" :key="c" class="chip"
              :class="{ on: f.company === c }" @click="set('company', c)">
        {{ c }}<small>{{ n }}</small></button>
    </div>
    <div class="frow">
      <label>状态</label>
      <button v-for="s in statuses" :key="s" class="chip"
              :class="{ on: f.status === s }" @click="set('status', s)">
        {{ s }}<small>{{ count('status', s) }}</small></button>
      <label style="margin-left:18px">结论</label>
      <button v-for="a in ['投', '观望', '不投']" :key="a" class="chip"
              :class="{ on: f.advice === a }" @click="set('advice', a)">
        {{ a }}<small>{{ count('advice', a) }}</small></button>
    </div>
    <div class="frow">
      <label>档位</label>
      <button v-for="t in ['第一档', '第二档', '第三档', '第四档', '偏低']" :key="t" class="chip"
              :class="{ on: f.tier === t }" @click="set('tier', t)">
        {{ t }}<small>{{ tierCount(t) }}</small></button>
      <input ref="searchInput" class="search" v-model="q"
             placeholder="搜岗位名 / 技能 / JD 正文,如 RAG、语音、海外(按 / 聚焦)" />
      <button v-if="f.company||f.status||f.advice||f.tier||f.q" class="btn ghost"
              @click="emit('update:modelValue', { company:'', status:'', advice:'', tier:'', q:'' })">
        清空筛选</button>
    </div>
  </section>
</template>
