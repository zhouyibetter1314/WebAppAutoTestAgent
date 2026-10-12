import { defineStore } from 'pinia'
import { api, type Application, type Scenario } from './api'
export const useCatalog = defineStore('catalog', {
  state: () => ({ applications: [] as Application[], scenarios: [] as Scenario[] }),
  actions: {
    async load() {
      ;[this.applications, this.scenarios] = await Promise.all([
        api<Application[]>('/applications'),
        api<Scenario[]>('/scenarios'),
      ])
    },
  },
})
