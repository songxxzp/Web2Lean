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

      <el-tab-pane label="Models" name="models">
        <el-form label-width="180px" style="max-width: 600px">
          <el-divider content-position="left">Zhipu AI Models (智谱AI)</el-divider>

          <el-form-item label="Text Model (文本处理)">
            <el-select v-model="models.glm_text_model" filterable allow-create style="width: 300px">
              <el-option label="GLM-4.7 (最新推荐)" value="glm-4.7" />
              <el-option label="GLM-4-Plus" value="glm-4-plus" />
              <el-option label="GLM-4.6" value="glm-4.6" />
              <el-option label="GLM-4.5" value="glm-4.5" />
              <el-option label="GLM-4" value="glm-4" />
            </el-select>
            <span style="margin-left: 10px; color: #999;">用于文本预处理和验证</span>
          </el-form-item>

          <el-form-item label="Preprocessing Concurrency">
            <el-input-number v-model="models.preprocessing_concurrency" :min="1" :max="8" :step="1" style="width: 200px" />
            <span style="margin-left: 10px; color: #999;">并发调用 LLM API 的数量（默认2）</span>
          </el-form-item>

          <el-form-item label="Max Token Length">
            <el-input-number v-model="models.preprocessing_max_length" :min="2000" :max="32000" :step="1000" style="width: 200px" />
            <span style="margin-left: 10px; color: #999;">LLM 最大 token 数（默认16000）</span>
          </el-form-item>

          <el-form-item label="Vision Model (图像OCR)">
            <el-select v-model="models.glm_vision_model" filterable allow-create style="width: 300px">
              <el-option label="GLM-4.6V (最新推荐)" value="glm-4.6v" />
              <el-option label="GLM-4V" value="glm-4v" />
            </el-select>
            <span style="margin-left: 10px; color: #999;">用于图像OCR和识别</span>
          </el-form-item>

          <el-form-item label="Lean Model (形式化)">
            <el-select v-model="models.glm_lean_model" filterable allow-create style="width: 300px">
              <el-option label="Local Model (Kimina本地推荐)" value="local" />
              <el-option label="GLM-4.7" value="glm-4.7" />
              <el-option label="GLM-4-Plus" value="glm-4-plus" />
              <el-option label="GLM-4" value="glm-4" />
            </el-select>
            <span style="margin-left: 10px; color: #999;">用于Lean代码转换(可选)</span>
          </el-form-item>

          <el-form-item label="Lean Max Iterations">
            <el-input-number v-model="models.lean_max_iterations" :min="0" :max="10" :step="1" style="width: 200px" />
            <span style="margin-left: 10px; color: #999;">LLM转换器最大迭代修正次数（默认1）</span>
          </el-form-item>

          <el-divider content-position="left">Local Models (本地模型)</el-divider>

          <el-form-item label="VLLM Base URL">
            <el-input v-model="models.vllm_base_url" placeholder="http://localhost:8000/v1" />
            <span style="margin-left: 10px; color: #999;">VLLM服务地址</span>
          </el-form-item>

          <el-form-item label="VLLM Model Path">
            <el-input v-model="models.vllm_model_path" placeholder="/root/Kimina-Autoformalizer-7B" />
            <span style="margin-left: 10px; color: #999;">本地模型路径</span>
          </el-form-item>

          <el-form-item label="Kimina URL">
            <el-input v-model="models.kimina_url" placeholder="http://127.0.0.1:9000" />
            <span style="margin-left: 10px; color: #999;">Lean验证服务器地址</span>
          </el-form-item>

          <el-form-item>
            <el-button type="primary" @click="saveModels">Save Models</el-button>
            <el-button @click="loadModels">Reset</el-button>
          </el-form-item>

          <el-alert type="info" :closable="false" style="margin-top: 20px;">
            <strong>模型说明:</strong>
            <ul style="margin: 10px 0; padding-left: 20px;">
              <li><strong>GLM-4.7</strong>: 最新最强的文本模型（深度思考模式），用于复杂推理和验证</li>
              <li><strong>GLM-4.6V</strong>: 最新多模态模型，用于图像OCR和理解</li>
              <li><strong>Kimina (Local)</strong>: 本地运行的Lean专用模型（推荐），需要VLLM服务</li>
              <li><strong>GLM Lean Agent</strong>: 基于GLM的Lean转换器，支持迭代修正，使用GLM-4.7时效果最佳</li>
            </ul>
          </el-alert>
        </el-form>
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
const models = ref({
  glm_text_model: 'glm-4.7',
  glm_vision_model: 'glm-4.6v',
  glm_lean_model: 'glm-4.7',
  vllm_base_url: 'http://localhost:8000/v1',
  vllm_model_path: '/root/Kimina-Autoformalizer-7B',
  preprocessing_concurrency: 2,
  preprocessing_max_length: 16000,
  lean_max_iterations: 1
})

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

async function loadModels() {
  try {
    const data = await configApi.getModels()
    // Merge with existing models to preserve defaults
    models.value = {
      ...models.value,
      ...data
    }
  } catch (error) {
    ElMessage.error('Failed to load models')
  }
}

async function saveModels() {
  try {
    await configApi.updateModels(models.value)
    ElMessage.success('Models saved successfully')
  } catch (error) {
    ElMessage.error('Failed to save models')
  }
}

onMounted(() => {
  loadSites()
  loadPrompts()
  loadSchedules()
  loadModels()
})
</script>

<style scoped>
.config h2 {
  margin-bottom: 1.5rem;
}
</style>
