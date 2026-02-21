<template>
  <view class="container">
    <!-- Custom Header -->
    <view class="header">
      <view class="header-left" @click="goBack">
        <text class="icon-back">←</text>
      </view>
      <text class="header-title">诊断结果</text>
      <view class="header-right" @click="showShareMenu">
        <text class="icon-share">⋮</text>
      </view>
    </view>

    <scroll-view class="content" scroll-y v-if="diagnosis">
      <!-- Tongue Image with Mask Overlay -->
      <view class="image-section">
        <view class="image-container">
          <image
            class="tongue-image"
            :src="diagnosis.image_url"
            mode="aspectFill"
          />
          <!-- Mask Overlay -->
          <image
            v-if="diagnosis.mask_url"
            class="mask-overlay"
            :src="diagnosis.mask_url"
            mode="aspectFill"
          />
        </view>
      </view>

      <!-- 6-Dimension Feature Display -->
      <view class="section features-section">
        <text class="section-title">舌象特征分析</text>
        <view class="features-grid">
          <!-- Tongue Color -->
          <view class="feature-item">
            <text class="feature-label">舌色</text>
            <view class="feature-values">
              <view
                v-for="(value, key) in diagnosis.features.tongue_color"
                :key="key"
                class="feature-value"
                :class="{ active: value > 0.3 }"
              >
                <text class="value-name">{{ key }}</text>
                <view class="value-bar">
                  <view class="bar-fill" :style="{ width: `${value * 100}%` }"></view>
                </view>
                <text class="value-percent">{{ Math.round(value * 100) }}%</text>
              </view>
            </view>
          </view>

          <!-- Tongue Shape -->
          <view class="feature-item">
            <text class="feature-label">舌形</text>
            <view class="feature-values">
              <view
                v-for="(value, key) in diagnosis.features.tongue_shape"
                :key="key"
                class="feature-value"
                :class="{ active: value > 0.3 }"
              >
                <text class="value-name">{{ key }}</text>
                <view class="value-bar">
                  <view class="bar-fill" :style="{ width: `${value * 100}%` }"></view>
                </view>
                <text class="value-percent">{{ Math.round(value * 100) }}%</text>
              </view>
            </view>
          </view>

          <!-- Coating Color -->
          <view class="feature-item">
            <text class="feature-label">苔色</text>
            <view class="feature-values">
              <view
                v-for="(value, key) in diagnosis.features.coating_color"
                :key="key"
                class="feature-value"
                :class="{ active: value > 0.3 }"
              >
                <text class="value-name">{{ key }}</text>
                <view class="value-bar">
                  <view class="bar-fill" :style="{ width: `${value * 100}%` }"></view>
                </view>
                <text class="value-percent">{{ Math.round(value * 100) }}%</text>
              </view>
            </view>
          </view>

          <!-- Coating Quality -->
          <view class="feature-item">
            <text class="feature-label">苔质</text>
            <view class="feature-values">
              <view
                v-for="(value, key) in diagnosis.features.coating_quality"
                :key="key"
                class="feature-value"
                :class="{ active: value > 0.3 }"
              >
                <text class="value-name">{{ key }}</text>
                <view class="value-bar">
                  <view class="bar-fill" :style="{ width: `${value * 100}%` }"></view>
                </view>
                <text class="value-percent">{{ Math.round(value * 100) }}%</text>
              </view>
            </view>
          </view>

          <!-- Sublingual Vein -->
          <view class="feature-item">
            <text class="feature-label">舌下络脉</text>
            <view class="feature-values">
              <view
                v-for="(value, key) in diagnosis.features.sublingual_vein"
                :key="key"
                class="feature-value"
                :class="{ active: value > 0.3 }"
              >
                <text class="value-name">{{ key }}</text>
                <view class="value-bar">
                  <view class="bar-fill" :style="{ width: `${value * 100}%` }"></view>
                </view>
                <text class="value-percent">{{ Math.round(value * 100) }}%</text>
              </view>
            </view>
          </view>

          <!-- Special Features -->
          <view class="feature-item">
            <text class="feature-label">特殊特征</text>
            <view class="feature-values">
              <view
                v-for="(value, key) in diagnosis.features.special_features"
                :key="key"
                class="feature-value"
                :class="{ active: value > 0.3 }"
              >
                <text class="value-name">{{ key }}</text>
                <view class="value-bar">
                  <view class="bar-fill" :style="{ width: `${value * 100}%` }"></view>
                </view>
                <text class="value-percent">{{ Math.round(value * 100) }}%</text>
              </view>
            </view>
          </view>
        </view>
      </view>

      <!-- Syndrome Analysis -->
      <view class="section syndrome-section">
        <text class="section-title">证型分析</text>
        <view class="syndrome-cards">
          <view
            v-for="syndrome in diagnosis.syndromes"
            :key="syndrome.name"
            class="syndrome-card"
            :class="{ primary: syndrome.confidence > 0.6 }"
          >
            <view class="syndrome-header">
              <text class="syndrome-name">{{ syndrome.name }}</text>
              <view class="syndrome-confidence">
                <text class="confidence-value">{{ Math.round(syndrome.confidence * 100) }}%</text>
              </view>
            </view>
            <text class="syndrome-desc">{{ syndrome.description }}</text>
            <view class="syndrome-theory" v-if="syndrome.tcm_theory">
              <text class="theory-label">中医理论：</text>
              <text class="theory-text">{{ syndrome.tcm_theory }}</text>
            </view>
          </view>
        </view>
      </view>

      <!-- Health Recommendations (Collapsible) -->
      <view class="section recommendations-section">
        <view class="section-header" @click="toggleRecommendations">
          <text class="section-title">健康建议</text>
          <text class="toggle-icon" :class="{ expanded: recommendationsExpanded }">▼</text>
        </view>
        <view class="recommendations-content" v-if="recommendationsExpanded">
          <!-- Dietary -->
          <view class="recommendation-group" v-if="diagnosis.recommendations.dietary?.length">
            <view class="group-header">
              <text class="group-icon">🥗</text>
              <text class="group-title">饮食建议</text>
            </view>
            <view class="recommendation-list">
              <text
                v-for="(item, index) in diagnosis.recommendations.dietary"
                :key="index"
                class="recommendation-item"
              >
                {{ item }}
              </text>
            </view>
          </view>

          <!-- Lifestyle -->
          <view class="recommendation-group" v-if="diagnosis.recommendations.lifestyle?.length">
            <view class="group-header">
              <text class="group-icon">🏃</text>
              <text class="group-title">生活建议</text>
            </view>
            <view class="recommendation-list">
              <text
                v-for="(item, index) in diagnosis.recommendations.lifestyle"
                :key="index"
                class="recommendation-item"
              >
                {{ item }}
              </text>
            </view>
          </view>

          <!-- Emotional -->
          <view class="recommendation-group" v-if="diagnosis.recommendations.emotional?.length">
            <view class="group-header">
              <text class="group-icon">😌</text>
              <text class="group-title">情志建议</text>
            </view>
            <view class="recommendation-list">
              <text
                v-for="(item, index) in diagnosis.recommendations.emotional"
                :key="index"
                class="recommendation-item"
              >
                {{ item }}
              </text>
            </view>
          </view>
        </view>
      </view>

      <!-- Risk Alert -->
      <view
        class="section risk-section"
        v-if="diagnosis.risks && diagnosis.risks.level !== 'low'"
        :class="`risk-${diagnosis.risks.level}`"
      >
        <view class="risk-header">
          <text class="risk-icon">⚠️</text>
          <text class="risk-title">健康提醒</text>
        </view>
        <view class="risk-content">
          <text
            v-for="(factor, index) in diagnosis.risks.factors"
            :key="index"
            class="risk-factor"
          >
            {{ factor }}
          </text>
          <text
            v-for="(suggestion, index) in diagnosis.risks.suggestions"
            :key="`sug-${index}`"
            class="risk-suggestion"
          >
            {{ suggestion }}
          </text>
        </view>
      </view>

      <!-- Meta Info -->
      <view class="section meta-section">
        <text class="meta-text">诊断时间：{{ formatDate(diagnosis.created_at) }}</text>
        <text class="meta-text">AI诊断耗时：{{ diagnosis.inference_time }}秒</text>
      </view>
    </scroll-view>

    <!-- Loading State -->
    <view class="loading-container" v-else>
      <view class="loading-spinner"></view>
      <text class="loading-text">正在加载诊断结果...</text>
    </view>

    <!-- Action Buttons -->
    <view class="action-bar" v-if="diagnosis">
      <button class="btn-action btn-feedback" @click="showFeedbackModal">
        <text class="btn-icon">👍</text>
        <text class="btn-text">反馈</text>
      </button>
      <button class="btn-action btn-share" @click="showShareMenu">
        <text class="btn-icon">📤</text>
        <text class="btn-text">分享</text>
      </button>
      <button class="btn-action btn-save" @click="saveImage">
        <text class="btn-icon">💾</text>
        <text class="btn-text">保存</text>
      </button>
    </view>

    <!-- Feedback Modal -->
    <view class="modal-overlay" v-if="showFeedback" @click="closeFeedbackModal">
      <view class="feedback-modal" @click.stop>
        <text class="modal-title">诊断结果是否有帮助？</text>
        <view class="feedback-buttons">
          <button class="btn-feedback-option" @click="submitFeedback(1)">
            <text class="feedback-icon">👍</text>
            <text class="feedback-text">准确</text>
          </button>
          <button class="btn-feedback-option" @click="submitFeedback(-1)">
            <text class="feedback-icon">👎</text>
            <text class="feedback-text">不准确</text>
          </button>
        </view>
        <button class="btn-close" @click="closeFeedbackModal">取消</button>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useDiagnosisStore } from '@/store'
import type { DiagnosisResult } from '@/store/modules/diagnosis'
import {
  generateShareImage,
  saveImageToAlbum,
  shareToWeChat,
  shareWithSystem,
  copyToClipboard,
  generateShareLink,
  shareDiagnosis,
  getPlatform
} from '@/utils/share'

const diagnosisStore = useDiagnosisStore()
const platform = getPlatform()

// State
const diagnosisId = ref<string>('')
const diagnosis = ref<DiagnosisResult | null>(null)
const recommendationsExpanded = ref(false)
const showFeedback = ref(false)

// Methods
function goBack() {
  uni.navigateBack({
    delta: 1
  })
}

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function toggleRecommendations() {
  recommendationsExpanded.value = !recommendationsExpanded.value
}

function showFeedbackModal() {
  showFeedback.value = true
}

function closeFeedbackModal() {
  showFeedback.value = false
}

async function submitFeedback(feedback: 1 | -1) {
  if (!diagnosis.value) return

  try {
    await diagnosisStore.submitFeedback(diagnosis.value.id, feedback)
    uni.showToast({
      title: '感谢您的反馈',
      icon: 'success'
    })
    closeFeedbackModal()
  } catch (error: any) {
    uni.showToast({
      title: error.message || '反馈失败',
      icon: 'none'
    })
  }
}

function showShareMenu() {
  uni.showActionSheet({
    itemList: ['保存图片', '分享给朋友', '复制链接'],
    success: (res) => {
      switch (res.tapIndex) {
        case 0:
          saveImage()
          break
        case 1:
          shareToFriend()
          break
        case 2:
          copyLink()
          break
      }
    }
  })
}

function saveResult() {
  uni.showToast({
    title: '保存功能开发中',
    icon: 'none'
  })
}

async function saveImage() {
  if (!diagnosis.value) return

  try {
    uni.showLoading({
      title: '正在生成图片...'
    })

    // Generate share image
    const result = await generateShareImage({
      title: 'AI舌诊诊断结果',
      imageUrl: diagnosis.value.image_url,
      primarySyndrome: diagnosis.value.syndromes[0]?.name || '',
      confidence: diagnosis.value.syndromes[0]?.confidence || 0,
      recommendations: diagnosis.value.recommendations.dietary?.slice(0, 3) || []
    })

    uni.hideLoading()

    if (result.success && result.filePath) {
      // For H5, download the image
      if (platform.isH5) {
        // Create download link for H5
        const link = document.createElement('a')
        link.href = result.filePath
        link.download = `tongue-diagnosis-${Date.now()}.png`
        link.click()

        uni.showToast({
          title: '图片已下载',
          icon: 'success'
        })
      } else {
        // For mini-programs, save to album
        const saveResult = await saveImageToAlbum(result.filePath)
        if (saveResult.success) {
          uni.showToast({
            title: saveResult.message || '已保存到相册',
            icon: 'success'
          })
        } else {
          uni.showToast({
            title: saveResult.message || '保存失败',
            icon: 'none'
          })
        }
      }
    } else {
      uni.showToast({
        title: result.message || '生成失败',
        icon: 'none'
      })
    }
  } catch (error: any) {
    uni.hideLoading()
    uni.showToast({
      title: error.message || '保存失败',
      icon: 'none'
    })
  }
}

async function shareToFriend() {
  if (!diagnosis.value) return

  try {
    uni.showLoading({
      title: '正在处理...'
    })

    // Use main share function
    const result = await shareDiagnosis({
      diagnosisId: diagnosis.value.id,
      title: 'AI舌诊诊断结果',
      imageUrl: diagnosis.value.image_url,
      primarySyndrome: diagnosis.value.syndromes[0]?.name || '',
      confidence: diagnosis.value.syndromes[0]?.confidence || 0,
      recommendations: diagnosis.value.recommendations.dietary?.slice(0, 3) || [],
      baseUrl: (typeof window !== 'undefined' ? window.location.origin : '') || 'https://your-app.com'
    })

    uni.hideLoading()

    if (result.success) {
      uni.showToast({
        title: result.message || '分享成功',
        icon: 'success'
      })
    } else {
      uni.showToast({
        title: result.message || '分享失败',
        icon: 'none'
      })
    }
  } catch (error: any) {
    uni.hideLoading()
    uni.showToast({
      title: error.message || '分享失败',
      icon: 'none'
    })
  }
}

async function copyLink() {
  if (!diagnosis.value) return

  try {
    const link = generateShareLink(
      diagnosis.value.id,
      (typeof window !== 'undefined' ? window.location.origin : '') || 'https://your-app.com'
    )
    const result = await copyToClipboard(link)

    if (result.success) {
      uni.showToast({
        title: result.message || '链接已复制',
        icon: 'success'
      })
    } else {
      uni.showToast({
        title: result.message || '复制失败',
        icon: 'none'
      })
    }
  } catch (error: any) {
    uni.showToast({
      title: error.message || '复制失败',
      icon: 'none'
    })
  }
}

// Lifecycle
onMounted(async () => {
  // Get diagnosis ID from query params
  const pages = getCurrentPages()
  const currentPage = pages[pages.length - 1]
  const options = currentPage.options as any

  if (options.id) {
    diagnosisId.value = options.id
    try {
      const result = await diagnosisStore.fetchDiagnosisDetail(diagnosisId.value)
      diagnosis.value = result
    } catch (error: any) {
      uni.showToast({
        title: error.message || '加载失败',
        icon: 'none'
      })
    }
  } else if (diagnosisStore.currentDiagnosis) {
    diagnosis.value = diagnosisStore.currentDiagnosis
  } else {
    uni.showToast({
      title: '未找到诊断结果',
      icon: 'none'
    })
    setTimeout(() => {
      uni.navigateBack()
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
  padding: 0 15px;
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
}

.mask-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  opacity: 0.5;
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

// Feedback Modal
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

.feedback-modal {
  width: 80%;
  max-width: 320px;
  background: #ffffff;
  border-radius: 16px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.modal-title {
  font-size: 16px;
  font-weight: 500;
  color: #333333;
  text-align: center;
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
}
</style>
