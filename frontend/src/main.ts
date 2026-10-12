import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import './style.css'
import App from './App.vue'
import Scenarios from './Scenarios.vue'
import Runs from './Runs.vue'
import RunDetail from './RunDetail.vue'
import Settings from './Settings.vue'
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Scenarios },
    { path: '/runs', component: Runs },
    { path: '/runs/:id', component: RunDetail },
    { path: '/settings', component: Settings },
  ],
})
createApp(App).use(createPinia()).use(router).use(ElementPlus, { locale: zhCn }).mount('#app')
