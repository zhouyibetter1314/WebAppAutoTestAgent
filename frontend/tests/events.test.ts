import { describe, expect, it } from 'vitest'
import { mergeEvents, type RunEvent } from '../src/api'
describe('event replay', () => {
  it('deduplicates replayed SSE events and retains sequence order', () => {
    const event = (sequence: number) =>
      ({ sequence, run_id: 'run', kind: 'action', created_at: '', data: {} }) as RunEvent
    expect(mergeEvents([event(2), event(1)], [event(2), event(3)]).map((e) => e.sequence)).toEqual([
      1, 2, 3,
    ])
  })
})
