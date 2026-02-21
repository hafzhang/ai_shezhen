<template>
  <view class="container">
    <view class="header">
      <view class="header-left" @click="goBack">
        <text class="back-icon">←</text>
      </view>
      <text class="header-title">健康档案</text>
      <view class="header-right" @click="showAddModal = true">
        <text class="add-icon">+</text>
      </view>
    </view>

    <view class="content">
      <!-- Empty state -->
      <view class="empty-state" v-if="!isLoading && records.length === 0">
        <text class="empty-icon">📋</text>
        <text class="empty-title">暂无健康档案</text>
        <text class="empty-desc">记录您的健康信息，便于跟踪健康趋势</text>
        <button class="btn btn-primary" @click="showAddModal = true">添加记录</button>
      </view>

      <!-- Records list -->
      <view class="records-list" v-else>
        <!-- Loading state -->
        <view class="loading-state" v-if="isLoading">
          <text class="loading-text">加载中...</text>
        </view>

        <!-- Records grouped by type -->
        <view class="record-group" v-for="group in groupedRecords" :key="group.type">
          <view class="group-header">
            <text class="group-title">{{ getRecordTypeLabel(group.type) }}</text>
            <text class="group-count">{{ group.records.length }} 条</text>
          </view>
          <view
            class="record-item"
            v-for="record in group.records"
            :key="record.id"
            @click="viewRecord(record)"
          >
            <view class="record-left">
              <text class="record-name">{{ record.record_name || record.record_type }}</text>
              <text class="record-date">{{ formatDate(record.record_date) }}</text>
            </view>
            <view class="record-right">
              <text class="record-value">{{ formatRecordValue(record) }}</text>
              <text class="arrow">›</text>
            </view>
          </view>
        </view>
      </view>

      <!-- Load more indicator -->
      <view class="load-more" v-if="hasMore && !isLoading">
        <text class="load-text" @click="loadMore">加载更多</text>
      </view>

      <!-- No more indicator -->
      <view class="no-more" v-if="!hasMore && records.length > 0">
        <text class="no-more-text">没有更多记录了</text>
      </view>
    </view>

    <!-- Add/Edit modal -->
    <u-popup v-model:show="showAddModal" mode="bottom" :round="20">
      <view class="modal">
        <view class="modal-header">
          <text class="modal-title">{{ editingRecord ? '编辑记录' : '添加记录' }}</text>
          <text class="modal-close" @click="closeModal">×</text>
        </view>

        <view class="modal-content">
          <!-- Record type -->
          <view class="form-item">
            <text class="form-label">记录类型</text>
            <view class="type-options">
              <view
                class="type-option"
                :class="{ active: formData.record_type === option.value }"
                v-for="option in recordTypeOptions"
                :key="option.value"
                @click="formData.record_type = option.value"
              >
                <text class="option-text">{{ option.label }}</text>
              </view>
            </view>
          </view>

          <!-- Record name -->
          <view class="form-item">
            <text class="form-label">记录名称</text>
            <input
              class="form-input"
              v-model="formData.record_name"
              placeholder="如：血压、血糖、体重等"
            />
          </view>

          <!-- Record value -->
          <view class="form-item">
            <text class="form-label">数值</text>
            <input
              class="form-input"
              v-model="formData.record_value"
              type="text"
              placeholder="请输入数值"
            />
            <text class="form-hint">例如：120/80, 5.6, 65kg等</text>
          </view>

          <!-- Record date -->
          <view class="form-item">
            <text class="form-label">记录日期</text>
            <view class="date-picker" @click="showDatePicker = true">
              <text class="date-text" v-if="formData.record_date">
                {{ formatDate(formData.record_date) }}
              </text>
              <text class="date-placeholder" v-else>选择日期</text>
              <text class="arrow">›</text>
            </view>
          </view>

          <!-- Notes -->
          <view class="form-item">
            <text class="form-label">备注</text>
            <textarea
              class="form-textarea"
              v-model="formData.notes"
              placeholder="添加备注信息（可选）"
              maxlength="200"
            />
          </view>
        </view>

        <view class="modal-actions">
          <button class="btn btn-secondary" @click="closeModal">取消</button>
          <button class="btn btn-primary" @click="saveRecord">保存</button>
        </view>
      </view>
    </u-popup>

    <!-- Date picker -->
    <u-popup v-model:show="showDatePicker" mode="bottom" :round="20">
      <view class="date-picker-modal">
        <view class="date-picker-header">
          <text class="date-picker-cancel" @click="showDatePicker = false">取消</text>
          <text class="date-picker-title">选择日期</text>
          <text class="date-picker-confirm" @click="confirmDate">确定</text>
        </view>
        <picker-view
          class="date-picker-view"
          :value="datePickerValue"
          @change="onDatePickerChange"
        >
          <picker-view-column>
            <view v-for="year in years" :key="year">{{ year }}年</view>
          </picker-view-column>
          <picker-view-column>
            <view v-for="month in months" :key="month">{{ month }}月</view>
          </picker-view-column>
          <picker-view-column>
            <view v-for="day in days" :key="day">{{ day }}日</view>
          </picker-view-column>
        </picker-view>
      </view>
    </u-popup>

    <!-- View record modal -->
    <u-popup v-model:show="showViewModal" mode="center" :round="20">
      <view class="view-modal" v-if="currentRecord">
        <view class="view-header">
          <text class="view-title">记录详情</text>
          <text class="view-close" @click="showViewModal = false">×</text>
        </view>
        <view class="view-content">
          <view class="view-item">
            <text class="view-label">类型</text>
            <text class="view-value">{{ getRecordTypeLabel(currentRecord.record_type) }}</text>
          </view>
          <view class="view-item" v-if="currentRecord.record_name">
            <text class="view-label">名称</text>
            <text class="view-value">{{ currentRecord.record_name }}</text>
          </view>
          <view class="view-item">
            <text class="view-label">数值</text>
            <text class="view-value">{{ formatRecordValue(currentRecord) }}</text>
          </view>
          <view class="view-item">
            <text class="view-label">日期</text>
            <text class="view-value">{{ formatDate(currentRecord.record_date) }}</text>
          </view>
          <view class="view-item" v-if="currentRecord.notes">
            <text class="view-label">备注</text>
            <text class="view-value">{{ currentRecord.notes }}</text>
          </view>
        </view>
        <view class="view-actions">
          <button class="btn btn-secondary" @click="editRecord(currentRecord)">编辑</button>
          <button class="btn btn-danger" @click="confirmDelete">删除</button>
        </view>
      </view>
    </u-popup>

    <!-- Delete confirmation modal -->
    <u-popup v-model:show="showDeleteModal" mode="center" :round="20">
      <view class="confirm-modal">
        <view class="confirm-header">
          <text class="confirm-title">删除记录</text>
        </view>
        <view class="confirm-content">
          <text class="confirm-message">确定要删除这条健康记录吗？</text>
        </view>
        <view class="confirm-actions">
          <button class="btn btn-secondary" @click="showDeleteModal = false">取消</button>
          <button class="btn btn-danger" @click="deleteRecord">删除</button>
        </view>
      </view>
    </u-popup>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { request } from '@/utils/request'

interface HealthRecord {
  id: string
  user_id: string
  record_type: string
  record_name?: string
  record_value: string
  record_date: string
  notes?: string
  created_at: string
  updated_at: string
}

// State
const records = ref<HealthRecord[]>([])
const isLoading = ref(false)
const hasMore = ref(false)
const page = ref(1)
const pageSize = 20

// Modal states
const showAddModal = ref(false)
const showViewModal = ref(false)
const showDatePicker = ref(false)
const showDeleteModal = ref(false)

// Form data
const editingRecord = ref<HealthRecord | null>(null)
const currentRecord = ref<HealthRecord | null>(null)
const formData = ref({
  record_type: 'blood_pressure',
  record_name: '',
  record_value: '',
  record_date: new Date().toISOString().split('T')[0],
  notes: ''
})

// Date picker
const datePickerValue = ref([0, 0, 0])
const years = computed(() => {
  const currentYear = new Date().getFullYear()
  return Array.from({ length: 10 }, (_, i) => currentYear - i)
})
const months = Array.from({ length: 12 }, (_, i) => i + 1)
const days = Array.from({ length: 31 }, (_, i) => i + 1)

// Record type options
const recordTypeOptions = [
  { label: '血压', value: 'blood_pressure' },
  { label: '血糖', value: 'blood_sugar' },
  { label: '体重', value: 'weight' },
  { label: '体温', value: 'temperature' },
  { label: '心率', value: 'heart_rate' },
  { label: '其他', value: 'other' }
]

// Computed
const groupedRecords = computed(() => {
  const groups: { [key: string]: { type: string; records: HealthRecord[] } } = {}
  records.value.forEach(record => {
    if (!groups[record.record_type]) {
      groups[record.record_type] = {
        type: record.record_type,
        records: []
      }
    }
    groups[record.record_type].records.push(record)
  })
  return Object.values(groups).sort((a, b) => b.records.length - a.records.length)
})

// Functions
function goBack() {
  uni.navigateBack()
}

function getRecordTypeLabel(type: string): string {
  const option = recordTypeOptions.find(opt => opt.value === type)
  return option?.label || type
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function formatRecordValue(record: HealthRecord): string {
  return record.record_value
}

function closeModal() {
  showAddModal.value = false
  editingRecord.value = null
  resetForm()
}

function resetForm() {
  formData.value = {
    record_type: 'blood_pressure',
    record_name: '',
    record_value: '',
    record_date: new Date().toISOString().split('T')[0],
    notes: ''
  }
  datePickerValue.value = [0, 0, 0]
}

async function loadRecords(refresh = false) {
  if (isLoading.value) return

  isLoading.value = true
  try {
    if (refresh) {
      page.value = 1
      records.value = []
    }

    const params = new URLSearchParams()
    params.append('page', page.value.toString())
    params.append('page_size', pageSize.toString())

    const response = await request<{
      items: HealthRecord[]
      total: number
    }>({
      url: `/health-records?${params.toString()}`,
      method: 'GET'
    })

    if (response.success && response.data) {
      if (refresh) {
        records.value = response.data.items
      } else {
        records.value.push(...response.data.items)
      }
      hasMore.value = records.value.length < response.data.total
    }
  } catch (error) {
    console.error('Failed to load health records:', error)
    uni.showToast({
      title: '加载失败',
      icon: 'none'
    })
  } finally {
    isLoading.value = false
  }
}

function loadMore() {
  if (!hasMore.value || isLoading.value) return
  page.value++
  loadRecords()
}

function viewRecord(record: HealthRecord) {
  currentRecord.value = record
  showViewModal.value = true
}

function editRecord(record: HealthRecord) {
  showViewModal.value = false
  editingRecord.value = record
  formData.value = {
    record_type: record.record_type,
    record_name: record.record_name || '',
    record_value: record.record_value,
    record_date: record.record_date.split('T')[0],
    notes: record.notes || ''
  }
  showAddModal.value = true
}

function confirmDelete() {
  showViewModal.value = false
  showDeleteModal.value = true
}

async function saveRecord() {
  if (!formData.value.record_value) {
    uni.showToast({
      title: '请输入数值',
      icon: 'none'
    })
    return
  }

  try {
    const isEdit = !!editingRecord.value
    const url = isEdit
      ? `/health-records/${editingRecord.value!.id}`
      : '/health-records'
    const method = isEdit ? 'PUT' : 'POST'

    const response = await request<HealthRecord>({
      url,
      method,
      data: formData.value
    })

    if (response.success) {
      uni.showToast({
        title: isEdit ? '更新成功' : '添加成功',
        icon: 'success'
      })
      closeModal()
      loadRecords(true)
    }
  } catch (error) {
    console.error('Failed to save record:', error)
    uni.showToast({
      title: '保存失败',
      icon: 'none'
    })
  }
}

async function deleteRecord() {
  if (!currentRecord.value) return

  try {
    const response = await request<{ success: boolean }>({
      url: `/health-records/${currentRecord.value.id}`,
      method: 'DELETE'
    })

    if (response.success) {
      uni.showToast({
        title: '删除成功',
        icon: 'success'
      })
      showDeleteModal.value = false
      loadRecords(true)
    }
  } catch (error) {
    console.error('Failed to delete record:', error)
    uni.showToast({
      title: '删除失败',
      icon: 'none'
    })
  }
}

function onDatePickerChange(e: any) {
  datePickerValue.value = e.detail.value
}

function confirmDate() {
  const [yearIndex, monthIndex, dayIndex] = datePickerValue.value
  const year = years.value[yearIndex]
  const month = String(months[monthIndex]).padStart(2, '0')
  const day = String(days[dayIndex]).padStart(2, '0')
  formData.value.record_date = `${year}-${month}-${day}`
  showDatePicker.value = false
}

// Lifecycle
onMounted(() => {
  loadRecords(true)
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

.back-icon,
.add-icon {
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

.records-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
}

.loading-text {
  font-size: 14px;
  color: #999999;
}

.record-group {
  background: #ffffff;
  border-radius: 12px;
  overflow: hidden;
}

.group-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 20px;
  background: #f8f9fa;
  border-bottom: 1px solid #f0f0f0;
}

.group-title {
  font-size: 15px;
  font-weight: 500;
  color: #333333;
}

.group-count {
  font-size: 13px;
  color: #999999;
}

.record-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 20px;
  border-bottom: 1px solid #f5f5f5;
}

.record-item:last-child {
  border-bottom: none;
}

.record-left {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.record-name {
  font-size: 15px;
  color: #333333;
  font-weight: 500;
}

.record-date {
  font-size: 12px;
  color: #999999;
}

.record-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.record-value {
  font-size: 15px;
  color: #667eea;
  font-weight: 500;
}

.arrow {
  font-size: 20px;
  color: #cccccc;
}

.load-more,
.no-more {
  text-align: center;
  padding: 15px 0;
}

.load-text {
  font-size: 14px;
  color: #667eea;
}

.no-more-text {
  font-size: 13px;
  color: #999999;
}

.modal,
.date-picker-modal,
.view-modal,
.confirm-modal {
  background: #ffffff;
  border-radius: 20px 20px 0 0;
  padding: 20px;
}

.view-modal,
.confirm-modal {
  border-radius: 20px;
  width: 280px;
}

.modal-header,
.view-header,
.confirm-header,
.date-picker-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.modal-title,
.view-title,
.confirm-title,
.date-picker-title {
  font-size: 18px;
  font-weight: 500;
  color: #333333;
}

.modal-close,
.view-close {
  font-size: 28px;
  color: #999999;
  line-height: 1;
}

.date-picker-cancel,
.date-picker-confirm {
  font-size: 15px;
  color: #667eea;
}

.modal-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.form-label {
  font-size: 14px;
  font-weight: 500;
  color: #333333;
}

.form-input,
.form-textarea {
  background: #f5f5f5;
  border-radius: 8px;
  padding: 12px 15px;
  font-size: 15px;
  color: #333333;
}

.form-textarea {
  min-height: 80px;
  resize: none;
}

.form-hint {
  font-size: 12px;
  color: #999999;
}

.type-options {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.type-option {
  padding: 8px 16px;
  border-radius: 20px;
  border: 1px solid #e0e0e0;
  background: #ffffff;
}

.type-option.active {
  background: #667eea;
  border-color: #667eea;
}

.option-text {
  font-size: 14px;
  color: #666666;
}

.type-option.active .option-text {
  color: #ffffff;
}

.date-picker {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #f5f5f5;
  border-radius: 8px;
  padding: 12px 15px;
}

.date-text {
  font-size: 15px;
  color: #333333;
}

.date-placeholder {
  font-size: 15px;
  color: #999999;
}

.date-picker-view {
  height: 300px;
}

.modal-actions,
.view-actions,
.confirm-actions {
  display: flex;
  gap: 15px;
  margin-top: 20px;
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

.btn-danger {
  background: #fff0f0;
  color: #ff4d4f;
}

.view-content {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.view-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.view-label {
  font-size: 14px;
  color: #999999;
}

.view-value {
  font-size: 15px;
  color: #333333;
  text-align: right;
  flex: 1;
  margin-left: 20px;
}

.confirm-content {
  padding: 10px 0;
}

.confirm-message {
  font-size: 15px;
  color: #333333;
  text-align: center;
  line-height: 1.6;
}
</style>
