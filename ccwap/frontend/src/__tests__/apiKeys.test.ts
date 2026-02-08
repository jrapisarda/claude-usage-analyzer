import { describe, it, expect } from 'vitest'
import {
  dashboardKeys,
  projectKeys,
  sessionKeys,
  costKeys,
  productivityKeys,
  analyticsKeys,
  experimentKeys,
  settingsKeys,
} from '@/api/keys'

describe('dashboardKeys', () => {
  it('all returns a stable key', () => {
    expect(dashboardKeys.all).toEqual(['dashboard'])
    expect(dashboardKeys.all).toBe(dashboardKeys.all) // referentially stable
  })

  it('data includes from and to', () => {
    const key = dashboardKeys.data({ from: '2025-01-01', to: '2025-01-31' })
    expect(key).toEqual(['dashboard', '2025-01-01', '2025-01-31'])
  })

  it('data handles null dates', () => {
    const key = dashboardKeys.data({ from: null, to: null })
    expect(key).toEqual(['dashboard', null, null])
  })

  it('data produces different keys for different ranges', () => {
    const a = dashboardKeys.data({ from: '2025-01-01', to: '2025-01-31' })
    const b = dashboardKeys.data({ from: '2025-02-01', to: '2025-02-28' })
    expect(a).not.toEqual(b)
  })
})

describe('projectKeys', () => {
  it('all returns a stable key', () => {
    expect(projectKeys.all).toEqual(['projects'])
  })

  it('list includes all parameters', () => {
    const key = projectKeys.list(
      { from: '2025-01-01', to: '2025-01-31' },
      'cost',
      'desc',
      2,
      'my-project'
    )
    expect(key).toEqual(['projects', 'list', '2025-01-01', '2025-01-31', 'cost', 'desc', 2, 'my-project'])
  })

  it('list handles optional params as undefined', () => {
    const key = projectKeys.list({ from: '2025-01-01', to: '2025-01-31' })
    expect(key).toEqual(['projects', 'list', '2025-01-01', '2025-01-31', undefined, undefined, undefined, undefined])
  })
})

describe('sessionKeys', () => {
  it('all returns a stable key', () => {
    expect(sessionKeys.all).toEqual(['sessions'])
  })

  it('list includes date range, project, and page', () => {
    const key = sessionKeys.list({ from: '2025-01-01', to: '2025-01-31' }, 'proj-a', 3)
    expect(key).toEqual(['sessions', 'list', '2025-01-01', '2025-01-31', 'proj-a', 3])
  })

  it('replay includes session id', () => {
    const key = sessionKeys.replay('abc-123')
    expect(key).toEqual(['sessions', 'replay', 'abc-123'])
  })
})

describe('costKeys', () => {
  it('all returns a stable key', () => {
    expect(costKeys.all).toEqual(['cost'])
  })

  it('data includes date range', () => {
    const key = costKeys.data({ from: '2025-01-01', to: '2025-01-31' })
    expect(key).toEqual(['cost', '2025-01-01', '2025-01-31'])
  })
})

describe('productivityKeys', () => {
  it('all returns a stable key', () => {
    expect(productivityKeys.all).toEqual(['productivity'])
  })

  it('data includes date range', () => {
    const key = productivityKeys.data({ from: '2025-03-01', to: '2025-03-31' })
    expect(key).toEqual(['productivity', '2025-03-01', '2025-03-31'])
  })
})

describe('analyticsKeys', () => {
  it('all returns a stable key', () => {
    expect(analyticsKeys.all).toEqual(['analytics'])
  })

  it('data includes date range', () => {
    const key = analyticsKeys.data({ from: null, to: null })
    expect(key).toEqual(['analytics', null, null])
  })
})

describe('experimentKeys', () => {
  it('tags returns a stable key', () => {
    expect(experimentKeys.tags).toEqual(['experiments', 'tags'])
    expect(experimentKeys.tags).toBe(experimentKeys.tags)
  })

  it('compare includes tag A and tag B', () => {
    const key = experimentKeys.compare('baseline', 'variant-1')
    expect(key).toEqual(['experiments', 'compare', 'baseline', 'variant-1'])
  })
})

describe('settingsKeys', () => {
  it('all returns a stable key', () => {
    expect(settingsKeys.all).toEqual(['settings'])
    expect(settingsKeys.all).toBe(settingsKeys.all)
  })
})
