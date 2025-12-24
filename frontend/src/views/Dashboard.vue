<template>
  <div class="dashboard">
    <h2>Dashboard</h2>

    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.total_questions || 0 }}</div>
          <div class="stat-label">Total Questions</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.total_answers || 0 }}</div>
          <div class="stat-label">Total Answers</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.lean_converted || 0 }}</div>
          <div class="stat-label">Lean Converted</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.total_images || 0 }}</div>
          <div class="stat-label">Images</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="charts-row">
      <el-col :span="12">
        <el-card>
          <h3>Processing Status</h3>
          <div ref="processingChart" style="height: 300px"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <h3>Data by Site</h3>
          <div ref="siteChart" style="height: 300px"></div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { statisticsApi } from '@/api'

const stats = ref({})
const processingChart = ref(null)
const siteChart = ref(null)
let processingChartInstance = null
let siteChartInstance = null

async function loadStats() {
  try {
    const data = await statisticsApi.overview()
    stats.value = {
      total_questions: data.total_questions,
      total_answers: data.total_answers,
      total_images: data.total_images,
      lean_converted: data.processing_status?.lean_converted || 0
    }

    // Update processing chart
    if (processingChartInstance) {
      const ps = data.processing_status || {}
      processingChartInstance.setOption({
        series: [{
          type: 'pie',
          data: [
            { value: ps.raw || 0, name: 'Raw' },
            { value: ps.preprocessed || 0, name: 'Preprocessed' },
            { value: ps.lean_converted || 0, name: 'Lean Converted' },
            { value: ps.failed || 0, name: 'Failed' }
          ]
        }]
      })
    }

    // Update site chart
    if (siteChartInstance) {
      const siteData = (data.by_site || []).map(s => ({
        name: s.site_name,
        value: s.total_count
      }))
      siteChartInstance.setOption({
        series: [{
          type: 'pie',
          data: siteData
        }]
      })
    }
  } catch (error) {
    console.error('Failed to load statistics:', error)
  }
}

onMounted(() => {
  // Init charts
  processingChartInstance = echarts.init(processingChart.value)
  siteChartInstance = echarts.init(siteChart.value)

  processingChartInstance.setOption({
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie',
      radius: '50%'
    }]
  })

  siteChartInstance.setOption({
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie',
      radius: '50%'
    }]
  })

  loadStats()
  // Refresh every 10 seconds
  const interval = setInterval(loadStats, 10000)
  onUnmounted(() => {
    clearInterval(interval)
    processingChartInstance?.dispose()
    siteChartInstance?.dispose()
  })
})
</script>

<style scoped>
.dashboard h2 {
  margin-bottom: 1.5rem;
}

.stats-row {
  margin-bottom: 1.5rem;
}

.stat-card {
  text-align: center;
}

.stat-value {
  font-size: 2rem;
  font-weight: bold;
  color: #409eff;
}

.stat-label {
  color: #606266;
  margin-top: 0.5rem;
}

.charts-row h3 {
  margin-bottom: 1rem;
}
</style>
