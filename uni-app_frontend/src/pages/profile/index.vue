<template>
  <div class="container">
    <!-- Header with profile info -->
    <div class="header">
      <div class="header-bg"></div>
      <div class="profile-section">
        <div class="avatar-container" @click="handleAvatarClick">
          <img
            class="avatar"
            :src="userInfo?.avatar_url || defaultAvatar"
            alt="Avatar"
          />
          <div class="avatar-edit">
            <span class="edit-icon">📷</span>
          </div>
        </div>
        <span class="nickname">{{ userInfo?.nickname || '未登录' }}</span>
        <span class="phone" v-if="userInfo">{{ formatPhone(userInfo.phone) }}</span>
        <button class="btn-login" v-else @click="goToLogin">立即登录</button>
      </div>
    </div>

    <!-- Stats section -->
    <div class="stats-section" v-if="userInfo">
      <div class="stat-item" @click="goToHistory">
        <span class="stat-value">{{ diagnosisCount }}</span>
        <span class="stat-label">诊断次数</span>
      </div>
      <div class="stat-divider"></div>
      <div class="stat-item">
        <span class="stat-value">{{ riskCount }}</span>
        <span class="stat-label">风险记录</span>
      </div>
      <div class="stat-divider"></div>
      <div class="stat-item" @click="goToHealthRecords">
        <span class="stat-value">{{ healthRecordCount }}</span>
        <span class="stat-label">健康档案</span>
      </div>
    </div>

    <!-- Menu section -->
    <div class="menu-section" v-if="userInfo">
      <!-- Health records entry -->
      <div class="menu-item" @click="goToHealthRecords">
        <div class="item-left">
          <span class="item-icon">📋</span>
          <span class="item-label">健康档案</span>
        </div>
        <div class="item-right">
          <span class="item-value">{{ healthRecordCount }} 条记录</span>
          <span class="arrow">›</span>
        </div>
      </div>

      <!-- Settings entry -->
      <div class="menu-item" @click="goToSettings">
        <div class="item-left">
          <span class="item-icon">⚙️</span>
          <span class="item-label">设置</span>
        </div>
        <div class="item-right">
          <span class="arrow">›</span>
        </div>
      </div>

      <!-- About entry -->
      <div class="menu-item" @click="showAbout">
        <div class="item-left">
          <span class="item-icon">ℹ️</span>
          <span class="item-label">关于我们</span>
        </div>
        <div class="item-right">
          <span class="item-value">v{{ appVersion }}</span>
          <span class="arrow">›</span>
        </div>
      </div>
    </div>

    <!-- Logout button -->
    <div class="logout-section" v-if="userInfo">
      <button class="btn-logout" @click="handleLogout">退出登录</button>
    </div>

    <!-- Guest section -->
    <div class="guest-section" v-else>
      <div class="guest-menu-item" @click="goToLogin">
        <div class="item-left">
          <span class="item-icon">🔑</span>
          <span class="item-label">登录 / 注册</span>
        </div>
        <div class="item-right">
          <span class="arrow">›</span>
        </div>
      </div>
      <div class="guest-menu-item" @click="goToSettings">
        <div class="item-left">
          <span class="item-icon">⚙️</span>
          <span class="item-label">设置</span>
        </div>
        <div class="item-right">
          <span class="arrow">›</span>
        </div>
      </div>
      <div class="guest-menu-item" @click="showAbout">
        <div class="item-left">
          <span class="item-icon">ℹ️</span>
          <span class="item-label">关于我们</span>
        </div>
        <div class="item-right">
          <span class="item-value">v{{ appVersion }}</span>
          <span class="arrow">›</span>
        </div>
      </div>
    </div>

    <!-- About modal -->
    <div class="modal-overlay" v-if="showAboutModal" @click="showAboutModal = false">
      <div class="about-modal" @click.stop>
        <div class="about-header">
          <span class="about-title">关于 AI 舌诊</span>
          <span class="about-close" @click="showAboutModal = false">×</span>
        </div>
        <div class="about-content">
          <span class="about-logo">👅</span>
          <span class="about-name">AI 舌诊智能诊断系统</span>
          <span class="about-version">版本 {{ appVersion }}</span>
          <div class="about-divider"></div>
          <span class="about-desc">
            基于深度学习的中医舌诊智能诊断系统，提供舌象分析、证型辨识和健康建议。
          </span>
          <div class="about-info">
            <span class="info-item">© 2026 AI 舌诊团队</span>
            <span class="info-item">基于 PaddlePaddle + 文心大模型</span>
          </div>
        </div>
        <button class="btn btn-primary" @click="showAboutModal = false">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore, useDiagnosisStore } from '@/store'

const router = useRouter()
const userStore = useUserStore()
const diagnosisStore = useDiagnosisStore()

// State
const userInfo = computed(() => userStore.userInfo)
const isLoggedIn = computed(() => userStore.isLoggedIn)
const showAboutModal = ref(false)
const appVersion = ref('3.0.0')
const defaultAvatar = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48Y2lyY2xlIGN4PSI1MCIgY3k9IjUwIiByPSI1MCIgZmlsbD0iI2YwZjBmMCIvPjxjaXJjbGUgY3g9IjUwIiBjeT0iNDAiIHI9IjIwIiBmaWxsPSIjZTB3MGUwIi8+PHBhdGggZD0iTTIwIDkwIFEzMCA3MCA1MCA3MCBRNzAgNzAgODAgOTAgTDgwIDEwMCBMMjAgMTAwIFoiIGZpbGw9IiNlMGUwZTAiLz48L3N2Zz4='

// Computed
const diagnosisCount = computed(() => {
  return diagnosisStore.diagnosisHistory.length
})

const riskCount = computed(() => {
  return diagnosisStore.diagnosisHistory.filter(d => d.has_risk).length
})

const healthRecordCount = ref(0) // TODO: Fetch from health records API

// Functions
function formatPhone(phone: string): string {
  if (!phone) return ''
  const match = phone.match(/^(\d{3})(\d{4})(\d{4})$/)
  if (match) {
    return `${match[1]}****${match[3]}`
  }
  return phone
}

function handleAvatarClick() {
  if (!isLoggedIn.value) {
    goToLogin()
    return
  }
  // TODO: Implement avatar upload/crop
  alert('头像编辑功能开发中')
}

function goToLogin() {
  router.push('/login')
}

function goToHistory() {
  router.push('/history')
}

function goToHealthRecords() {
  router.push('/health-records')
}

function goToSettings() {
  router.push('/settings')
}

function showAbout() {
  showAboutModal.value = true
}

function handleLogout() {
  if (confirm('确定要退出登录吗？')) {
    userStore.logout()
    alert('已退出登录')
  }
}

// Lifecycle
onMounted(() => {
  if (isLoggedIn.value && !userInfo.value) {
    userStore.fetchUserInfo()
  }
  // TODO: Fetch health records count
})
</script>

<style lang="scss" scoped>
.container {
  min-height: 100vh;
  background: #f5f5f5;
}

.header {
  position: relative;
  background: #ffffff;
  padding-bottom: 30px;
  margin-bottom: 10px;
}

.header-bg {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 200px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.profile-section {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 100px;
}

.avatar-container {
  position: relative;
  width: 100px;
  height: 100px;
  margin-bottom: 15px;
  cursor: pointer;
}

.avatar {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  border: 4px solid #ffffff;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  object-fit: cover;
}

.avatar-edit {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 32px;
  height: 32px;
  background: #667eea;
  border-radius: 50%;
  border: 3px solid #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.edit-icon {
  font-size: 16px;
}

.nickname {
  font-size: 20px;
  font-weight: 500;
  color: #333333;
  margin-bottom: 5px;
}

.phone {
  font-size: 14px;
  color: #999999;
}

.btn-login {
  margin-top: 20px;
  width: 120px;
  height: 40px;
  border-radius: 20px;
  background: #667eea;
  color: #ffffff;
  font-size: 14px;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.stats-section {
  background: #ffffff;
  display: flex;
  align-items: center;
  justify-content: space-around;
  padding: 25px 0;
  margin-bottom: 10px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  cursor: pointer;
}

.stat-value {
  font-size: 24px;
  font-weight: 500;
  color: #667eea;
  margin-bottom: 5px;
}

.stat-label {
  font-size: 13px;
  color: #999999;
}

.stat-divider {
  width: 1px;
  height: 40px;
  background: #f0f0f0;
}

.menu-section,
.guest-section {
  background: #ffffff;
  margin-bottom: 10px;
}

.menu-item,
.guest-menu-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 20px;
  border-bottom: 1px solid #f5f5f5;
  cursor: pointer;
}

.menu-item:last-child,
.guest-menu-item:last-child {
  border-bottom: none;
}

.menu-item:hover,
.guest-menu-item:hover {
  background: #f8f8f8;
}

.item-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.item-icon {
  font-size: 20px;
}

.item-label {
  font-size: 15px;
  color: #333333;
}

.item-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.item-value {
  font-size: 13px;
  color: #999999;
}

.arrow {
  font-size: 20px;
  color: #cccccc;
}

.logout-section {
  padding: 20px;
}

.btn-logout {
  width: 100%;
  height: 48px;
  border-radius: 24px;
  background: #ffffff;
  border: 1px solid #e0e0e0;
  color: #ff4d4f;
  font-size: 15px;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.btn-logout:hover {
  background: #fff0f0;
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

.about-modal {
  background: #ffffff;
  border-radius: 20px;
  padding: 25px;
  width: 280px;
  max-width: 90%;
}

.about-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.about-title {
  font-size: 18px;
  font-weight: 500;
  color: #333333;
}

.about-close {
  font-size: 28px;
  color: #999999;
  line-height: 1;
  cursor: pointer;
}

.about-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.about-logo {
  font-size: 60px;
  margin-bottom: 15px;
}

.about-name {
  font-size: 16px;
  font-weight: 500;
  color: #333333;
  margin-bottom: 5px;
}

.about-version {
  font-size: 13px;
  color: #999999;
  margin-bottom: 15px;
}

.about-divider {
  width: 100%;
  height: 1px;
  background: #f0f0f0;
  margin-bottom: 15px;
}

.about-desc {
  font-size: 13px;
  color: #666666;
  line-height: 1.6;
  margin-bottom: 15px;
}

.about-info {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.info-item {
  font-size: 12px;
  color: #999999;
}

.btn {
  width: 100%;
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
  margin-top: 20px;
}

.btn-primary:hover {
  opacity: 0.9;
}

/* Dark mode styles */
:global(.dark-mode) .container {
  background: #1a1a1a;
}

:global(.dark-mode) .header {
  background: #2a2a2a;
}

:global(.dark-mode) .header-bg {
  background: linear-gradient(135deg, #4a5a9a 0%, #5a4a7a 100%);
}

:global(.dark-mode) .avatar {
  border-color: #2a2a2a;
}

:global(.dark-mode) .avatar-edit {
  background: #5a6fd8;
  border-color: #2a2a2a;
}

:global(.dark-mode) .nickname {
  color: #e0e0e0;
}

:global(.dark-mode) .phone {
  color: #888888;
}

:global(.dark-mode) .btn-login {
  background: #5a6fd8;
}

:global(.dark-mode) .stats-section {
  background: #2a2a2a;
}

:global(.dark-mode) .stat-value {
  color: #8b9cf5;
}

:global(.dark-mode) .stat-label {
  color: #888888;
}

:global(.dark-mode) .stat-divider {
  background: #3a3a3a;
}

:global(.dark-mode) .menu-section,
:global(.dark-mode) .guest-section {
  background: #2a2a2a;
}

:global(.dark-mode) .menu-item,
:global(.dark-mode) .guest-menu-item {
  border-bottom-color: #3a3a3a;
}

:global(.dark-mode) .menu-item:hover,
:global(.dark-mode) .guest-menu-item:hover {
  background: #3a3a3a;
}

:global(.dark-mode) .item-label {
  color: #e0e0e0;
}

:global(.dark-mode) .item-value {
  color: #888888;
}

:global(.dark-mode) .arrow {
  color: #666666;
}

:global(.dark-mode) .btn-logout {
  background: #2a2a2a;
  border-color: #3a3a3a;
  color: #ff6b6b;
}

:global(.dark-mode) .about-modal {
  background: #2a2a2a;
}

:global(.dark-mode) .about-title {
  color: #e0e0e0;
}

:global(.dark-mode) .about-close {
  color: #888888;
}

:global(.dark-mode) .about-name {
  color: #e0e0e0;
}

:global(.dark-mode) .about-version {
  color: #888888;
}

:global(.dark-mode) .about-divider {
  background: #3a3a3a;
}

:global(.dark-mode) .about-desc {
  color: #aaaaaa;
}

:global(.dark-mode) .info-item {
  color: #888888;
}

:global(.dark-mode) .btn-primary {
  background: #5a6fd8;
}
</style>
