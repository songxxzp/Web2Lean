<template>
  <div class="crawlers">
    <h2>Crawler Management</h2>

    <el-table :data="sites" stripe>
      <el-table-column prop="site_name" label="Site Name" width="200" />
      <el-table-column prop="site_type" label="Type" width="150" />
      <el-table-column label="Status" width="150">
        <template #default="{ row }">
          <el-tag :type="getStatusType(getStatus(row.site_name))">
            {{ getStatus(row.site_name) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="Progress" width="200">
        <template #default="{ row }">
          <span v-if="getCrawler(row.site_name)">
            {{ getCrawler(row.site_name)?.questions_crawled || 0 }} questions
          </span>
        </template>
      </el-table-column>
      <el-table-column label="Actions">
        <template #default="{ row }">
          <el-button
            v-if="getStatus(row.site_name) !== 'running'"
            type="primary"
            size="small"
            @click="startCrawler(row.site_name)"
            :disabled="!row.enabled"
          >
            Start
          </el-button>
          <el-button
            v-else
            type="danger"
            size="small"
            @click="stopCrawler(row.site_name)"
          >
            Stop
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { crawlersApi } from '@/api'

const sites = ref([])
const activeCrawlers = ref({})
let refreshInterval = null

async function loadStatus() {
  try {
    const data = await crawlersApi.getAllStatus()
    sites.value = data.all_sites || []
    activeCrawlers.value = data.active_crawlers || {}
  } catch (error) {
    ElMessage.error('Failed to load crawler status')
  }
}

function getStatus(siteName) {
  const crawler = activeCrawlers.value[siteName]
  return crawler?.status || 'idle'
}

function getStatusType(status) {
  const types = {
    running: 'success',
    idle: 'info',
    stopped: 'warning',
    error: 'danger',
    completed: 'success'
  }
  return types[status] || 'info'
}

function getCrawler(siteName) {
  return activeCrawlers.value[siteName]
}

async function startCrawler(siteName) {
  try {
    await crawlersApi.start(siteName, 'incremental')
    ElMessage.success(`Crawler for ${siteName} started`)
    await loadStatus()
  } catch (error) {
    ElMessage.error(error.message || 'Failed to start crawler')
  }
}

async function stopCrawler(siteName) {
  try {
    await crawlersApi.stop(siteName)
    ElMessage.success(`Crawler for ${siteName} stopped`)
    await loadStatus()
  } catch (error) {
    ElMessage.error(error.message || 'Failed to stop crawler')
  }
}

onMounted(() => {
  loadStatus()
  refreshInterval = setInterval(loadStatus, 5000)
})

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval)
})
</script>

<style scoped>
.crawlers h2 {
  margin-bottom: 1.5rem;
}
</style>
