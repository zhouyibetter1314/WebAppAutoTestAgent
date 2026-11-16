import type { RunEvent } from './api'

type Data = Record<string, unknown>

export const eventLabels: Record<string, string> = {
  queued: '任务已排队',
  started: '开始执行',
  parsed: '解析场景',
  planned: '生成计划',
  observation: '观察页面',
  decision: '选择下一步',
  action: '执行操作',
  verification: '检查验收条件',
  evidence_audit: '审查判定证据',
  final_verification: '结束前复核',
  verification_rejected: '证据不足，继续验证',
  recovery: '尝试恢复',
  finished: '生成报告',
  cancelled: '运行已取消',
  interrupted: '运行已中断',
  error: '执行异常',
  cleanup_error: '资源收尾异常',
}

const record = (value: unknown): Data =>
  value && typeof value === 'object' && !Array.isArray(value) ? (value as Data) : {}

const text = (value: unknown): string => (typeof value === 'string' ? value : '')

const count = (value: unknown): number => (Array.isArray(value) ? value.length : 0)

function locator(value: unknown): string {
  const target = record(value)
  return text(target.name) || text(target.value) || '页面元素'
}

export function actionSummary(value: unknown): string {
  const action = record(value)
  switch (action.kind) {
    case 'navigate':
      return `打开 ${text(action.url) || '目标页面'}`
    case 'click':
      return `点击“${locator(action.target)}”`
    case 'fill':
      return `在“${locator(action.target)}”中输入内容`
    case 'select':
      return `在“${locator(action.target)}”中选择“${text(action.value)}”`
    case 'scroll':
      return `${Number(action.delta_y) >= 0 ? '向下' : '向上'}滚动页面`
    case 'drag':
      return `将“${locator(action.source)}”拖到“${locator(action.destination)}”`
    case 'press':
      return `在“${locator(action.target)}”上按下 ${text(action.key)}`
    default:
      return '执行浏览器操作'
  }
}

export function eventSummary(event: Pick<RunEvent, 'kind' | 'data'>): string {
  const data = record(event.data)
  switch (event.kind) {
    case 'queued':
      return '任务正在等待执行。'
    case 'started':
      return '浏览器和测试智能体已经启动。'
    case 'parsed': {
      const specification = record(data.specification)
      return `已提取 ${count(specification.goals)} 个目标和 ${count(specification.checkpoints)} 个检查点。`
    }
    case 'planned':
      return `已生成 ${count(data.steps)} 个执行步骤。`
    case 'observation':
      return `已观察“${text(data.title) || '未命名页面'}” · ${text(data.url) || '地址未知'}`
    case 'decision':
      if (data.finish === true) return `准备结束：${text(data.reason) || '当前目标已处理'}`
      if (Number(data.wait_ms) > 0) return `等待页面稳定（${Number(data.wait_ms)} ms）。`
      return `${actionSummary(data.action)}。${text(data.reason)}`.trim()
    case 'action': {
      const error = text(data.error)
      const result = `${actionSummary(data.action)}（第 ${Number(data.step) || '?'} 步）`
      return error ? `${result}失败：${error}` : `${result}成功。`
    }
    case 'verification':
      return `本轮接受了 ${count(data.checks)} 项有充分证据的检查结果。`
    case 'evidence_audit':
      return `已独立审查 ${count(data.checks)} 项候选证据。`
    case 'verification_rejected':
      return text(data.reason) || '当前证据不足以支持检查结论。'
    case 'final_verification':
      return `正在进行第 ${Number(data.attempt) || 1} 次结束前复核。`
    case 'recovery':
      return `第 ${Number(data.attempt) || 1} 次恢复：${text(data.error) || '重新观察并调整计划'}`
    case 'finished':
      return `${text(data.verdict) || '未判定'}：${text(data.reason) || '运行已经结束'}`
    case 'cancelled':
    case 'interrupted':
    case 'error':
      return text(data.reason) || eventLabels[event.kind]
    case 'cleanup_error':
      return `报告或资源收尾失败：${text(data.error) || '未知原因'}`
    default:
      return '已记录一条执行事件。'
  }
}

export function eventTone(kind: string): 'normal' | 'success' | 'warning' | 'danger' {
  if (['error', 'cleanup_error'].includes(kind)) return 'danger'
  if (['recovery', 'verification_rejected', 'interrupted'].includes(kind)) return 'warning'
  if (kind === 'finished') return 'success'
  return 'normal'
}
