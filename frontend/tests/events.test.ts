import { describe, expect, it } from 'vitest'
import { mergeEvents, type RunEvent } from '../src/api'
import { actionSummary, eventSummary, eventTone } from '../src/events'
describe('event replay', () => {
  it('deduplicates replayed SSE events and retains sequence order', () => {
    const event = (sequence: number) =>
      ({ sequence, run_id: 'run', kind: 'action', created_at: '', data: {} }) as RunEvent
    expect(mergeEvents([event(2), event(1)], [event(2), event(3)]).map((e) => e.sequence)).toEqual([
      1, 2, 3,
    ])
  })

  it('turns browser actions and failures into readable summaries without input values', () => {
    expect(
      actionSummary({
        kind: 'fill',
        target: { by: 'label', value: 'Password', name: '密码' },
        value: 'secret-value',
      }),
    ).toBe('在“密码”中输入内容')
    const summary = eventSummary({
      kind: 'action',
      data: {
        step: 3,
        action: { kind: 'click', target: { value: 'Add project' } },
        error: '元素不可见',
      },
    })
    expect(summary).toContain('第 3 步')
    expect(summary).toContain('元素不可见')
    expect(eventTone('error')).toBe('danger')
    expect(eventTone('recovery')).toBe('warning')
  })

  it('summarizes plans, observations and final results', () => {
    expect(eventSummary({ kind: 'planned', data: { steps: [{}, {}, {}] } })).toContain('3')
    expect(
      eventSummary({ kind: 'observation', data: { title: 'Dashboard', url: 'http://localhost' } }),
    ).toContain('Dashboard')
    expect(
      eventSummary({ kind: 'finished', data: { verdict: 'PASS', reason: '全部检查点已验证' } }),
    ).toBe('PASS：全部检查点已验证')
  })
})
