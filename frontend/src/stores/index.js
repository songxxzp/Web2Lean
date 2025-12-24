/**
 * Pinia stores for Web2Lean
 */
import { defineStore } from 'pinia'
import { crawlersApi, statisticsApi } from '@/api'

export const useCrawlerStore = defineStore('crawlers', {
  state: () => ({
    activeCrawlers: {},
    sites: [],
    loading: false
  }),

  actions: {
    async fetchStatus() {
      this.loading = true
      try {
        const data = await crawlersApi.getAllStatus()
        this.activeCrawlers = data.active_crawlers || {}
        this.sites = data.all_sites || []
      } catch (error) {
        console.error('Failed to fetch crawler status:', error)
      } finally {
        this.loading = false
      }
    },

    async startCrawler(siteName, mode = 'incremental') {
      try {
        return await crawlersApi.start(siteName, mode)
      } catch (error) {
        throw error
      }
    },

    async stopCrawler(siteName) {
      try {
        return await crawlersApi.stop(siteName)
      } catch (error) {
        throw error
      }
    }
  }
})

export const useStatisticsStore = defineStore('statistics', {
  state: () => ({
    overview: null,
    loading: false
  }),

  actions: {
    async fetchOverview() {
      this.loading = true
      try {
        this.overview = await statisticsApi.overview()
      } catch (error) {
        console.error('Failed to fetch statistics:', error)
      } finally {
        this.loading = false
      }
    }
  }
})
