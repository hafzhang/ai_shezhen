<template>
  <div class="container">
    <div class="header">
      <div class="header-left" @click="goBack">
        <span class="back-icon">←</span>
      </div>
      <span class="header-title">诊断详情</span>
      <div class="header-right" @click="showShareSheet = true">
        <span class="share-icon">⋮</span>
      </div>
    </div>

    <div class="content" v-if="diagnosis">
      <!-- Tongue image section -->
      <div class="image-section">
        <div class="image-container">
          <img
            class="tongue-image"
            :src="diagnosis.image_url"
            alt="Tongue"
          />
          <div
            class="mask-overlay"
            v-if="diagnosis.mask_url"
            :style="{ backgroundImage: `url(${diagnosis.mask_url})` }"
          />
        </div>
        <div class="image-info">
          <span class="diagnosis-time">{{ formatDateTime(diagnosis.created_at) }}</span>
          <div class="confidence-badge">
            <span class="confidence-text">置信度 {{ Math.round(diagnosis.confidence * 100) }}%</span>
          </div>
        </div>
      </div>

      <!-- Syndrome analysis -->
      <div class="section syndrome-section">
        <div class="section-header">
          <span class="section-title">证型分析</span>
        </div>
        <div class="syndrome-list">
          <div
            class="syndrome-item"
            v-for="(syndrome, index) in diagnosis.syndromes"
            :key="index"
            :class="{ primary: index === 0 }"
          >
            <div class="syndrome-header">
              <span class="syndrome-name">{{ syndrome.name }}</span>
              <div class="syndrome-confidence">
                <span class="confidence-value">{{ Math.round(syndrome.confidence * 100) }}%</span>
              </div>
            </div>
            <span class="syndrome-description">{{ syndrome.description }}</span>
            <div class="tcm-theory" v-if="syndrome.tcm_theory">
              <span class="theory-label">中医理论：</span>
              <span class="theory-text">{{ syndrome.tcm_theory }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Risk assessment -->
      <div class="section risk-section" v-if="diagnosis.risks">
        <div class="section-header">
          <span class="section-title">风险评估</span>
        </div>
        <div class="risk-card" :class="`risk-${diagnosis.risks.level}`">
          <div class="risk-header">
            <span class="risk-title">{{ riskLevelTitle }}</span>
            <div class="risk-indicator" :class="`indicator-${diagnosis.risks.level}`"></div>
          </div>
          <div class="risk-factors" v-if="diagnosis.risks.factors.length > 0">
            <span class="factors-label">风险因素：</span>
            <span class="factors-text">{{ diagnosis.risks.factors.join('、') }}</span>
          </div>
          <div class="risk-suggestions" v-if="diagnosis.risks.suggestions.length > 0">
            <span class="suggestions-label">建议：</span>
            <span class="suggestions-text">{{ diagnosis.risks.suggestions.join('；') }}</span>
          </div>
        </div>
      </div>

      <!-- Health recommendations -->
      <div class="section recommendation-section">
        <div class="section-header">
          <span class="section-title">健康建议</span>
        </div>
        <div class="recommendations-list">
          <div
            class="recommendation-item"
            v-for="(rec, index) in diagnosis.recommendations"
            :key="index"
          >
            <span class="rec-category">{{ rec.category }}</span>
            <span class="rec-text">{{ rec.text }}</span>
          </div>
        </div>
      </div>

      <!-- Model info -->
      <div class="section model-section">
        <div class="section-header">
          <span class="section-title">诊断信息</span>
        </div>
        <div class="model-info">
          <div class="info-row">
            <span class="info-label">分割模型</span>
            <span class="info-value">{{ diagnosis.model_info.segmentation_model }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">分类模型</span>
            <span class="info-value">{{ diagnosis.model_info.classification_model }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">诊断模型</span>
            <span class="info-value">{{ diagnosis.model_info.diagnosis_model }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">推理时间</span>
            <span class="info-value">{{ diagnosis.inference_time }}ms</span>
          </div>
        </div>
      </div>

      <!-- Feedback section -->
      <div class="feedback-section">
        <span class="feedback-question">诊断结果准确吗？</span>
        <div class="feedback-buttons">
          <button
            class="feedback-btn"
            :class="{ active: feedback === 1 }"
            @click="submitFeedback(1)"
          >
            <span class="feedback-icon">👍</span>
            <span class="feedback-text">准确</span>
          </button>
          <button
            class="feedback-btn"
            :class="{ active: feedback === -1 }"
            @click="submitFeedback(-1)"
          >
            <span class="feedback-icon">👎</span>
            <span class="feedback-text">不准确</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Loading state -->
    <div class="loading-state" v-else-if="isLoading">
      <span class="loading-text">加载中...</span>
    </div>

    <!-- Error state -->
    <div class="error-state" v-else>
      <span class="error-icon">⚠️</span>
      <span class="error-title">加载失败</span>
      <span class="error-desc">{{ errorMessage }}</span>
      <button class="btn btn-primary" @click="loadDetail">重新加载</button>
    </div>

    <!-- Share sheet -->
    <div class="modal-overlay" v-if="showShareSheet" @click="showShareSheet = false">
      <div class="share-sheet" @click.stop>
        <div class="sheet-header">
          <span class="sheet-title">分享诊断结果</span>
          <span class="sheet-close" @click="showShareSheet = false">取消</span>
        </div>
        <div class="share-options">
          <div class="share-option" @click="shareToWeChat">
            <span class="share-icon">💬</span>
            <span class="share-label">微信</span>
          </div>
          <div class="share-option" @click="saveImage">
            <span class="share-icon">📷</span>
            <span class="share-label">保存图片</span>
          </div>
          <div class="share-option" @click="copyLink">
            <span class="share-icon">🔗</span>
            <span class="share-label">复制链接</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useDiagnosisStore, type DiagnosisResult } from '@/store'

const router = useRouter()
const route = useRoute()
const diagnosisStore = useDiagnosisStore()

// State
const diagnosis = ref<DiagnosisResult | null>(null)
const isLoading = ref(false)
const errorMessage = ref('')
const feedback = ref<1 | -1 | 0>(0)
const showShareSheet = ref(false)

// Computed
const riskLevelTitle = computed(() => {
  if (!diagnosis.value) return ''
  switch (diagnosis.value.risks.level) {
    case 'low':
      return '低风险'
    case 'medium':
      return '中风险'
    case 'high':
      return '高风险'
    default:
      return ''
  }
})

// Functions
function formatDateTime(timestamp: string): string {
  const date = new Date(timestamp)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}`
}

function goBack() {
  router.back()
}

async function loadDetail() {
  const id = route.params.id as string
  if (!id) {
    errorMessage.value = '诊断ID不存在'
    return
  }

  isLoading.value = true
  errorMessage.value = ''
  try {
    const result = await diagnosisStore.fetchDiagnosisDetail(id)
    diagnosis.value = result
  } catch (error) {
    console.error('Failed to load diagnosis detail:', error)
    errorMessage.value = error instanceof Error ? error.message : '加载失败'
  } finally {
    isLoading.value = false
  }
}

async function submitFeedback(value: 1 | -1) {
  const id = route.params.id as string
  if (!id || feedback.value !== 0) return

  try {
    await diagnosisStore.submitFeedback(id, value)
    feedback.value = value
    alert('感谢反馈')
  } catch (error) {
    console.error('Failed to submit feedback:', error)
    alert('反馈失败')
  }
}

function shareToWeChat() {
  alert('分享功能开发中')
  showShareSheet.value = false
}

function saveImage() {
  alert('保存功能开发中')
  showShareSheet.value = false
}

function copyLink() {
  alert('复制功能开发中')
  showShareSheet.value = false
}

// Lifecycle
onMounted(() => {
  loadDetail()
})
</script>

<style lang="scss" scoped>
.container {
  min-height: 100vh;
  background: #f5f5f5;
}

.header {
  background: #ffffff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 40px 15px 15px;
  border-bottom: 1px solid #f0f0f0;
}

.header-left,
.header-right {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.back-icon,
.share-icon {
  font-size: 24px;
  color: #333333;
}

.header-title {
  font-size: 18px;
  font-weight: 500;
  color: #333333;
}

.content {
  padding-bottom: 30px;
}

.image-section {
  background: #ffffff;
  padding: 20px;
  margin-bottom: 10px;
}

.image-container {
  position: relative;
  width: 100%;
  height: 300px;
  background: #f5f5f5;
  border-radius: 12px;
  overflow: hidden;
}

.tongue-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.mask-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-size: contain;
  background-repeat: no-repeat;
  background-position: center;
  pointer-events: none;
}

.image-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}

.diagnosis-time {
  font-size: 13px;
  color: #999999;
}

.confidence-badge {
  background: #f0f9ff;
  padding: 4px 10px;
  border-radius: 10px;
}

.confidence-text {
  font-size: 12px;
  color: #52c41a;
  font-weight: 500;
}

.section {
  background: #ffffff;
  margin-bottom: 10px;
  padding: 20px;
}

.section-header {
  margin-bottom: 15px;
}

.section-title {
  font-size: 16px;
  font-weight: 500;
  color: #333333;
}

.syndrome-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.syndrome-item {
  padding: 15px;
  border-radius: 12px;
  background: #f8f9fa;
  border-left: 3px solid #e0e0e0;
}

.syndrome-item.primary {
  background: #fff7e6;
  border-left-color: #667eea;
}

.syndrome-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.syndrome-name {
  font-size: 15px;
  font-weight: 500;
  color: #333333;
}

.syndrome-confidence {
  background: #ffffff;
  padding: 4px 10px;
  border-radius: 10px;
}

.confidence-value {
  font-size: 12px;
  color: #667eea;
  font-weight: 500;
}

.syndrome-description {
  font-size: 14px;
  color: #666666;
  line-height: 1.6;
  display: block;
  margin-bottom: 8px;
}

.tcm-theory {
  padding-top: 8px;
  border-top: 1px solid #e0e0e0;
}

.theory-label {
  font-size: 13px;
  color: #999999;
  margin-right: 4px;
}

.theory-text {
  font-size: 13px;
  color: #666666;
  line-height: 1.6;
}

.risk-card {
  padding: 15px;
  border-radius: 12px;
}

.risk-card.risk-low {
  background: #f0f9ff;
  border: 1px solid #b3e0ff;
}

.risk-card.risk-medium {
  background: #fff7e6;
  border: 1px solid #ffd591;
}

.risk-card.risk-high {
  background: #fff0f0;
  border: 1px solid #ffb3b3;
}

.risk-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.risk-title {
  font-size: 15px;
  font-weight: 500;
  color: #333333;
}

.risk-indicator {
  width: 12px;
  height: 12px;
  border-radius: 6px;
}

.risk-indicator.indicator-low {
  background: #52c41a;
}

.risk-indicator.indicator-medium {
  background: #faad14;
}

.risk-indicator.indicator-high {
  background: #ff4d4f;
}

.risk-factors,
.risk-suggestions {
  margin-bottom: 8px;
}

.factors-label,
.suggestions-label {
  font-size: 13px;
  color: #999999;
  margin-right: 4px;
}

.factors-text,
.suggestions-text {
  font-size: 13px;
  color: #666666;
  line-height: 1.6;
}

.recommendations-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.recommendation-item {
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
}

.rec-category {
  font-size: 13px;
  color: #667eea;
  font-weight: 500;
  display: block;
  margin-bottom: 5px;
}

.rec-text {
  font-size: 14px;
  color: #333333;
  line-height: 1.6;
}

.model-info {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.info-label {
  font-size: 14px;
  color: #999999;
}

.info-value {
  font-size: 14px;
  color: #333333;
  font-weight: 500;
}

.feedback-section {
  background: #ffffff;
  margin: 10px 0;
  padding: 20px;
  text-align: center;
}

.feedback-question {
  font-size: 15px;
  color: #333333;
  margin-bottom: 15px;
}

.feedback-buttons {
  display: flex;
  gap: 15px;
  justify-content: center;
}

.feedback-btn {
  flex: 1;
  max-width: 150px;
  height: 44px;
  border-radius: 22px;
  border: 1px solid #e0e0e0;
  background: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 14px;
  color: #666666;
  cursor: pointer;
}

.feedback-btn.active {
  background: #667eea;
  border-color: #667eea;
  color: #ffffff;
}

.feedback-icon {
  font-size: 20px;
}

.share-sheet {
  background: #ffffff;
  border-radius: 20px 20px 0 0;
  width: 100%;
  max-width: 500px;
  position: fixed;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  padding: 20px;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  z-index: 1000;
}

.sheet-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.sheet-title {
  font-size: 18px;
  font-weight: 500;
  color: #333333;
}

.sheet-close {
  font-size: 15px;
  color: #667eea;
  cursor: pointer;
}

.share-options {
  display: flex;
  justify-content: space-around;
}

.share-option {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 15px;
  cursor: pointer;
}

.share-option:hover {
  opacity: 0.7;
}

.share-icon {
  font-size: 40px;
}

.share-label {
  font-size: 13px;
  color: #666666;
}

.loading-state,
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  text-align: center;
}

.loading-text {
  font-size: 14px;
  color: #999999;
}

.error-icon {
  font-size: 60px;
  margin-bottom: 20px;
}

.error-title {
  font-size: 18px;
  font-weight: 500;
  color: #333333;
  margin-bottom: 10px;
}

.error-desc {
  font-size: 14px;
  color: #999999;
  margin-bottom: 30px;
}

.btn {
  height: 44px;
  padding: 0 30px;
  border-radius: 22px;
  font-size: 15px;
  font-weight: 500;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.btn-primary {
  background: #667eea;
  color: #ffffff;
}

.btn-primary:hover {
  opacity: 0.9;
}

/* Dark mode styles */
:global(.dark-mode) .container {
  background: #1a1a1a;
}

:global(.dark-mode) .header {
  background: #2a2a2a;
  border-bottom-color: #3a3a3a;
}

:global(.dark-mode) .back-icon,
:global(.dark-mode) .share-icon,
:global(.dark-mode) .header-title {
  color: #e0e0e0;
}

:global(.dark-mode) .image-section,
:global(.dark-mode) .section,
:global(.dark-mode) .feedback-section {
  background: #2a2a2a;
}

:global(.dark-mode) .section-title,
:global(.dark-mode) .syndrome-name,
:global(.dark-mode) .info-value,
:global(.dark-mode) .feedback-question {
  color: #e0e0e0;
}

:global(.dark-mode) .syndrome-description,
:global(.dark-mode) .theory-text,
:global(.dark-mode) .factors-text,
:global(.dark-mode) .suggestions-text,
:global(.dark-mode) .rec-text {
  color: #aaaaaa;
}

:global(.dark-mode) .share-sheet {
  background: #2a2a2a;
}

:global(.dark-mode) .sheet-title {
  color: #e0e0e0;
}

:global(.dark-mode) .share-label {
  color: #888888;
}

:global(.dark-mode) .feedback-btn.active {
  background: #5a6fd8;
  border-color: #5a6fd8;
}
</style>
