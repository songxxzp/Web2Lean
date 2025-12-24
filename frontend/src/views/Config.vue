<template>
  <div class="config">
    <h2>Configuration</h2>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="Sites" name="sites">
        <el-button type="primary" @click="showAddSiteDialog">Add Site</el-button>

        <el-table :data="sites" stripe style="margin-top: 1rem">
          <el-table-column prop="site_name" label="Name" />
          <el-table-column prop="site_type" label="Type" />
          <el-table-column prop="base_url" label="URL" show-overflow-tooltip />
          <el-table-column label="Enabled">
            <template #default="{ row }">
              <el-switch v-model="row.enabled" @change="toggleSite(row)" />
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="Prompts" name="prompts">
        <el-form label-width="150px">
          <el-form-item label="OCR Decision">
            <el-input
              v-model="prompts.image_ocr_decision"
              type="textarea"
              :rows="4"
            />
          </el-form-item>
          <el-form-item label="Content Correction">
            <el-input
              v-model="prompts.content_correction"
              type="textarea"
              :rows="6"
            />
          </el-form-item>
          <el-form-item label="Lean Conversion">
            <el-input
              v-model="prompts.lean_conversion"
              type="textarea"
              :rows="4"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="savePrompts">Save Prompts</el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <el-tab-pane label="Scheduled Tasks" name="schedules">
        <el-button type="primary" @click="showAddScheduleDialog">Add Schedule</el-button>

        <el-table :data="schedules" stripe style="margin-top: 1rem">
          <el-table-column prop="task_name" label="Task Name" />
          <el-table-column prop="task_type" label="Type" />
          <el-table-column label="Interval">
            <template #default="{ row }">
              {{ row.interval_hours || 0 }}h {{ row.interval_minutes || 0 }}m
            </template>
          </el-table-column>
          <el-table-column label="Enabled">
            <template #default="{ row }">
              <el-switch v-model="row.enabled" />
            </template>
          </el-table-column>
          <el-table-column label="Actions">
            <template #default="{ row }">
              <el-button size="small" type="danger" @click="deleteSchedule(row.id)">Delete</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="API Settings" name="api">
        <el-alert
          title="Zhipu API Key"
          type="info"
          :description="apiKeyMasked"
          show-icon
          style="margin-bottom: 1rem"
        />

        <el-form label-width="200px">
          <el-form-item label="VLLM Base URL">
            <el-input v-model="apiSettings.vllm_base_url" />
          </el-form-item>
          <el-form-item label="VLLM Model Path">
            <el-input v-model="apiSettings.vllm_model_path" />
          </el-form-item>
        </el-form>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { configApi } from '@/api'

const activeTab = ref('sites')
const sites = ref([])
const prompts = ref({})
const schedules = ref([])
const apiKeyMasked = ref('Set ZHIPU_API_KEY environment variable')
const apiSettings = ref({
  vllm_base_url: 'http://localhost:8000/v1',
  vllm_model_path: '/root/Kimina-Autoformalizer-7B'
})

async function loadSites() {
  try {
    sites.value = await configApi.getSites()
  } catch (error) {
    ElMessage.error('Failed to load sites')
  }
}

async function loadPrompts() {
  try {
    prompts.value = await configApi.getPrompts()
  } catch (error) {
    ElMessage.error('Failed to load prompts')
  }
}

async function loadSchedules() {
  try {
    schedules.value = await configApi.getSchedules()
  } catch (error) {
    ElMessage.error('Failed to load schedules')
  }
}

async function savePrompts() {
  try {
    await configApi.updatePrompts(prompts.value)
    ElMessage.success('Prompts saved')
  } catch (error) {
    ElMessage.error('Failed to save prompts')
  }
}

async function toggleSite(site) {
  try {
    await configApi.updateSite(site.site_id, { enabled: site.enabled })
    ElMessage.success('Site updated')
  } catch (error) {
    ElMessage.error('Failed to update site')
  }
}

async function deleteSchedule(taskId) {
  try {
    await configApi.deleteSchedule(taskId)
    await loadSchedules()
    ElMessage.success('Schedule deleted')
  } catch (error) {
    ElMessage.error('Failed to delete schedule')
  }
}

function showAddSiteDialog() {
  ElMessage.info('Add site feature - implement as needed')
}

function showAddScheduleDialog() {
  ElMessage.info('Add schedule feature - implement as needed')
}

onMounted(() => {
  loadSites()
  loadPrompts()
  loadSchedules()
})
</script>

<style scoped>
.config h2 {
  margin-bottom: 1.5rem;
}
</style>
