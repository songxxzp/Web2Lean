/**
 * Vue Router configuration
 */
import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from '@/views/Dashboard.vue'
import Crawlers from '@/views/Crawlers.vue'
import Processing from '@/views/Processing.vue'
import Database from '@/views/Database.vue'
import Config from '@/views/Config.vue'

const routes = [
  { path: '/', name: 'Dashboard', component: Dashboard },
  { path: '/crawlers', name: 'Crawlers', component: Crawlers },
  { path: '/processing', name: 'Processing', component: Processing },
  { path: '/database', name: 'Database', component: Database },
  { path: '/config', name: 'Config', component: Config }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
