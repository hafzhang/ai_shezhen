<template>
  <div class="container">
    <div class="header">
      <div class="header-left" @click="goBack">
        <span class="back-icon">←</span>
      </div>
      <span class="header-title">健康档案</span>
      <div class="header-right" @click="showAddModal = true">
        <span class="add-icon">+</span>
      </div>
    </div>

    <div class="content">
      <!-- Empty state -->
      <div class="empty-state" v-if="!isLoading && records.length === 0">
        <span class="empty-icon">📋</span>
        <span class="empty-title">暂无健康档案</span>
        <span class="empty-desc">记录您的健康信息，便于跟踪健康趋势</span>
        <button class="btn btn-primary" @click="showAddModal = true">添加记录</button>
      </div>

      <!-- Records list -->
      <div class="records-list" v-else>
        <!-- Pull to refresh indicator -->
        <div class="refresh-indicator" v-if="isRefreshing">
          <span class="refresh-text">正在刷新...</span>
        </div>

        <!-- Loading state -->
        <div class="loading-state" v-if="isLoading">
          <span class="loading-text">加载中...</span>
        </div>

        <!-- Records grouped by type -->
        <div class="record-group" v-for="group in groupedRecords" :key="group.type">
          <div class="group-header">
            <span class="group-title">{{ getRecordTypeLabel(group.type) }}</span>
            <span class="group-count">{{ group.records.length }} 条</span>
          </div>
          <div
            class="record-item"
            v-for="record in group.records"
            :key="record.id"
            @click="viewRecord(record)"
          >
            <div class="record-left">
              <span class="record-name">{{ record.record_name || record.record_type }}</span>
              <span class="record-date">{{ formatDate(record.record_date) }}</span>
            </div>
            <div class="record-right">
              <span class="record-value">{{ formatRecordValue(record) }}</span>
              <span class="arrow">›</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Load more indicator -->
      <div class="load-more" v-if="hasMore && !isLoading">
        <span class="load-text" @click="loadMore">加载更多</span>
      </div>

      <!-- No more indicator -->
      <div class="no-more" v-if="!hasMore && records.length > 0">
        <span class="no-more-text">没有更多记录了</span>
      </div>
    </div>

    <!-- Add/Edit modal -->
    <div class="modal-overlay" v-if="showAddModal" @click="closeModal">
      <div class="modal" @click.stop>
        <div class="modal-header">
          <span class="modal-title">{{ editingRecord ? '编辑记录' : '添加记录' }}</span>
          <span class="modal-close" @click="closeModal">×</span>
        </div>

        <div class="modal-content">
          <!-- Record type -->
          <div class="form-item">
            <span class="form-label">记录类型</span>
            <div class="type-options">
              <div
                class="type-option"
                :class="{ active: formData.record_type === option.value }"
                v-for="option in recordTypeOptions"
                :key="option.value"
                @click="formData.record_type = option.value"
              >
                <span class="option-text">{{ option.label }}</span>
              </div>
            </div>
          </div>

          <!-- Record name -->
          <div class="form-item">
            <span class="form-label">记录名称</span>
            <input
              class="form-input"
              v-model="formData.record_name"
              placeholder="如：血压、血糖、体重等"
            />
          </div>

          <!-- Record value -->
          <div class="form-item">
            <span class="form-label">数值</span>
            <input
              class="form-input"
              v-model="formData.record_value"
              type="text"
              placeholder="请输入数值"
            />
            <span class="form-hint">例如：120/80, 5.6, 65kg等</span>
          </div>

          <!-- Record date -->
          <div class="form-item">
            <span class="form-label">记录日期</span>
            <input
              type="date"
              class="form-input"
              v-model="formData.record_date"
            />
          </div>

          <!-- Notes -->
          <div class="form-item">
            <span class="form-label">备注</span>
            <textarea
              class="form-textarea"
              v-model="formData.notes"
              placeholder="添加备注信息（可选）"
              maxlength="200"
            />
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn btn-secondary" @click="closeModal">取消</button>
          <button class="btn btn-primary" @click="saveRecord">保存</button>
        </div>
      </div>
    </div>

    <!-- View record modal -->
    <div class="modal-overlay" v-if="showViewModal" @click="showViewModal = false">
      <div class="view-modal" @click.stop v-if="currentRecord">
        <div class="view-header">
          <span class="view-title">记录详情</span>
          <span class="view-close" @click="showViewModal = false">×</span>
        </div>
        <div class="view-content">
          <div class="view-item">
            <span class="view-label">类型</span>
            <span class="view-value">{{ getRecordTypeLabel(currentRecord.record_type) }}</span>
          </div>
          <div class="view-item" v-if="currentRecord.record_name">
            <span class="view-label">名称</span>
            <span class="view-value">{{ currentRecord.record_name }}</span>
          </div>
          <div class="view-item">
            <span class="view-label">数值</span>
            <span class="view-value">{{ formatRecordValue(currentRecord) }}</span>
          </div>
          <div class="view-item">
            <span class="view-label">日期</span>
            <span class="view-value">{{ formatDate(currentRecord.record_date) }}</span>
          </div>
          <div class="view-item" v-if="currentRecord.notes">
            <span class="view-label">备注</span>
            <span class="view-value">{{ currentRecord.notes }}</span>
          </div>
        </div>
        <div class="view-actions">
          <button class="btn btn-secondary" @click="editRecord(currentRecord)">编辑</button>
          <button class="btn btn-danger" @click="confirmDelete">删除</button>
        </div>
      </div>
    </div>

    <!-- Delete confirmation modal -->
    <div class="modal-overlay" v-if="showDeleteModal" @click="showDeleteModal = false">
      <div class="confirm-modal" @click.stop>
        <div class="confirm-header">
          <span class="confirm-title">删除记录</span>
        </div>
        <div class="confirm-content">
          <span class="confirm-message">确定要删除这条健康记录吗？</span>
        </div>
        <div class="confirm-actions">
          <button class="btn btn-secondary" @click="showDeleteModal = false">取消</button>
          <button class="btn btn-danger" @click="deleteRecord">删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
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

const router = useRouter()

// State
const records = ref<HealthRecord[]>([])
const isLoading = ref(false)
const isRefreshing = ref(false)
const hasMore = ref(false)
const page = ref(1)
const pageSize = 20

// Modal states
const showAddModal = ref(false)
const showViewModal = ref(false)
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
  router.back()
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
}

async function loadRecords(refresh = false) {
  if (isLoading.value && !refresh) return

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
    alert('加载失败')
  } finally {
    isLoading.value = false
  }
}

async function onRefresh() {
  if (isRefreshing.value) return

  isRefreshing.value = true
  try {
    await loadRecords(true)
  } catch (error) {
    console.error('Refresh failed:', error)
  } finally {
    isRefreshing.value = false
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
    alert('请输入数值')
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
      alert(isEdit ? '更新成功' : '添加成功')
      closeModal()
      loadRecords(true)
    }
  } catch (error) {
    console.error('Failed to save record:', error)
    alert('保存失败')
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
      alert('删除成功')
      showDeleteModal.value = false
      loadRecords(true)
    }
  } catch (error) {
    console.error('Failed to delete record:', error)
    alert('删除失败')
  }
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
  padding: 40px 15px 15px;
  border-bottom: 1px solid #f0f0f0;
}

.header-left,
.header-right {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
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
}

.empty-desc {
  font-size: 14px;
  color: #999999;
  margin-bottom: 30px;
}

.records-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.refresh-indicator {
  text-align: center;
  padding: 10px 0;
}

.refresh-text {
  font-size: 13px;
  color: #999999;
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
  cursor: pointer;
}

.record-item:last-child {
  border-bottom: none;
}

.record-item:hover {
  background: #f8f8f8;
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
  cursor: pointer;
}

.no-more-text {
  font-size: 13px;
  color: #999999;
}

// Modal styles
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

.modal,
.view-modal,
.confirm-modal {
  background: #ffffff;
  border-radius: 20px 20px 0 0;
  padding: 20px;
  width: 100%;
  max-width: 500px;
  max-height: 80vh;
  overflow-y: auto;
  position: fixed;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
}

.view-modal,
.confirm-modal {
  border-radius: 20px;
  width: 280px;
  max-width: 90%;
}

.modal-header,
.view-header,
.confirm-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.modal-title,
.view-title,
.confirm-title {
  font-size: 18px;
  font-weight: 500;
  color: #333333;
}

.modal-close,
.view-close {
  font-size: 28px;
  color: #999999;
  line-height: 1;
  cursor: pointer;
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
  border: 1px solid #e0e0e0;
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
  cursor: pointer;
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
  cursor: pointer;
}

.btn-primary {
  background: #667eea;
  color: #ffffff;
}

.btn-primary:hover {
  opacity: 0.9;
}

.btn-secondary {
  background: #f0f0f0;
  color: #666666;
}

.btn-secondary:hover {
  background: #e0e0e0;
}

.btn-danger {
  background: #fff0f0;
  color: #ff4d4f;
}

.btn-danger:hover {
  background: #ffe0e0;
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

/* Dark mode styles */
:global(.dark-mode) .container {
  background: #1a1a1a;
}

:global(.dark-mode) .header {
  background: #2a2a2a;
  border-bottom-color: #3a3a3a;
}

:global(.dark-mode) .back-icon,
:global(.dark-mode) .add-icon,
:global(.dark-mode) .header-title {
  color: #e0e0e0;
}

:global(.dark-mode) .record-group {
  background: #2a2a2a;
}

:global(.dark-mode) .group-header {
  background: #3a3a3a;
  border-bottom-color: #4a4a4a;
}

:global(.dark-mode) .group-title,
:global(.dark-mode) .record-name {
  color: #e0e0e0;
}

:global(.dark-mode) .record-item {
  border-bottom-color: #3a3a3a;
}

:global(.dark-mode) .record-item:hover {
  background: #3a3a3a;
}

:global(.dark-mode) .modal,
:global(.dark-mode) .view-modal,
:global(.dark-mode) .confirm-modal {
  background: #2a2a2a;
}

:global(.dark-mode) .modal-title,
:global(.dark-mode) .view-title,
:global(.dark-mode) .confirm-title {
  color: #e0e0e0;
}

:global(.dark-mode) .modal-close,
:global(.dark-mode) .view-close {
  color: #888888;
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

:global(.dark-mode) .type-option {
  background: #3a3a3a;
  border-color: #4a4a4a;
}

:global(.dark-mode) .option-text {
  color: #aaaaaa;
}

:global(.dark-mode) .view-value {
  color: #e0e0e0;
}

:global(.dark-mode) .confirm-message {
  color: #e0e0e0;
}

:global(.dark-mode) .btn-secondary {
  background: #3a3a3a;
  color: #aaaaaa;
}

:global(.dark-mode) .btn-danger {
  background: #3a2a2a;
  color: #ff6b6b;
}
</style>
