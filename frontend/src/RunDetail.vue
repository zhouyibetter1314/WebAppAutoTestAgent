<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, type Run, type RunEvent, mergeEvents, terminal, statusText, verdictText } from './api'
const route = useRoute(),
  router = useRouter(),
  run = ref<Run>(),
  events = ref<RunEvent[]>([]),
  busy = ref(false),
  connection = ref('正在连接'),
  observationId = ref('')
let stream: EventSource | undefined
const observation = computed(
  () =>
    run.value?.observations.find((o) => o.id === observationId.value) ??
    run.value?.observations.at(-1),
)
const artifact = (name: string) => `/api/runs/${run.value?.id}/artifacts/${name}`
async function load() {
  run.value = await api<Run>(`/runs/${route.params.id}`)
}
async function connect() {
  stream?.close()
  events.value = []
  observationId.value = ''
  try {
    await load()
    events.value = await api<RunEvent[]>(`/runs/${route.params.id}/events`)
    stream = new EventSource(
      `/api/runs/${route.params.id}/events/stream?after=${events.value.at(-1)?.sequence ?? 0}`,
    )
    stream.onopen = () => (connection.value = '已连接')
    stream.onerror = () => (connection.value = '连接中断，正在重连')
    stream.addEventListener('update', (e) => {
      events.value = mergeEvents(events.value, [JSON.parse(e.data)])
      void load().catch((e) => ElMessage.error(String(e)))
    })
    stream.addEventListener('complete', () => {
      stream?.close()
      connection.value = '记录已保存'
      void load().catch((e) => ElMessage.error(String(e)))
    })
  } catch (e) {
    ElMessage.error(String(e))
  }
}
async function action(kind: 'cancel' | 'rerun') {
  busy.value = true
  try {
    if (kind === 'cancel') await api(`/runs/${run.value?.id}/cancel`, {})
    else {
      const next = await api<Run>('/runs', {
        scenario_id: run.value?.scenario.id,
        max_steps: run.value?.max_steps,
      })
      await router.push(`/runs/${next.id}`)
    }
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    busy.value = false
  }
}
onMounted(connect)
watch(() => route.params.id, connect)
onBeforeUnmount(() => stream?.close())
const labels: Record<string, string> = {
  queued: '任务已排队',
  started: '开始执行',
  parsed: '解析场景',
  planned: '生成计划',
  observation: '观察页面',
  decision: '选择操作',
  action: '执行操作',
  verification: '检查验收条件',
  evidence_audit: '审查判定证据',
  final_verification: '结束前复核',
  verification_rejected: '证据不足，继续验证',
  recovery: '尝试恢复',
  finished: '生成报告',
  cancelled: '已取消',
}
</script>
<template>
  <section v-if="run" class="page">
    <div class="eyebrow">RUN / {{ run.id.slice(0, 8) }}</div>
    <div class="heading">
      <div>
        <h1>{{ run.scenario.name }}</h1>
        <p>{{ statusText[run.status] }} · {{ connection }}</p>
      </div>
      <div>
        <el-button v-if="!terminal(run.status)" :loading="busy" @click="action('cancel')">
          取消运行 </el-button
        ><el-button v-else :loading="busy" @click="action('rerun')">重新运行</el-button
        ><a v-if="run.report" :href="`/api/runs/${run.id}/export`"
          ><el-button type="primary">下载报告包</el-button></a
        >
      </div>
    </div>
    <div class="summary">
      <div>
        <strong
          >{{ run.resources.browser_steps }}<small> / {{ run.max_steps }}</small></strong
        ><span>已用操作数</span>
      </div>
      <div>
        <strong>{{ run.resources.elapsed_seconds.toFixed(1) }}<small> s</small></strong
        ><span>累计耗时</span>
      </div>
      <div>
        <strong :class="run.verdict?.toLowerCase()">{{
          run.verdict ? verdictText[run.verdict] : '待判定'
        }}</strong
        ><span>测试结论</span>
      </div>
    </div>
    <el-alert
      v-if="run.reason"
      :title="run.reason"
      :closable="false"
      :type="run.verdict === 'PASS' ? 'success' : 'info'"
    />
    <div class="run-grid">
      <div class="panel timeline">
        <h3>执行时间线</h3>
        <div v-for="event in events" :key="event.sequence" class="event">
          <span class="event-index">{{ event.sequence }}</span>
          <div>
            <b>{{ labels[event.kind] ?? event.kind }}</b
            ><small>{{ new Date(event.created_at).toLocaleTimeString() }}</small>
            <details>
              <summary>详细记录</summary>
              <pre>{{ JSON.stringify(event.data, null, 2) }}</pre>
            </details>
          </div>
        </div>
      </div>
      <div>
        <div class="panel">
          <div class="panel-title">
            <h3>页面证据</h3>
            <el-select v-model="observationId" placeholder="最新观察" style="width: 180px">
              <el-option
                v-for="(o, index) in run.observations"
                :key="o.id"
                :label="`观察 ${index + 1} · ${o.id.slice(0, 6)}`"
                :value="o.id"
              />
            </el-select>
          </div>
          <img
            v-if="observation"
            class="screenshot"
            :src="artifact(observation.screenshot)"
            alt="运行页面截图"
          />
          <p v-else class="empty">等待浏览器的第一条观察记录。</p>
          <p v-if="observation" class="subtle">
            证据 {{ observation.id }} · {{ observation.title }}
          </p>
        </div>
        <div class="panel">
          <h3>验收检查点</h3>
          <div v-for="check in run.checkpoints" :key="check.id" class="check">
            <b>{{ check.expected }}</b
            ><el-tag
              :type="
                check.status === 'satisfied'
                  ? 'success'
                  : check.status === 'violated'
                    ? 'danger'
                    : 'info'
              "
            >
              {{ { satisfied: '已满足', violated: '不满足', pending: '待验证' }[check.status] }}
            </el-tag>
            <p>{{ check.actual || '尚未取得充分证据' }}</p>
            <small>证据：{{ check.evidence_ids.join(', ') || '暂无' }}</small>
          </div>
          <p v-if="!run.checkpoints.length" class="empty">解析后会显示独立检查点。</p>
          <a v-if="run.report?.trace" :href="artifact(run.report.trace)">下载 Playwright Trace</a>
        </div>
      </div>
    </div>
  </section>
</template>
