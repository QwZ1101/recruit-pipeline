<script setup>
import { computed, inject, nextTick, onBeforeUnmount, ref } from 'vue'
import { tone } from '../fmt.js'

const props = defineProps({ job: Object, small: Boolean })
const led = inject('ledger')

const show = ref(false)
const pos = ref({ top: 0, left: 0 })
const pick = ref('')
const force = ref(false)
const note = ref('')
const input = ref(null)

const allowed = computed(() => led.transitions[props.job.status] || [])
const options = computed(() => (force.value ? led.statuses : allowed.value))
const editable = computed(() => props.job.status !== '未入台账')

function open(e) {
  if (!editable.value) return
  const r = e.currentTarget.getBoundingClientRect()
  pos.value = {
    top: Math.min(r.bottom + 6, window.innerHeight - 250),
    left: Math.min(r.left, window.innerWidth - 268),
  }
  pick.value = allowed.value.includes(props.job.status) ? props.job.status : ''
  force.value = false
  note.value = ''
  show.value = true
  nextTick(() => input.value && input.value.focus())
  document.addEventListener('mousedown', outside)
}
function outside(e) {
  if (!e.target.closest('.pop')) close()
}
function close() {
  show.value = false
  document.removeEventListener('mousedown', outside)
}
async function save() {
  if (!pick.value) return
  const ok = await led.setStatus(props.job, {
    status: pick.value, note: note.value.trim() || null, force: force.value,
  })
  if (ok) close()
}
onBeforeUnmount(() => document.removeEventListener('mousedown', outside))
</script>

<template>
  <button class="pill" :class="[tone(job.status), { pickable: editable }]"
          :title="editable ? '点这里改状态(规则来自后端状态机)' : '不在台账,先跑 ledger.py init --from-rank'"
          @click.stop="open">
    {{ job.status }}<i v-if="editable">▾</i>
  </button>

  <Teleport to="body">
    <div v-if="show" class="pop" :style="{ top: pos.top + 'px', left: pos.left + 'px' }"
         @mousedown.stop @click.stop>
      <div class="pop-h">
        <span class="pill" :class="tone(job.status)">{{ job.status }}</span>
        <span class="hint">流转到 →</span>
        <b v-if="pick">{{ pick }}</b>
      </div>
      <div class="pop-title">{{ job.company }} · {{ job.name.slice(0, 26) }}</div>
      <div class="pop-opts">
        <button v-for="s in options" :key="s" class="chip"
                :class="{ on: pick === s }" @click="pick = s">{{ s }}</button>
      </div>
      <p v-if="!force && !options.length" class="hint" style="margin:6px 0">
        这个状态在后端没有合法的下一步了,勾「强行改」再选。</p>
      <label class="pop-force">
        <input type="checkbox" v-model="force" />
        强行改(跳过状态机校验,会写进 history)
      </label>
      <input ref="input" class="pop-note" v-model="note"
             placeholder="备注(可空),如:HR 说下周约面" @keydown.enter="save" />
      <div class="pop-f">
        <button class="btn ghost" @click="close">取消</button>
        <button class="btn" :disabled="!pick || led.busy" @click="save">
          {{ led.busy ? '提交中…' : '保存' }}</button>
      </div>
    </div>
  </Teleport>
</template>
