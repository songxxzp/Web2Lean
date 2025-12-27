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
          <el-button type="danger" @click="clearAll('lean')" :loading="clearing">
            Clear All Lean Code
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
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="loadQuestions">Search</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="questions" stripe @row-click="showDetail">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="title" label="Title" show-overflow-tooltip />
      <el-table-column prop="score" label="Score" width="100" />
      <el-table-column prop="answer_count" label="Answers" width="100" />
      <el-table-column label="Status" width="150">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.status)">
            {{ row.status }}
          </el-tag>
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

    <!-- Question Detail Dialog -->
    <el-dialog v-model="detailVisible" title="Question Detail" width="70%">
      <div v-if="selectedQuestion">
        <div style="margin-bottom: 1rem;">
          <el-button-group>
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

        <h3>{{ selectedQuestion.title }}</h3>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="ID">{{ selectedQuestion.id }}</el-descriptions-item>
          <el-descriptions-item label="Score">{{ selectedQuestion.score }}</el-descriptions-item>
          <el-descriptions-item label="Status">
            <el-tag>{{ selectedQuestion.processing_status?.status }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="Answers">{{ selectedQuestion.answers?.length || 0 }}</el-descriptions-item>
        </el-descriptions>

        <el-tabs v-model="activeTab">
          <el-tab-pane label="Original Body" name="original">
            <div class="content">{{ selectedQuestion.body }}</div>
          </el-tab-pane>
          <el-tab-pane label="Preprocessed" name="preprocessed">
            <div class="content">
              {{ selectedQuestion.processing_status?.preprocessed_body || 'Not processed' }}
            </div>
          </el-tab-pane>
          <el-tab-pane label="Lean Code" name="lean">
            <pre class="code">{{ selectedQuestion.processing_status?.lean_code || 'Not converted' }}</pre>
          </el-tab-pane>
          <el-tab-pane label="Answers" name="answers">
            <div v-for="(answer, index) in selectedQuestion.answers" :key="answer.id" class="answer">
              <strong>Answer {{ index + 1 }} {{ answer.is_accepted ? '(✓ Accepted)' : '' }}</strong>
              <div class="content">{{ answer.body }}</div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { databaseApi, configApi } from '@/api'

const filters = ref({
  site_id: null,
  status: null
})

const pagination = ref({
  page: 1,
  pageSize: 20,
  total: 0
})

const questions = ref([])
const sites = ref([])
const detailVisible = ref(false)
const selectedQuestion = ref(null)
const activeTab = ref('original')
const clearing = ref(false)

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
  loadQuestions()
}

function showDetail(row) {
  databaseApi.getQuestion(row.id).then(q => {
    selectedQuestion.value = q
    detailVisible.value = true
  }).catch(() => {
    ElMessage.error('Failed to load question detail')
  })
}

function getStatusType(status) {
  const types = {
    raw: 'info',
    preprocessed: 'warning',
    lean_converted: 'success',
    failed: 'danger'
  }
  return types[status] || 'info'
}

async function clearAll(stage) {
  const titles = {
    lean: 'Clear All Lean Code',
    preprocess: 'Clear All Preprocessed Data',
    failed: 'Clear All Failed Questions',
    raw: 'Delete All Data'
  }

  const warnings = {
    lean: 'This will remove all Lean code from all questions. Questions will revert to "preprocessed" status.',
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

onMounted(() => {
  loadSites()
  loadQuestions()
})
</script>

<style scoped>
.filter-form {
  margin-bottom: 1rem;
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
}

.answer {
  margin-bottom: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #eee;
}
</style>
