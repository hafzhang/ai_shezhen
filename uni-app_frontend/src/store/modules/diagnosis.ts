import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { request, isUniApp } from '@/utils/request'

// Storage abstraction for persistence
const storage = {
  getItem(key: string): string | null {
    if (isUniApp) {
      return uni.getStorageSync(key) || null
    }
    return localStorage.getItem(key)
  },
  setItem(key: string, value: string): void {
    if (isUniApp) {
      uni.setStorageSync(key, value)
    } else {
      localStorage.setItem(key, value)
    }
  }
}

/**
 * Tongue Features - 6维度舌象特征
 */
export interface TongueFeatures {
  // 舌色 (Tongue Color)
  tongue_color: {
   淡红: number
    红: number
    绛: number
    紫: number
  }
  // 舌形 (Tongue Shape)
  tongue_shape: {
    胖大: number
    瘦薄: number
    齿痕: number
    裂纹: number
  }
  // 苔色 (Coating Color)
  coating_color: {
    白苔: number
    黄苔: number
    灰苔: number
    黑苔: number
  }
  // 苔质 (Coating Quality)
  coating_quality: {
    薄苔: number
    厚苔: number
    腻苔: number
    剥苔: number
  }
  // 舌下络脉 (Sublingual Vein)
  sublingual_vein: {
    正常: number
    迂曲: number
    扩张: number
  }
  // 特征 (Special Features)
  special_features: {
    瘀点: number
    瘀斑: number
    出血点: number
  }
}

/**
 * Syndrome Analysis - 证型分析
 */
export interface SyndromeAnalysis {
  name: string          // 证型名称
  confidence: number    // 置信度
  description: string   // 证型描述
  tcm_theory: string    // 中医理论解释
}

/**
 * Health Recommendations - 健康建议
 */
export interface HealthRecommendations {
  dietary: string[]     // 饮食建议
  lifestyle: string[]   // 生活建议
  emotional: string[]   // 情志建议
}

/**
 * Risk Assessment - 风险评估
 */
export interface RiskAssessment {
  level: 'low' | 'medium' | 'high'   // 风险等级
  factors: string[]                   // 风险因素
  suggestions: string[]               // 建议
}

/**
 * Diagnosis Result - 诊断结果
 */
export interface DiagnosisResult {
  id: string
  user_id?: string
  image_url: string
  mask_url?: string
  features: TongueFeatures
  syndromes: SyndromeAnalysis[]
  recommendations: HealthRecommendations
  risks: RiskAssessment
  inference_time: number
  model_info: {
    segmentation_model: string
    classification_model: string
    diagnosis_model: string
  }
  created_at: string
}

/**
 * Diagnosis History - 诊断历史记录
 */
export interface DiagnosisHistory {
  id: string
  created_at: string
  primary_syndrome: string
  confidence: number
  has_risk: boolean
}

/**
 * Diagnosis Filters - 诊断历史筛选条件
 */
export interface DiagnosisFilters {
  start_date?: string
  end_date?: string
  syndrome?: string
  has_risk?: boolean
}

/**
 * Diagnosis Store State
 */
interface DiagnosisState {
  currentDiagnosis: DiagnosisResult | null
  isDiagnosing: boolean
  diagnosisHistory: DiagnosisHistory[]
  historyPagination: {
    page: number
    pageSize: number
    total: number
  }
  historyFilters: DiagnosisFilters
}

/**
 * Diagnosis Store - Pinia store for tongue diagnosis state
 */
export const useDiagnosisStore = defineStore('diagnosis', () => {
  // State
  const currentDiagnosis = ref<DiagnosisResult | null>(null)
  const isDiagnosing = ref(false)
  const diagnosisHistory = ref<DiagnosisHistory[]>([])
  const historyPagination = ref({
    page: 1,
    pageSize: 10,
    total: 0
  })
  const historyFilters = ref<DiagnosisFilters>({})

  // Computed
  const latestDiagnosis = computed(() => {
    return diagnosisHistory.value[0] || null
  })

  const hasRiskHistory = computed(() => {
    return diagnosisHistory.value.some(d => d.has_risk)
  })

  const commonSyndromes = computed(() => {
    const syndromeCounts = new Map<string, number>()
    diagnosisHistory.value.forEach(d => {
      syndromeCounts.set(d.primary_syndrome, (syndromeCounts.get(d.primary_syndrome) || 0) + 1)
    })
    return Array.from(syndromeCounts.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([name, count]) => ({ name, count }))
  })

  // Actions
  function setCurrentDiagnosis(diagnosis: DiagnosisResult | null) {
    currentDiagnosis.value = diagnosis
  }

  function setDiagnosing(value: boolean) {
    isDiagnosing.value = value
  }

  async function submitDiagnosis(imageBase64: string, userInfo?: {
    age?: number
    gender?: 'male' | 'female' | 'other'
    chief_complaint?: string
  }) {
    setDiagnosing(true)
    try {
      const response = await request<DiagnosisResult>({
        url: '/diagnosis',
        method: 'POST',
        data: {
          image: imageBase64,
          user_info: userInfo
        }
      })

      if (response.success && response.data) {
        setCurrentDiagnosis(response.data)
        // Refresh history after new diagnosis
        await fetchDiagnosisHistory(1)
        return response.data
      }

      throw new Error(response.error || 'Diagnosis failed')
    } catch (error) {
      console.error('Diagnosis failed:', error)
      throw error
    } finally {
      setDiagnosing(false)
    }
  }

  async function fetchDiagnosisHistory(page: number = 1, filters?: DiagnosisFilters) {
    try {
      const params = new URLSearchParams()
      params.append('page', page.toString())
      params.append('page_size', historyPagination.value.pageSize.toString())

      if (filters?.start_date) {
        params.append('start_date', filters.start_date)
      }
      if (filters?.end_date) {
        params.append('end_date', filters.end_date)
      }
      if (filters?.syndrome) {
        params.append('syndrome', filters.syndrome)
      }
      if (filters?.has_risk !== undefined) {
        params.append('has_risk', filters.has_risk.toString())
      }

      const response = await request<{
        items: DiagnosisHistory[]
        total: number
      }>({
        url: `/history/diagnoses?${params.toString()}`,
        method: 'GET'
      })

      if (response.success && response.data) {
        diagnosisHistory.value = response.data.items
        historyPagination.value = {
          page,
          pageSize: historyPagination.value.pageSize,
          total: response.data.total
        }
        if (filters) {
          historyFilters.value = filters
        }
      }
    } catch (error) {
      console.error('Failed to fetch diagnosis history:', error)
      throw error
    }
  }

  async function fetchDiagnosisDetail(id: string) {
    try {
      const response = await request<DiagnosisResult>({
        url: `/diagnosis/${id}`,
        method: 'GET'
      })

      if (response.success && response.data) {
        setCurrentDiagnosis(response.data)
        return response.data
      }

      throw new Error(response.error || 'Failed to fetch diagnosis detail')
    } catch (error) {
      console.error('Failed to fetch diagnosis detail:', error)
      throw error
    }
  }

  async function submitFeedback(id: string, feedback: 1 | -1) {
    try {
      const response = await request<{ success: boolean }>({
        url: `/diagnosis/${id}/feedback`,
        method: 'POST',
        data: { feedback }
      })

      if (response.success) {
        // Update current diagnosis if it matches
        if (currentDiagnosis.value?.id === id) {
          // Feedback is stored on backend, no local update needed
        }
        return true
      }

      return false
    } catch (error) {
      console.error('Failed to submit feedback:', error)
      throw error
    }
  }

  function setHistoryFilters(filters: DiagnosisFilters) {
    historyFilters.value = filters
    historyPagination.value.page = 1
  }

  function resetFilters() {
    historyFilters.value = {}
    historyPagination.value.page = 1
  }

  return {
    // State
    currentDiagnosis,
    isDiagnosing,
    diagnosisHistory,
    historyPagination,
    historyFilters,

    // Computed
    latestDiagnosis,
    hasRiskHistory,
    commonSyndromes,

    // Actions
    setCurrentDiagnosis,
    setDiagnosing,
    submitDiagnosis,
    fetchDiagnosisHistory,
    fetchDiagnosisDetail,
    submitFeedback,
    setHistoryFilters,
    resetFilters
  }
}, {
  persist: {
    key: 'diagnosis-store',
    storage: storage,
    paths: ['diagnosisHistory', 'historyPagination', 'historyFilters']
    // Don't persist currentDiagnosis and isDiagnosing as they are transient
  }
})

// Re-export types
export type {
  TongueFeatures,
  SyndromeAnalysis,
  HealthRecommendations,
  RiskAssessment,
  DiagnosisResult,
  DiagnosisHistory,
  DiagnosisFilters
}
