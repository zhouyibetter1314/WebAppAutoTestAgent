<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, type SettingsInfo } from './api'
const settings = ref<SettingsInfo>()
const environment = ref<Record<string, string>>({})
onMounted(async () => {
  try {
    settings.value = await api<SettingsInfo>('/settings')
    environment.value = await api<Record<string, string>>('/environment')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  }
})
</script>
<template>
  <section class="page">
    <div class="eyebrow">LOCAL CONFIGURATION</div>
    <h1>环境与设置</h1>
    <p>模型密钥保存在本机，工作台仅显示配置状态。</p>
    <div v-if="settings" class="panel settings">
      <el-alert
        :title="
          settings.model_configured
            ? '已配置模型密钥；真实连接以运行结果为准'
            : '尚未配置 DeepSeek 密钥，真实模型验收未验证'
        "
        :type="settings.model_configured ? 'success' : 'warning'"
        :closable="false"
      />
      <h3 style="margin-top: 24px">运行配置</h3>
      <dl>
        <dt>课程要求模型</dt>
        <dd>{{ settings.required_model }}</dd>
        <dt>API 请求名称</dt>
        <dd>{{ settings.api_model }}</dd>
        <dt>模型服务地址</dt>
        <dd>{{ settings.base_url }}</dd>
        <dt>单次操作上限</dt>
        <dd>{{ settings.max_steps }}</dd>
        <dt>执行模式</dt>
        <dd>{{ settings.execution_mode }}</dd>
        <dt>浏览器</dt>
        <dd>{{ settings.headless ? '无头模式' : '可见窗口' }}</dd>
      </dl>
      <h3>环境检查</h3>
      <dl>
        <template v-for="(value, name) in environment" :key="name"
          ><dt>{{ name }}</dt>
          <dd>{{ value }}</dd></template
        >
      </dl>
      <p>
        在项目 .env 中配置 DEEPSEEK_API_KEY，修改后重启后端。完整的环境诊断使用项目的 doctor 命令。
      </p>
      <h3>DeepSeek API 配置位置</h3>
      <p>
        在项目根目录的
        <code>.env</code> 文件中填写以下配置。密钥不会通过工作台接口返回，也不要提交到 Git。
      </p>
      <pre class="config-example">
DEEPSEEK_API_KEY=你的_API_Key
WAAT_MODEL_BASE_URL=https://api.deepseek.com
WAAT_API_MODEL=deepseek-flash</pre>
      <p>保存后重启后端，再回到本页确认“已配置模型密钥”。</p>
    </div>
  </section>
</template>
