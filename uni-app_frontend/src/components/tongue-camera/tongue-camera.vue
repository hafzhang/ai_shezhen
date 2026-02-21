<template>
  <view class="tongue-camera">
    <!-- Camera Preview / Image Selection -->
    <view class="camera-container">
      <!-- Live Camera Preview -->
      <view v-if="showCamera" class="camera-preview">
        <view class="preview-placeholder">
          <text class="placeholder-icon">📷</text>
          <text class="placeholder-text">相机预览</text>
        </view>

        <!-- Photo Guide Frame Overlay -->
        <view class="guide-frame">
          <view class="frame-corner corner-top-left"></view>
          <view class="frame-corner corner-top-right"></view>
          <view class="frame-corner corner-bottom-left"></view>
          <view class="frame-corner corner-bottom-right"></view>
          <view class="frame-label">请将舌头置于框内</view>
        </view>
      </view>

      <!-- Selected Image Preview -->
      <view v-else-if="selectedImagePath" class="image-preview">
        <image
          class="preview-image"
          :src="selectedImagePath"
          mode="aspectFill"
        />
      </view>

      <!-- Empty State -->
      <view v-else class="empty-state">
        <text class="empty-icon">📷</text>
        <text class="empty-text">请拍摄或选择舌部照片</text>
      </view>
    </view>

    <!-- Action Buttons -->
    <view class="action-buttons">
      <button
        v-if="!selectedImagePath"
        class="btn-action btn-camera"
        @click="openCamera"
      >
        <view class="btn-icon">📷</view>
        <text class="btn-text">拍照</text>
      </button>

      <button
        v-if="!selectedImagePath"
        class="btn-action btn-album"
        @click="openAlbum"
      >
        <view class="btn-icon">🖼️</view>
        <text class="btn-text">相册</text>
      </button>

      <button
        v-if="selectedImagePath"
        class="btn-action btn-confirm"
        @click="confirmPhoto"
      >
        <view class="btn-icon">✓</view>
        <text class="btn-text">确认</text>
      </button>

      <button
        v-if="selectedImagePath"
        class="btn-action btn-retake"
        @click="retakePhoto"
      >
        <view class="btn-icon">↺</view>
        <text class="btn-text">重拍</text>
      </button>
    </view>

    <!-- Photo Tips -->
    <view class="photo-tips">
      <text class="tips-title">拍照提示</text>
      <view class="tips-list">
        <text class="tip-item">• 在自然光或明亮灯光下拍摄</text>
        <text class="tip-item">• 舌头自然伸出，不要过度用力</text>
        <text class="tip-item">• 保持舌面平整，尽量舒展</text>
        <text class="tip-item">• 避免有色食物后立即拍摄</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

// Props
interface Props {
  autoConfirm?: boolean // Auto confirm after photo selection
}

const props = withDefaults(defineProps<Props>(), {
  autoConfirm: false
})

// Emits
interface Emits {
  (e: 'photo-confirm', data: { imagePath: string; base64: string }): void
  (e: 'cancel'): void
}

const emit = defineEmits<Emits>()

// State
const showCamera = ref(false)
const selectedImagePath = ref('')
const selectedImageBase64 = ref('')

// Methods
function openCamera() {
  showCamera.value = true

  uni.chooseImage({
    count: 1,
    sizeType: ['compressed'],
    sourceType: ['camera'],
    success: (res) => {
      handleImageSelected(res.tempFilePaths[0])
    },
    fail: (error) => {
      console.error('Camera failed:', error)
      showCamera.value = false
      uni.showToast({
        title: '拍照失败',
        icon: 'none'
      })
    }
  })
}

function openAlbum() {
  uni.chooseImage({
    count: 1,
    sizeType: ['compressed'],
    sourceType: ['album'],
    success: (res) => {
      handleImageSelected(res.tempFilePaths[0])
    },
    fail: (error) => {
      console.error('Album selection failed:', error)
      uni.showToast({
        title: '选择失败',
        icon: 'none'
      })
    }
  })
}

function handleImageSelected(filePath: string) {
  showCamera.value = false
  selectedImagePath.value = filePath

  // Convert to base64
  uni.getFileSystemManager().readFile({
    filePath: filePath,
    encoding: 'base64',
    success: (res) => {
      selectedImageBase64.value = `data:image/jpeg;base64,${res.data}`

      // Auto confirm if enabled
      if (props.autoConfirm) {
        confirmPhoto()
      }
    },
    fail: (error) => {
      console.error('Failed to convert image:', error)
      uni.showToast({
        title: '图片处理失败',
        icon: 'none'
      })
      // Clear selection on error
      selectedImagePath.value = ''
      selectedImageBase64.value = ''
    }
  })
}

function confirmPhoto() {
  if (!selectedImagePath.value || !selectedImageBase64.value) {
    return
  }

  emit('photo-confirm', {
    imagePath: selectedImagePath.value,
    base64: selectedImageBase64.value
  })
}

function retakePhoto() {
  selectedImagePath.value = ''
  selectedImageBase64.value = ''
  showCamera.value = false
}

function reset() {
  selectedImagePath.value = ''
  selectedImageBase64.value = ''
  showCamera.value = false
}

// Expose methods for parent component
defineExpose({
  reset,
  openCamera,
  openAlbum
})
</script>

<style lang="scss" scoped>
.tongue-camera {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 20px;
  background: #f5f5f5;
}

.camera-container {
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  max-height: 400px;
  border-radius: 12px;
  overflow: hidden;
  background: #000;
}

.camera-preview,
.image-preview,
.empty-state {
  width: 100%;
  height: 100%;
  position: relative;
}

.camera-preview {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
}

.preview-placeholder {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.placeholder-icon {
  font-size: 64px;
  opacity: 0.6;
}

.placeholder-text {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.8);
}

// Photo Guide Frame
.guide-frame {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 70%;
  aspect-ratio: 1;
}

.frame-corner {
  position: absolute;
  width: 40px;
  height: 40px;
  border: 3px solid rgba(102, 126, 234, 0.8);
  box-shadow: 0 0 10px rgba(102, 126, 234, 0.4);
}

.corner-top-left {
  top: 0;
  left: 0;
  border-right: none;
  border-bottom: none;
  border-radius: 8px 0 0 0;
}

.corner-top-right {
  top: 0;
  right: 0;
  border-left: none;
  border-bottom: none;
  border-radius: 0 8px 0 0;
}

.corner-bottom-left {
  bottom: 0;
  left: 0;
  border-right: none;
  border-top: none;
  border-radius: 0 0 0 8px;
}

.corner-bottom-right {
  bottom: 0;
  right: 0;
  border-left: none;
  border-top: none;
  border-radius: 0 0 8px 0;
}

.frame-label {
  position: absolute;
  bottom: -30px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 14px;
  color: rgba(255, 255, 255, 0.9);
  white-space: nowrap;
  background: rgba(0, 0, 0, 0.5);
  padding: 4px 12px;
  border-radius: 12px;
}

// Image Preview
.preview-image {
  width: 100%;
  height: 100%;
}

// Empty State
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: #fafafa;
  border: 2px dashed #d0d0d0;
}

.empty-icon {
  font-size: 64px;
  opacity: 0.4;
}

.empty-text {
  font-size: 14px;
  color: #999999;
}

// Action Buttons
.action-buttons {
  display: flex;
  gap: 12px;
}

.btn-action {
  flex: 1;
  height: 56px;
  border-radius: 12px;
  border: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 0;
  transition: all 0.2s;
}

.btn-action:active {
  transform: scale(0.98);
}

.btn-icon {
  font-size: 24px;
}

.btn-text {
  font-size: 12px;
}

.btn-camera,
.btn-confirm {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #ffffff;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.btn-album {
  background: rgba(102, 126, 234, 0.1);
  border: 1px solid #667eea;
  color: #667eea;
}

.btn-retake {
  background: rgba(255, 107, 107, 0.1);
  border: 1px solid #ff6b6b;
  color: #ff6b6b;
}

// Photo Tips
.photo-tips {
  background: #ffffff;
  border-radius: 12px;
  padding: 16px;
}

.tips-title {
  font-size: 14px;
  font-weight: 500;
  color: #667eea;
  display: block;
  margin-bottom: 12px;
}

.tips-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tip-item {
  font-size: 12px;
  color: #666666;
  line-height: 1.6;
}
</style>
