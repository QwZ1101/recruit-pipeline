<script setup>
defineProps({ rows: Array })
</script>

<template>
  <div>
    <p class="hint" style="margin:0 0 10px">这些岗位在 embedding 粗筛阶段命中了 AI 关键词,但被硬门槛正则挡在可投池外。
      门槛是<b>确定性的文本规则</b>,不是模型判断;补上条件(比如过四级)后重跑 <code class="cmd">rank_jobs.py --report-only</code> 就会回到池子里。</p>
    <div class="tbl">
      <table>
        <thead>
          <tr>
            <th style="width:96px">公司</th>
            <th>职位</th>
            <th style="width:80px">学历</th>
            <th>被什么挡住</th>
            <th style="width:70px">链接</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="j in rows" :key="j.id">
            <td class="nowrap">{{ j.company }}</td>
            <td><span class="strong">{{ j.name }}</span></td>
            <td class="num">{{ j.degree || '-' }}</td>
            <td><span class="pill red" v-for="b in j.blockers" :key="b" style="margin-right:6px">{{ b }}</span></td>
            <td><a :href="j.url" target="_blank">查看</a></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
