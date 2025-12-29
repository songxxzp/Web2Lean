/**
 * API client for Web2Lean backend
 */

const API_BASE = '/api'

/**
 * Make API request
 */
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

/**
 * Crawlers API
 */
export const crawlersApi = {
  start: (siteName, mode = 'incremental') =>
    apiRequest('/crawlers/start', {
      method: 'POST',
      body: { site_name: siteName, mode }
    }),

  stop: (siteName) =>
    apiRequest(`/crawlers/stop/${siteName}`, { method: 'POST' }),

  getAllStatus: () =>
    apiRequest('/crawlers/status'),

  getStatus: (siteName) =>
    apiRequest(`/crawlers/status/${siteName}`)
}

/**
 * Statistics API
 */
export const statisticsApi = {
  overview: () =>
    apiRequest('/statistics/overview'),

  site: (siteId) =>
    apiRequest(`/statistics/site/${siteId}`),

  processing: () =>
    apiRequest('/statistics/processing'),

  detailed: () =>
    apiRequest('/statistics/detailed')
}

/**
 * Processing API
 */
export const processingApi = {
  startLean: (options = {}) =>
    apiRequest('/processing/start-lean', {
      method: 'POST',
      body: options
    }),

  preprocess: (options = {}) =>
    apiRequest('/processing/preprocess', {
      method: 'POST',
      body: options
    }),

  getProgress: (taskType) =>
    apiRequest(`/processing/task/${taskType}/progress`),

  pauseTask: (taskId) =>
    apiRequest(`/processing/task/${taskId}/pause`, { method: 'POST' }),

  resumeTask: (taskId) =>
    apiRequest(`/processing/task/${taskId}/resume`, { method: 'POST' }),

  stopTask: (taskId) =>
    apiRequest(`/processing/task/${taskId}/stop`, { method: 'POST' }),

  getStatus: (questionId) =>
    apiRequest(`/processing/status/${questionId}`),

  retry: (questionId) =>
    apiRequest(`/processing/retry/${questionId}`, { method: 'POST' })
}

/**
 * Database API
 */
export const databaseApi = {
  listQuestions: (params = {}) => {
    // Filter out null/undefined values
    const cleanParams = Object.fromEntries(
      Object.entries(params).filter(([_, v]) => v != null)
    )
    const query = new URLSearchParams(cleanParams).toString()
    const url = query ? `/database/questions?${query}` : '/database/questions'
    return apiRequest(url)
  },

  getQuestion: (questionId) =>
    apiRequest(`/database/questions/${questionId}`),

  getImages: (questionId) =>
    apiRequest(`/database/questions/${questionId}/images`),

  getStatistics: () =>
    apiRequest('/database/statistics'),

  clearData: (stage) =>
    apiRequest('/database/clear', {
      method: 'POST',
      body: { stage }
    }),

  clearQuestionStage: (questionId, stage) =>
    apiRequest(`/database/questions/${questionId}/clear`, {
      method: 'POST',
      body: { stage }
    }),

  exportVerifiedLean: () => {
    // Direct fetch for file download
    return fetch('/api/database/export/verified-lean')
      .then(response => {
        if (!response.ok) {
          throw new Error('Export failed')
        }

        // Get filename from headers before consuming response
        const disposition = response.headers.get('Content-Disposition')
        const filenameMatch = disposition && disposition.match(/filename="(.+)"/)
        const filename = filenameMatch ? filenameMatch[1] : 'lean_verified_data.jsonl'

        return response.blob().then(blob => ({ blob, filename }))
      })
      .then(({ blob, filename }) => {
        // Create download link
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = filename

        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)
      })
  }
}

/**
 * Configuration API
 */
export const configApi = {
  getSites: () =>
    apiRequest('/config/sites'),

  addSite: (siteData) =>
    apiRequest('/config/sites', {
      method: 'POST',
      body: siteData
    }),

  updateSite: (siteId, data) =>
    apiRequest(`/config/sites/${siteId}`, {
      method: 'PUT',
      body: data
    }),

  deleteSite: (siteId) =>
    apiRequest(`/config/sites/${siteId}`, { method: 'DELETE' }),

  getPrompts: () =>
    apiRequest('/config/prompts'),

  updatePrompts: (prompts) =>
    apiRequest('/config/prompts', {
      method: 'PUT',
      body: prompts
    }),

  getSchedules: () =>
    apiRequest('/config/schedules'),

  createSchedule: (scheduleData) =>
    apiRequest('/config/schedules', {
      method: 'POST',
      body: scheduleData
    }),

  updateSchedule: (taskId, data) =>
    apiRequest(`/config/schedules/${taskId}`, {
      method: 'PUT',
      body: data
    }),

  deleteSchedule: (taskId) =>
    apiRequest(`/config/schedules/${taskId}`, { method: 'DELETE' }),

  getModels: () =>
    apiRequest('/config/models'),

  updateModels: (models) =>
    apiRequest('/config/models', {
      method: 'PUT',
      body: models
    })
}

/**
 * Verification API
 */
export const verificationApi = {
  verify: (questionId) =>
    apiRequest(`/verification/verify/${questionId}`, { method: 'POST' }),

  verifyAll: (options = {}) =>
    apiRequest('/verification/verify-all', {
      method: 'POST',
      body: options
    }),

  getStatus: (questionId) =>
    apiRequest(`/verification/status/${questionId}`)
}

/**
 * Scheduler API
 */
export const schedulerApi = {
  getTasks: () =>
    apiRequest('/scheduler/tasks'),

  createTask: (taskData) =>
    apiRequest('/scheduler/tasks', {
      method: 'POST',
      body: taskData
    }),

  updateTask: (taskName, data) =>
    apiRequest(`/scheduler/tasks/${taskName}`, {
      method: 'PUT',
      body: data
    }),

  deleteTask: (taskName) =>
    apiRequest(`/scheduler/tasks/${taskName}`, { method: 'DELETE' }),

  getStatus: () =>
    apiRequest('/scheduler/status')
}

export default {
  crawlers: crawlersApi,
  statistics: statisticsApi,
  processing: processingApi,
  database: databaseApi,
  config: configApi,
  verification: verificationApi,
  scheduler: schedulerApi
}
