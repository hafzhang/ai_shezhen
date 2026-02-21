<template>
  <view v-if="visible" class="global-toast" :class="[`toast-${type}`, `toast-${position}`]">
    <!-- Icon -->
    <view v-if="showIcon" class="toast-icon">
      <!-- Success Icon -->
      <view v-if="type === 'success'" class="icon-success">
        <view class="success-circle"></view>
        <view class="success-check">
          <view class="check-line check-line-1"></view>
          <view class="check-line check-line-2"></view>
        </view>
      </view>
      <!-- Error Icon -->
      <view v-else-if="type === 'error'" class="icon-error">
        <view class="error-circle"></view>
        <view class="error-cross">
          <view class="cross-line cross-line-1"></view>
          <view class="cross-line cross-line-2"></view>
        </view>
      </view>
      <!-- Warning Icon -->
      <view v-else-if="type === 'warning'" class="icon-warning">
        <view class="warning-triangle"></view>
        <view class="warning-exclamation"></view>
      </view>
      <!-- Info Icon -->
      <view v-else-if="type === 'info'" class="icon-info">
        <view class="info-circle"></view>
        <view class="info-dot"></view>
      </view>
      <!-- Loading Icon -->
      <view v-else-if="type === 'loading'" class="icon-loading">
        <view class="loading-spinner"></view>
      </view>
    </view>

    <!-- Message -->
    <text class="toast-message">{{ message }}</text>
  </view>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'

// Props
interface Props {
  visible?: boolean
  message?: string
  type?: 'success' | 'error' | 'warning' | 'info' | 'loading'
  duration?: number
  position?: 'top' | 'center' | 'bottom'
  showIcon?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  message: '',
  type: 'info',
  duration: 3000,
  position: 'center',
  showIcon: true
})

// Emits
interface Emits {
  (e: 'update:visible', value: boolean): void
  (e: 'close'): void
}

const emit = defineEmits<Emits>()

// Auto dismiss timer
let timer: ReturnType<typeof setTimeout> | null = null

// Clear timer on component unmount
function clearTimer() {
  if (timer) {
    clearTimeout(timer)
    timer = null
  }
}

// Watch visibility changes for auto-dismiss
watch(
  () => props.visible,
  (newValue) => {
    clearTimer()
    if (newValue && props.duration > 0 && props.type !== 'loading') {
      timer = setTimeout(() => {
        emit('update:visible', false)
        emit('close')
      }, props.duration)
    }
  },
  { immediate: true }
)

// Cleanup on unmount
onMounted(() => {
  return () => {
    clearTimer()
  }
})
</script>

<style lang="scss" scoped>
.global-toast {
  position: fixed;
  z-index: 10000;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 16px 20px;
  background: rgba(0, 0, 0, 0.85);
  backdrop-filter: blur(8px);
  border-radius: 12px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
  max-width: 80%;
  min-width: 120px;
  animation: toast-fade-in 0.3s ease-out;

  &.toast-top {
    top: 80px;
    left: 50%;
    transform: translateX(-50%);
  }

  &.toast-center {
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
  }

  &.toast-bottom {
    bottom: 80px;
    left: 50%;
    transform: translateX(-50%);
  }
}

@keyframes toast-fade-in {
  0% {
    opacity: 0;
    transform: translate(-50%, -20px) scale(0.9);
  }
  100% {
    opacity: 1;
    transform: translate(-50%, 0) scale(1);
  }
}

.toast-center@keyframes toast-fade-in {
  0% {
    opacity: 0;
    transform: translate(-50%, -50%) scale(0.9);
  }
  100% {
    opacity: 1;
    transform: translate(-50%, -50%) scale(1);
  }
}

.toast-bottom@keyframes toast-fade-in {
  0% {
    opacity: 0;
    transform: translate(-50%, 20px) scale(0.9);
  }
  100% {
    opacity: 1;
    transform: translate(-50%, 0) scale(1);
  }
}

// Toast Icon
.toast-icon {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  position: relative;
}

// Success Icon
.icon-success {
  width: 100%;
  height: 100%;
  position: relative;
}

.success-circle {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border: 2px solid #52c41a;
  border-radius: 50%;
}

.success-check {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 12px;
  height: 12px;
}

.check-line {
  position: absolute;
  background: #52c41a;
  border-radius: 1px;
}

.check-line-1 {
  width: 2px;
  height: 7px;
  top: 3px;
  left: 2px;
  transform: rotate(45deg);
}

.check-line-2 {
  width: 2px;
  height: 12px;
  top: 0px;
  left: 5px;
  transform: rotate(-45deg);
}

// Error Icon
.icon-error {
  width: 100%;
  height: 100%;
  position: relative;
}

.error-circle {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border: 2px solid #ff4d4f;
  border-radius: 50%;
}

.error-cross {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 12px;
  height: 12px;
}

.cross-line {
  position: absolute;
  background: #ff4d4f;
  border-radius: 1px;
  width: 2px;
  height: 12px;
  top: 0;
  left: 5px;
}

.cross-line-1 {
  transform: rotate(45deg);
}

.cross-line-2 {
  transform: rotate(-45deg);
}

// Warning Icon
.icon-warning {
  width: 100%;
  height: 100%;
  position: relative;
}

.warning-triangle {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border: 2px solid #faad14;
  border-radius: 2px;
  clip-path: polygon(50% 0%, 0% 100%, 100% 100%);
}

.warning-exclamation {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 2px;
  height: 10px;
  background: #faad14;
  border-radius: 1px;
}

.warning-exclamation::after {
  content: '';
  position: absolute;
  bottom: -4px;
  left: 50%;
  transform: translateX(-50%);
  width: 2px;
  height: 2px;
  background: #faad14;
  border-radius: 50%;
}

// Info Icon
.icon-info {
  width: 100%;
  height: 100%;
  position: relative;
}

.info-circle {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border: 2px solid #1890ff;
  border-radius: 50%;
}

.info-dot {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 4px;
  height: 4px;
  background: #1890ff;
  border-radius: 50%;
}

// Loading Icon
.icon-loading {
  width: 100%;
  height: 100%;
  position: relative;
}

.loading-spinner {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: toast-spin 0.8s linear infinite;
}

@keyframes toast-spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

// Toast Message
.toast-message {
  font-size: 15px;
  font-weight: 400;
  color: #ffffff;
  text-align: center;
  line-height: 1.5;
  word-wrap: break-word;
}

// Type-specific styles
.toast-success .toast-message {
  color: #52c41a;
}

.toast-error .toast-message {
  color: #ff4d4f;
}

.toast-warning .toast-message {
  color: #faad14;
}

.toast-info .toast-message {
  color: #1890ff;
}

.toast-loading .toast-message {
  color: #ffffff;
}

// Dark mode support
@media (prefers-color-scheme: dark) {
  .global-toast {
    background: rgba(42, 42, 42, 0.95);
  }

  .toast-message {
    color: #e0e0e0;
  }
}
</style>
