<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, type Run, type Application, type Scenario } from './api'
import { useCatalog } from './store'
const catalog = useCatalog(),
  router = useRouter()
const busy = ref(false),
  appDialog = ref(false),
  scenarioDialog = ref(false),
  importDialog = ref(false),
  imported = ref(''),
  selected = ref<string[]>([])
const editingApp = ref(''),
  editingScenario = ref('')
const app = reactive({
  name: '4gaBoards',
  base_url: 'http://localhost:3000',
  username_env: 'BOARDS_USERNAME',
  password_env: 'BOARDS_PASSWORD',
  version: '3.2.16',
})
const scenario = reactive({ application_id: '', name: '', description: '', source: '自建场景' })
async function safely(action: () => Promise<void>) {
  if (busy.value) return
  busy.value = true
  try {
    await action()
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    busy.value = false
  }
}
onMounted(() => safely(() => catalog.load()))
function createApplication() {
  editingApp.value = ''
  appDialog.value = true
}
function editApplication(value: Application) {
  editingApp.value = value.id
  Object.assign(app, {
    name: value.name,
    base_url: value.base_url,
    username_env: value.username_env,
    password_env: value.password_env,
    version: value.version,
  })
  appDialog.value = true
}
function editScenario(value: Scenario) {
  editingScenario.value = value.id
  Object.assign(scenario, {
    application_id: value.application_id,
    name: value.name,
    description: value.description,
    source: value.source,
  })
  scenarioDialog.value = true
}
function createScenario() {
  editingScenario.value = ''
  scenario.name = ''
  scenario.description = ''

  scenario.application_id = catalog.applications[0]?.id ?? ''
  scenarioDialog.value = true
}
async function saveApp() {
  await safely(async () => {
    await api<Application>(
      editingApp.value ? `/applications/${editingApp.value}` : '/applications',
      app,
      editingApp.value ? 'PUT' : 'POST',
    )
    await catalog.load()
    appDialog.value = false
  })
}
async function saveScenario() {
  await safely(async () => {
    await api(
      editingScenario.value ? `/scenarios/${editingScenario.value}` : '/scenarios',
      scenario,
      editingScenario.value ? 'PUT' : 'POST',
    )
    await catalog.load()
    scenarioDialog.value = false
  })
}
async function launch(ids: string[]) {
  await safely(async () => {
    let last: Run | undefined
    for (const id of ids) last = await api<Run>('/runs', { scenario_id: id, max_steps: 35 })
    if (last) await router.push(ids.length === 1 ? `/runs/${last.id}` : '/runs')
  })
}
async function importScenarios() {
  await safely(async () => {
    const value = JSON.parse(imported.value)
    await api('/scenarios/import', { scenarios: Array.isArray(value) ? value : value.scenarios })
    await catalog.load()
    importDialog.value = false
  })
}
</script>
<template>
  <section class="page">
    <div class="eyebrow">TEST DESIGN</div>
    <div class="heading">
      <div>
        <h1>场景与应用</h1>
        <p>描述你的目标，让 Agent 执行操作并留下可检查的证据。</p>
      </div>
      <el-button type="primary" @click="createScenario">新建场景</el-button>
    </div>
    <div class="summary">
      <div>
        <strong>{{ catalog.scenarios.length }}</strong
        ><span>测试场景</span>
      </div>
      <div>
        <strong>{{ catalog.applications.length }}</strong
        ><span>被测应用</span>
      </div>
      <div><strong>35</strong><span>单次操作上限</span></div>
    </div>
    <div class="panel">
      <div class="panel-title">
        <h3>应用配置</h3>
        <el-button @click="createApplication">添加应用</el-button>
      </div>
      <p v-if="!catalog.applications.length" class="empty">先添加本地被测应用，再创建场景。</p>
      <div v-for="item in catalog.applications" :key="item.id" class="app-row">
        <b>{{ item.name }}</b
        ><span>{{ item.base_url }}</span
        ><el-tag type="info">{{ item.version || '版本未记录' }}</el-tag
        ><el-button link @click="editApplication(item)">编辑</el-button>
      </div>
    </div>
    <div class="panel">
      <div class="panel-title">
        <h3>场景库</h3>
        <div>
          <el-button @click="importDialog = true">导入 JSON</el-button
          ><el-button :disabled="!selected.length" :loading="busy" @click="launch(selected)">
            批量运行（{{ selected.length }}）
          </el-button>
        </div>
      </div>
      <el-table
        :data="catalog.scenarios"
        empty-text="还没有场景。点击右上角“新建场景”开始。"
        @selection-change="
          (rows: { id: string }[]) => (selected = rows.map((r: { id: string }) => r.id))
        "
      >
        <el-table-column type="selection" width="44" /><el-table-column
          prop="name"
          label="场景"
          min-width="160"
        /><el-table-column
          prop="description"
          label="目标描述"
          min-width="250"
          show-overflow-tooltip
        /><el-table-column prop="source" label="来源" width="130" /><el-table-column
          label="操作"
          width="100"
        >
          <template #default="{ row }">
            <el-button link @click="editScenario(row)">编辑</el-button>
            <el-button type="primary" link :disabled="busy" @click="launch([row.id])">
              运行
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <el-dialog
      v-model="appDialog"
      :title="editingApp ? '编辑被测应用' : '添加被测应用'"
      width="560px"
    >
      <el-form label-position="top">
        <el-form-item label="应用名称"><el-input v-model="app.name" /></el-form-item
        ><el-form-item label="应用地址"><el-input v-model="app.base_url" /></el-form-item
        ><el-form-item label="版本"><el-input v-model="app.version" /></el-form-item
        ><el-form-item label="用户名环境变量名称">
          <el-input v-model="app.username_env" /> </el-form-item
        ><el-form-item label="密码环境变量名称">
          <el-input v-model="app.password_env" />
        </el-form-item>
        <p>这里只填写变量名称，账号与密码保存在本机 .env。</p> </el-form
      ><template #footer>
        <el-button type="primary" :loading="busy" @click="saveApp">保存应用</el-button>
      </template> </el-dialog
    ><el-dialog
      v-model="scenarioDialog"
      :title="editingScenario ? '编辑测试场景' : '新建测试场景'"
      width="640px"
    >
      <el-form label-position="top">
        <el-form-item label="被测应用">
          <el-select v-model="scenario.application_id">
            <el-option
              v-for="item in catalog.applications"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select> </el-form-item
        ><el-form-item label="场景名称"><el-input v-model="scenario.name" /></el-form-item
        ><el-form-item label="场景原文与验收条件">
          <el-input
            v-model="scenario.description"
            type="textarea"
            :rows="7"
            placeholder="例如：创建 Course Test 项目，确认仪表盘和侧栏均显示该项目。"
          />
        </el-form-item> </el-form
      ><template #footer>
        <el-button type="primary" :loading="busy" @click="saveScenario"> 保存场景 </el-button>
      </template> </el-dialog
    ><el-dialog v-model="importDialog" title="导入场景 JSON" width="640px">
      <p>输入场景数组，每项包含 application_id、name、description、source。</p>
      <el-input v-model="imported" type="textarea" :rows="12" /><template #footer>
        <el-button type="primary" :loading="busy" @click="importScenarios"> 导入 </el-button>
      </template>
    </el-dialog>
  </section>
</template>
