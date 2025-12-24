<template>
  <div class="processing">
    <h2>Processing Pipeline</h2>

    <el-card class="actions-card">
      <el-row :gutter="20">
        <el-col :span="12">
          <h3>Preprocessing (GLM-4)</h3>
          <p>Process raw questions through LLM validation and correction</p>
          <el-button type="primary" @click="startPreprocessing" :loading="processing">
            Start Preprocessing
          </el-button>
        </el-col>
        <el-col :span="12">
          <h3>Lean Conversion (Kimina)</h3>
          <p>Convert preprocessed questions to Lean 4</p>
          <el-button type="success" @click="startLeanConversion" :loading="processing">
            Start Lean Conversion
          </el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-card class="status-card">
      <h3>Pipeline Status</h3>
      <el-steps :active="getActiveStep()" finish-status="success">
        <el-step title="Raw Data" description="Crawled from web"></el-step>
        <el-step title="Preprocessed" description="LLM validated"></el-step>
        <el-step title="Lean Converted" description="Formalized in Lean 4"></el-step>
      </el-steps>
    </el-card>

    <el-card class="queue-card">
      <h3>Processing Queue</h3>
      <el-table :data="queueStats" stripe>
        <el-table-column prop="status" label="Status" width="200" />
        <el-table-column prop="count" label="Count" width="150" />
        <el-table-column label="Progress">
          <template #default="{ row }">
            <el-progress :percentage="getPercentage(row.status)" />
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { statisticsApi, processingApi } from '@/api'

const processing = ref(false)
const queueStats = ref([])
const totalQuestions = ref(0)

async function loadStats() {
  try {
    const data = await statisticsApi.overview()
    const ps = data.processing_status || {}
    totalQuestions.value = data.total_questions || 0
    queueStats.value = [
      { status: 'Raw', count: ps.raw || 0 },
      { status: 'Preprocessed', count: ps.preprocessed || 0 },
      { status: 'Lean Converted', count: ps.lean_converted || 0 },
      { status: 'Failed', count: ps.failed || 0 }
    ]
  } catch (error) {
    ElMessage.error('Failed to load statistics')
  }
}

function getActiveStep() {
  // Return step based on pipeline state
  if (queueStats.value.find(s => s.status === 'Lean Converted')?.count > 0) return 2
  if (queueStats.value.find(s => s.status === 'Preprocessed')?.count > 0) return 1
  return 0
}

function getPercentage(status) {
  if (totalQuestions.value === 0) return 0
  const item = queueStats.value.find(s => s.status === status)
  return Math.round((item?.count || 0) / totalQuestions.value * 100)
}

async function startPreprocessing() {
  processing.value = true
  try {
    const result = await processingApi.preprocess({ limit: 10 })
    ElMessage.success(result.message)
    await loadStats()
  } catch (error) {
    ElMessage.error(error.message || 'Failed to start preprocessing')
  } finally {
    processing.value = false
  }
}

async function startLeanConversion() {
  processing.value = true
  try {
    const result = await processingApi.startLean({ limit: 10 })
    ElMessage.success(result.message)
    await loadStats()
  } catch (error) {
    ElMessage.error(error.message || 'Failed to start Lean conversion')
  } finally {
    processing.value = false
  }
}

onMounted(() => {
  loadStats()
})
</script>

<style scoped>
.processing h2 {
  margin-bottom: 1.5rem;
}

.actions-card, .status-card, .queue-card {
  margin-bottom: 1.5rem;
}

.actions-card h3 {
  margin-bottom: 0.5rem;
}

.status-card {
  padding: 1rem 0;
}
</style>
