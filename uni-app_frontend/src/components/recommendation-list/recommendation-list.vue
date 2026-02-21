<template>
  <view class="recommendation-list" :class="{ 'recommendation-list--collapsed': !isExpanded }">
    <!-- Header with Toggle -->
    <view class="recommendation-list__header" @click="toggleExpanded">
      <view class="recommendation-list__title-section">
        <text class="recommendation-list__icon">{{ titleIcon }}</text>
        <text class="recommendation-list__title">{{ title }}</text>
      </view>
      <view class="recommendation-list__toggle" :class="{ 'recommendation-list__toggle--expanded': isExpanded }">
        <text class="recommendation-list__toggle-icon">▼</text>
      </view>
    </view>

    <!-- Collapsible Content -->
    <view
      class="recommendation-list__content"
      :class="{ 'recommendation-list__content--expanded': isExpanded }"
    >
      <!-- Dietary Recommendations -->
      <view
        v-if="recommendations.dietary && recommendations.dietary.length > 0"
        class="recommendation-list__group"
      >
        <view class="recommendation-list__group-header">
          <text class="recommendation-list__group-icon">{{ groupIcons.dietary }}</text>
          <text class="recommendation-list__group-title">饮食建议</text>
          <text class="recommendation-list__group-count">({{ recommendations.dietary.length }})</text>
        </view>
        <view class="recommendation-list__items">
          <view
            v-for="(item, index) in recommendations.dietary"
            :key="`dietary-${index}`"
            class="recommendation-list__item"
          >
            <view class="recommendation-list__item-bullet"></view>
            <text class="recommendation-list__item-text">{{ item }}</text>
          </view>
        </view>
      </view>

      <!-- Lifestyle Recommendations -->
      <view
        v-if="recommendations.lifestyle && recommendations.lifestyle.length > 0"
        class="recommendation-list__group"
      >
        <view class="recommendation-list__group-header">
          <text class="recommendation-list__group-icon">{{ groupIcons.lifestyle }}</text>
          <text class="recommendation-list__group-title">生活建议</text>
          <text class="recommendation-list__group-count">({{ recommendations.lifestyle.length }})</text>
        </view>
        <view class="recommendation-list__items">
          <view
            v-for="(item, index) in recommendations.lifestyle"
            :key="`lifestyle-${index}`"
            class="recommendation-list__item"
          >
            <view class="recommendation-list__item-bullet"></view>
            <text class="recommendation-list__item-text">{{ item }}</text>
          </view>
        </view>
      </view>

      <!-- Emotional Recommendations -->
      <view
        v-if="recommendations.emotional && recommendations.emotional.length > 0"
        class="recommendation-list__group"
      >
        <view class="recommendation-list__group-header">
          <text class="recommendation-list__group-icon">{{ groupIcons.emotional }}</text>
          <text class="recommendation-list__group-title">情志建议</text>
          <text class="recommendation-list__group-count">({{ recommendations.emotional.length }})</text>
        </view>
        <view class="recommendation-list__items">
          <view
            v-for="(item, index) in recommendations.emotional"
            :key="`emotional-${index}`"
            class="recommendation-list__item"
          >
            <view class="recommendation-list__item-bullet"></view>
            <text class="recommendation-list__item-text">{{ item }}</text>
          </view>
        </view>
      </view>

      <!-- Empty State -->
      <view v-if="isEmpty" class="recommendation-list__empty">
        <text class="recommendation-list__empty-text">暂无健康建议</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { HealthRecommendations } from '@/store/modules/diagnosis'

// Props
interface Props {
  recommendations: HealthRecommendations    // Health recommendations data
  title?: string                            // Section title (default: '健康建议')
  titleIcon?: string                        // Title icon (default: '💡')
  expanded?: boolean                        // Initial expanded state (default: false)
  showCount?: boolean                       // Show item count per group (default: true)
  groupIcons?: {                            // Custom icons for each group
    dietary?: string
    lifestyle?: string
    emotional?: string
  }
}

const props = withDefaults(defineProps<Props>(), {
  title: '健康建议',
  titleIcon: '💡',
  expanded: false,
  showCount: true,
  groupIcons: () => ({
    dietary: '🥗',
    lifestyle: '🏃',
    emotional: '😌'
  })
})

// State
const isExpanded = ref(props.expanded)

// Emits
const emit = defineEmits<{
  toggle: [expanded: boolean]
}>()

// Computed
const isEmpty = computed(() => {
  return (
    !props.recommendations.dietary?.length &&
    !props.recommendations.lifestyle?.length &&
    !props.recommendations.emotional?.length
  )
})

const totalItems = computed(() => {
  let count = 0
  if (props.recommendations.dietary) count += props.recommendations.dietary.length
  if (props.recommendations.lifestyle) count += props.recommendations.lifestyle.length
  if (props.recommendations.emotional) count += props.recommendations.emotional.length
  return count
})

// Methods
function toggleExpanded() {
  isExpanded.value = !isExpanded.value
  emit('toggle', isExpanded.value)
}

// Expose methods for parent component
defineExpose({
  expand: () => { isExpanded.value = true },
  collapse: () => { isExpanded.value = false }
})
</script>

<style lang="scss" scoped>
.recommendation-list {
  display: flex;
  flex-direction: column;
  background: #ffffff;
  border-radius: 12px;
  overflow: hidden;
}

// Header
.recommendation-list__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
  border-bottom: 1px solid #e5e5e5;
  cursor: pointer;
  transition: background 0.2s ease;
}

.recommendation-list__header:active {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
}

.recommendation-list__title-section {
  display: flex;
  align-items: center;
  gap: 8px;
}

.recommendation-list__icon {
  font-size: 18px;
}

.recommendation-list__title {
  font-size: 16px;
  font-weight: 500;
  color: #333333;
}

.recommendation-list__toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: rgba(102, 126, 234, 0.1);
  border-radius: 50%;
  transition: transform 0.3s ease;
}

.recommendation-list__toggle--expanded {
  transform: rotate(180deg);
}

.recommendation-list__toggle-icon {
  font-size: 12px;
  color: #667eea;
}

// Content
.recommendation-list__content {
  display: flex;
  flex-direction: column;
  max-height: 0;
  overflow: hidden;
  transition: max-height 0.3s ease-out;
}

.recommendation-list__content--expanded {
  max-height: 1000px;
  transition: max-height 0.5s ease-in;
}

.recommendation-list__group {
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
}

.recommendation-list__group:last-child {
  border-bottom: none;
}

.recommendation-list__group-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
}

.recommendation-list__group-icon {
  font-size: 16px;
}

.recommendation-list__group-title {
  font-size: 14px;
  font-weight: 500;
  color: #667eea;
}

.recommendation-list__group-count {
  font-size: 12px;
  color: #999999;
  margin-left: 4px;
}

.recommendation-list__items {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-left: 22px;
}

.recommendation-list__item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.recommendation-list__item-bullet {
  position: relative;
  width: 6px;
  height: 6px;
  margin-top: 7px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  flex-shrink: 0;
}

.recommendation-list__item-text {
  flex: 1;
  font-size: 13px;
  color: #666666;
  line-height: 1.6;
}

// Empty State
.recommendation-list__empty {
  padding: 24px 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.recommendation-list__empty-text {
  font-size: 13px;
  color: #999999;
}

// Collapsed mode - content hidden but maintain spacing
.recommendation-list--collapsed {
  .recommendation-list__content {
    display: none;
  }
}
</style>
