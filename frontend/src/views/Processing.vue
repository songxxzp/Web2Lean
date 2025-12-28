<template>
  <div class="processing">
    <h2>Processing Pipeline</h2>

    <el-card class="actions-card">
      <el-row :gutter="20">
        <el-col :span="8">
          <h3>Preprocessing (GLM-4.7)</h3>
          <p>Process raw questions through LLM validation and correction</p>

          <!-- Processing Controls -->
          <el-space v-if="preprocessTask" direction="vertical" style="width: 100%">
            <div style="display: flex; align-items: center; gap: 10px;">
              <el-progress
                :percentage="preprocessTask.progress_percent"
                :status="preprocessTask.status === 'completed' ? 'success' : undefined"
                style="flex: 1"
              >
                <template #default="{ percentage }">
                  <span>{{ percentage }}% ({{ preprocessTask.processed }}/{{ preprocessTask.total }})</span>
                </template>
              </el-progress>
            </div>

            <el-space>
              <el-button
                v-if="preprocessTask.status === 'running'"
                type="warning"
                @click="pausePreprocessing"
                :loading="pauseLoading"
              >
                Pause
              </el-button>
              <el-button
                v-if="preprocessTask.status === 'paused'"
                type="success"
                @click="resumePreprocessing"
                :loading="resumeLoading"
              >
                Resume
              </el-button>
              <el-button
                v-if="['running', 'paused'].includes(preprocessTask.status)"
                type="danger"
                @click="stopPreprocessing"
                :loading="stopLoading"
              >
                Stop
              </el-button>
            </el-space>

            <div v-if="preprocessTask.status !== 'completed'" style="color: #909399; font-size: 12px;">
              Status: {{ preprocessTask.status }} | Failed: {{ preprocessTask.failed }}
            </div>
          </el-space>

          <!-- Start Controls (only shown when no active task) -->
          <el-space v-else direction="vertical" style="width: 100%">
            <el-space>
              <el-input-number
                v-model="preprocessLimit"
                :min="0"
                :max="1000"
                placeholder="0 for all"
                style="width: 150px"
              />
              <el-button
                type="primary"
                @click="startPreprocessing"
                :loading="processing"
              >
                Start
              </el-button>
            </el-space>
            <div style="color: #909399; font-size: 12px;">
              Set to 0 to process all raw questions
            </div>
          </el-space>
        </el-col>

        <el-col :span="8">
          <h3>Lean Conversion (Kimina)</h3>
          <p>Convert preprocessed questions to Lean 4</p>

          <!-- Processing Controls -->
          <el-space v-if="leanTask" direction="vertical" style="width: 100%">
            <div style="display: flex; align-items: center; gap: 10px;">
              <el-progress
                :percentage="leanTask.progress_percent"
                :status="leanTask.status === 'completed' ? 'success' : undefined"
                style="flex: 1"
              >
                <template #default="{ percentage }">
                  <span>{{ percentage }}% ({{ leanTask.processed }}/{{ leanTask.total }})</span>
                </template>
              </el-progress>
            </div>

            <el-space>
              <el-button
                v-if="leanTask.status === 'running'"
                type="warning"
                @click="pauseLean"
                :loading="pauseLoading"
              >
                Pause
              </el-button>
              <el-button
                v-if="leanTask.status === 'paused'"
                type="success"
                @click="resumeLean"
                :loading="resumeLoading"
              >
                Resume
              </el-button>
              <el-button
                v-if="['running', 'paused'].includes(leanTask.status)"
                type="danger"
                @click="stopLean"
                :loading="stopLoading"
              >
                Stop
              </el-button>
            </el-space>

            <div v-if="leanTask.status !== 'completed'" style="color: #909399; font-size: 12px;">
              Status: {{ leanTask.status }} | Failed: {{ leanTask.failed }}
            </div>
          </el-space>

          <!-- Start Controls (only shown when no active task) -->
          <el-space v-else direction="vertical" style="width: 100%">
            <el-space>
              <el-input-number
                v-model="leanLimit"
                :min="0"
                :max="1000"
                placeholder="0 for all"
                style="width: 150px"
              />
              <el-select v-model="leanConverter" style="width: 200px" placeholder="Select Converter">
                <el-option label="Kimina (Legacy)" value="kimina" />
                <el-option label="GLM LLM Agent" value="llm" />
              </el-select>
              <el-button
                type="success"
                @click="startLeanConversion"
                :loading="processing"
              >
                Start
              </el-button>
            </el-space>
            <div style="color: #909399; font-size: 12px;">
              Set to 0 to process all preprocessed questions
            </div>
          </el-space>
        </el-col>

        <el-col :span="8">
          <h3>Lean Verification (Kimina)</h3>
          <p>Verify Lean code against kimina-lean-server</p>

          <!-- Processing Controls -->
          <el-space v-if="verificationTask" direction="vertical" style="width: 100%">
            <div style="display: flex; align-items: center; gap: 10px;">
              <el-progress
                :percentage="verificationTask.progress_percent"
                :status="verificationTask.status === 'completed' ? 'success' : undefined"
                style="flex: 1"
              >
                <template #default="{ percentage }">
                  <span>{{ percentage }}% ({{ verificationTask.processed }}/{{ verificationTask.total }})</span>
                </template>
              </el-progress>
            </div>

            <el-space>
              <el-button
                v-if="verificationTask.status === 'running'"
                type="warning"
                @click="pauseVerification"
                :loading="pauseLoading"
              >
                Pause
              </el-button>
              <el-button
                v-if="verificationTask.status === 'paused'"
                type="success"
                @click="resumeVerification"
                :loading="resumeLoading"
              >
                Resume
              </el-button>
              <el-button
                v-if="['running', 'paused'].includes(verificationTask.status)"
                type="danger"
                @click="stopVerification"
                :loading="stopLoading"
              >
                Stop
              </el-button>
            </el-space>

            <div v-if="verificationTask.status !== 'completed'" style="color: #909399; font-size: 12px;">
              Status: {{ verificationTask.status }} | Passed: {{ verificationTask.passed }} | Failed: {{ verificationTask.failed }}
            </div>
          </el-space>

          <!-- Start Controls (only shown when no active task) -->
          <el-space v-else direction="vertical" style="width: 100%">
            <el-space>
              <el-input-number
                v-model="verificationLimit"
                :min="0"
                :max="1000"
                placeholder="0 for all"
                style="width: 150px"
              />
              <el-button
                type="info"
                @click="startVerification"
                :loading="processing"
              >
                Start
              </el-button>
            </el-space>
            <div style="color: #909399; font-size: 12px;">
              Set to 0 to verify all converted questions
            </div>
          </el-space>
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
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { statisticsApi, processingApi, verificationApi } from '@/api'

const processing = ref(false)
const pauseLoading = ref(false)
const resumeLoading = ref(false)
const stopLoading = ref(false)
const queueStats = ref([])
const totalQuestions = ref(0)
const preprocessLimit = ref(10)
const leanLimit = ref(10)
const leanConverter = ref('kimina')  // 'kimina' or 'llm'
const verificationLimit = ref(10)

const preprocessTask = ref(null)
const leanTask = ref(null)
const verificationTask = ref(null)

let progressInterval = null

async function loadStats() {
  try {
    const data = await statisticsApi.overview()
    const ps = data.processing_status || {}
    totalQuestions.value = data.total_questions || 0
    queueStats.value = [
      { status: 'Raw', count: ps.raw || 0 },
      { status: 'Preprocessed', count: ps.preprocessed || 0 },
      { status: 'Lean Converted', count: ps.lean_converted || 0 },
      { status: 'Lean Verified', count: ps.lean_verified || 0 },
      { status: 'Failed', count: ps.failed || 0 }
    ]
  } catch (error) {
    ElMessage.error('Failed to load statistics')
  }
}

async function loadProgress() {
  try {
    const preprocessResp = await processingApi.getProgress('preprocessing')
    if (preprocessResp.active) {
      preprocessTask.value = preprocessResp.progress
    } else {
      preprocessTask.value = null
    }

    // Check for either kimina or llm lean conversion tasks
    const kiminaResp = await processingApi.getProgress('lean_conversion_kimina')
    const llmResp = await processingApi.getProgress('lean_conversion_llm')

    // Show progress for whichever is active (prioritize based on selected converter)
    if (leanConverter.value === 'kimina' && kiminaResp.active) {
      leanTask.value = kiminaResp.progress
    } else if (leanConverter.value === 'llm' && llmResp.active) {
      leanTask.value = llmResp.progress
    } else if (kiminaResp.active) {
      leanTask.value = kiminaResp.progress
    } else if (llmResp.active) {
      leanTask.value = llmResp.progress
    } else {
      leanTask.value = null
    }

    const verifyResp = await processingApi.getProgress('verification')
    if (verifyResp.active) {
      verificationTask.value = verifyResp.progress
    } else {
      verificationTask.value = null
    }
  } catch (error) {
    console.error('Failed to load progress:', error)
  }
}

function getActiveStep() {
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
    const limit = preprocessLimit.value === 0 ? 10000 : preprocessLimit.value
    const result = await processingApi.preprocess({ limit })
    ElMessage.success(result.message)

    if (result.task_id) {
      preprocessTask.value = result.progress
      startProgressPolling()
    }

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
    const limit = leanLimit.value === 0 ? 10000 : leanLimit.value
    const result = await processingApi.startLean({ limit, converter: leanConverter.value })
    ElMessage.success(result.message)

    if (result.task_id) {
      leanTask.value = result.progress
      startProgressPolling()
    }

    await loadStats()
  } catch (error) {
    ElMessage.error(error.message || 'Failed to start Lean conversion')
  } finally {
    processing.value = false
  }
}

async function pausePreprocessing() {
  pauseLoading.value = true
  try {
    await processingApi.pauseTask(preprocessTask.value.task_id)
    ElMessage.success('Preprocessing paused')
    await loadProgress()
  } catch (error) {
    ElMessage.error(error.message || 'Failed to pause preprocessing')
  } finally {
    pauseLoading.value = false
  }
}

async function resumePreprocessing() {
  resumeLoading.value = true
  try {
    await processingApi.resumeTask(preprocessTask.value.task_id)
    ElMessage.success('Preprocessing resumed')
    await loadProgress()
  } catch (error) {
    ElMessage.error(error.message || 'Failed to resume preprocessing')
  } finally {
    resumeLoading.value = false
  }
}

async function stopPreprocessing() {
  stopLoading.value = true
  try {
    await processingApi.stopTask(preprocessTask.value.task_id)
    ElMessage.success('Preprocessing stopped')
    await loadProgress()
    await loadStats()
  } catch (error) {
    ElMessage.error(error.message || 'Failed to stop preprocessing')
  } finally {
    stopLoading.value = false
  }
}

async function pauseLean() {
  pauseLoading.value = true
  try {
    await processingApi.pauseTask(leanTask.value.task_id)
    ElMessage.success('Lean conversion paused')
    await loadProgress()
  } catch (error) {
    ElMessage.error(error.message || 'Failed to pause Lean conversion')
  } finally {
    pauseLoading.value = false
  }
}

async function resumeLean() {
  resumeLoading.value = true
  try {
    await processingApi.resumeTask(leanTask.value.task_id)
    ElMessage.success('Lean conversion resumed')
    await loadProgress()
  } catch (error) {
    ElMessage.error(error.message || 'Failed to resume Lean conversion')
  } finally {
    resumeLoading.value = false
  }
}

async function stopLean() {
  stopLoading.value = true
  try {
    await processingApi.stopTask(leanTask.value.task_id)
    ElMessage.success('Lean conversion stopped')
    await loadProgress()
    await loadStats()
  } catch (error) {
    ElMessage.error(error.message || 'Failed to stop Lean conversion')
  } finally {
    stopLoading.value = false
  }
}

async function startVerification() {
  processing.value = true
  try {
    // Use verification API to start batch verification
    const limit = verificationLimit.value === 0 ? 10000 : verificationLimit.value

    // Start verification as a background task
    const result = await verificationApi.verifyAll({ limit, async: true })

    if (result.task_id) {
      verificationTask.value = result.progress
      ElMessage.success('Lean verification started')
      startProgressPolling()
    } else {
      // Synchronous completion
      const totalTime = result.results?.reduce((sum, r) => sum + (r.total_time || 0), 0) || 0
      ElMessage.success(`Verification completed: ${result.passed} passed, ${result.failed} failed, ${result.total_time || totalTime.toFixed(2)}s`)
      await loadStats()
    }
  } catch (error) {
    ElMessage.error(error.message || 'Failed to start verification')
  } finally {
    processing.value = false
  }
}

async function pauseVerification() {
  pauseLoading.value = true
  try {
    await processingApi.pauseTask(verificationTask.value.task_id)
    ElMessage.success('Verification paused')
    await loadProgress()
  } catch (error) {
    ElMessage.error(error.message || 'Failed to pause verification')
  } finally {
    pauseLoading.value = false
  }
}

async function resumeVerification() {
  resumeLoading.value = true
  try {
    await processingApi.resumeTask(verificationTask.value.task_id)
    ElMessage.success('Verification resumed')
    await loadProgress()
  } catch (error) {
    ElMessage.error(error.message || 'Failed to resume verification')
  } finally {
    resumeLoading.value = false
  }
}

async function stopVerification() {
  stopLoading.value = true
  try {
    await processingApi.stopTask(verificationTask.value.task_id)
    ElMessage.success('Verification stopped')
    await loadProgress()
    await loadStats()
  } catch (error) {
    ElMessage.error(error.message || 'Failed to stop verification')
  } finally {
    stopLoading.value = false
  }
}

function startProgressPolling() {
  if (progressInterval) return

  progressInterval = setInterval(async () => {
    await loadProgress()
    await loadStats()

    // Stop polling if no active tasks
    if (!preprocessTask.value && !leanTask.value && !verificationTask.value) {
      stopProgressPolling()
    }
  }, 2000) // Poll every 2 seconds
}

function stopProgressPolling() {
  if (progressInterval) {
    clearInterval(progressInterval)
    progressInterval = null
  }
}

onMounted(async () => {
  await loadStats()
  await loadProgress()

  // Start polling if there are active tasks
  if (preprocessTask.value || leanTask.value || verificationTask.value) {
    startProgressPolling()
  }
})

onUnmounted(() => {
  stopProgressPolling()
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
