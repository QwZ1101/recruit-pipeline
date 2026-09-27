<script setup>
import { ref } from 'vue'
import JobDetail from './JobDetail.vue'
import StatusPicker from './StatusPicker.vue'
import { starsStyle, tier } from '../fmt.js'

const props = defineProps({ rows: Array })
const open = ref('')
function toggle(id) { open.value = open.value === id ? '' : id }
</script>

<template>
  <div class="tbl">
    <table v-if="rows.length">
      <thead>
        <tr>
          <th style="width:64px">发布</th>
          <th style="width:92px">公司</th>
          <th>职位</th>
          <th style="width:132px">人岗匹配度</th>
          <th style="width:62px">相似度</th>
          <th style="width:96px">城市</th>
          <th style="width:70px">结论</th>
          <th style="width:86px">状态</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="j in rows" :key="j.id">
          <tr class="row" :class="{ open: open === j.id }" @click="toggle(j.id)">
            <td class="num nowrap">{{ j.post ? j.post.slice(5) : '-' }}</td>
            <td class="nowrap">{{ j.company }}</td>
            <td>
              <span class="strong">{{ j.name }}</span>
              <div style="margin-top:3px">
                <span class="tag" v-for="s in j.skills.slice(0, 6)" :key="s">{{ s }}</span>
              </div>
            </td>
            <td class="nowrap">
              <span class="stars" :style="starsStyle(j.score)">★★★★★</span>
              <span class="num" style="margin-left:6px">{{ j.score }}</span>
              <span class="hint" style="margin-left:4px">{{ tier(j.score) }}</span>
            </td>
            <td class="num">{{ j.cos }}</td>
            <td class="num">{{ j.cities.length ? j.cities.join('/') : '-' }}</td>
            <td><span class="pill" :class="j.advice === '投' ? 'green' : 'amber'">{{ j.advice }}</span></td>
            <td><StatusPicker :job="j" /></td>
          </tr>
          <JobDetail v-if="open === j.id" :job="j" />
        </template>
      </tbody>
    </table>
    <div v-else class="empty">没有符合筛选条件的岗位。点「清空筛选」或换个关键词。</div>
  </div>
</template>
