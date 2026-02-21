<template>
  <view class="image-preview" v-if="imageSrc">
    <!-- Image Display -->
    <view class="preview-container" @click="handlePreview">
      <image
        class="preview-image"
        :src="imageSrc"
        mode="aspectFill"
      />

      <!-- Image Actions Overlay -->
      <view class="actions-overlay" v-if="showActions">
        <!-- Delete Button -->
        <button
          class="btn-action btn-delete"
          @click.stop="handleDelete"
        >
          <view class="btn-icon">✕</view>
          <text class="btn-text">删除</text>
        </button>

        <!-- Reselect Button -->
        <button
          class="btn-action btn-reselect"
          @click.stop="handleReselect"
        >
          <view class="btn-icon">↺</view>
          <text class="btn-text">重选</text>
        </button>
      </view>

      <!-- Preview Hint -->
      <view class="preview-hint" v-if="showPreviewHint">
        <text class="hint-text">点击预览</text>
      </view>
    </view>

    <!-- Image Info -->
    <view class="image-info" v-if="showInfo && imageInfo">
      <text class="info-text">{{ imageInfo.width }} x {{ imageInfo.height }}</text>
      <text class="info-text">{{ formatFileSize(imageInfo.size) }}</text>
    </view>
  </view>

  <!-- Empty State -->
  <view class="empty-state" v-else>
    <view class="empty-placeholder" @click="handleEmptyClick">
      <text class="empty-icon">📷</text>
      <text class="empty-text">{{ emptyText }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'

// Props
interface Props {
  imageSrc?: string // Image source (base64, url, or temp file path)
  showActions?: boolean // Show delete and reselect buttons
  showInfo?: boolean // Show image dimensions and size info
  showPreviewHint?: boolean // Show preview hint overlay
  emptyText?: string // Empty state text
  enablePreview?: boolean // Enable click to preview in full screen
}

const props = withDefaults(defineProps<Props>(), {
  imageSrc: '',
  showActions: true,
  showInfo: false,
  showPreviewHint: true,
  emptyText: '暂无图片',
  enablePreview: true
})

// Emits
interface Emits {
  (e: 'delete'): void
  (e: 'reselect'): void
  (e: 'empty-click'): void
  (e: 'load', info: { width: number; height: number; size: number }): void
}

const emit = defineEmits<Emits>()

// State
const imageInfo = ref<{ width: number; height: number; size: number } | null>(null)

// Methods
function handlePreview() {
  if (!props.imageSrc || !props.enablePreview) {
    return
  }

  uni.previewImage({
    urls: [props.imageSrc],
    current: 0,
    fail: (error) => {
      console.error('Preview failed:', error)
      uni.showToast({
        title: '预览失败',
        icon: 'none'
      })
    }
  })
}

function handleDelete() {
  uni.showModal({
    title: '确认删除',
    content: '确定要删除这张图片吗？',
    success: (res) => {
      if (res.confirm) {
        emit('delete')
      }
    }
  })
}

function handleReselect() {
  emit('reselect')
}

function handleEmptyClick() {
  emit('empty-click')
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`
  } else if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`
  } else {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }
}

function getImageInfo(src: string) {
  uni.getImageInfo({
    src: src,
    success: (res) => {
      const info = {
        width: res.width,
        height: res.height,
        size: 0 // Size not available in getImageInfo
      }

      // Try to get file size if it's a local file
      if (src.startsWith('file://') || !src.startsWith('http')) {
        const filePath = src.startsWith('file://') ? src.substring(7) : src
        uni.getFileInfo({
          filePath: filePath,
          success: (fileInfo) => {
            info.size = fileInfo.size
            imageInfo.value = info
            emit('load', info)
          },
          fail: () => {
            imageInfo.value = info
            emit('load', info)
          }
        })
      } else {
        imageInfo.value = info
        emit('load', info)
      }
    },
    fail: (error) => {
      console.error('Failed to get image info:', error)
      imageInfo.value = null
    }
  })
}

// Watch for imageSrc changes
watch(() => props.imageSrc, (newSrc) => {
  if (newSrc && props.showInfo) {
    getImageInfo(newSrc)
  } else {
    imageInfo.value = null
  }
}, { immediate: true })

// Expose methods
defineExpose({
  preview: handlePreview,
  getImageInfo
})
</script>

<style lang="scss" scoped>
.image-preview {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.preview-container {
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  max-height: 400px;
  border-radius: 12px;
  overflow: hidden;
  background: #000;
}

.preview-image {
  width: 100%;
  height: 100%;
}

.actions-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  gap: 8px;
  padding: 12px;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.7), transparent);
}

.btn-action {
  flex: 1;
  height: 44px;
  border-radius: 22px;
  border: none;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 16px;
  transition: all 0.2s;
}

.btn-action:active {
  transform: scale(0.95);
}

.btn-icon {
  font-size: 18px;
}

.btn-text {
  font-size: 13px;
  font-weight: 500;
}

.btn-delete {
  background: rgba(255, 107, 107, 0.9);
  color: #ffffff;
}

.btn-reselect {
  background: rgba(102, 126, 234, 0.9);
  color: #ffffff;
}

.preview-hint {
  position: absolute;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.5);
  padding: 6px 16px;
  border-radius: 16px;
  backdrop-filter: blur(10px);
}

.hint-text {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.9);
}

.image-info {
  display: flex;
  justify-content: space-between;
  padding: 0 4px;
}

.info-text {
  font-size: 12px;
  color: #999999;
}

.empty-state {
  width: 100%;
  aspect-ratio: 1;
  max-height: 400px;
  border-radius: 12px;
  background: #fafafa;
  border: 2px dashed #d0d0d0;
}

.empty-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.empty-icon {
  font-size: 64px;
  opacity: 0.3;
}

.empty-text {
  font-size: 14px;
  color: #999999;
}
</style>
