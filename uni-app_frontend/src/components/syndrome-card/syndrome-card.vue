<template>
  <view
    class="syndrome-card"
    :class="{
      'syndrome-card--primary': isPrimary,
      'syndrome-card--compact': compact,
      'syndrome-card--clickable': clickable
    }"
    @click="handleClick"
  >
    <!-- Card Header -->
    <view class="syndrome-card__header">
      <view class="syndrome-card__name-section">
        <text v-if="showIcon" class="syndrome-card__icon">{{ icon }}</text>
        <text class="syndrome-card__name">{{ syndrome.name }}</text>
      </view>

      <!-- Confidence Badge -->
      <view
        class="syndrome-card__confidence"
        :class="`syndrome-card__confidence--${confidenceLevel}`"
      >
        <text class="syndrome-card__confidence-value">{{ formattedConfidence }}</text>
      </view>
    </view>

    <!-- Card Description -->
    <view v-if="!compact && syndrome.description" class="syndrome-card__description">
      <text class="syndrome-card__desc-text">{{ syndrome.description }}</text>
    </view>

    <!-- TCM Theory Section -->
    <view
      v-if="!compact && showTheory && syndrome.tcm_theory"
      class="syndrome-card__theory"
    >
      <view class="syndrome-card__theory-header">
        <text class="syndrome-card__theory-label">中医理论</text>
      </view>
      <text class="syndrome-card__theory-text">{{ syndrome.tcm_theory }}</text>
    </view>

    <!-- Risk Indicator (if applicable) -->
    <view v-if="showRisk && isHighRisk" class="syndrome-card__risk">
      <text class="syndrome-card__risk-icon">⚠️</text>
      <text class="syndrome-card__risk-text">需关注</text>
    </view>

    <!-- Expand Indicator (for clickable cards) -->
    <view v-if="clickable" class="syndrome-card__expand">
      <text class="syndrome-card__expand-icon">›</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { SyndromeAnalysis } from '@/store/modules/diagnosis'

// Props
interface Props {
  syndrome: SyndromeAnalysis          // Syndrome data
  compact?: boolean                    // Compact mode (hide description and theory)
  showIcon?: boolean                   // Show syndrome icon
  showTheory?: boolean                 // Show TCM theory section
  showRisk?: boolean                   // Show risk indicator for high confidence syndromes
  clickable?: boolean                  // Make card clickable
  primaryThreshold?: number            // Confidence threshold for primary card styling (default: 0.6)
  icon?: string                        // Custom icon emoji
}

const props = withDefaults(defineProps<Props>(), {
  compact: false,
  showIcon: true,
  showTheory: true,
  showRisk: false,
  clickable: false,
  primaryThreshold: 0.6,
  icon: '🩺'
})

// Emits
const emit = defineEmits<{
  click: [syndrome: SyndromeAnalysis]
}>()

// Computed
const isPrimary = computed(() => {
  return props.syndrome.confidence >= props.primaryThreshold
})

const confidenceLevel = computed(() => {
  const conf = props.syndrome.confidence
  if (conf >= 0.7) return 'high'
  if (conf >= 0.5) return 'medium'
  return 'low'
})

const formattedConfidence = computed(() => {
  return `${Math.round(props.syndrome.confidence * 100)}%`
})

const isHighRisk = computed(() => {
  return props.syndrome.confidence >= 0.7
})

// Methods
function handleClick() {
  if (props.clickable) {
    emit('click', props.syndrome)
  }
}
</script>

<style lang="scss" scoped>
.syndrome-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 16px;
  background: #f8f9fa;
  border-radius: 10px;
  border-left: 3px solid #667eea;
  transition: all 0.2s ease;
}

.syndrome-card--primary {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
  border-left-color: #764ba2;
}

.syndrome-card--compact {
  padding: 10px 12px;
  gap: 6px;
}

.syndrome-card--clickable {
  cursor: pointer;
}

.syndrome-card--clickable:active {
  transform: scale(0.98);
  opacity: 0.9;
}

// Header
.syndrome-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.syndrome-card__name-section {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.syndrome-card__icon {
  font-size: 18px;
  flex-shrink: 0;
}

.syndrome-card__name {
  font-size: 15px;
  font-weight: 500;
  color: #333333;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.syndrome-card--primary .syndrome-card__name {
  color: #764ba2;
  font-weight: 600;
}

// Confidence Badge
.syndrome-card__confidence {
  flex-shrink: 0;
  padding: 4px 12px;
  border-radius: 12px;
  background: #667eea;
}

.syndrome-card__confidence--high {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}

.syndrome-card__confidence--medium {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.syndrome-card__confidence--low {
  background: linear-gradient(135deg, #a8a8a8 0%, #8a8a8a 100%);
}

.syndrome-card__confidence-value {
  font-size: 12px;
  font-weight: 500;
  color: #ffffff;
}

// Description
.syndrome-card__description {
  display: flex;
  flex-direction: column;
}

.syndrome-card__desc-text {
  font-size: 13px;
  color: #666666;
  line-height: 1.6;
}

// Theory Section
.syndrome-card__theory {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-top: 8px;
  border-top: 1px solid #e5e5e5;
}

.syndrome-card__theory-header {
  display: flex;
  align-items: center;
}

.syndrome-card__theory-label {
  font-size: 12px;
  font-weight: 500;
  color: #667eea;
}

.syndrome-card__theory-text {
  font-size: 12px;
  color: #999999;
  line-height: 1.6;
}

// Risk Indicator
.syndrome-card__risk {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: rgba(255, 68, 68, 0.1);
  border-radius: 6px;
  align-self: flex-start;
}

.syndrome-card__risk-icon {
  font-size: 14px;
}

.syndrome-card__risk-text {
  font-size: 12px;
  color: #ff4444;
  font-weight: 500;
}

// Expand Indicator
.syndrome-card__expand {
  position: absolute;
  right: 12px;
  bottom: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: rgba(102, 126, 234, 0.1);
  border-radius: 50%;
}

.syndrome-card__expand-icon {
  font-size: 16px;
  color: #667eea;
}

// Compact mode adjustments
.syndrome-card--compact .syndrome-card__expand {
  top: 50%;
  bottom: auto;
  transform: translateY(-50%);
}
</style>
