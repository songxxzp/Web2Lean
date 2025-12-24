<template>
  <div class="config">
    <h2>Configuration</h2>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="Sites" name="sites">
        <el-table :data="sites" stripe style="margin-top: 1rem">
          <el-table-column prop="site_name" label="Name" width="150" />
          <el-table-column prop="site_type" label="Type" width="130" />
          <el-table-column prop="base_url" label="URL" show-overflow-tooltip />
          <el-table-column label="Config" width="300">
            <template #default="{ row }">
              <span v-if="row.config_json">
                <span v-if="getConfig(row, 'stop_strategy') === 'questions'">
                  Stop: {{ getConfig(row, 'new_questions_limit') || 0 }} new questions
                </span>
                <span v-else>
                  Stop: {{ getConfig(row, 'pages_per_run') || 'N/A' }} pages
                </span>
                <br>
                <span style="color: #999; font-size: 12px;">
                  Start: {{ getConfig(row, 'start_page') || 1 }} |
                  Delay: {{ getConfig(row, 'request_delay') || 'N/A' }}s
                </span>
              </span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="Enabled" width="100">
            <template #default="{ row }">
              <el-switch v-model="row.enabled" @change="toggleSite(row)" />
            </template>
          </el-table-column>
          <el-table-column label="Actions" width="100">
            <template #default="{ row }">
              <el-button size="small" @click="editSite(row)">Edit</el-button>
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
    </el-tabs>

    <!-- Site Config Dialog -->
    <el-dialog v-model="siteDialogVisible" title="Edit Site Configuration" width="550px">
      <el-form :model="siteForm" label-width="150px">
        <el-form-item label="Start Page">
          <el-input-number v-model="siteForm.start_page" :min="1" :max="10000" />
          <span style="margin-left: 10px; color: #999;">Starting page (default: 1)</span>
        </el-form-item>

        <el-form-item label="Stop Strategy">
          <el-select v-model="siteForm.stop_strategy" style="width: 200px">
            <el-option label="By Pages (固定页数)" value="pages" />
            <el-option label="By Questions (新问题数)" value="questions" />
          </el-select>
        </el-form-item>

        <template v-if="siteForm.stop_strategy === 'pages'">
          <el-form-item label="Pages Per Run">
            <el-input-number v-model="siteForm.pages_per_run" :min="1" :max="1000" />
            <span style="margin-left: 10px; color: #999;">Total pages to crawl</span>
          </el-form-item>
        </template>

        <template v-if="siteForm.stop_strategy === 'questions'">
          <el-form-item label="New Questions Limit">
            <el-input-number v-model="siteForm.new_questions_limit" :min="0" :max="10000" />
            <span style="margin-left: 10px; color: #999;">0 = unlimited</span>
          </el-form-item>
        </template>

        <el-form-item label="Request Delay (s)">
          <el-input-number v-model="siteForm.request_delay" :min="0" :max="60" :step="0.5" />
          <span style="margin-left: 10px; color: #999;">Delay between requests</span>
        </el-form-item>

        <el-form-item label="Max Retries">
          <el-input-number v-model="siteForm.max_retries" :min="0" :max="10" />
          <span style="margin-left: 10px; color: #999;">Retry attempts</span>
        </el-form-item>

        <el-divider content-position="left">Strategy Examples</el-divider>
        <el-alert type="info" :closable="false">
          <template v-if="siteForm.stop_strategy === 'pages'">
            <strong>By Pages:</strong> Crawls exactly {{ siteForm.pages_per_run }} pages
            <ul style="margin: 10px 0; padding-left: 20px;">
              <li>Start=1, Pages=10 → Crawls pages 1-10</li>
              <li>Start=11, Pages=50 → Crawls pages 11-60</li>
            </ul>
          </template>
          <template v-else>
            <strong>By Questions:</strong> Crawls until {{ siteForm.new_questions_limit === 0 ? 'no more new questions' : siteForm.new_questions_limit + ' new questions found' }}
            <ul style="margin: 10px 0; padding-left: 20px;">
              <li>Start=1, Limit=0 → Crawls all pages (unlimited)</li>
              <li>Start=1, Limit=100 → Stops after 100 new questions</li>
              <li>Start=1, Limit=10 → Quickly fetches 10 new questions</li>
            </ul>
          </template>
        </el-alert>
      </el-form>
      <template #footer>
        <el-button @click="siteDialogVisible = false">Cancel</el-button>
        <el-button type="primary" @click="saveSiteConfig">Save</el-button>
      </template>
    </el-dialog>
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

// Site config dialog
const siteDialogVisible = ref(false)
const currentSite = ref(null)
const siteForm = ref({
  start_page: 1,
  stop_strategy: 'pages',
  pages_per_run: 10,
  new_questions_limit: 0,
  request_delay: 8.0,
  max_retries: 3
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

function getConfig(site, key) {
  try {
    const config = typeof site.config_json === 'string'
      ? JSON.parse(site.config_json)
      : site.config_json
    return config?.[key]
  } catch {
    return null
  }
}

function editSite(site) {
  currentSite.value = site
  siteForm.value = {
    start_page: getConfig(site, 'start_page') || 1,
    stop_strategy: getConfig(site, 'stop_strategy') || 'pages',
    pages_per_run: getConfig(site, 'pages_per_run') || 10,
    new_questions_limit: getConfig(site, 'new_questions_limit') || 0,
    request_delay: getConfig(site, 'request_delay') || 8.0,
    max_retries: getConfig(site, 'max_retries') || 3
  }
  siteDialogVisible.value = true
}

async function saveSiteConfig() {
  try {
    await configApi.updateSite(currentSite.value.site_id, {
      config: siteForm.value
    })
    ElMessage.success('Site configuration saved')
    siteDialogVisible.value = false
    await loadSites()
  } catch (error) {
    ElMessage.error('Failed to save site configuration')
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
