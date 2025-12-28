<template>
  <div class="database">
    <h2>Database Viewer</h2>

    <!-- Bulk Clear Actions -->
    <el-alert type="warning" :closable="false" style="margin-bottom: 1rem">
      <template #title>
        <strong>Bulk Data Management</strong>
      </template>
      <div style="margin-top: 10px;">
        <el-button-group>
          <el-button type="success" @click="exportVerifiedLean" :loading="exporting">
            Export Verified Lean Data
          </el-button>
          <el-button type="danger" @click="clearAll('lean')" :loading="clearing">
            Clear All Lean Code
          </el-button>
          <el-button type="success" @click="clearAll('verification')" :loading="clearing">
            Clear All Verification Status
          </el-button>
          <el-button type="warning" @click="clearAll('preprocess')" :loading="clearing">
            Clear All Preprocessed
          </el-button>
          <el-button type="primary" @click="clearAll('failed')" :loading="clearing">
            Clear Failed
          </el-button>
          <el-button type="info" @click="clearAll('raw')" :loading="clearing">
            Delete All Data
          </el-button>
        </el-button-group>
      </div>
    </el-alert>

    <el-form :inline="true" class="filter-form">
      <el-form-item label="Site">
        <el-select v-model="filters.site_id" placeholder="All Sites" clearable>
          <el-option
            v-for="site in sites"
            :key="site.site_id"
            :label="site.site_name"
            :value="site.site_id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="Status">
        <el-select v-model="filters.status" placeholder="All Status" clearable>
          <el-option label="Raw" value="raw" />
          <el-option label="Preprocessed" value="preprocessed" />
          <el-option label="Lean Converted" value="lean_converted" />
          <el-option label="Failed" value="failed" />
          <el-option label="Can't Convert" value="cant_convert" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="loadQuestions">Search</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="questions" stripe @row-click="showDetail">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="title" label="Title" show-overflow-tooltip />
      <el-table-column label="Theorem Name" width="180">
        <template #default="{ row }">
          <span v-if="row.processing_status?.theorem_name" class="theorem-name">
            {{ row.processing_status.theorem_name }}
          </span>
          <span v-else style="color: #999;">-</span>
        </template>
      </el-table-column>
      <el-table-column prop="score" label="Score" width="100" />
      <el-table-column prop="answer_count" label="Answers" width="100" />
      <el-table-column label="Status" width="150">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.status)">
            {{ row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="Verification" width="150">
        <template #default="{ row }">
          <el-tag v-if="getVerificationStatus(row)" :type="getVerificationStatusType(getVerificationStatus(row))">
            {{ getVerificationStatusLabel(getVerificationStatus(row)) }}
          </el-tag>
          <span v-else style="color: #999;">-</span>
        </template>
      </el-table-column>
      <el-table-column label="Actions" width="180" fixed="right">
        <template #default="{ row }">
          <el-button-group size="small">
            <el-button
              v-if="row.processing_status?.lean_code"
              type="danger"
              size="small"
              @click.stop="clearQuestionStage(row.id, 'lean')"
            >
              Clear Lean
            </el-button>
            <el-button
              v-if="row.processing_status?.preprocessed_body || row.processing_status?.lean_code"
              type="warning"
              size="small"
              @click.stop="clearQuestionStage(row.id, 'preprocess')"
            >
              Clear Prep
            </el-button>
            <el-button
              type="info"
              size="small"
              @click.stop="clearQuestionStage(row.id, 'raw')"
            >
              Delete
            </el-button>
          </el-button-group>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="pagination.page"
      v-model:page-size="pagination.pageSize"
      :total="pagination.total"
      layout="total, prev, pager, next"
      @current-change="handlePageChange"
    />

    <div style="margin-top: 10px; display: flex; align-items: center; justify-content: center; gap: 8px;">
      <span style="color: #606266;">Go to page:</span>
      <el-input-number
        v-model="jumpPage"
        :min="1"
        :max="maxPages"
        :controls="false"
        style="width: 120px;"
        size="small"
      />
      <el-button type="primary" size="small" @click="jumpToPage">Go</el-button>
      <span style="color: #909399; font-size: 12px;">(Total: {{ maxPages }} pages)</span>
    </div>

    <!-- Question Detail Dialog -->
    <el-dialog v-model="detailVisible" :title="selectedQuestion?.title || 'Question Detail'" width="80%">
      <div v-if="selectedQuestion">
        <div style="margin-bottom: 1rem;">
          <el-button-group>
            <el-button
              v-if="selectedQuestion.processing_status?.question_lean_code || selectedQuestion.processing_status?.lean_code"
              type="success"
              size="small"
              @click="verifyQuestion(selectedQuestion.id)"
              :loading="verifying"
            >
              Verify Lean
            </el-button>
            <el-button
              v-if="selectedQuestion.processing_status?.lean_code"
              type="danger"
              size="small"
              @click="clearQuestionStage(selectedQuestion.id, 'lean')"
            >
              Clear Lean Code
            </el-button>
            <el-button
              v-if="selectedQuestion.processing_status?.preprocessed_body || selectedQuestion.processing_status?.lean_code"
              type="warning"
              size="small"
              @click="clearQuestionStage(selectedQuestion.id, 'preprocess')"
            >
              Clear Preprocessed
            </el-button>
            <el-button
              type="info"
              size="small"
              @click="clearQuestionStage(selectedQuestion.id, 'raw')"
            >
              Delete Question
            </el-button>
          </el-button-group>
        </div>

        <el-descriptions :column="2" border style="margin-bottom: 1rem">
          <el-descriptions-item label="ID">{{ selectedQuestion.id }}</el-descriptions-item>
          <el-descriptions-item label="Score">{{ selectedQuestion.score }}</el-descriptions-item>
          <el-descriptions-item label="Theorem Name">
            <span v-if="selectedQuestion.processing_status?.theorem_name" class="theorem-name">
              {{ selectedQuestion.processing_status.theorem_name }}
            </span>
            <span v-else style="color: #999;">Not generated</span>
          </el-descriptions-item>
          <el-descriptions-item label="Status">
            <el-tag>{{ selectedQuestion.processing_status?.status || 'raw' }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="Answers">{{ selectedQuestion.answers?.length || 0 }}</el-descriptions-item>
        </el-descriptions>

        <el-tabs v-model="activeTab">
          <!-- Raw Question and Answers -->
          <el-tab-pane label="Raw Content" name="raw">
            <h4>Question</h4>
            <div class="content">{{ selectedQuestion.body }}</div>

            <el-divider style="margin: 1.5rem 0;" />

            <h4>Answers</h4>
            <div v-if="selectedQuestion.answers && selectedQuestion.answers.length > 0">
              <div v-for="(answer, index) in sortedAnswers" :key="answer.id" class="answer">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 0.5rem;">
                  <el-tag v-if="answer.is_accepted" type="success" size="small">✓ Accepted</el-tag>
                  <el-tag v-else type="info" size="small">Answer {{ index + 1 }}</el-tag>
                  <el-tag size="small">Score: {{ answer.score }}</el-tag>
                </div>
                <div class="content">{{ answer.body }}</div>
              </div>
            </div>
            <div v-else class="content" style="color: #999; font-style: italic;">
              No answers for this question
            </div>
          </el-tab-pane>

          <!-- Preprocessed Content -->
          <el-tab-pane label="Preprocessed" name="preprocessed">
            <!-- Show preprocessing error if failed at preprocessing stage -->
            <div v-if="selectedQuestion.processing_status?.preprocessing_error &&
                        (selectedQuestion.processing_status.status === 'failed' ||
                         selectedQuestion.processing_status.status === 'cant_convert')">
              <el-alert type="error" :closable="false">
                <strong>Preprocessing Failed:</strong>
                <div style="margin-top: 0.5rem; white-space: pre-wrap;">{{ selectedQuestion.processing_status.preprocessing_error }}</div>
              </el-alert>

              <div v-if="selectedQuestion.processing_status?.correction_notes" style="margin-top: 1rem;">
                <el-alert type="warning" :closable="false">
                  <strong>Details:</strong>
                  <div style="margin-top: 0.5rem; white-space: pre-wrap;">{{ selectedQuestion.processing_status.correction_notes }}</div>
                </el-alert>
              </div>
            </div>

            <!-- Show preprocessed content if available -->
            <div v-else-if="selectedQuestion.processing_status?.preprocessed_body">
              <h4>Preprocessed Question</h4>
              <div class="content">{{ selectedQuestion.processing_status.preprocessed_body }}</div>

              <div v-if="selectedQuestion.processing_status.preprocessed_answer">
                <h4 style="margin-top: 1rem;">Preprocessed Answer</h4>
                <div class="content">{{ selectedQuestion.processing_status.preprocessed_answer }}</div>
              </div>

              <div v-if="selectedQuestion.processing_status.correction_notes" style="margin-top: 1rem;">
                <el-alert type="info" :closable="false">
                  <strong>Correction Notes:</strong>
                  <div style="margin-top: 0.5rem; white-space: pre-wrap;">{{ selectedQuestion.processing_status.correction_notes }}</div>
                </el-alert>
              </div>
            </div>

            <!-- Not processed yet -->
            <div v-else class="content">Not processed yet</div>
          </el-tab-pane>

          <!-- Lean Code -->
          <el-tab-pane label="Lean Code" name="lean">
            <!-- Show verification status -->
            <div v-if="selectedQuestion.processing_status?.verification_status && selectedQuestion.processing_status.verification_status !== 'not_verified'" style="margin-bottom: 1rem;">
              <el-alert
                :type="getVerificationStatusType(selectedQuestion.processing_status.verification_status)"
                :closable="false"
              >
                <template #title>
                  <strong>Verification Status: {{ selectedQuestion.processing_status.verification_status }}</strong>
                </template>
                <div v-if="selectedQuestion.processing_status.verification_time" style="margin-top: 0.5rem;">
                  Time: {{ selectedQuestion.processing_status.verification_time.toFixed(3) }}s
                </div>
                <!-- Show verification messages if any -->
                <div v-if="selectedQuestion.processing_status.verification_messages && selectedQuestion.processing_status.verification_messages.length > 0" style="margin-top: 0.5rem;">
                  <div v-for="(msg, idx) in selectedQuestion.processing_status.verification_messages" :key="idx" style="margin-top: 0.25rem;">
                    <el-tag :type="msg.severity === 'error' ? 'danger' : msg.severity === 'warning' ? 'warning' : 'info'" size="small">
                      Line {{ msg.line }}: {{ msg.message }}
                    </el-tag>
                  </div>
                </div>
              </el-alert>
            </div>

            <!-- Show Lean conversion error first -->
            <div v-if="selectedQuestion.processing_status?.lean_error" style="margin-bottom: 1rem;">
              <el-alert type="error" :closable="false">
                <strong>Lean Conversion Failed:</strong>
                <div style="margin-top: 0.5rem; white-space: pre-wrap;">{{ selectedQuestion.processing_status.lean_error }}</div>
              </el-alert>
            </div>

            <!-- Show Lean code split into question and answer -->
            <div v-if="selectedQuestion.processing_status?.question_lean_code || selectedQuestion.processing_status?.lean_code">
              <!-- Question Lean Code (Theorem Declaration Only) -->
              <div v-if="selectedQuestion.processing_status?.question_lean_code">
                <h4>Question (Theorem Declaration)</h4>
                <pre class="code">{{ selectedQuestion.processing_status.question_lean_code }}</pre>
              </div>

              <!-- Answer Lean Code (Complete Theorem with Proof) -->
              <div v-if="selectedQuestion.processing_status?.answer_lean_code">
                <el-divider style="margin: 1.5rem 0;" />
                <h4>Lean Theorem Statement (Complete with Proof)</h4>
                <pre class="code">{{ selectedQuestion.processing_status.answer_lean_code }}</pre>
              </div>

              <!-- Fallback: Show combined lean_code if separate fields don't exist -->
              <div v-if="!selectedQuestion.processing_status?.question_lean_code && selectedQuestion.processing_status?.lean_code">
                <h4>Lean Formalization</h4>
                <pre class="code">{{ selectedQuestion.processing_status.lean_code }}</pre>
              </div>
            </div>

            <!-- Not converted yet -->
            <div v-else-if="!selectedQuestion.processing_status?.lean_error" class="content">Not converted yet</div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { databaseApi, configApi, verificationApi } from '@/api'

const filters = ref({
  site_id: null,
  status: null
})

const pagination = ref({
  page: 1,
  pageSize: 20,
  total: 0
})

const jumpPage = ref(1)

// Computed max pages to avoid min > max error
const maxPages = computed(() => {
  const totalPages = Math.ceil(pagination.value.total / pagination.value.pageSize)
  return totalPages > 0 ? totalPages : 1
})

const questions = ref([])
const sites = ref([])
const detailVisible = ref(false)
const selectedQuestion = ref(null)
const activeTab = ref('raw')
const clearing = ref(false)
const verifying = ref(false)
const exporting = ref(false)

// Sort answers: accepted first, then by score
const sortedAnswers = computed(() => {
  if (!selectedQuestion.value?.answers) return []
  return [...selectedQuestion.value.answers].sort((a, b) => {
    if (a.is_accepted && !b.is_accepted) return -1
    if (!a.is_accepted && b.is_accepted) return 1
    return b.score - a.score
  })
})

async function loadSites() {
  try {
    sites.value = await configApi.getSites()
  } catch (error) {
    console.error('Failed to load sites')
  }
}

async function loadQuestions() {
  try {
    const data = await databaseApi.listQuestions({
      site_id: filters.value.site_id,
      status: filters.value.status,
      limit: pagination.value.pageSize,
      offset: (pagination.value.page - 1) * pagination.value.pageSize
    })
    questions.value = data.questions
    pagination.value.total = data.count
  } catch (error) {
    ElMessage.error('Failed to load questions')
  }
}

function handlePageChange(newPage) {
  pagination.value.page = newPage
  jumpPage.value = newPage
  loadQuestions()
}

function jumpToPage() {
  if (jumpPage.value < 1) {
    jumpPage.value = 1
  } else if (jumpPage.value > maxPages.value) {
    jumpPage.value = maxPages.value
  }
  pagination.value.page = jumpPage.value
  loadQuestions()
}

function showDetail(row) {
  databaseApi.getQuestion(row.id).then(q => {
    selectedQuestion.value = q
    detailVisible.value = true
    activeTab.value = 'raw'
  }).catch(() => {
    ElMessage.error('Failed to load question detail')
  })
}

function getStatusType(status) {
  const types = {
    raw: 'info',
    preprocessed: 'warning',
    lean_converted: 'success',
    failed: 'danger',
    cant_convert: 'warning'
  }
  return types[status] || 'info'
}

function getVerificationStatus(row) {
  // Get verification status from processing_status
  return row.processing_status?.verification_status || null
}

function getVerificationStatusLabel(status) {
  const labels = {
    'not_verified': 'Not Verified',
    'verifying': 'Verifying',
    'passed': 'Passed',
    'warning': 'Warning',
    'failed': 'Failed',
    'connection_error': 'Conn Error',
    'error': 'Error'
  }
  return labels[status] || status
}

async function clearAll(stage) {
  const titles = {
    lean: 'Clear All Lean Code',
    verification: 'Clear All Verification Status',
    preprocess: 'Clear All Preprocessed Data',
    failed: 'Clear All Failed Questions',
    raw: 'Delete All Data'
  }

  const warnings = {
    lean: 'This will remove all Lean code from all questions. Questions will revert to "preprocessed" status.',
    verification: 'This will remove all verification status but keep Lean code. You can re-verify questions.',
    preprocess: 'This will remove all preprocessed data and Lean code. Questions will revert to "raw" status.',
    failed: 'This will reset all failed questions to "raw" status, clearing all error data. You can retry processing them.',
    raw: 'This will DELETE ALL QUESTIONS from the database. This action cannot be undone!'
  }

  try {
    await ElMessageBox.confirm(
      warnings[stage],
      titles[stage],
      {
        confirmButtonText: 'Confirm',
        cancelButtonText: 'Cancel',
        type: stage === 'raw' ? 'error' : 'warning'
      }
    )

    clearing.value = true
    const result = await databaseApi.clearData(stage)
    ElMessage.success(result.message)
    await loadQuestions()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || 'Failed to clear data')
    }
  } finally {
    clearing.value = false
  }
}

async function clearQuestionStage(questionId, stage) {
  const titles = {
    lean: 'Clear Lean Code',
    preprocess: 'Clear Preprocessed Data',
    raw: 'Delete Question'
  }

  const warnings = {
    lean: 'This will remove the Lean code from this question.',
    preprocess: 'This will remove preprocessed data and Lean code from this question.',
    raw: 'This will DELETE this question and all related data. This action cannot be undone!'
  }

  try {
    await ElMessageBox.confirm(
      warnings[stage],
      titles[stage],
      {
        confirmButtonText: 'Confirm',
        cancelButtonText: 'Cancel',
        type: stage === 'raw' ? 'error' : 'warning'
      }
    )

    const result = await databaseApi.clearQuestionStage(questionId, stage)
    ElMessage.success(result.message)

    if (detailVisible.value && selectedQuestion.value?.id === questionId) {
      detailVisible.value = false
    }

    await loadQuestions()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || 'Failed to clear data')
    }
  }
}

async function exportVerifiedLean() {
  exporting.value = true
  try {
    await databaseApi.exportVerifiedLean()
    ElMessage.success('Export completed successfully')
  } catch (error) {
    ElMessage.error(error.message || 'Export failed')
  } finally {
    exporting.value = false
  }
}

async function verifyQuestion(questionId) {
  verifying.value = true
  try {
    const result = await verificationApi.verify(questionId)

    if (result.verification_status === 'passed') {
      ElMessage.success(`Verification passed in ${result.total_time.toFixed(2)}s`)
    } else if (result.verification_status === 'warning') {
      ElMessage.warning(`Verification passed with ${result.message_count} warnings in ${result.total_time.toFixed(2)}s`)
    } else if (result.verification_status === 'failed') {
      ElMessage.error(`Verification failed: ${result.message_count} errors`)
    } else if (result.verification_status === 'connection_error') {
      ElMessage.error('Failed to connect to kimina-lean-server')
    }

    // Reload question data
    selectedQuestion.value = await databaseApi.getQuestion(questionId)
  } catch (error) {
    ElMessage.error(error.message || 'Verification failed')
  } finally {
    verifying.value = false
  }
}

function getVerificationStatusType(status) {
  const types = {
    'not_verified': 'info',
    'verifying': 'warning',
    'passed': 'success',
    'warning': 'warning',
    'failed': 'danger',
    'connection_error': 'danger',
    'error': 'danger'
  }
  return types[status] || 'info'
}

onMounted(() => {
  loadSites()
  loadQuestions()
})
</script>

<style scoped>
.filter-form {
  margin-bottom: 1rem;
}

.theorem-name {
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Code', 'Droid Sans Mono', 'Source Code Pro', monospace;
  color: #409eff;
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: inline-block;
  max-width: 100%;
}

.content {
  white-space: pre-wrap;
  word-break: break-word;
  padding: 1rem;
  background: #f5f7fa;
  border-radius: 4px;
  max-height: 400px;
  overflow-y: auto;
}

.code {
  background: #2c3e50;
  color: #ecf0f1;
  padding: 1rem;
  border-radius: 4px;
  max-height: 400px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.answer {
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #eee;
}

.answer:last-child {
  border-bottom: none;
}
</style>
