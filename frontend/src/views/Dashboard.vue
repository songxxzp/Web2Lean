<template>
  <div class="dashboard">
    <h2>Dashboard</h2>

    <!-- Basic Statistics Cards -->
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

    <!-- Detailed Statistics -->
    <el-row :gutter="20" class="detailed-stats-row">
      <!-- Preprocessing Statistics -->
      <el-col :span="8">
        <el-card class="detail-card">
          <h3>Preprocessing Statistics</h3>
          <div class="stat-item">
            <span class="stat-item-label">Total Processed:</span>
            <span class="stat-item-value">{{ preprocessingStats.total_processed || 0 }}</span>
          </div>
          <div class="stat-item success">
            <span class="stat-item-label">Success:</span>
            <span class="stat-item-value">{{ preprocessingStats.success || 0 }}</span>
          </div>
          <div class="stat-item error">
            <span class="stat-item-label">Failed:</span>
            <span class="stat-item-value">{{ preprocessingStats.failed || 0 }}</span>
          </div>
          <div class="stat-item warning">
            <span class="stat-item-label">Can't Convert:</span>
            <span class="stat-item-value">{{ preprocessingStats.cant_convert || 0 }}</span>
          </div>
          <el-progress
            :percentage="getPreprocessingSuccessRate()"
            :color="getProgressColor(getPreprocessingSuccessRate())"
            :stroke-width="8"
          />
          <div class="rate-label">Success Rate</div>
        </el-card>
      </el-col>

      <!-- Verification Statistics -->
      <el-col :span="8">
        <el-card class="detail-card">
          <h3>Lean Verification Statistics</h3>
          <div class="stat-item">
            <span class="stat-item-label">Total Checked:</span>
            <span class="stat-item-value">{{ verificationStats.total_checked || 0 }}</span>
          </div>
          <div class="stat-item success">
            <span class="stat-item-label">Fully Passed:</span>
            <span class="stat-item-value">{{ verificationStats.passed || 0 }}</span>
          </div>
          <div class="stat-item warning">
            <span class="stat-item-label">Warnings (Passed):</span>
            <span class="stat-item-value">{{ verificationStats.warning || 0 }}</span>
          </div>
          <div class="stat-item error">
            <span class="stat-item-label">Failed:</span>
            <span class="stat-item-value">{{ verificationStats.failed || 0 }}</span>
          </div>
          <el-progress
            :percentage="getVerificationPassRate()"
            :color="getProgressColor(getVerificationPassRate())"
            :stroke-width="8"
          />
          <div class="rate-label">Verification Pass Rate (Passed + Warning)</div>
        </el-card>
      </el-col>

      <!-- Site Statistics Summary -->
      <el-col :span="8">
        <el-card class="detail-card">
          <h3>Site Statistics Summary</h3>
          <el-table :data="siteStats" stripe size="small" max-height="200">
            <el-table-column prop="site_name" label="Site" width="120" />
            <el-table-column prop="total_questions" label="Questions" width="70" />
            <el-table-column prop="avg_answers_per_question" label="Avg Answers" width="90" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- Charts Row -->
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

    <!-- Detailed Site Statistics Table -->
    <el-row :gutter="20" class="table-row">
      <el-col :span="24">
        <el-card>
          <h3>Detailed Site Statistics</h3>
          <el-table :data="siteStats" stripe>
            <el-table-column prop="site_name" label="Site Name" width="200" />
            <el-table-column prop="total_questions" label="Total Questions" width="150" sortable />
            <el-table-column prop="total_answers" label="Total Answers" width="150" sortable />
            <el-table-column prop="avg_answers_per_question" label="Avg Answers/Question" width="180" sortable />
            <el-table-column prop="avg_question_length" label="Avg Question Length (chars)" width="220" sortable />
            <el-table-column prop="avg_answer_length" label="Avg Answer Length (chars)" width="220" sortable />
          </el-table>
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
const preprocessingStats = ref({})
const verificationStats = ref({})
const siteStats = ref([])
const processingChart = ref(null)
const siteChart = ref(null)
let processingChartInstance = null
let siteChartInstance = null

function getPreprocessingSuccessRate() {
  const total = preprocessingStats.value.total_processed || 0
  const success = preprocessingStats.value.success || 0
  return total > 0 ? Math.round((success / total) * 100) : 0
}

function getVerificationPassRate() {
  const total = verificationStats.value.total_checked || 0
  const verified = verificationStats.value.total_verified || 0
  return total > 0 ? Math.round((verified / total) * 100) : 0
}

function getProgressColor(percentage) {
  if (percentage >= 80) return '#67c23a'
  if (percentage >= 60) return '#e6a23c'
  return '#f56c6c'
}

async function loadStats() {
  try {
    // Load basic stats
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

async function loadDetailedStats() {
  try {
    const data = await statisticsApi.detailed()
    preprocessingStats.value = data.preprocessing || {}
    verificationStats.value = data.verification || {}
    siteStats.value = data.by_site_detailed || []
  } catch (error) {
    console.error('Failed to load detailed statistics:', error)
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
  loadDetailedStats()

  // Refresh every 10 seconds
  const interval = setInterval(() => {
    loadStats()
    loadDetailedStats()
  }, 10000)

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

.detailed-stats-row {
  margin-bottom: 1.5rem;
}

.table-row {
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

.detail-card h3 {
  margin-bottom: 1rem;
  font-size: 1.1rem;
  color: #303133;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  padding: 0.5rem 0;
  border-bottom: 1px solid #ebeef5;
}

.stat-item:last-of-type {
  border-bottom: none;
  margin-bottom: 1rem;
}

.stat-item-label {
  font-weight: 500;
  color: #606266;
}

.stat-item-value {
  font-weight: bold;
  color: #303133;
}

.stat-item.success .stat-item-value {
  color: #67c23a;
}

.stat-item.warning .stat-item-value {
  color: #e6a23c;
}

.stat-item.error .stat-item-value {
  color: #f56c6c;
}

.rate-label {
  text-align: center;
  margin-top: 0.5rem;
  font-size: 0.9rem;
  color: #909399;
}

.charts-row h3 {
  margin-bottom: 1rem;
}

.table-row h3 {
  margin-bottom: 1rem;
}
</style>
