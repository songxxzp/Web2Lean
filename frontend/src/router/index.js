/**
 * Vue Router configuration
 */
import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from '@/views/Dashboard.vue'
import Crawlers from '@/views/Crawlers.vue'
import Processing from '@/views/Processing.vue'
import Database from '@/views/Database.vue'
import Config from '@/views/Config.vue'
import Scheduler from '@/views/Scheduler.vue'

const routes = [
  { path: '/', name: 'Dashboard', component: Dashboard },
  { path: '/crawlers', name: 'Crawlers', component: Crawlers },
  { path: '/processing', name: 'Processing', component: Processing },
  { path: '/database', name: 'Database', component: Database },
  { path: '/config', name: 'Config', component: Config },
  { path: '/scheduler', name: 'Scheduler', component: Scheduler }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
