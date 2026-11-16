import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../src/api'

describe('API errors', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('explains when the backend cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network error')))
    await expect(api('/health')).rejects.toThrow('无法连接后端服务')
  })

  it('uses the backend detail when available', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: '未配置 DEEPSEEK_API_KEY' }), {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
    await expect(api('/runs', { scenario_id: 'scenario' })).rejects.toThrow(
      '未配置 DEEPSEEK_API_KEY',
    )
  })

  it('handles non-JSON proxy errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('Bad Gateway', { status: 502 })))
    await expect(api('/runs')).rejects.toThrow('HTTP 502')
  })
})
