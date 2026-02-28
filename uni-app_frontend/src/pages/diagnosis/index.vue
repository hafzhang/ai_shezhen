<template>
  <div class="container">
    <!-- Custom Header -->
    <div class="header">
      <div class="header-left" @click="goBack">
        <span class="icon-back">←</span>
      </div>
      <span class="header-title">舌诊诊断</span>
      <div class="header-right"></div>
    </div>

    <div class="content">
      <!-- Image Upload Section -->
      <div class="upload-section">
        <span class="section-title">上传舌部照片</span>
        <span class="section-desc">请拍摄清晰的舌部照片，确保光线充足</span>

        <!-- Image Upload Area -->
        <div class="upload-area" v-if="!selectedImage" @click="showUploadOptions = true">
          <div class="upload-icon">📷</div>
          <span class="upload-text">点击拍摄或选择照片</span>
          <span class="upload-hint">支持 JPG、PNG 格式，建议不超过 5MB</span>
        </div>

        <!-- Image Preview -->
        <div class="image-preview" v-else>
          <img class="preview-image" :src="selectedImage" alt="舌部照片" />
          <div class="preview-overlay">
            <button class="btn-remove" @click="removeImage">删除</button>
            <button class="btn-reselect" @click="showUploadOptions = true">重新选择</button>
          </div>
          <div class="compression-info" v-if="compressionInfo">
            <span class="info-text">已压缩: {{ compressionInfo.originalSize }} → {{ compressionInfo.compressedSize }} ({{ compressionInfo.ratio }})</span>
          </div>
        </div>

        <!-- Hidden file inputs -->
        <input
          ref="fileInputCamera"
          type="file"
          accept="image/*"
          capture="environment"
          style="display: none"
          @change="handleFileSelect"
        />
        <input
          ref="fileInputAlbum"
          type="file"
          accept="image/*"
          style="display: none"
          @change="handleFileSelect"
        />

        <!-- Upload Options Modal -->
        <div class="modal-overlay" v-if="showUploadOptions" @click="showUploadOptions = false">
          <div class="upload-options-modal" @click.stop>
            <div class="modal-header">
              <span class="modal-title">选择照片</span>
              <span class="modal-close" @click="showUploadOptions = false">×</span>
            </div>
            <div class="upload-actions">
              <button class="upload-option" @click="selectFromCamera">
                <span class="option-icon">📷</span>
                <span class="option-text">拍照</span>
              </button>
              <button class="upload-option" @click="selectFromAlbum">
                <span class="option-icon">🖼️</span>
                <span class="option-text">从相册选择</span>
              </button>
            </div>
            <button class="btn-cancel" @click="showUploadOptions = false">取消</button>
          </div>
        </div>

        <!-- Photo Tips -->
        <div class="photo-tips">
          <span class="tips-title">拍照提示：</span>
          <div class="tips-list">
            <span class="tip-item">• 请在自然光或明亮灯光下拍摄</span>
            <span class="tip-item">• 舌头自然伸出，不要过度用力</span>
            <span class="tip-item">• 保持舌面平整，尽量舒展</span>
            <span class="tip-item">• 避免有色食物（如咖啡、咖喱）后立即拍摄</span>
          </div>
        </div>
      </div>

      <!-- User Info Form -->
      <div class="form-section">
        <span class="section-title">基本信息（可选）</span>
        <span class="section-desc">提供信息有助于更准确的诊断分析</span>

        <div class="form-group">
          <span class="form-label">年龄</span>
          <input
            class="form-input"
            type="number"
            v-model="formData.age"
            placeholder="请输入年龄"
            maxlength="3"
          />
        </div>

        <div class="form-group">
          <span class="form-label">性别</span>
          <div class="gender-options">
            <div
              class="gender-option"
              :class="{ active: formData.gender === 'male' }"
              @click="selectGender('male')"
            >
              <span class="gender-icon">♂</span>
              <span class="gender-text">男</span>
            </div>
            <div
              class="gender-option"
              :class="{ active: formData.gender === 'female' }"
              @click="selectGender('female')"
            >
              <span class="gender-icon">♀</span>
              <span class="gender-text">女</span>
            </div>
          </div>
        </div>

        <div class="form-group">
          <span class="form-label">主要症状</span>
          <textarea
            class="form-textarea"
            v-model="formData.chief_complaint"
            placeholder="请描述您的主要症状或不适（可选）"
            maxlength="200"
          />
          <span class="char-count">{{ formData.chief_complaint.length }}/200</span>
        </div>
      </div>

      <!-- Submit Button -->
      <div class="submit-section">
        <button
          class="btn-submit"
          :class="{ disabled: !canSubmit || isDiagnosing }"
          :disabled="!canSubmit || isDiagnosing"
          @click="submitDiagnosis"
        >
          <span v-if="!isDiagnosing">开始诊断</span>
          <span v-else>诊断中...</span>
        </button>
        <span class="submit-hint">诊断过程可能需要几秒钟，请耐心等待</span>
      </div>
    </div>

    <!-- Loading overlay -->
    <div class="loading-overlay" v-if="isLoading">
      <div class="loading-content">
        <div class="loading-spinner"></div>
        <span class="loading-text">{{ loadingText }}</span>
      </div>
    </div>

    <!-- Toast message -->
    <div class="toast" :class="{ show: showToast }" v-if="toastMessage">
      <span class="toast-text">{{ toastMessage }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useDiagnosisStore } from '@/store'

const router = useRouter()
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

// Selected image (base64)
const selectedImage = ref<string>('')
const originalFileName = ref<string>('')

// Compression info
const compressionInfo = ref<{
  originalSize: string
  compressedSize: string
  ratio: string
} | null>(null)

// File input refs
const fileInputCamera = ref<HTMLInputElement | null>(null)
const fileInputAlbum = ref<HTMLInputElement | null>(null)

// UI state
const showUploadOptions = ref(false)
const isLoading = ref(false)
const loadingText = ref('处理中...')
const showToast = ref(false)
const toastMessage = ref('')

// Computed
const canSubmit = computed(() => {
  return selectedImage.value.length > 0
})

const isDiagnosing = computed(() => {
  return diagnosisStore.isDiagnosing
})

// Actions
function goBack() {
  router.back()
}

function selectGender(gender: 'male' | 'female') {
  if (formData.value.gender === gender) {
    formData.value.gender = null
  } else {
    formData.value.gender = gender
  }
}

// Toast message
function showToastMsg(message: string, duration = 2000) {
  toastMessage.value = message
  showToast.value = true
  setTimeout(() => {
    showToast.value = false
  }, duration)
}

// Show loading
function showLoading(text = '处理中...') {
  loadingText.value = text
  isLoading.value = true
}

// Hide loading
function hideLoading() {
  isLoading.value = false
}

// Camera functionality
function selectFromCamera() {
  showUploadOptions.value = false
  fileInputCamera.value?.click()
}

function selectFromAlbum() {
  showUploadOptions.value = false
  fileInputAlbum.value?.click()
}

async function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]

  if (!file) return

  // Validate file type
  if (!file.type.startsWith('image/')) {
    showToastMsg('请选择图片文件')
    return
  }

  // Validate file size (max 10MB)
  if (file.size > 10 * 1024 * 1024) {
    showToastMsg('图片大小不能超过 10MB')
    return
  }

  originalFileName.value = file.name

  // Show loading
  showLoading('处理图片...')

  try {
    // Compress and convert to base64
    const result = await compressImage(file)

    selectedImage.value = result.dataUrl

    compressionInfo.value = {
      originalSize: formatFileSize(file.size),
      compressedSize: formatFileSize(result.compressedSize),
      ratio: `${Math.round(result.ratio * 100)}%`
    }

    console.log('Image processed:', {
      original: formatFileSize(file.size),
      compressed: formatFileSize(result.compressedSize),
      ratio: compressionInfo.value.ratio,
      dimensions: `${result.width}x${result.height}`
    })

    showToastMsg(`已压缩 (${compressionInfo.value.ratio})`)
  } catch (error) {
    console.error('Image processing failed:', error)
    showToastMsg('图片处理失败，请重试')
  } finally {
    hideLoading()
    // Clear input
    target.value = ''
  }
}

// Image compression using Canvas
function compressImage(file: File): Promise<{
  dataUrl: string
  compressedSize: number
  originalSize: number
  ratio: number
  width: number
  height: number
}> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()

    reader.onload = (e) => {
      const img = new Image()

      img.onload = () => {
        // Calculate dimensions (max 1920x1920)
        const maxWidth = 1920
        const maxHeight = 1920
        let width = img.width
        let height = img.height

        if (width > height) {
          if (width > maxWidth) {
            height = (height * maxWidth) / width
            width = maxWidth
          }
        } else {
          if (height > maxHeight) {
            width = (width * maxHeight) / height
            height = maxHeight
          }
        }

        // Create canvas
        const canvas = document.createElement('canvas')
        canvas.width = width
        canvas.height = height

        const ctx = canvas.getContext('2d')
        if (!ctx) {
          reject(new Error('Failed to get canvas context'))
          return
        }

        // Draw image
        ctx.fillStyle = '#ffffff'
        ctx.fillRect(0, 0, width, height)
        ctx.drawImage(img, 0, 0, width, height)

        // Compress to JPEG with quality 0.8
        const dataUrl = canvas.toDataURL('image/jpeg', 0.8)

        // Calculate compressed size
        const compressedSize = Math.round((dataUrl.length - 'data:image/jpeg;base64,'.length) * 3 / 4)
        const originalSize = file.size

        resolve({
          dataUrl,
          compressedSize,
          originalSize,
          ratio: compressedSize / originalSize,
          width: Math.round(width),
          height: Math.round(height)
        })
      }

      img.onerror = () => {
        reject(new Error('Failed to load image'))
      }

      img.src = e.target?.result as string
    }

    reader.onerror = () => {
      reject(new Error('Failed to read file'))
    }

    reader.readAsDataURL(file)
  })
}

// Format file size
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function removeImage() {
  selectedImage.value = ''
  compressionInfo.value = null
  originalFileName.value = ''
}

async function submitDiagnosis() {
  if (!canSubmit.value || isDiagnosing.value) {
    return
  }

  // Validate age if provided
  if (formData.value.age) {
    const ageNum = parseInt(formData.value.age)
    if (isNaN(ageNum) || ageNum < 0 || ageNum > 150) {
      showToastMsg('请输入有效的年龄')
      return
    }
  }

  showLoading('诊断中...')

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

    showToastMsg('诊断完成！')

    // Navigate to result page
    setTimeout(() => {
      router.push(`/result?id=${result.id}`)
    }, 500)
  } catch (error: any) {
    console.error('Diagnosis failed:', error)
    showToastMsg(error?.message || '诊断失败，请重试')
  } finally {
    hideLoading()
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
  padding: 40px 15px 15px;
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
  cursor: pointer;
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

.upload-area {
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  border: 2px dashed #dee2e6;
  border-radius: 12px;
  padding: 40px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s;
}

.upload-area:hover {
  border-color: #667eea;
  background: linear-gradient(135deg, #f0f4ff 0%, #e0e9ff 100%);
}

.upload-icon {
  font-size: 50px;
  margin-bottom: 15px;
}

.upload-text {
  font-size: 16px;
  font-weight: 500;
  color: #333333;
  margin-bottom: 8px;
}

.upload-hint {
  font-size: 12px;
  color: #999999;
}

.image-preview {
  position: relative;
  border-radius: 12px;
  overflow: hidden;
}

.preview-image {
  width: 100%;
  height: auto;
  max-height: 400px;
  object-fit: contain;
  display: block;
}

.preview-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.7));
  padding: 15px;
  display: flex;
  gap: 10px;
}

.btn-remove,
.btn-reselect {
  flex: 1;
  padding: 10px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  border: none;
  cursor: pointer;
}

.btn-remove {
  background: rgba(255, 77, 79, 0.9);
  color: #ffffff;
}

.btn-reselect {
  background: rgba(102, 126, 234, 0.9);
  color: #ffffff;
}

.compression-info {
  padding: 8px 15px;
  background: rgba(0, 0, 0, 0.5);
}

.info-text {
  font-size: 12px;
  color: #ffffff;
}

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

.upload-options-modal {
  background: #ffffff;
  border-radius: 20px;
  padding: 20px;
  width: 280px;
  max-width: 90%;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.modal-title {
  font-size: 18px;
  font-weight: 500;
  color: #333333;
}

.modal-close {
  font-size: 28px;
  color: #999999;
  line-height: 1;
  cursor: pointer;
}

.upload-actions {
  display: flex;
  flex-direction: column;
  gap: 15px;
  margin-bottom: 15px;
}

.upload-option {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 15px;
  padding: 15px;
  border-radius: 12px;
  background: #f8f9fa;
  border: 1px solid #e5e5e5;
  font-size: 16px;
  font-weight: 500;
  color: #333333;
  cursor: pointer;
  transition: all 0.2s;
}

.upload-option:hover {
  background: #e9ecef;
  border-color: #667eea;
}

.option-icon {
  font-size: 24px;
}

.btn-cancel {
  width: 100%;
  padding: 15px;
  border-radius: 12px;
  background: #f0f0f0;
  border: none;
  font-size: 16px;
  color: #666666;
  cursor: pointer;
}

.photo-tips {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 12px;
  margin-top: 15px;
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
  box-sizing: border-box;
}

.form-input:focus {
  outline: none;
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
  cursor: pointer;
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
  box-sizing: border-box;
  font-family: inherit;
}

.form-textarea:focus {
  outline: none;
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
  cursor: pointer;
  transition: all 0.2s;
}

.btn-submit:active:not(:disabled) {
  opacity: 0.8;
}

.btn-submit:disabled {
  background: #d0d0d0;
  box-shadow: none;
  cursor: not-allowed;
}

.submit-hint {
  font-size: 12px;
  color: #999999;
  text-align: center;
  display: block;
  margin-top: 12px;
}

// Loading overlay
.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

.loading-content {
  background: #ffffff;
  border-radius: 12px;
  padding: 30px 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 15px;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #f0f0f0;
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
  color: #666666;
}

// Toast
.toast {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: rgba(0, 0, 0, 0.8);
  color: #ffffff;
  padding: 12px 24px;
  border-radius: 8px;
  font-size: 14px;
  z-index: 3000;
  opacity: 0;
  transition: opacity 0.3s;
}

.toast.show {
  opacity: 1;
}

/* Dark mode styles */
:global(.dark-mode) .container {
  background: #1a1a1a;
}

:global(.dark-mode) .header {
  background: #2a2a2a;
  border-bottom-color: #3a3a3a;
}

:global(.dark-mode) .icon-back,
:global(.dark-mode) .header-title {
  color: #e0e0e0;
}

:global(.dark-mode) .upload-section,
:global(.dark-mode) .form-section {
  background: #2a2a2a;
}

:global(.dark-mode) .section-title {
  color: #e0e0e0;
}

:global(.dark-mode) .upload-area {
  background: linear-gradient(135deg, #2a2a2a 0%, #3a3a3a 100%);
  border-color: #4a4a4a;
}

:global(.dark-mode) .upload-area:hover {
  border-color: #667eea;
  background: linear-gradient(135deg, #1a2540 0%, #2a3a50 100%);
}

:global(.dark-mode) .upload-text {
  color: #e0e0e0;
}

:global(.dark-mode) .upload-options-modal {
  background: #2a2a2a;
}

:global(.dark-mode) .modal-title {
  color: #e0e0e0;
}

:global(.dark-mode) .upload-option {
  background: #3a3a3a;
  border-color: #4a4a4a;
  color: #e0e0e0;
}

:global(.dark-mode) .upload-option:hover {
  background: #4a4a4a;
}

:global(.dark-mode) .btn-cancel {
  background: #3a3a3a;
  color: #aaaaaa;
}

:global(.dark-mode) .form-label {
  color: #e0e0e0;
}

:global(.dark-mode) .form-input,
:global(.dark-mode) .form-textarea {
  background: #3a3a3a;
  border-color: #4a4a4a;
  color: #e0e0e0;
}

:global(.dark-mode) .form-input:focus,
:global(.dark-mode) .form-textarea:focus {
  border-color: #667eea;
  background: #4a4a4a;
}

:global(.dark-mode) .gender-option {
  background: #3a3a3a;
  border-color: #4a4a4a;
}

:global(.dark-mode) .gender-text {
  color: #aaaaaa;
}

:global(.dark-mode) .loading-content {
  background: #2a2a2a;
}

:global(.dark-mode) .loading-text {
  color: #aaaaaa;
}
</style>
