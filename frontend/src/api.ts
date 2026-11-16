import type { components } from './schema'
export type Application = components['schemas']['Application']
export type Scenario = components['schemas']['Scenario']
export type Run = components['schemas']['Run']
export type RunEvent = components['schemas']['Event']
export type SettingsInfo = components['schemas']['SettingsInfo']
export async function api<T>(path: string, body?: unknown, method?: string): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      method: method ?? (body ? 'POST' : 'GET'),
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new Error('无法连接后端服务，请确认 API 已启动')
  }
  if (!response.ok) {
    let detail = ''
    try {
      const error = await response.json()
      detail = typeof error.detail === 'string' ? error.detail : ''
    } catch {
      // A proxy or upstream service may return a non-JSON error page.
    }
    throw new Error(detail || `请求失败（HTTP ${response.status}），请检查输入或服务状态`)
  }
  return response.json()
}
export const terminal = (status: string) =>
  ['completed', 'cancelled', 'interrupted', 'error'].includes(status)
export const statusText: Record<string, string> = {
  queued: '排队中',
  running: '执行中',
  completed: '已完成',
  cancelled: '已取消',
  interrupted: '已中断',
  error: '执行异常',
}
export const verdictText: Record<string, string> = {
  PASS: '通过',
  FAIL: '不通过',
  INCONCLUSIVE: '无法判定',
}
export function mergeEvents(current: RunEvent[], incoming: RunEvent[]): RunEvent[] {
  return [...new Map([...current, ...incoming].map((e) => [e.sequence, e])).values()].sort(
    (a, b) => a.sequence - b.sequence,
  )
}
