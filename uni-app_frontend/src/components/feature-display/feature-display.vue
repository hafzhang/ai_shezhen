<template>
  <view class="feature-display">
    <!-- Feature Items Grid -->
    <view class="features-grid">
      <!-- Tongue Color -->
      <view class="feature-item" v-if="features.tongue_color">
        <view class="feature-header">
          <text class="feature-icon">👅</text>
          <text class="feature-label">舌色</text>
        </view>
        <view class="feature-values">
          <view
            v-for="(value, key) in features.tongue_color"
            :key="`tongue_color-${key}`"
            class="feature-value"
            :class="{ active: value > threshold }"
          >
            <text class="value-name">{{ key }}</text>
            <view class="value-bar">
              <view
                class="bar-fill"
                :style="getBarStyle(value)"
              ></view>
            </view>
            <text class="value-percent">{{ formatPercent(value) }}</text>
          </view>
        </view>
      </view>

      <!-- Tongue Shape -->
      <view class="feature-item" v-if="features.tongue_shape">
        <view class="feature-header">
          <text class="feature-icon">🔷</text>
          <text class="feature-label">舌形</text>
        </view>
        <view class="feature-values">
          <view
            v-for="(value, key) in features.tongue_shape"
            :key="`tongue_shape-${key}`"
            class="feature-value"
            :class="{ active: value > threshold }"
          >
            <text class="value-name">{{ key }}</text>
            <view class="value-bar">
              <view
                class="bar-fill"
                :style="getBarStyle(value)"
              ></view>
            </view>
            <text class="value-percent">{{ formatPercent(value) }}</text>
          </view>
        </view>
      </view>

      <!-- Coating Color -->
      <view class="feature-item" v-if="features.coating_color">
        <view class="feature-header">
          <text class="feature-icon">🎨</text>
          <text class="feature-label">苔色</text>
        </view>
        <view class="feature-values">
          <view
            v-for="(value, key) in features.coating_color"
            :key="`coating_color-${key}`"
            class="feature-value"
            :class="{ active: value > threshold }"
          >
            <text class="value-name">{{ key }}</text>
            <view class="value-bar">
              <view
                class="bar-fill"
                :style="getBarStyle(value)"
              ></view>
            </view>
            <text class="value-percent">{{ formatPercent(value) }}</text>
          </view>
        </view>
      </view>

      <!-- Coating Quality -->
      <view class="feature-item" v-if="features.coating_quality">
        <view class="feature-header">
          <text class="feature-icon">🧬</text>
          <text class="feature-label">苔质</text>
        </view>
        <view class="feature-values">
          <view
            v-for="(value, key) in features.coating_quality"
            :key="`coating_quality-${key}`"
            class="feature-value"
            :class="{ active: value > threshold }"
          >
            <text class="value-name">{{ key }}</text>
            <view class="value-bar">
              <view
                class="bar-fill"
                :style="getBarStyle(value)"
              ></view>
            </view>
            <text class="value-percent">{{ formatPercent(value) }}</text>
          </view>
        </view>
      </view>

      <!-- Sublingual Vein -->
      <view class="feature-item" v-if="features.sublingual_vein">
        <view class="feature-header">
          <text class="feature-icon">🩸</text>
          <text class="feature-label">舌下络脉</text>
        </view>
        <view class="feature-values">
          <view
            v-for="(value, key) in features.sublingual_vein"
            :key="`sublingual_vein-${key}`"
            class="feature-value"
            :class="{ active: value > threshold }"
          >
            <text class="value-name">{{ key }}</text>
            <view class="value-bar">
              <view
                class="bar-fill"
                :style="getBarStyle(value)"
              ></view>
            </view>
            <text class="value-percent">{{ formatPercent(value) }}</text>
          </view>
        </view>
      </view>

      <!-- Special Features -->
      <view class="feature-item" v-if="features.special_features">
        <view class="feature-header">
          <text class="feature-icon">⭐</text>
          <text class="feature-label">特殊特征</text>
        </view>
        <view class="feature-values">
          <view
            v-for="(value, key) in features.special_features"
            :key="`special_features-${key}`"
            class="feature-value"
            :class="{ active: value > threshold }"
          >
            <text class="value-name">{{ key }}</text>
            <view class="value-bar">
              <view
                class="bar-fill"
                :style="getBarStyle(value)"
              ></view>
            </view>
            <text class="value-percent">{{ formatPercent(value) }}</text>
          </view>
        </view>
      </view>
    </view>

    <!-- Summary Stats (Optional) -->
    <view class="summary-stats" v-if="showSummary">
      <view class="stat-item">
        <text class="stat-label">主要特征</text>
        <text class="stat-value">{{ primaryFeaturesCount }}</text>
      </view>
      <view class="stat-item">
        <text class="stat-label">最高置信度</text>
        <text class="stat-value">{{ formatPercent(highestConfidence) }}</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { TongueFeatures } from '@/store/modules/diagnosis'

// Props
interface Props {
  features: TongueFeatures // 6-dimension tongue features
  threshold?: number // Confidence threshold for highlighting active features (default: 0.3)
  showSummary?: boolean // Show summary statistics
  activeColor?: string // Color for active feature bars (default: gradient)
  inactiveColor?: string // Color for inactive feature bars (default: gray)
}

const props = withDefaults(defineProps<Props>(), {
  threshold: 0.3,
  showSummary: false,
  activeColor: '',
  inactiveColor: ''
})

// Computed
const primaryFeaturesCount = computed(() => {
  let count = 0
  const allFeatures = props.features as Record<string, Record<string, number>>

  Object.values(allFeatures).forEach(dimension => {
    if (dimension) {
      Object.values(dimension).forEach(value => {
        if (value > props.threshold) {
          count++
        }
      })
    }
  })

  return count
})

const highestConfidence = computed(() => {
  let max = 0
  const allFeatures = props.features as Record<string, Record<string, number>>

  Object.values(allFeatures).forEach(dimension => {
    if (dimension) {
      Object.values(dimension).forEach(value => {
        if (value > max) {
          max = value
        }
      })
    }
  })

  return max
})

// Methods
function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`
}

function getBarStyle(value: number): Record<string, string> {
  const width = `${value * 100}%`

  if (value > props.threshold) {
    // Active feature - use custom color or default gradient
    if (props.activeColor) {
      return { width, background: props.activeColor }
    }
    return { width, background: 'linear-gradient(90deg, #f093fb 0%, #f5576c 100%)' }
  } else {
    // Inactive feature - use custom color or default gray
    if (props.inactiveColor) {
      return { width, background: props.inactiveColor }
    }
    return { width, background: 'linear-gradient(90deg, #667eea 0%, #764ba2 100%)' }
  }
}
</script>

<style lang="scss" scoped>
.feature-display {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.features-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.feature-item {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
}

.feature-header {
  display: flex;
  align-items: center;
  gap: 6px;
}

.feature-icon {
  font-size: 16px;
}

.feature-label {
  font-size: 14px;
  font-weight: 500;
  color: #667eea;
}

.feature-values {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.feature-value {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

.value-name {
  font-size: 13px;
  color: #666666;
  min-width: 50px;
  flex-shrink: 0;
}

.value-bar {
  flex: 1;
  height: 8px;
  background: #f0f0f0;
  border-radius: 4px;
  overflow: hidden;
  min-width: 60px;
}

.bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s ease-out;
  min-width: 2px;
}

.feature-value.active .value-name {
  color: #f5576c;
  font-weight: 500;
}

.value-percent {
  font-size: 11px;
  color: #999999;
  min-width: 40px;
  text-align: right;
  flex-shrink: 0;
}

.feature-value.active .value-percent {
  color: #f5576c;
  font-weight: 500;
}

// Summary Stats
.summary-stats {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
  border-radius: 8px;
}

.stat-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.stat-label {
  font-size: 12px;
  color: #999999;
}

.stat-value {
  font-size: 18px;
  font-weight: 500;
  color: #667eea;
}
</style>
