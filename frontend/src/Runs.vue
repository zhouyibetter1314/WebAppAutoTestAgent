<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, type Run, statusText, verdictText } from './api'
const runs = ref<Run[]>([]),
  filter = ref('')
const filtered = computed(() =>
  runs.value.filter((r) => !filter.value || r.verdict === filter.value),
)
async function refresh() {
  try {
    runs.value = await api<Run[]>('/runs')
  } catch (e) {
    ElMessage.error(String(e))
  }
}
onMounted(refresh)
</script>
<template>
  <section class="page">
    <div class="eyebrow">EXECUTION ARCHIVE</div>
    <div class="heading">
      <div>
        <h1>运行与报告</h1>
        <p>运行状态和测试结论分别记录，每个结论都有证据。</p>
      </div>
      <el-button @click="refresh">刷新记录</el-button>
    </div>
    <div class="panel">
      <div class="panel-title">
        <h3>运行历史</h3>
        <el-select v-model="filter" placeholder="全部结论" clearable style="width: 160px">
          <el-option
            v-for="(label, value) in verdictText"
            :key="value"
            :label="label"
            :value="value"
          />
        </el-select>
      </div>
      <el-table :data="filtered" empty-text="运行场景后，记录会显示在这里。">
        <el-table-column label="场景" min-width="180">
          <template #default="{ row }">
            <RouterLink :to="`/runs/${row.id}`">{{ row.scenario.name }}</RouterLink>
          </template> </el-table-column
        ><el-table-column label="运行状态">
          <template #default="{ row }">{{ statusText[row.status] }}</template> </el-table-column
        ><el-table-column label="测试结论">
          <template #default="{ row }">
            {{ row.verdict ? verdictText[row.verdict] : '待判定' }}
          </template> </el-table-column
        ><el-table-column label="操作数">
          <template #default="{ row }">
            {{ row.resources.browser_steps }} / {{ row.max_steps }}
          </template> </el-table-column
        ><el-table-column label="创建时间" min-width="180">
          <template #default="{ row }">
            {{ new Date(row.created_at).toLocaleString() }}
          </template>
        </el-table-column>
      </el-table>
    </div>
  </section>
</template>
