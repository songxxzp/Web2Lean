<template>
  <div class="scheduler">
    <div class="header-row">
      <h2>Scheduled Tasks</h2>
      <el-button type="primary" @click="showAddDialog">Add Task</el-button>
    </div>

    <!-- Scheduler Status -->
    <el-card class="status-card">
      <template #header>
        <span>Scheduler Status</span>
      </template>
      <el-row :gutter="20">
        <el-col :span="6">
          <div class="status-item">
            <div class="label">Status:</div>
            <el-tag :type="schedulerStatus.running ? 'success' : 'danger'" size="large">
              {{ schedulerStatus.running ? 'Running' : 'Stopped' }}
            </el-tag>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="status-item">
            <div class="label">Active Jobs:</div>
            <span class="value">{{ schedulerStatus.jobs?.length || 0 }}</span>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="status-item">
            <div class="label">Running Tasks:</div>
            <el-tag :type="schedulerStatus.running_tasks?.length > 0 ? 'warning' : 'info'" size="large">
              {{ schedulerStatus.running_tasks?.length || 0 }}
            </el-tag>
          </div>
        </el-col>
        <el-col :span="6">
          <el-button type="primary" size="small" @click="loadTasks">Refresh</el-button>
        </el-col>
      </el-row>
      <el-alert
        v-if="schedulerStatus.running_tasks?.length > 0"
        type="warning"
        :closable="false"
        style="margin-top: 15px"
      >
        <template #title>
          Currently running: {{ schedulerStatus.running_tasks.join(', ') }}
        </template>
      </el-alert>
    </el-card>

    <!-- Tasks Table -->
    <el-card class="tasks-card">
      <el-table :data="tasks" stripe v-loading="loading">
        <el-table-column prop="task_name" label="Task Name" width="180" />
        <el-table-column prop="task_type" label="Type" width="130">
          <template #default="{ row }">
            <el-tag :type="getTaskTypeColor(row.task_type)" size="small">
              {{ formatTaskType(row.task_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="site_name" label="Site" width="150">
          <template #default="{ row }">
            {{ row.site_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="Interval" width="100">
          <template #default="{ row }">
            {{ formatInterval(row) }}
          </template>
        </el-table-column>
        <el-table-column label="Last Run" width="120">
          <template #default="{ row }">
            {{ row.last_run ? formatDate(row.last_run) : 'Never' }}
          </template>
        </el-table-column>
        <el-table-column label="Next Run" width="120">
          <template #default="{ row }">
            {{ row.next_run ? formatDate(row.next_run) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="Status" width="120">
          <template #default="{ row }">
            <el-tag v-if="isTaskRunning(row.task_name)" type="warning" size="small">
              Running
            </el-tag>
            <el-tag v-else-if="row.enabled" type="success" size="small">
              Scheduled
            </el-tag>
            <el-tag v-else type="info" size="small">
              Disabled
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Enabled" width="100">
          <template #default="{ row }">
            <el-switch
              v-model="row.enabled"
              @change="toggleTask(row)"
              :loading="row.updating"
            />
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="editTask(row)">Edit</el-button>
            <el-button
              size="small"
              type="danger"
              @click="confirmDelete(row)"
            >Delete</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Add/Edit Task Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? 'Edit Task' : 'Add New Task'"
      width="600px"
      @closed="resetForm"
    >
      <el-form :model="form" :rules="rules" ref="formRef" label-width="140px">
        <el-form-item label="Task Name" prop="task_name">
          <el-input
            v-model="form.task_name"
            placeholder="Unique task name"
            :disabled="isEdit"
          />
        </el-form-item>

        <el-form-item label="Task Type" prop="task_type">
          <el-select v-model="form.task_type" placeholder="Select type" style="width: 100%">
            <el-option label="Crawl" value="crawl" />
            <el-option label="Preprocess" value="preprocess" />
            <el-option label="Convert Lean" value="convert_lean" />
            <el-option label="Verify" value="verify" />
          </el-select>
        </el-form-item>

        <el-form-item label="Site" prop="site_id" v-if="form.task_type === 'crawl'">
          <el-select v-model="form.site_id" placeholder="Select site" style="width: 100%">
            <el-option
              v-for="site in sites"
              :key="site.site_id"
              :label="site.site_name"
              :value="site.site_id"
            />
          </el-select>
        </el-form-item>

        <el-divider content-position="left">Interval Configuration</el-divider>

        <el-form-item label="Interval">
          <el-row :gutter="10">
            <el-col :span="8">
              <el-input-number
                v-model="form.interval_days"
                :min="0"
                :max="365"
                controls-position="right"
                style="width: 100%"
              />
              <span class="unit-label">Days</span>
            </el-col>
            <el-col :span="8">
              <el-input-number
                v-model="form.interval_hours"
                :min="0"
                :max="23"
                controls-position="right"
                style="width: 100%"
              />
              <span class="unit-label">Hours</span>
            </el-col>
            <el-col :span="8">
              <el-input-number
                v-model="form.interval_minutes"
                :min="0"
                :max="59"
                controls-position="right"
                style="width: 100%"
              />
              <span class="unit-label">Minutes</span>
            </el-col>
          </el-row>
          <div class="interval-preview">
            Total: {{ totalMinutes }} minutes ({{ totalMinutes >= 1440 ? (totalMinutes / 1440).toFixed(1) + ' days' : totalMinutes + ' minutes' }})
          </div>
        </el-form-item>

        <el-form-item label="Enabled">
          <el-switch v-model="form.enabled" />
          <span style="margin-left: 10px; color: #999;">
            Task will {{ form.enabled ? 'run automatically' : 'not run' }}
          </span>
        </el-form-item>

        <el-form-item label="Configuration" v-if="form.task_type !== 'crawl'">
          <el-input
            v-model="form.config_json"
            type="textarea"
            :rows="3"
            placeholder='e.g., {"limit": 10}'
          />
          <span style="color: #999; font-size: 12px;">JSON format</span>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">Cancel</el-button>
        <el-button type="primary" @click="saveTask" :loading="saving">Save</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const API_BASE = '/api/scheduler'

// State
const loading = ref(false)
const tasks = ref([])
const sites = ref([])
const schedulerStatus = ref({ running: false, jobs: [] })
const dialogVisible = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const formRef = ref(null)

// Form
const form = ref({
  task_name: '',
  task_type: 'crawl',
  site_id: null,
  interval_days: 0,
  interval_hours: 24,
  interval_minutes: 0,
  enabled: false,
  config_json: ''
})

const rules = {
  task_name: [
    { required: true, message: 'Please enter task name', trigger: 'blur' }
  ],
  task_type: [
    { required: true, message: 'Please select task type', trigger: 'change' }
  ],
  site_id: [
    { required: true, message: 'Please select site', trigger: 'change' }
  ]
}

// Computed
const totalMinutes = computed(() => {
  return (
    form.value.interval_days * 24 * 60 +
    form.value.interval_hours * 60 +
    form.value.interval_minutes
  )
})

// API functions
async function apiRequest(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`
  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers
    },
    ...options
  }

  if (config.body && typeof config.body === 'object') {
    config.body = JSON.stringify(config.body)
  }

  const response = await fetch(url, config)
  const data = await response.json()

  if (!response.ok) {
    throw new Error(data.error || 'Request failed')
  }

  return data
}

async function loadTasks() {
  loading.value = true
  try {
    const result = await apiRequest('/tasks')
    tasks.value = result.tasks || []
  } catch (error) {
    ElMessage.error('Failed to load tasks: ' + error.message)
  } finally {
    loading.value = false
  }
}

async function loadSites() {
  try {
    const response = await fetch('/api/config/sites')
    const result = await response.json()
    sites.value = result.sites || []
  } catch (error) {
    console.error('Failed to load sites:', error)
  }
}

async function loadSchedulerStatus() {
  try {
    const status = await apiRequest('/status')
    schedulerStatus.value = status
  } catch (error) {
    console.error('Failed to load scheduler status:', error)
  }
}

async function toggleTask(task) {
  task.updating = true
  try {
    await apiRequest(`/tasks/${task.task_name}`, {
      method: 'PUT',
      body: { enabled: task.enabled }
    })
    ElMessage.success(`Task ${task.enabled ? 'enabled' : 'disabled'}`)
    await loadTasks()
    await loadSchedulerStatus()
  } catch (error) {
    ElMessage.error('Failed to update task: ' + error.message)
    task.enabled = !task.enabled // Revert
  } finally {
    task.updating = false
  }
}

async function saveTask() {
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  saving.value = true
  try {
    const data = {
      task_name: form.value.task_name,
      task_type: form.value.task_type,
      site_id: form.value.site_id,
      interval_days: form.value.interval_days,
      interval_hours: form.value.interval_hours,
      interval_minutes: form.value.interval_minutes,
      enabled: form.value.enabled,
      config_json: form.value.config_json || null
    }

    if (isEdit.value) {
      // Remove task_name from data when editing (it's in the URL)
      const { task_name, ...updateData } = data
      await apiRequest(`/tasks/${form.value.task_name}`, {
        method: 'PUT',
        body: updateData
      })
      ElMessage.success('Task updated successfully')
    } else {
      await apiRequest('/tasks', {
        method: 'POST',
        body: data
      })
      ElMessage.success('Task created successfully')
    }

    dialogVisible.value = false
    await loadTasks()
    await loadSchedulerStatus()
  } catch (error) {
    ElMessage.error('Failed to save task: ' + error.message)
  } finally {
    saving.value = false
  }
}

function editTask(task) {
  isEdit.value = true
  form.value = {
    task_name: task.task_name,
    task_type: task.task_type,
    site_id: task.site_id,
    interval_days: task.interval_days || 0,
    interval_hours: task.interval_hours || 0,
    interval_minutes: task.interval_minutes || 0,
    enabled: task.enabled,
    config_json: task.config_json || ''
  }
  dialogVisible.value = true
}

function showAddDialog() {
  isEdit.value = false
  resetForm()
  dialogVisible.value = true
}

function confirmDelete(task) {
  ElMessageBox.confirm(
    `Are you sure to delete task "${task.task_name}"?`,
    'Confirm Delete',
    {
      confirmButtonText: 'Delete',
      cancelButtonText: 'Cancel',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await apiRequest(`/tasks/${task.task_name}`, { method: 'DELETE' })
      ElMessage.success('Task deleted successfully')
      await loadTasks()
      await loadSchedulerStatus()
    } catch (error) {
      ElMessage.error('Failed to delete task: ' + error.message)
    }
  }).catch(() => {
    // User cancelled
  })
}

function resetForm() {
  form.value = {
    task_name: '',
    task_type: 'crawl',
    site_id: null,
    interval_days: 0,
    interval_hours: 24,
    interval_minutes: 0,
    enabled: false,
    config_json: ''
  }
  formRef.value?.clearValidate()
}

// Utility functions
function isTaskRunning(taskName) {
  return schedulerStatus.value.running_tasks?.includes(taskName) || false
}

function formatTaskType(type) {
  const types = {
    crawl: 'Crawl',
    preprocess: 'Preprocess',
    convert_lean: 'Convert',
    verify: 'Verify'
  }
  return types[type] || type
}

function getTaskTypeColor(type) {
  const colors = {
    crawl: 'primary',
    preprocess: 'success',
    convert_lean: 'warning',
    verify: 'info'
  }
  return colors[type] || ''
}

function formatInterval(task) {
  const days = task.interval_days || 0
  const hours = task.interval_hours || 0
  const minutes = task.interval_minutes || 0

  const parts = []
  if (days > 0) parts.push(`${days}d`)
  if (hours > 0) parts.push(`${hours}h`)
  if (minutes > 0) parts.push(`${minutes}m`)

  return parts.length > 0 ? parts.join(' ') : '0m'
}

function formatDate(dateStr) {
  if (!dateStr) return '-'
  try {
    const date = new Date(dateStr)
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return dateStr
  }
}

onMounted(() => {
  loadTasks()
  loadSites()
  loadSchedulerStatus()
})
</script>

<style scoped>
.scheduler {
  padding: 0;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.header-row h2 {
  margin: 0;
}

.status-card {
  margin-bottom: 1.5rem;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.status-item .label {
  color: #666;
  font-weight: 500;
}

.status-item .value {
  font-size: 1.5rem;
  font-weight: bold;
  color: #409eff;
}

.tasks-card {
  margin-bottom: 1.5rem;
}

.unit-label {
  margin-left: 5px;
  color: #999;
  font-size: 12px;
}

.interval-preview {
  margin-top: 10px;
  padding: 8px 12px;
  background: #f0f9ff;
  border-left: 3px solid #409eff;
  border-radius: 4px;
  color: #666;
  font-size: 13px;
}
</style>
