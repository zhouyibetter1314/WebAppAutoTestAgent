import type { components } from './schema'
export type Application = components['schemas']['Application']
export type Scenario = components['schemas']['Scenario']
export type Run = components['schemas']['Run']
export type RunEvent = components['schemas']['Event']
export type SettingsInfo = components['schemas']['SettingsInfo']
export async function api<T>(path: string, body?: unknown, method?: string): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: method ?? (body ? 'POST' : 'GET'),
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!response.ok) {
    const error = await response.json()
    throw new Error(typeof error.detail === 'string' ? error.detail : '请检查输入内容')
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
