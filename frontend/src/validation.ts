export type ApplicationDraft = {
  name: string
  base_url: string
  username_env: string
  password_env: string
  version: string
}

export type ScenarioDraft = {
  application_id: string
  name: string
  description: string
  source: string
}

const envName = /^[A-Za-z_][A-Za-z0-9_]*$/

export function applicationError(value: ApplicationDraft): string {
  if (!value.name.trim()) return '请输入应用名称'
  try {
    const url = new URL(value.base_url)
    if (!['http:', 'https:'].includes(url.protocol)) return '应用地址必须使用 http 或 https'
  } catch {
    return '请输入有效的应用地址，例如 http://localhost:3000'
  }
  if (value.username_env && !envName.test(value.username_env)) return '用户名环境变量名称格式不正确'
  if (value.password_env && !envName.test(value.password_env)) return '密码环境变量名称格式不正确'
  return ''
}

export function scenarioError(value: Partial<ScenarioDraft>): string {
  if (!value.application_id) return '请先选择被测应用'
  if (!value.name?.trim()) return '请输入场景名称'
  if (!value.description?.trim()) return '请输入场景原文与验收条件'
  if (value.name.trim().length > 200) return '场景名称不能超过 200 个字符'
  if (value.description.trim().length > 12000) return '场景描述不能超过 12000 个字符'
  return ''
}

export function parseScenarioImport(source: string): unknown[] {
  if (!source.trim()) throw new Error('请粘贴需要导入的场景 JSON')
  let parsed: unknown
  try {
    parsed = JSON.parse(source)
  } catch {
    throw new Error('JSON 格式不正确，请检查括号、引号和逗号')
  }
  const items = Array.isArray(parsed)
    ? parsed
    : parsed &&
        typeof parsed === 'object' &&
        Array.isArray((parsed as { scenarios?: unknown }).scenarios)
      ? (parsed as { scenarios: unknown[] }).scenarios
      : []
  if (!items.length) throw new Error('导入内容必须包含至少一个场景')
  for (const [index, item] of items.entries()) {
    if (!item || typeof item !== 'object') throw new Error(`第 ${index + 1} 个场景格式不正确`)
    const error = scenarioError(item as Partial<ScenarioDraft>)
    if (error) throw new Error(`第 ${index + 1} 个场景：${error}`)
  }
  return items
}
