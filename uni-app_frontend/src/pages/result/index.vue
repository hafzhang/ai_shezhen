<template>
  <div class="container">
    <!-- Custom Header -->
    <div class="header">
      <div class="header-left" @click="goBack">
        <span class="icon-back">←</span>
      </div>
      <span class="header-title">诊断结果</span>
      <div class="header-right" @click="showShareModal = true">
        <span class="icon-share">⋮</span>
      </div>
    </div>

    <div class="content" v-if="diagnosis">
      <!-- Tongue Image with Mask Overlay -->
      <div class="image-section">
        <div class="image-container">
          <img
            class="tongue-image"
            :src="diagnosis.image_url"
            alt="舌部照片"
          />
          <!-- Mask Overlay -->
          <div
            v-if="diagnosis.mask_url"
            class="mask-overlay"
            :style="{ backgroundImage: `url(${diagnosis.mask_url})` }"
          />
        </div>
      </div>

      <!-- 6-Dimension Feature Display -->
      <div class="section features-section">
        <span class="section-title">舌象特征分析</span>
        <div class="features-grid">
          <!-- Tongue Color -->
          <div class="feature-item">
            <span class="feature-label">舌色</span>
            <div class="feature-values">
              <div
                v-for="(value, key) in diagnosis.features.tongue_color"
                :key="key"
                class="feature-value"
                :class="{ active: value > 0.3 }"
              >
                <span class="value-name">{{ key }}</span>
                <div class="value-bar">
                  <div class="bar-fill" :style="{ width: `${value * 100}%` }"></div>
                </div>
                <span class="value-percent">{{ Math.round(value * 100) }}%</span>
              </div>
            </div>
          </div>

          <!-- Tongue Shape -->
          <div class="feature-item">
            <span class="feature-label">舌形</span>
            <div class="feature-values">
              <div
                v-for="(value, key) in diagnosis.features.tongue_shape"
                :key="key"
                class="feature-value"
                :class="{ active: value > 0.3 }"
              >
                <span class="value-name">{{ key }}</span>
                <div class="value-bar">
                  <div class="bar-fill" :style="{ width: `${value * 100}%` }"></div>
                </div>
                <span class="value-percent">{{ Math.round(value * 100) }}%</span>
              </div>
            </div>
          </div>

          <!-- Coating Color -->
          <div class="feature-item">
            <span class="feature-label">苔色</span>
            <div class="feature-values">
              <div
                v-for="(value, key) in diagnosis.features.coating_color"
                :key="key"
                class="feature-value"
                :class="{ active: value > 0.3 }"
              >
                <span class="value-name">{{ key }}</span>
                <div class="value-bar">
                  <div class="bar-fill" :style="{ width: `${value * 100}%` }"></div>
                </div>
                <span class="value-percent">{{ Math.round(value * 100) }}%</span>
              </div>
            </div>
          </div>

          <!-- Coating Quality -->
          <div class="feature-item">
            <span class="feature-label">苔质</span>
            <div class="feature-values">
              <div
                v-for="(value, key) in diagnosis.features.coating_quality"
                :key="key"
                class="feature-value"
                :class="{ active: value > 0.3 }"
              >
                <span class="value-name">{{ key }}</span>
                <div class="value-bar">
                  <div class="bar-fill" :style="{ width: `${value * 100}%` }"></div>
                </div>
                <span class="value-percent">{{ Math.round(value * 100) }}%</span>
              </div>
            </div>
          </div>

          <!-- Sublingual Vein -->
          <div class="feature-item">
            <span class="feature-label">舌下络脉</span>
            <div class="feature-values">
              <div
                v-for="(value, key) in diagnosis.features.sublingual_vein"
                :key="key"
                class="feature-value"
                :class="{ active: value > 0.3 }"
              >
                <span class="value-name">{{ key }}</span>
                <div class="value-bar">
                  <div class="bar-fill" :style="{ width: `${value * 100}%` }"></div>
                </div>
                <span class="value-percent">{{ Math.round(value * 100) }}%</span>
              </div>
            </div>
          </div>

          <!-- Special Features -->
          <div class="feature-item">
            <span class="feature-label">特殊特征</span>
            <div class="feature-values">
              <div
                v-for="(value, key) in diagnosis.features.special_features"
                :key="key"
                class="feature-value"
                :class="{ active: value > 0.3 }"
              >
                <span class="value-name">{{ key }}</span>
                <div class="value-bar">
                  <div class="bar-fill" :style="{ width: `${value * 100}%` }"></div>
                </div>
                <span class="value-percent">{{ Math.round(value * 100) }}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Syndrome Analysis -->
      <div class="section syndrome-section">
        <span class="section-title">证型分析</span>
        <div class="syndrome-cards">
          <div
            v-for="syndrome in diagnosis.syndromes"
            :key="syndrome.name"
            class="syndrome-card"
            :class="{ primary: syndrome.confidence > 0.6 }"
          >
            <div class="syndrome-header">
              <span class="syndrome-name">{{ syndrome.name }}</span>
              <div class="syndrome-confidence">
                <span class="confidence-value">{{ Math.round(syndrome.confidence * 100) }}%</span>
              </div>
            </div>
            <span class="syndrome-desc">{{ syndrome.description }}</span>
            <div class="syndrome-theory" v-if="syndrome.tcm_theory">
              <span class="theory-label">中医理论：</span>
              <span class="theory-text">{{ syndrome.tcm_theory }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Health Recommendations (Collapsible) -->
      <div class="section recommendations-section">
        <div class="section-header" @click="toggleRecommendations">
          <span class="section-title">健康建议</span>
          <span class="toggle-icon" :class="{ expanded: recommendationsExpanded }">▼</span>
        </div>
        <div class="recommendations-content" v-if="recommendationsExpanded">
          <!-- Dietary -->
          <div class="recommendation-group" v-if="diagnosis.recommendations.dietary?.length">
            <div class="group-header">
              <span class="group-icon">🥗</span>
              <span class="group-title">饮食建议</span>
            </div>
            <div class="recommendation-list">
              <span
                v-for="(item, index) in diagnosis.recommendations.dietary"
                :key="index"
                class="recommendation-item"
              >
                {{ item }}
              </span>
            </div>
          </div>

          <!-- Lifestyle -->
          <div class="recommendation-group" v-if="diagnosis.recommendations.lifestyle?.length">
            <div class="group-header">
              <span class="group-icon">🏃</span>
              <span class="group-title">生活建议</span>
            </div>
            <div class="recommendation-list">
              <span
                v-for="(item, index) in diagnosis.recommendations.lifestyle"
                :key="index"
                class="recommendation-item"
              >
                {{ item }}
              </span>
            </div>
          </div>

          <!-- Emotional -->
          <div class="recommendation-group" v-if="diagnosis.recommendations.emotional?.length">
            <div class="group-header">
              <span class="group-icon">😌</span>
              <span class="group-title">情志建议</span>
            </div>
            <div class="recommendation-list">
              <span
                v-for="(item, index) in diagnosis.recommendations.emotional"
                :key="index"
                class="recommendation-item"
              >
                {{ item }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Risk Alert -->
      <div
        class="section risk-section"
        v-if="diagnosis.risks && diagnosis.risks.level !== 'low'"
        :class="`risk-${diagnosis.risks.level}`"
      >
        <div class="risk-header">
          <span class="risk-icon">⚠️</span>
          <span class="risk-title">健康提醒</span>
        </div>
        <div class="risk-content">
          <span
            v-for="(factor, index) in diagnosis.risks.factors"
            :key="index"
            class="risk-factor"
          >
            {{ factor }}
          </span>
          <span
            v-for="(suggestion, index) in diagnosis.risks.suggestions"
            :key="`sug-${index}`"
            class="risk-suggestion"
          >
            {{ suggestion }}
          </span>
        </div>
      </div>

      <!-- Meta Info -->
      <div class="section meta-section">
        <span class="meta-text">诊断时间：{{ formatDate(diagnosis.created_at) }}</span>
        <span class="meta-text">AI诊断耗时：{{ (diagnosis.inference_time / 1000).toFixed(2) }}秒</span>
      </div>
    </div>

    <!-- Loading State -->
    <div class="loading-container" v-else>
      <div class="loading-spinner"></div>
      <span class="loading-text">正在加载诊断结果...</span>
    </div>

    <!-- Action Buttons -->
    <div class="action-bar" v-if="diagnosis">
      <button class="btn-action btn-feedback" @click="showFeedbackModal">
        <span class="btn-icon">👍</span>
        <span class="btn-text">反馈</span>
      </button>
      <button class="btn-action btn-share" @click="showShareModal = true">
        <span class="btn-icon">📤</span>
        <span class="btn-text">分享</span>
      </button>
      <button class="btn-action btn-save" @click="saveImage">
        <span class="btn-icon">💾</span>
        <span class="btn-text">保存</span>
      </button>
    </div>

    <!-- Feedback Modal -->
    <div class="modal-overlay" v-if="showFeedback" @click="showFeedback = false">
      <div class="feedback-modal" @click.stop>
        <span class="modal-title">诊断结果是否有帮助？</span>
        <div class="feedback-buttons">
          <button class="btn-feedback-option" @click="submitFeedback(1)">
            <span class="feedback-icon">👍</span>
            <span class="feedback-text">准确</span>
          </button>
          <button class="btn-feedback-option" @click="submitFeedback(-1)">
            <span class="feedback-icon">👎</span>
            <span class="feedback-text">不准确</span>
          </button>
        </div>
        <button class="btn-close" @click="showFeedback = false">取消</button>
      </div>
    </div>

    <!-- Share Modal -->
    <div class="modal-overlay" v-if="showShareModal" @click="showShareModal = false">
      <div class="share-modal" @click.stop>
        <div class="modal-header">
          <span class="modal-title">分享诊断结果</span>
          <span class="modal-close" @click="showShareModal = false">×</span>
        </div>
        <div class="share-options">
          <div class="share-option" @click="saveImage">
            <span class="share-icon">📷</span>
            <span class="share-label">保存图片</span>
          </div>
          <div class="share-option" @click="copyLink">
            <span class="share-icon">🔗</span>
            <span class="share-label">复制链接</span>
          </div>
        </div>
        <button class="btn btn-close" @click="showShareModal = false">取消</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useDiagnosisStore } from '@/store'
import type { DiagnosisResult } from '@/store/modules/diagnosis'

const router = useRouter()
const route = useRoute()
const diagnosisStore = useDiagnosisStore()

// State
const diagnosis = ref<DiagnosisResult | null>(null)
const recommendationsExpanded = ref(false)
const showFeedback = ref(false)
const showShareModal = ref(false)

// Methods
function goBack() {
  router.back()
}

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function toggleRecommendations() {
  recommendationsExpanded.value = !recommendationsExpanded.value
}

async function submitFeedback(feedback: 1 | -1) {
  if (!diagnosis.value) return

  try {
    await diagnosisStore.submitFeedback(diagnosis.value.id, feedback)
    alert('感谢您的反馈')
    showFeedback.value = false
  } catch (error: any) {
    alert(error.message || '反馈失败')
  }
}

function saveImage() {
  alert('保存图片功能开发中')
}

function copyLink() {
  const link = `${window.location.origin}/result?id=${diagnosis.value?.id || ''}`

  if (navigator.clipboard) {
    navigator.clipboard.writeText(link).then(() => {
      alert('链接已复制')
    }).catch(() => {
      alert('复制失败')
    })
  } else {
    // Fallback for older browsers
    const textArea = document.createElement('textarea')
    textArea.value = link
    document.body.appendChild(textArea)
    textArea.select()
    try {
      document.execCommand('copy')
      alert('链接已复制')
    } catch {
      alert('复制失败')
    }
    document.body.removeChild(textArea)
  }
  showShareModal.value = false
}

// Lifecycle
onMounted(async () => {
  // Get diagnosis ID from query params
  const id = route.query.id as string

  if (id) {
    // Try to get from current diagnosis (for mock results)
    if (diagnosisStore.currentDiagnosis?.id === id) {
      diagnosis.value = diagnosisStore.currentDiagnosis
    } else {
      // Otherwise try to fetch from API
      try {
        const result = await diagnosisStore.fetchDiagnosisDetail(id)
        diagnosis.value = result
      } catch (error: any) {
        alert(error.message || '加载失败')
        router.back()
      }
    }
  } else if (diagnosisStore.currentDiagnosis) {
    diagnosis.value = diagnosisStore.currentDiagnosis
  } else {
    alert('未找到诊断结果')
    setTimeout(() => {
      router.back()
    }, 1500)
  }
})
</script>

<style lang="scss" scoped>
.container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f5f5;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 44px;
  padding: 40px 15px 15px;
  background: #ffffff;
  border-bottom: 1px solid #e5e5e5;
}

.header-left,
.header-right {
  width: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-back,
.icon-share {
  font-size: 20px;
  color: #333333;
}

.header-title {
  font-size: 17px;
  font-weight: 500;
  color: #333333;
}

.content {
  flex: 1;
  padding: 15px;
  overflow-y: auto;
}

.image-section {
  margin-bottom: 15px;
}

.image-container {
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  border-radius: 12px;
  overflow: hidden;
  background: #000;
}

.tongue-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.mask-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-size: contain;
  background-repeat: no-repeat;
  background-position: center;
  opacity: 0.5;
  pointer-events: none;
}

.section {
  background: #ffffff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
}

.section-title {
  font-size: 16px;
  font-weight: 500;
  color: #333333;
  display: block;
  margin-bottom: 12px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  cursor: pointer;
}

.toggle-icon {
  font-size: 14px;
  color: #667eea;
  transition: transform 0.3s;
}

.toggle-icon.expanded {
  transform: rotate(180deg);
}

// Features Section
.features-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.feature-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.feature-label {
  font-size: 14px;
  font-weight: 500;
  color: #667eea;
}

.feature-values {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.feature-value {
  display: flex;
  align-items: center;
  gap: 8px;
}

.value-name {
  font-size: 13px;
  color: #666666;
  min-width: 50px;
}

.value-bar {
  flex: 1;
  height: 8px;
  background: #f0f0f0;
  border-radius: 4px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
  border-radius: 4px;
  transition: width 0.3s;
}

.feature-value.active .bar-fill {
  background: linear-gradient(90deg, #f093fb 0%, #f5576c 100%);
}

.value-percent {
  font-size: 11px;
  color: #999999;
  min-width: 40px;
  text-align: right;
}

// Syndrome Section
.syndrome-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.syndrome-card {
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
  border-left: 3px solid #667eea;
}

.syndrome-card.primary {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
  border-left-color: #764ba2;
}

.syndrome-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.syndrome-name {
  font-size: 15px;
  font-weight: 500;
  color: #333333;
}

.syndrome-confidence {
  background: #667eea;
  color: #ffffff;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
}

.confidence-value {
  font-weight: 500;
}

.syndrome-desc {
  font-size: 13px;
  color: #666666;
  line-height: 1.6;
  margin-bottom: 8px;
}

.syndrome-theory {
  padding-top: 8px;
  border-top: 1px solid #e5e5e5;
}

.theory-label {
  font-size: 12px;
  color: #667eea;
  font-weight: 500;
}

.theory-text {
  font-size: 12px;
  color: #999999;
  line-height: 1.6;
}

// Recommendations Section
.recommendations-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.recommendation-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.group-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.group-icon {
  font-size: 18px;
}

.group-title {
  font-size: 14px;
  font-weight: 500;
  color: #333333;
}

.recommendation-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-left: 26px;
}

.recommendation-item {
  font-size: 13px;
  color: #666666;
  line-height: 1.6;
}

// Risk Section
.risk-section {
  border-left: 3px solid #ffa500;
}

.risk-section.risk-medium {
  border-left-color: #ff6b00;
  background: linear-gradient(135deg, rgba(255, 165, 0, 0.05) 0%, rgba(255, 107, 0, 0.05) 100%);
}

.risk-section.risk-high {
  border-left-color: #ff4444;
  background: linear-gradient(135deg, rgba(255, 68, 68, 0.05) 0%, rgba(220, 20, 60, 0.05) 100%);
}

.risk-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.risk-icon {
  font-size: 20px;
}

.risk-title {
  font-size: 16px;
  font-weight: 500;
  color: #ff4444;
}

.risk-content {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.risk-factor,
.risk-suggestion {
  font-size: 13px;
  color: #666666;
  line-height: 1.6;
}

.risk-factor {
  color: #ff6b00;
}

// Meta Section
.meta-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.meta-text {
  font-size: 12px;
  color: #999999;
}

// Loading State
.loading-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #f0f0f0;
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.loading-text {
  font-size: 14px;
  color: #999999;
}

// Action Bar
.action-bar {
  display: flex;
  gap: 12px;
  padding: 12px 15px;
  background: #ffffff;
  border-top: 1px solid #e5e5e5;
}

.btn-action {
  flex: 1;
  height: 48px;
  border-radius: 24px;
  border: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  font-size: 11px;
  color: #ffffff;
  cursor: pointer;
}

.btn-feedback {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.btn-share {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}

.btn-save {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
}

.btn-icon {
  font-size: 18px;
}

.btn-text {
  font-size: 12px;
  font-weight: 500;
}

// Modal styles
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.feedback-modal,
.share-modal {
  width: 80%;
  max-width: 320px;
  background: #ffffff;
  border-radius: 16px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.share-modal {
  max-width: 280px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-title {
  font-size: 16px;
  font-weight: 500;
  color: #333333;
}

.modal-close {
  font-size: 24px;
  color: #999999;
  line-height: 1;
  cursor: pointer;
}

.feedback-buttons {
  display: flex;
  gap: 12px;
}

.btn-feedback-option {
  flex: 1;
  height: 80px;
  border-radius: 12px;
  border: 1px solid #e5e5e5;
  background: #ffffff;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
}

.btn-feedback-option:active {
  background: #f8f9fa;
}

.feedback-icon {
  font-size: 28px;
}

.feedback-text {
  font-size: 14px;
  color: #666666;
}

.btn-close {
  width: 100%;
  height: 44px;
  border-radius: 22px;
  border: none;
  background: #f5f5f5;
  color: #666666;
  font-size: 15px;
  cursor: pointer;
}

.share-options {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.share-option {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 15px;
  border-radius: 12px;
  border: 1px solid #e5e5e5;
  background: #ffffff;
  cursor: pointer;
}

.share-option:hover {
  background: #f8f9fa;
}

.share-icon {
  font-size: 24px;
}

.share-label {
  font-size: 15px;
  color: #333333;
}
</style>