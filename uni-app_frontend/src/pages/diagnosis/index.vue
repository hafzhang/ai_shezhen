<template>
  <view class="container">
    <!-- Custom Header -->
    <view class="header">
      <view class="header-left" @click="goBack">
        <text class="icon-back">←</text>
      </view>
      <text class="header-title">舌诊诊断</text>
      <view class="header-right"></view>
    </view>

    <view class="content">
      <!-- Image Upload Section -->
      <view class="upload-section">
        <text class="section-title">上传舌部照片</text>
        <text class="section-desc">请拍摄清晰的舌部照片，确保光线充足</text>

        <!-- Image Preview Component -->
        <image-preview
          :image-src="selectedImage"
          :show-actions="true"
          :show-info="false"
          :show-preview-hint="true"
          :compression-info="compressionInfo"
          empty-text="请拍摄或选择舌部照片"
          @delete="removeImage"
          @reselect="selectFromAlbum"
          @empty-click="takePhoto"
        />

        <!-- Photo Tips -->
        <view class="photo-tips">
          <text class="tips-title">拍照提示：</text>
          <view class="tips-list">
            <text class="tip-item">• 请在自然光或明亮灯光下拍摄</text>
            <text class="tip-item">• 舌头自然伸出，不要过度用力</text>
            <text class="tip-item">• 保持舌面平整，尽量舒展</text>
            <text class="tip-item">• 避免有色食物（如咖啡、咖喱）后立即拍摄</text>
          </view>
        </view>
      </view>

      <!-- User Info Form -->
      <view class="form-section">
        <text class="section-title">基本信息（可选）</text>
        <text class="section-desc">提供信息有助于更准确的诊断分析</text>

        <view class="form-group">
          <text class="form-label">年龄</text>
          <input
            class="form-input"
            type="number"
            v-model="formData.age"
            placeholder="请输入年龄"
            :maxlength="3"
          />
        </view>

        <view class="form-group">
          <text class="form-label">性别</text>
          <view class="gender-options">
            <view
              class="gender-option"
              :class="{ active: formData.gender === 'male' }"
              @click="selectGender('male')"
            >
              <text class="gender-icon">♂</text>
              <text class="gender-text">男</text>
            </view>
            <view
              class="gender-option"
              :class="{ active: formData.gender === 'female' }"
              @click="selectGender('female')"
            >
              <text class="gender-icon">♀</text>
              <text class="gender-text">女</text>
            </view>
          </view>
        </view>

        <view class="form-group">
          <text class="form-label">主要症状</text>
          <textarea
            class="form-textarea"
            v-model="formData.chief_complaint"
            placeholder="请描述您的主要症状或不适（可选）"
            :maxlength="200"
          />
          <text class="char-count">{{ formData.chief_complaint.length }}/200</text>
        </view>
      </view>

      <!-- Submit Button -->
      <view class="submit-section">
        <button
          class="btn-submit"
          :class="{ disabled: !canSubmit || isDiagnosing }"
          :disabled="!canSubmit || isDiagnosing"
          @click="submitDiagnosis"
        >
          <text v-if="!isDiagnosing">开始诊断</text>
          <text v-else>诊断中...</text>
        </button>
        <text class="submit-hint">诊断过程可能需要几秒钟，请耐心等待</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useDiagnosisStore } from '@/store'
import type { DiagnosisResult } from '@/store/modules/diagnosis'
import ImagePreview from '@/components/image-preview/image-preview.vue'
import { compressImage, formatFileSize } from '@/utils/imageCompress'

const diagnosisStore = useDiagnosisStore()

// Form data
interface FormData {
  age: string
  gender: 'male' | 'female' | null
  chief_complaint: string
}

const formData = ref<FormData>({
  age: '',
  gender: null,
  chief_complaint: ''
})

// Selected image (base64 or temp file path)
const selectedImage = ref<string>('')

// Compression info
const compressionInfo = ref<{
  originalSize: string
  compressedSize: string
  ratio: string
} | null>(null)

// Computed
const canSubmit = computed(() => {
  return selectedImage.value.length > 0
})

const isDiagnosing = computed(() => {
  return diagnosisStore.isDiagnosing
})

// Actions
function goBack() {
  uni.navigateBack({
    delta: 1
  })
}

function selectGender(gender: 'male' | 'female') {
  if (formData.value.gender === gender) {
    formData.value.gender = null
  } else {
    formData.value.gender = gender
  }
}

// Camera functionality
function takePhoto() {
  uni.chooseImage({
    count: 1,
    sizeType: ['compressed'], // Use compressed image
    sourceType: ['camera'],
    success: (res) => {
      handleSelectedImage(res.tempFilePaths[0])
    },
    fail: (error) => {
      console.error('Failed to take photo:', error)
      uni.showToast({
        title: '拍照失败，请重试',
        icon: 'none'
      })
    }
  })
}

function selectFromAlbum() {
  uni.chooseImage({
    count: 1,
    sizeType: ['compressed'],
    sourceType: ['album'],
    success: (res) => {
      handleSelectedImage(res.tempFilePaths[0])
    },
    fail: (error) => {
      console.error('Failed to select from album:', error)
      uni.showToast({
        title: '选择图片失败，请重试',
        icon: 'none'
      })
    }
  })
}

async function handleSelectedImage(filePath: string) {
  // Show loading
  uni.showLoading({
    title: '处理中...',
    mask: true
  })

  try {
    // Compress image using canvas
    const result = await compressImage(filePath, {
      quality: 0.8,
      maxWidth: 1920,
      maxHeight: 1920,
      maxFileSize: 2 * 1024 * 1024, // 2MB
      format: 'jpeg'
    })

    // Update selected image
    selectedImage.value = result.dataUrl

    // Store compression info
    compressionInfo.value = {
      originalSize: formatFileSize(result.originalSize),
      compressedSize: formatFileSize(result.compressedSize),
      ratio: `${Math.round(result.ratio * 100)}%`
    }

    // Show compression success message
    uni.showToast({
      title: `已压缩 (${compressionInfo.value.ratio})`,
      icon: 'success',
      duration: 2000
    })

    console.log('Image compressed:', {
      original: formatFileSize(result.originalSize),
      compressed: formatFileSize(result.compressedSize),
      ratio: compressionInfo.value.ratio,
      dimensions: `${result.width}x${result.height}`
    })
  } catch (error) {
    console.error('Image compression failed:', error)

    // Fallback to direct base64 conversion
    uni.getFileSystemManager().readFile({
      filePath: filePath,
      encoding: 'base64',
      success: (res) => {
        const base64 = `data:image/jpeg;base64,${res.data}`
        selectedImage.value = base64
        compressionInfo.value = null
        uni.hideLoading()
        uni.showToast({
          title: '图片处理完成',
          icon: 'success'
        })
      },
      fail: (err) => {
        console.error('Failed to read file:', err)
        uni.hideLoading()
        uni.showToast({
          title: '图片处理失败',
          icon: 'none'
        })
      }
    })
  } finally {
    uni.hideLoading()
  }
}

function removeImage() {
  selectedImage.value = ''
  compressionInfo.value = null
}

async function submitDiagnosis() {
  if (!canSubmit.value || isDiagnosing.value) {
    return
  }

  // Validate age if provided
  if (formData.value.age) {
    const ageNum = parseInt(formData.value.age)
    if (isNaN(ageNum) || ageNum < 0 || ageNum > 150) {
      uni.showToast({
        title: '请输入有效的年龄',
        icon: 'none'
      })
      return
    }
  }

  try {
    // Prepare user info
    const userInfo: {
      age?: number
      gender?: 'male' | 'female'
      chief_complaint?: string
    } = {}

    if (formData.value.age) {
      userInfo.age = parseInt(formData.value.age)
    }
    if (formData.value.gender) {
      userInfo.gender = formData.value.gender
    }
    if (formData.value.chief_complaint) {
      userInfo.chief_complaint = formData.value.chief_complaint
    }

    // Submit diagnosis
    const result = await diagnosisStore.submitDiagnosis(selectedImage.value, userInfo)

    // Navigate to result page
    uni.redirectTo({
      url: `/pages/result/index?id=${result.id}`
    })
  } catch (error: any) {
    console.error('Diagnosis failed:', error)
    uni.showToast({
      title: error.message || '诊断失败，请重试',
      icon: 'none',
      duration: 3000
    })
  }
}
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
}

.icon-back {
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
  padding: 20px 15px;
}

.upload-section {
  background: #ffffff;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 15px;
}

.section-title {
  font-size: 16px;
  font-weight: 500;
  color: #333333;
  display: block;
  margin-bottom: 8px;
}

.section-desc {
  font-size: 13px;
  color: #999999;
  display: block;
  margin-bottom: 15px;
}

.photo-tips {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 12px;
}

.tips-title {
  font-size: 13px;
  font-weight: 500;
  color: #667eea;
  display: block;
  margin-bottom: 8px;
}

.tips-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tip-item {
  font-size: 12px;
  color: #666666;
  line-height: 1.5;
}

.form-section {
  background: #ffffff;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 15px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-label {
  font-size: 14px;
  font-weight: 500;
  color: #333333;
  display: block;
  margin-bottom: 10px;
}

.form-input {
  width: 100%;
  height: 44px;
  border-radius: 8px;
  border: 1px solid #e5e5e5;
  background: #fafafa;
  padding: 0 15px;
  font-size: 15px;
  color: #333333;
}

.form-input:focus {
  border-color: #667eea;
  background: #ffffff;
}

.gender-options {
  display: flex;
  gap: 12px;
}

.gender-option {
  flex: 1;
  height: 50px;
  border-radius: 8px;
  border: 1px solid #e5e5e5;
  background: #fafafa;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s;
}

.gender-option.active {
  border-color: #667eea;
  background: rgba(102, 126, 234, 0.1);
}

.gender-icon {
  font-size: 22px;
}

.gender-option.active .gender-icon {
  color: #667eea;
}

.gender-text {
  font-size: 15px;
  color: #666666;
}

.gender-option.active .gender-text {
  color: #667eea;
  font-weight: 500;
}

.form-textarea {
  width: 100%;
  min-height: 100px;
  border-radius: 8px;
  border: 1px solid #e5e5e5;
  background: #fafafa;
  padding: 12px 15px;
  font-size: 15px;
  color: #333333;
  line-height: 1.5;
}

.form-textarea:focus {
  border-color: #667eea;
  background: #ffffff;
}

.char-count {
  font-size: 12px;
  color: #999999;
  text-align: right;
  display: block;
  margin-top: 6px;
}

.submit-section {
  padding: 10px 0;
}

.btn-submit {
  width: 100%;
  height: 50px;
  border-radius: 25px;
  border: none;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #ffffff;
  font-size: 18px;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.btn-submit:active {
  opacity: 0.8;
}

.btn-submit.disabled {
  background: #d0d0d0;
  box-shadow: none;
}

.submit-hint {
  font-size: 12px;
  color: #999999;
  text-align: center;
  display: block;
  margin-top: 12px;
}
</style>
