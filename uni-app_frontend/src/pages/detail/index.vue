<template>
  <view class="container">
    <view class="header">
      <view class="header-left" @click="goBack">
        <text class="back-icon">←</text>
      </view>
      <text class="header-title">诊断详情</text>
      <view class="header-right" @click="showShareSheet = true">
        <text class="share-icon">⋮</text>
      </view>
    </view>

    <view class="content" v-if="diagnosis">
      <!-- Tongue image section -->
      <view class="image-section">
        <view class="image-container">
          <image
            class="tongue-image"
            :src="diagnosis.image_url"
            mode="aspectFit"
          />
          <view
            class="mask-overlay"
            v-if="diagnosis.mask_url"
            :style="{ backgroundImage: `url(${diagnosis.mask_url})` }"
          />
        </view>
        <view class="image-info">
          <text class="diagnosis-time">{{ formatDateTime(diagnosis.created_at) }}</text>
          <view class="confidence-badge">
            <text class="confidence-text">置信度 {{ Math.round(diagnosis.confidence * 100) }}%</text>
          </view>
        </view>
      </view>

      <!-- Syndrome analysis -->
      <view class="section syndrome-section">
        <view class="section-header">
          <text class="section-title">证型分析</text>
        </view>
        <view class="syndrome-list">
          <view
            class="syndrome-item"
            v-for="(syndrome, index) in diagnosis.syndromes"
            :key="index"
            :class="{ primary: index === 0 }"
          >
            <view class="syndrome-header">
              <text class="syndrome-name">{{ syndrome.name }}</text>
              <view class="syndrome-confidence">
                <text class="confidence-value">{{ Math.round(syndrome.confidence * 100) }}%</text>
              </view>
            </view>
            <text class="syndrome-description">{{ syndrome.description }}</text>
            <view class="tcm-theory" v-if="syndrome.tcm_theory">
              <text class="theory-label">中医理论：</text>
              <text class="theory-text">{{ syndrome.tcm_theory }}</text>
            </view>
          </view>
        </view>
      </view>

      <!-- Feature display -->
      <view class="section feature-section">
        <view class="section-header">
          <text class="section-title">舌象特征</text>
        </view>
        <feature-display :features="diagnosis.features" />
      </view>

      <!-- Risk assessment -->
      <view class="section risk-section" v-if="diagnosis.risks">
        <view class="section-header">
          <text class="section-title">风险评估</text>
        </view>
        <view class="risk-card" :class="`risk-${diagnosis.risks.level}`">
          <view class="risk-header">
            <text class="risk-title">{{ riskLevelTitle }}</text>
            <view class="risk-indicator" :class="`indicator-${diagnosis.risks.level}`"></view>
          </view>
          <view class="risk-factors" v-if="diagnosis.risks.factors.length > 0">
            <text class="factors-label">风险因素：</text>
            <text class="factors-text">{{ diagnosis.risks.factors.join('、') }}</text>
          </view>
          <view class="risk-suggestions" v-if="diagnosis.risks.suggestions.length > 0">
            <text class="suggestions-label">建议：</text>
            <text class="suggestions-text">{{ diagnosis.risks.suggestions.join('；') }}</text>
          </view>
        </view>
      </view>

      <!-- Health recommendations -->
      <view class="section recommendation-section">
        <view class="section-header">
          <text class="section-title">健康建议</text>
        </view>
        <recommendation-list :recommendations="diagnosis.recommendations" />
      </view>

      <!-- Model info -->
      <view class="section model-section">
        <view class="section-header">
          <text class="section-title">诊断信息</text>
        </view>
        <view class="model-info">
          <view class="info-row">
            <text class="info-label">分割模型</text>
            <text class="info-value">{{ diagnosis.model_info.segmentation_model }}</text>
          </view>
          <view class="info-row">
            <text class="info-label">分类模型</text>
            <text class="info-value">{{ diagnosis.model_info.classification_model }}</text>
          </view>
          <view class="info-row">
            <text class="info-label">诊断模型</text>
            <text class="info-value">{{ diagnosis.model_info.diagnosis_model }}</text>
          </view>
          <view class="info-row">
            <text class="info-label">推理时间</text>
            <text class="info-value">{{ diagnosis.inference_time }}ms</text>
          </view>
        </view>
      </view>

      <!-- Feedback section -->
      <view class="feedback-section">
        <text class="feedback-question">诊断结果准确吗？</text>
        <view class="feedback-buttons">
          <button
            class="feedback-btn"
            :class="{ active: feedback === 1 }"
            @click="submitFeedback(1)"
          >
            <text class="feedback-icon">👍</text>
            <text class="feedback-text">准确</text>
          </button>
          <button
            class="feedback-btn"
            :class="{ active: feedback === -1 }"
            @click="submitFeedback(-1)"
          >
            <text class="feedback-icon">👎</text>
            <text class="feedback-text">不准确</text>
          </button>
        </view>
      </view>
    </view>

    <!-- Loading state -->
    <view class="loading-state" v-else-if="isLoading">
      <text class="loading-text">加载中...</text>
    </view>

    <!-- Error state -->
    <view class="error-state" v-else>
      <text class="error-icon">⚠️</text>
      <text class="error-title">加载失败</text>
      <text class="error-desc">{{ errorMessage }}</text>
      <button class="btn btn-primary" @click="loadDetail">重新加载</button>
    </view>

    <!-- Share sheet -->
    <u-popup v-model:show="showShareSheet" mode="bottom" :round="20">
      <view class="share-sheet">
        <view class="sheet-header">
          <text class="sheet-title">分享诊断结果</text>
          <text class="sheet-close" @click="showShareSheet = false">取消</text>
        </view>
        <view class="share-options">
          <view class="share-option" @click="shareToWeChat">
            <text class="share-icon">💬</text>
            <text class="share-label">微信</text>
          </view>
          <view class="share-option" @click="saveImage">
            <text class="share-icon">📷</text>
            <text class="share-label">保存图片</text>
          </view>
          <view class="share-option" @click="copyLink">
            <text class="share-icon">🔗</text>
            <text class="share-label">复制链接</text>
          </view>
        </view>
      </view>
    </u-popup>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useDiagnosisStore, type DiagnosisResult } from '@/store'
import { onLoad } from '@dcloudio/uni-app'

const diagnosisStore = useDiagnosisStore()

// State
const diagnosis = ref<DiagnosisResult | null>(null)
const isLoading = ref(false)
const errorMessage = ref('')
const feedback = ref<1 | -1 | 0>(0)
const showShareSheet = ref(false)
const diagnosisId = ref('')

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
  uni.navigateBack()
}

async function loadDetail() {
  if (!diagnosisId.value) {
    errorMessage.value = '诊断ID不存在'
    return
  }

  isLoading.value = true
  errorMessage.value = ''
  try {
    const result = await diagnosisStore.fetchDiagnosisDetail(diagnosisId.value)
    diagnosis.value = result
  } catch (error) {
    console.error('Failed to load diagnosis detail:', error)
    errorMessage.value = error instanceof Error ? error.message : '加载失败'
  } finally {
    isLoading.value = false
  }
}

async function submitFeedback(value: 1 | -1) {
  if (!diagnosisId.value || feedback.value !== 0) return

  try {
    await diagnosisStore.submitFeedback(diagnosisId.value, value)
    feedback.value = value
    uni.showToast({
      title: '感谢反馈',
      icon: 'success'
    })
  } catch (error) {
    console.error('Failed to submit feedback:', error)
    uni.showToast({
      title: '反馈失败',
      icon: 'none'
    })
  }
}

function shareToWeChat() {
  // Implement WeChat share
  uni.showToast({
    title: '分享功能开发中',
    icon: 'none'
  })
  showShareSheet.value = false
}

function saveImage() {
  // Implement save image
  uni.showToast({
    title: '保存功能开发中',
    icon: 'none'
  })
  showShareSheet.value = false
}

function copyLink() {
  // Implement copy link
  uni.showToast({
    title: '复制功能开发中',
    icon: 'none'
  })
  showShareSheet.value = false
}

// Lifecycle
onLoad((options: any) => {
  diagnosisId.value = options?.id || ''
  if (diagnosisId.value) {
    loadDetail()
  } else {
    errorMessage.value = '缺少诊断ID参数'
  }
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
  padding: 50px 15px 15px;
  border-bottom: 1px solid #f0f0f0;
}

.header-left,
.header-right {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
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
  display: block;
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
  padding: 20px;
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
  display: block;
}

.error-desc {
  font-size: 14px;
  color: #999999;
  margin-bottom: 30px;
  display: block;
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
}

.btn-primary {
  background: #667eea;
  color: #ffffff;
}
</style>
