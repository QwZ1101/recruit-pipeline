<script setup>
import { computed } from 'vue'

const props = defineProps({ stats: Object, tracked: Array })

const byStatus = computed(() => props.stats.by_status || {})
const applied = computed(() =>
  ['已投', '笔试', '面试', 'offer'].reduce((s, k) => s + (byStatus.value[k] || 0), 0))
</script>

<template>
  <section class="cards">
    <div class="card">
      <div class="idx">01 / 岗位池</div>
      <h3>{{ stats.pool }} 个本科可投 AI 岗</h3>
      <p>进入精排 <b>{{ stats.ranked }}</b> · 被硬门槛挡住 <b>{{ stats.blocked }}</b>
        (其中 <b>{{ stats.cet4_excluded }}</b> 个只因四级)</p>
    </div>
    <div class="card">
      <div class="idx">02 / 投递进度</div>
      <h3>已投出 {{ applied }} · 待投 {{ byStatus['待投'] || 0 }}</h3>
      <p><b>{{ byStatus['暂缓'] || 0 }}</b> 个观望暂缓 ·
        进度只前进不后退,北森侧状态由 <code class="cmd">sync</code> 推</p>
    </div>
    <div class="card">
      <div class="idx">03 / 匹配口径</div>
      <h3>门槛过滤 → embedding 粗筛 → LLM 精排</h3>
      <p>分数由大模型给,<b>重复跑有 ±7 抖动</b>;同一档位视为等价,别比较名次</p>
    </div>
    <div class="card">
      <div class="idx">04 / 作品集</div>
      <h3>可验证外链是讯飞岗的加分项原文</h3>
      <p>RAG 项目 Demo 已挂简历,<b>必须保持公网可访问</b>;GitHub 仓库仍缺</p>
    </div>
  </section>
</template>
