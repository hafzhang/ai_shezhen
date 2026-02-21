<template>
  <view class="container">
    <view class="header">
      <view class="header-left" @click="goBack">
        <text class="back-icon">←</text>
      </view>
      <text class="header-title">诊断历史</text>
      <view class="header-right"></view>
    </view>

    <view class="content">
      <!-- Filters -->
      <view class="filters" v-if="hasActiveFilters">
        <view class="filter-chips">
          <view class="chip" v-if="filters.syndrome" @click="clearSyndromeFilter">
            <text class="chip-text">{{ filters.syndrome }}</text>
            <text class="chip-close">×</text>
          </view>
          <view class="chip" v-if="filters.has_risk !== undefined" @click="clearRiskFilter">
            <text class="chip-text">{{ filters.has_risk ? '有风险' : '无风险' }}</text>
            <text class="chip-close">×</text>
          </view>
          <view class="chip" v-if="filters.start_date || filters.end_date" @click="clearDateFilter">
            <text class="chip-text">日期筛选</text>
            <text class="chip-close">×</text>
          </view>
          <view class="chip chip-clear" @click="clearAllFilters">
            <text class="chip-text">清空</text>
          </view>
        </view>
      </view>

      <!-- Empty state -->
      <view class="empty-state" v-if="!isLoading && history.length === 0">
        <text class="empty-icon">📋</text>
        <text class="empty-title">暂无诊断记录</text>
        <text class="empty-desc">完成首次诊断后，这里将显示您的诊断历史</text>
        <button class="btn btn-primary" @click="goToDiagnosis">开始诊断</button>
      </view>

      <!-- History list -->
      <view class="history-list" v-else>
        <!-- Pull to refresh indicator -->
        <view class="refresh-indicator" v-if="isRefreshing">
          <text class="refresh-text">正在刷新...</text>
        </view>

        <!-- List items -->
        <view
          class="history-item"
          v-for="item in history"
          :key="item.id"
          @click="viewDetail(item.id)"
        >
          <view class="item-header">
            <view class="syndrome-info">
              <text class="syndrome-name">{{ item.primary_syndrome }}</text>
              <view
                class="risk-badge"
                :class="{ 'has-risk': item.has_risk, 'no-risk': !item.has_risk }"
              >
                <text class="risk-text">{{ item.has_risk ? '风险' : '正常' }}</text>
              </view>
            </view>
            <text class="confidence">{{ Math.round(item.confidence * 100) }}%</text>
          </view>

          <view class="item-footer">
            <text class="diagnosis-time">{{ formatTime(item.created_at) }}</text>
            <text class="view-detail">查看详情 →</text>
          </view>
        </view>

        <!-- Loading more indicator -->
        <view class="load-more" v-if="isLoadingMore">
          <text class="load-text">加载中...</text>
        </view>

        <!-- No more data indicator -->
        <view class="no-more" v-if="!hasMore && history.length > 0">
          <text class="no-more-text">没有更多记录了</text>
        </view>
      </view>

      <!-- Loading state -->
      <view class="loading-state" v-if="isLoading && history.length === 0">
        <text class="loading-text">加载中...</text>
      </view>
    </view>

    <!-- Filter button (bottom right) -->
    <view class="filter-button" @click="showFilterSheet = true" v-if="history.length > 0">
      <text class="filter-icon">🔍</text>
    </view>

    <!-- Filter sheet -->
    <u-popup v-model:show="showFilterSheet" mode="bottom" :round="20">
      <view class="filter-sheet">
        <view class="sheet-header">
          <text class="sheet-title">筛选条件</text>
          <text class="sheet-close" @click="showFilterSheet = false">完成</text>
        </view>

        <view class="sheet-content">
          <!-- Date range filter -->
          <view class="filter-section">
            <text class="section-title">日期范围</text>
            <view class="date-options">
              <view
                class="date-option"
                :class="{ active: dateRange === option.value }"
                v-for="option in dateRangeOptions"
                :key="option.value"
                @click="selectDateRange(option.value)"
              >
                <text class="option-text">{{ option.label }}</text>
              </view>
            </view>
          </view>

          <!-- Risk filter -->
          <view class="filter-section">
            <text class="section-title">风险状态</text>
            <view class="risk-options">
              <view
                class="risk-option"
                :class="{ active: filters.has_risk === undefined }"
                @click="filters.has_risk = undefined"
              >
                <text class="option-text">全部</text>
              </view>
              <view
                class="risk-option"
                :class="{ active: filters.has_risk === true }"
                @click="filters.has_risk = true"
              >
                <text class="option-text">有风险</text>
              </view>
              <view
                class="risk-option"
                :class="{ active: filters.has_risk === false }"
                @click="filters.has_risk = false"
              >
                <text class="option-text">无风险</text>
              </view>
            </view>
          </view>

          <!-- Apply button -->
          <view class="sheet-actions">
            <button class="btn btn-secondary" @click="resetFilters">重置</button>
            <button class="btn btn-primary" @click="applyFilters">应用</button>
          </view>
        </view>
      </view>
    </u-popup>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useDiagnosisStore, type DiagnosisHistory, type DiagnosisFilters } from '@/store'
import { onPullDownRefresh, onReachBottom } from '@dcloudio/uni-app'

const diagnosisStore = useDiagnosisStore()

// State
const history = computed(() => diagnosisStore.diagnosisHistory)
const pagination = computed(() => diagnosisStore.historyPagination)
const filters = computed(() => diagnosisStore.historyFilters)

const isLoading = ref(false)
const isRefreshing = ref(false)
const isLoadingMore = ref(false)
const showFilterSheet = ref(false)
const dateRange = ref<string>('all')

// Date range options
const dateRangeOptions = [
  { label: '全部', value: 'all' },
  { label: '今天', value: 'today' },
  { label: '最近7天', value: 'week' },
  { label: '最近30天', value: 'month' },
  { label: '最近3个月', value: 'quarter' }
]

// Computed
const hasMore = computed(() => {
  return history.value.length < pagination.value.total
})

const hasActiveFilters = computed(() => {
  return !!(filters.value.syndrome ||
             filters.value.has_risk !== undefined ||
             filters.value.start_date ||
             filters.value.end_date)
})

// Functions
function formatTime(timestamp: string): string {
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)

  if (days > 7) {
    return `${date.getMonth() + 1}月${date.getDate()}日`
  } else if (days > 0) {
    return `${days}天前`
  } else if (hours > 0) {
    return `${hours}小时前`
  } else if (minutes > 0) {
    return `${minutes}分钟前`
  } else {
    return '刚刚'
  }
}

function goBack() {
  uni.navigateBack()
}

function goToDiagnosis() {
  uni.navigateTo({
    url: '/pages/diagnosis/index'
  })
}

function viewDetail(id: string) {
  uni.navigateTo({
    url: `/pages/detail/index?id=${id}`
  })
}

async function loadHistory(refresh: boolean = false) {
  if (isLoading.value && !refresh) return

  isLoading.value = true
  try {
    const page = refresh ? 1 : pagination.value.page
    await diagnosisStore.fetchDiagnosisHistory(page, filters.value)
  } catch (error) {
    console.error('Failed to load history:', error)
    uni.showToast({
      title: '加载失败',
      icon: 'none'
    })
  } finally {
    isLoading.value = false
  }
}

async function onRefresh() {
  if (isRefreshing.value) return

  isRefreshing.value = true
  try {
    await diagnosisStore.fetchDiagnosisHistory(1, filters.value)
  } catch (error) {
    console.error('Refresh failed:', error)
  } finally {
    isRefreshing.value = false
    uni.stopPullDownRefresh()
  }
}

async function loadMore() {
  if (isLoadingMore.value || !hasMore.value) return

  isLoadingMore.value = true
  try {
    const nextPage = pagination.value.page + 1
    await diagnosisStore.fetchDiagnosisHistory(nextPage, filters.value)
  } catch (error) {
    console.error('Failed to load more:', error)
  } finally {
    isLoadingMore.value = false
  }
}

function selectDateRange(value: string) {
  dateRange.value = value
  const now = new Date()

  switch (value) {
    case 'all':
      filters.value.start_date = undefined
      filters.value.end_date = undefined
      break
    case 'today':
      filters.value.start_date = new Date(now.setHours(0, 0, 0, 0)).toISOString()
      filters.value.end_date = new Date().toISOString()
      break
    case 'week':
      filters.value.start_date = new Date(now.setDate(now.getDate() - 7)).toISOString()
      filters.value.end_date = new Date().toISOString()
      break
    case 'month':
      filters.value.start_date = new Date(now.setDate(now.getDate() - 30)).toISOString()
      filters.value.end_date = new Date().toISOString()
      break
    case 'quarter':
      filters.value.start_date = new Date(now.setDate(now.getDate() - 90)).toISOString()
      filters.value.end_date = new Date().toISOString()
      break
  }
}

function applyFilters() {
  showFilterSheet.value = false
  loadHistory(true)
}

function resetFilters() {
  dateRange.value = 'all'
  diagnosisStore.resetFilters()
}

function clearSyndromeFilter() {
  diagnosisStore.setHistoryFilters({
    ...filters.value,
    syndrome: undefined
  })
  loadHistory(true)
}

function clearRiskFilter() {
  diagnosisStore.setHistoryFilters({
    ...filters.value,
    has_risk: undefined
  })
  loadHistory(true)
}

function clearDateFilter() {
  dateRange.value = 'all'
  diagnosisStore.setHistoryFilters({
    ...filters.value,
    start_date: undefined,
    end_date: undefined
  })
  loadHistory(true)
}

function clearAllFilters() {
  resetFilters()
  loadHistory(true)
}

// Lifecycle
onMounted(() => {
  loadHistory(true)
})

// Pull to refresh (uni-app API)
onPullDownRefresh(() => {
  onRefresh()
})

// Load more on scroll (uni-app API)
onReachBottom(() => {
  loadMore()
})
</script>

<style lang="scss" scoped>
.container {
  min-height: 100vh;
  background: #f5f5f5;
}

.header {
  background: #ffffff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 50px 15px 15px;
  border-bottom: 1px solid #f0f0f0;
}

.header-left,
.header-right {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.back-icon {
  font-size: 24px;
  color: #333333;
}

.header-title {
  font-size: 18px;
  font-weight: 500;
  color: #333333;
}

.content {
  padding: 15px;
}

.filters {
  margin-bottom: 15px;
}

.filter-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.chip {
  background: #e8f2ff;
  border-radius: 16px;
  padding: 6px 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.chip-clear {
  background: #f0f0f0;
}

.chip-text {
  font-size: 13px;
  color: #667eea;
}

.chip-close {
  font-size: 18px;
  color: #667eea;
  line-height: 1;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  text-align: center;
}

.empty-icon {
  font-size: 80px;
  margin-bottom: 20px;
}

.empty-title {
  font-size: 18px;
  font-weight: 500;
  color: #333333;
  margin-bottom: 10px;
  display: block;
}

.empty-desc {
  font-size: 14px;
  color: #999999;
  margin-bottom: 30px;
  display: block;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.refresh-indicator {
  text-align: center;
  padding: 10px 0;
}

.refresh-text {
  font-size: 13px;
  color: #999999;
}

.history-item {
  background: #ffffff;
  border-radius: 12px;
  padding: 15px;
  transition: background 0.2s;
}

.history-item:active {
  background: #f8f8f8;
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.syndrome-info {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
}

.syndrome-name {
  font-size: 16px;
  font-weight: 500;
  color: #333333;
}

.risk-badge {
  padding: 4px 10px;
  border-radius: 10px;
}

.risk-badge.has-risk {
  background: #fff0f0;
}

.risk-badge.has-risk .risk-text {
  color: #ff4d4f;
}

.risk-badge.no-risk {
  background: #f0f9ff;
}

.risk-badge.no-risk .risk-text {
  color: #52c41a;
}

.risk-text {
  font-size: 11px;
}

.confidence {
  font-size: 14px;
  color: #52c41a;
  font-weight: 500;
}

.item-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.diagnosis-time {
  font-size: 12px;
  color: #999999;
}

.view-detail {
  font-size: 13px;
  color: #667eea;
}

.load-more,
.no-more {
  text-align: center;
  padding: 15px 0;
}

.load-text,
.no-more-text {
  font-size: 13px;
  color: #999999;
}

.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
}

.loading-text {
  font-size: 14px;
  color: #999999;
}

.filter-button {
  position: fixed;
  right: 20px;
  bottom: 100px;
  width: 50px;
  height: 50px;
  background: #667eea;
  border-radius: 25px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.filter-icon {
  font-size: 24px;
}

.filter-sheet {
  background: #ffffff;
  border-radius: 20px 20px 0 0;
  padding: 20px;
}

.sheet-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.sheet-title {
  font-size: 18px;
  font-weight: 500;
  color: #333333;
}

.sheet-close {
  font-size: 15px;
  color: #667eea;
}

.sheet-content {
  display: flex;
  flex-direction: column;
  gap: 25px;
}

.filter-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-title {
  font-size: 14px;
  font-weight: 500;
  color: #666666;
}

.date-options,
.risk-options {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.date-option,
.risk-option {
  padding: 8px 16px;
  border-radius: 8px;
  border: 1px solid #e0e0e0;
  background: #ffffff;
}

.date-option.active,
.risk-option.active {
  background: #667eea;
  border-color: #667eea;
}

.option-text {
  font-size: 14px;
  color: #666666;
}

.active .option-text {
  color: #ffffff;
}

.sheet-actions {
  display: flex;
  gap: 15px;
}

.btn {
  flex: 1;
  height: 44px;
  border-radius: 22px;
  font-size: 15px;
  font-weight: 500;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-primary {
  background: #667eea;
  color: #ffffff;
}

.btn-secondary {
  background: #f0f0f0;
  color: #666666;
}
</style>
