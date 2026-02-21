<template>
  <view class="container">
    <!-- Header with profile info -->
    <view class="header">
      <view class="header-bg"></view>
      <view class="profile-section">
        <view class="avatar-container" @click="handleAvatarClick">
          <image
            class="avatar"
            :src="userInfo?.avatar_url || defaultAvatar"
            mode="aspectFill"
          />
          <view class="avatar-edit">
            <text class="edit-icon">📷</text>
          </view>
        </view>
        <text class="nickname">{{ userInfo?.nickname || '未登录' }}</text>
        <text class="phone" v-if="userInfo">{{ formatPhone(userInfo.phone) }}</text>
        <button class="btn-login" v-else @click="goToLogin">立即登录</button>
      </view>
    </view>

    <!-- Stats section -->
    <view class="stats-section" v-if="userInfo">
      <view class="stat-item" @click="goToHistory">
        <text class="stat-value">{{ diagnosisCount }}</text>
        <text class="stat-label">诊断次数</text>
      </view>
      <view class="stat-divider"></view>
      <view class="stat-item">
        <text class="stat-value">{{ riskCount }}</text>
        <text class="stat-label">风险记录</text>
      </view>
      <view class="stat-divider"></view>
      <view class="stat-item" @click="goToHealthRecords">
        <text class="stat-value">{{ healthRecordCount }}</text>
        <text class="stat-label">健康档案</text>
      </view>
    </view>

    <!-- Menu section -->
    <view class="menu-section" v-if="userInfo">
      <!-- Health records entry -->
      <view class="menu-item" @click="goToHealthRecords">
        <view class="item-left">
          <text class="item-icon">📋</text>
          <text class="item-label">健康档案</text>
        </view>
        <view class="item-right">
          <text class="item-value">{{ healthRecordCount }} 条记录</text>
          <text class="arrow">›</text>
        </view>
      </view>

      <!-- Settings entry -->
      <view class="menu-item" @click="goToSettings">
        <view class="item-left">
          <text class="item-icon">⚙️</text>
          <text class="item-label">设置</text>
        </view>
        <view class="item-right">
          <text class="arrow">›</text>
        </view>
      </view>

      <!-- About entry -->
      <view class="menu-item" @click="showAbout">
        <view class="item-left">
          <text class="item-icon">ℹ️</text>
          <text class="item-label">关于我们</text>
        </view>
        <view class="item-right">
          <text class="item-value">v{{ appVersion }}</text>
          <text class="arrow">›</text>
        </view>
      </view>
    </view>

    <!-- Logout button -->
    <view class="logout-section" v-if="userInfo">
      <button class="btn-logout" @click="handleLogout">退出登录</button>
    </view>

    <!-- Guest section -->
    <view class="guest-section" v-else>
      <view class="guest-menu-item" @click="goToLogin">
        <view class="item-left">
          <text class="item-icon">🔑</text>
          <text class="item-label">登录 / 注册</text>
        </view>
        <view class="item-right">
          <text class="arrow">›</text>
        </view>
      </view>
      <view class="guest-menu-item" @click="goToSettings">
        <view class="item-left">
          <text class="item-icon">⚙️</text>
          <text class="item-label">设置</text>
        </view>
        <view class="item-right">
          <text class="arrow">›</text>
        </view>
      </view>
      <view class="guest-menu-item" @click="showAbout">
        <view class="item-left">
          <text class="item-icon">ℹ️</text>
          <text class="item-label">关于我们</text>
        </view>
        <view class="item-right">
          <text class="item-value">v{{ appVersion }}</text>
          <text class="arrow">›</text>
        </view>
      </view>
    </view>

    <!-- About modal -->
    <u-popup v-model:show="showAboutModal" mode="center" :round="20">
      <view class="about-modal">
        <view class="about-header">
          <text class="about-title">关于 AI 舌诊</text>
          <text class="about-close" @click="showAboutModal = false">×</text>
        </view>
        <view class="about-content">
          <text class="about-logo">👅</text>
          <text class="about-name">AI 舌诊智能诊断系统</text>
          <text class="about-version">版本 {{ appVersion }}</text>
          <view class="about-divider"></view>
          <text class="about-desc">
            基于深度学习的中医舌诊智能诊断系统，提供舌象分析、证型辨识和健康建议。
          </text>
          <view class="about-info">
            <text class="info-item">© 2026 AI 舌诊团队</text>
            <text class="info-item">基于 PaddlePaddle + 文心大模型</text>
          </view>
        </view>
        <button class="btn btn-primary" @click="showAboutModal = false">关闭</button>
      </view>
    </u-popup>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useUserStore, useDiagnosisStore } from '@/store'

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
  uni.showToast({
    title: '头像编辑功能开发中',
    icon: 'none'
  })
}

function goToLogin() {
  uni.navigateTo({
    url: '/pages/login/index'
  })
}

function goToHistory() {
  uni.switchTab({
    url: '/pages/history/index'
  })
}

function goToHealthRecords() {
  if (!isLoggedIn.value) {
    uni.showToast({
      title: '请先登录',
      icon: 'none'
    })
    setTimeout(() => {
      goToLogin()
    }, 1500)
    return
  }
  uni.navigateTo({
    url: '/pages/health-records/index'
  })
}

function goToSettings() {
  uni.navigateTo({
    url: '/pages/settings/index'
  })
}

function showAbout() {
  showAboutModal.value = true
}

function handleLogout() {
  uni.showModal({
    title: '退出登录',
    content: '确定要退出登录吗？',
    success: (res) => {
      if (res.confirm) {
        userStore.logout()
        uni.showToast({
          title: '已退出登录',
          icon: 'success'
        })
      }
    }
  })
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
}

.avatar {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  border: 4px solid #ffffff;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
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
}

.menu-item:last-child,
.guest-menu-item:last-child {
  border-bottom: none;
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
}

.about-modal {
  background: #ffffff;
  border-radius: 20px;
  padding: 25px;
  width: 280px;
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
}

.btn-primary {
  background: #667eea;
  color: #ffffff;
  margin-top: 20px;
}
</style>
