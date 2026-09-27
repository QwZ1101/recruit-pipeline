<script setup>
import { computed, inject, ref } from 'vue'
import StatusPicker from './StatusPicker.vue'

const props = defineProps({ job: Object })
const led = inject('ledger')
const showJd = ref(false)
const note = ref('')

const next = computed(() => led.transitions[props.job.status] || [])
// 「待投 → 已投」是最高频动作,给一个一键按钮,其余走状态胶囊
const canDone = computed(() => next.value.includes('已投'))

async function markApplied() {
  await led.setStatus(props.job, { status: '已投' })
}
async function saveNote() {
  if (!note.value.trim()) return
  if (await led.addNote(props.job, note.value.trim())) note.value = ''
}
</script>

<template>
  <tr class="detail">
    <td colspan="8">
    <div class="dgrid">
      <p class="oneline" v-if="job.one_line">{{ job.one_line }}</p>

      <div class="dblock">
        <h4>命中的要求({{ job.matched.length }})</h4>
        <ul>
          <li v-for="m in job.matched" :key="m" class="good">{{ m }}</li>
          <li v-if="!job.matched.length" class="hint">未精排,无明细</li>
        </ul>
      </div>

      <div class="dblock">
        <h4>缺口({{ job.gaps.length }})</h4>
        <ul>
          <li v-for="g in job.gaps" :key="g" class="bad">{{ g }}</li>
          <li v-if="!job.gaps.length" class="hint">无明显缺口</li>
        </ul>
        <template v-if="job.risk.length">
          <h4 style="margin-top:14px">风险提示</h4>
          <ul><li v-for="r in job.risk" :key="r">{{ r }}</li></ul>
        </template>
        <p v-if="job.city_note" class="hint" style="margin-top:12px">{{ job.city_note }}</p>
      </div>

      <div class="dblock">
        <h4>JD 里点名的技能</h4>
        <span class="tag" v-for="s in job.skills" :key="s">{{ s }}</span>
        <h4 style="margin-top:14px">岗位技能相似度</h4>
        <p class="hint">embedding 余弦 {{ job.cos }}(粗筛排序用,不代表最终结论)</p>
      </div>

      <div class="dblock">
        <h4>台账</h4>
        <div class="kv"><span>状态</span><b><StatusPicker :job="job" /></b></div>
        <div class="kv"><span>短码</span><b>{{ job.short }}</b></div>
        <div class="kv" v-if="job.applied_at"><span>投递时间</span><b>{{ job.applied_at }}</b></div>
        <div class="kv" v-if="job.note"><span>备注</span><b>{{ job.note }}</b></div>
        <div class="notebox">
          <input v-model="note" placeholder="加一条备注,如:已联系 HR"
                 @keydown.enter="saveNote" />
          <button class="btn ghost" :disabled="!note.trim() || led.busy" @click="saveNote">
            记一笔</button>
        </div>
      </div>

      <div class="dactions">
        <a class="btn" style="color:#fff" :href="job.url" target="_blank"
           @click.stop>去投递页</a>
        <button v-if="canDone" class="btn green" :disabled="led.busy"
                @click.stop="markApplied">标记已投</button>
        <span v-else-if="job.status === '未入台账'" class="hint">
          这条还没进台账,先跑 <code class="cmd">python src\ledger.py init --from-rank</code></span>
        <button class="btn ghost" @click.stop="showJd = !showJd">
          {{ showJd ? '收起' : '展开' }} JD 原文</button>
      </div>

      <template v-if="showJd">
        <div class="dblock" style="grid-column:1/-1">
          <h4>职责</h4>
          <div class="jd">{{ job.duty || '无' }}</div>
          <h4 style="margin-top:12px">要求</h4>
          <div class="jd">{{ job.require || '无' }}</div>
        </div>
      </template>
    </div>
  </td>
  </tr>
</template>
