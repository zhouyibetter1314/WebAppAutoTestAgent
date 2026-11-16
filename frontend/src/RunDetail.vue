<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, type Run, type RunEvent, mergeEvents, terminal, statusText, verdictText } from './api'
import { eventLabels, eventSummary, eventTone } from './events'
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
const currentEvent = computed(() => events.value.at(-1))
const artifact = (name: string) =>
  `/api/runs/${run.value?.id}/artifacts/${encodeURIComponent(name)}`
const readableError = (value: unknown) => (value instanceof Error ? value.message : String(value))
const formatNumber = (value: number) => new Intl.NumberFormat('zh-CN').format(value)
const modeText = (value: string) =>
  ({ real: '真实模型', 'test-double': '测试模型' })[value] ?? value
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
    if (run.value && terminal(run.value.status)) {
      connection.value = '记录已保存'
      return
    }
    stream = new EventSource(
      `/api/runs/${route.params.id}/events/stream?after=${events.value.at(-1)?.sequence ?? 0}`,
    )
    stream.onopen = () => (connection.value = '已连接')
    stream.onerror = () => (connection.value = '连接中断，正在重连')
    stream.addEventListener('update', (e) => {
      try {
        events.value = mergeEvents(events.value, [JSON.parse(e.data)])
      } catch {
        connection.value = '收到无法解析的事件'
      }
      void load().catch((e) => ElMessage.error(readableError(e)))
    })
    stream.addEventListener('complete', () => {
      stream?.close()
      connection.value = '记录已保存'
      void load().catch((e) => ElMessage.error(readableError(e)))
    })
  } catch (e) {
    connection.value = '连接失败'
    ElMessage.error(readableError(e))
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
    ElMessage.error(readableError(e))
  } finally {
    busy.value = false
  }
}
onMounted(connect)
watch(() => route.params.id, connect)
onBeforeUnmount(() => stream?.close())
</script>
<template>
  <section v-if="run" class="page">
    <div class="eyebrow">RUN / {{ run.id.slice(0, 8) }}</div>
    <div class="heading">
      <div>
        <h1>{{ run.scenario.name }}</h1>
        <p>
          {{ statusText[run.status] }} ·
          <span :class="{ 'connection-error': connection.includes('失败') }">{{ connection }}</span>
        </p>
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
    <el-alert
      v-if="connection === '连接失败'"
      title="无法读取运行数据，请确认后端服务已启动后刷新页面"
      type="error"
      :closable="false"
      show-icon
    />
    <div v-if="currentEvent && !terminal(run.status)" class="current-step">
      <span>当前进度</span>
      <div>
        <b>{{ eventLabels[currentEvent.kind] ?? currentEvent.kind }}</b>
        <p>{{ eventSummary(currentEvent) }}</p>
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
    <div class="resource-summary">
      <div>
        <span>模型请求</span><b>{{ formatNumber(run.resources.model_requests) }}</b>
      </div>
      <div>
        <span>输入 Token</span><b>{{ formatNumber(run.resources.input_tokens) }}</b>
      </div>
      <div>
        <span>输出 Token</span><b>{{ formatNumber(run.resources.output_tokens) }}</b>
      </div>
      <div>
        <span>Token 统计</span
        ><b>{{ run.resources.token_usage_complete ? '完整' : '可能不完整' }}</b>
      </div>
    </div>
    <el-alert
      v-if="run.reason"
      :title="run.reason"
      :closable="false"
      :type="run.verdict === 'PASS' ? 'success' : run.verdict === 'FAIL' ? 'error' : 'warning'"
    />
    <div class="run-grid">
      <div class="panel timeline">
        <h3>执行时间线</h3>
        <p v-if="!events.length" class="empty">等待第一条运行事件。</p>
        <div
          v-for="event in events"
          :key="event.sequence"
          class="event"
          :class="`event-${eventTone(event.kind)}`"
        >
          <span class="event-index">{{ event.sequence }}</span>
          <div>
            <b>{{ eventLabels[event.kind] ?? event.kind }}</b>
            <p>{{ eventSummary(event) }}</p>
            <small>{{ new Date(event.created_at).toLocaleTimeString() }}</small>
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
        <div v-if="run.report" class="panel report-meta">
          <h3>报告信息</h3>
          <dl>
            <dt>执行模式</dt>
            <dd>{{ modeText(run.report.execution_mode) }}</dd>
            <dt>请求模型</dt>
            <dd>{{ run.report.model.api_model || '未记录' }}</dd>
            <dt>服务返回模型</dt>
            <dd>{{ run.report.model.returned_model || '未记录' }}</dd>
            <dt>模型服务</dt>
            <dd>{{ run.report.model.base_url || '未记录' }}</dd>
            <dt>完成时间</dt>
            <dd>{{ run.finished_at ? new Date(run.finished_at).toLocaleString() : '未完成' }}</dd>
          </dl>
          <p>完整 JSON、Markdown、模型调用记录、截图和 Trace 包含在报告包中。</p>
        </div>
      </div>
    </div>
  </section>
</template>
