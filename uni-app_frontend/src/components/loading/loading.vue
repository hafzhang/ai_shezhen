<template>
  <view v-if="visible" class="global-loading" @touchmove.stop.prevent>
    <!-- Background Mask -->
    <view class="loading-mask"></view>

    <!-- Loading Content -->
    <view class="loading-content">
      <!-- Spinner Animation -->
      <view class="spinner-container">
        <view class="spinner-ring" :style="{ borderLeftColor: themeColor }"></view>
        <view class="spinner-ring-inner" :style="{ borderRightColor: themeColor }"></view>
      </view>

      <!-- Loading Text -->
      <text v-if="text" class="loading-text">{{ text }}</text>

      <!-- Optional Progress Indicator -->
      <view v-if="showProgress && progress >= 0" class="progress-container">
        <view class="progress-bar-bg">
          <view
            class="progress-bar-fill"
            :style="{ width: `${progress}%`, backgroundColor: themeColor }"
          ></view>
        </view>
        <text class="progress-text">{{ progress }}%</text>
      </view>

      <!-- Optional Cancel Button -->
      <view v-if="cancelable" class="cancel-btn" @click="handleCancel">
        <text class="cancel-text">取消</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

// Props
interface Props {
  visible?: boolean
  text?: string
  themeColor?: string
  showProgress?: boolean
  progress?: number
  cancelable?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  text: '加载中...',
  themeColor: '#667eea',
  showProgress: false,
  progress: -1,
  cancelable: false
})

// Emits
interface Emits {
  (e: 'update:visible', value: boolean): void
  (e: 'cancel'): void
}

const emit = defineEmits<Emits>()

// Methods
function handleCancel() {
  emit('update:visible', false)
  emit('cancel')
}

// Prevent body scroll when loading is visible
watch(
  () => props.visible,
  (newValue) => {
    if (newValue) {
      // Prevent scroll on page
      document.body.style.overflow = 'hidden'
    } else {
      // Restore scroll
      document.body.style.overflow = ''
    }
  },
  { immediate: true }
)
</script>

<style lang="scss" scoped>
.global-loading {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-mask {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(2px);
}

.loading-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 24px;
  padding: 40px 32px;
  background: #ffffff;
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
  min-width: 200px;
  max-width: 80%;
}

// Spinner Animation
.spinner-container {
  position: relative;
  width: 60px;
  height: 60px;
}

.spinner-ring {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border: 4px solid rgba(102, 126, 234, 0.2);
  border-left-color: #667eea;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.spinner-ring-inner {
  position: absolute;
  top: 12px;
  left: 12px;
  width: calc(100% - 24px);
  height: calc(100% - 24px);
  border: 3px solid rgba(102, 126, 234, 0.15);
  border-right-color: #667eea;
  border-radius: 50%;
  animation: spin-reverse 0.6s linear infinite;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

@keyframes spin-reverse {
  0% {
    transform: rotate(360deg);
  }
  100% {
    transform: rotate(0deg);
  }
}

// Loading Text
.loading-text {
  font-size: 16px;
  font-weight: 500;
  color: #333333;
  text-align: center;
  line-height: 1.5;
}

// Progress Bar
.progress-container {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.progress-bar-bg {
  width: 100%;
  height: 6px;
  background: #f0f0f0;
  border-radius: 3px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: #667eea;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 12px;
  color: #999999;
  text-align: center;
}

// Cancel Button
.cancel-btn {
  padding: 10px 24px;
  background: rgba(102, 126, 234, 0.1);
  border-radius: 8px;
  transition: background 0.2s;
}

.cancel-btn:active {
  background: rgba(102, 126, 234, 0.2);
}

.cancel-text {
  font-size: 14px;
  color: #667eea;
  font-weight: 500;
}

// Dark mode support
@media (prefers-color-scheme: dark) {
  .loading-content {
    background: #2a2a2a;
  }

  .loading-text {
    color: #e0e0e0;
  }

  .progress-bar-bg {
    background: #3a3a3a;
  }

  .progress-text {
    color: #999999;
  }
}
</style>
