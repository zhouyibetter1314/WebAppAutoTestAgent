import { describe, expect, it } from 'vitest'
import { applicationError, parseScenarioImport, scenarioError } from '../src/validation'

describe('workbench input validation', () => {
  it('accepts the local 4gaBoards configuration', () => {
    expect(
      applicationError({
        name: '4gaBoards',
        base_url: 'http://localhost:3000',
        username_env: 'BOARDS_USERNAME',
        password_env: 'BOARDS_PASSWORD',
        version: '3.2.16',
      }),
    ).toBe('')
  })

  it('rejects unsafe URLs and invalid environment variable names', () => {
    expect(
      applicationError({
        name: 'fixture',
        base_url: 'file:///tmp/index.html',
        username_env: 'NOT VALID',
        password_env: '',
        version: '',
      }),
    ).toContain('http')
    expect(
      applicationError({
        name: 'fixture',
        base_url: 'http://localhost:3000',
        username_env: 'NOT VALID',
        password_env: '',
        version: '',
      }),
    ).toContain('环境变量')
  })

  it('validates scenarios and imported JSON before calling the API', () => {
    expect(
      scenarioError({ application_id: '', name: '', description: '', source: '自建场景' }),
    ).toContain('被测应用')
    expect(() => parseScenarioImport('{broken')).toThrow('JSON 格式不正确')
    expect(() => parseScenarioImport('[]')).toThrow('至少一个场景')
    expect(() => parseScenarioImport('[{}]')).toThrow('第 1 个场景')
    expect(
      parseScenarioImport(
        JSON.stringify([
          {
            application_id: 'app-id',
            name: '创建项目',
            description: '创建 Course Test 并验证结果',
            source: '自建场景',
          },
        ]),
      ),
    ).toHaveLength(1)
  })
})
