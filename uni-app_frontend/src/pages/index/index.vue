<template>
  <view class="container">
    <view class="header">
      <text class="title">AI舌诊智能诊断</text>
      <text class="subtitle">基于人工智能的中医舌诊分析</text>
    </view>

    <view class="content">
      <!-- User info section -->
      <view class="user-card" v-if="userStore.isLoggedIn && userStore.userInfo">
        <view class="user-info">
          <image
            class="avatar"
            :src="userStore.userInfo.avatar_url || '/static/default-avatar.png'"
            mode="aspectFill"
          />
          <view class="user-details">
            <text class="nickname">{{ userStore.userInfo.nickname || '用户' }}</text>
            <text class="phone">{{ maskPhone(userStore.userInfo.phone) }}</text>
          </view>
        </view>
        <view class="user-actions">
          <text class="action-link" @click="goToProfile">个人中心</text>
        </view>
      </view>

      <!-- Welcome card -->
      <view class="welcome-card">
        <text class="logo">🏥</text>
        <text class="welcome-text">欢迎使用AI舌诊系统</text>
        <text class="description">通过拍照上传舌部照片，AI将为您分析舌象特征并给出健康建议</text>
      </view>

      <!-- Start diagnosis button -->
      <view class="action-buttons">
        <button class="btn btn-primary" @click="startDiagnosis">
          开始诊断
        </button>
      </view>

      <!-- Feature grid -->
      <view class="feature-grid">
        <view class="feature-item" @click="viewHistory">
          <view class="feature-icon">📋</view>
          <text class="feature-title">历史记录</text>
          <text class="feature-desc">查看诊断历史</text>
        </view>

        <view class="feature-item" @click="viewHealthRecords">
          <view class="feature-icon">📊</view>
          <text class="feature-title">健康档案</text>
          <text class="feature-desc">管理健康数据</text>
        </view>

        <view class="feature-item" @click="viewStatistics">
          <view class="feature-icon">📈</view>
          <text class="feature-title">健康趋势</text>
          <text class="feature-desc">查看健康变化</text>
        </view>

        <view class="feature-item" @click="goToSettings">
          <view class="feature-icon">⚙️</view>
          <text class="feature-title">设置</text>
          <text class="feature-desc">应用设置</text>
        </view>
      </view>

      <!-- Login prompt for non-logged-in users -->
      <view class="info-section" v-if="!userStore.isLoggedIn">
        <text class="info-text">登录后可保存诊断记录并查看历史</text>
        <view class="info-actions">
          <button class="btn btn-text" @click="goToLogin">登录</button>
          <text class="divider">|</text>
          <button class="btn btn-text" @click="goToRegister">注册</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useUserStore } from '@/store'

const userStore = useUserStore()

onMounted(() => {
  // Fetch user info if logged in
  if (userStore.isLoggedIn && !userStore.userInfo) {
    userStore.fetchUserInfo()
  }
})

function maskPhone(phone: string): string {
  if (!phone) return ''
  return phone.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2')
}

function startDiagnosis() {
  // Navigate to diagnosis page (to be implemented in US-143)
  uni.navigateTo({
    url: '/pages/diagnosis/index'
  })
}

function viewHistory() {
  if (!userStore.isLoggedIn) {
    uni.showToast({
      title: '请先登录',
      icon: 'none'
    })
    goToLogin()
    return
  }
  // Navigate to history page (to be implemented in US-150)
  uni.navigateTo({
    url: '/pages/history/index'
  })
}

function viewHealthRecords() {
  if (!userStore.isLoggedIn) {
    uni.showToast({
      title: '请先登录',
      icon: 'none'
    })
    goToLogin()
    return
  }
  // Navigate to health records page (to be implemented in US-153)
  uni.navigateTo({
    url: '/pages/health-records/index'
  })
}

function viewStatistics() {
  if (!userStore.isLoggedIn) {
    uni.showToast({
      title: '请先登录',
      icon: 'none'
    })
    goToLogin()
    return
  }
  // Navigate to statistics/trends page
  uni.navigateTo({
    url: '/pages/statistics/index'
  })
}

function goToSettings() {
  // Navigate to settings page (to be implemented in US-154)
  uni.navigateTo({
    url: '/pages/settings/index'
  })
}

function goToProfile() {
  // Navigate to profile page (to be implemented in US-152)
  uni.navigateTo({
    url: '/pages/profile/index'
  })
}

function goToLogin() {
  uni.navigateTo({
    url: '/pages/login/index'
  })
}

function goToRegister() {
  uni.navigateTo({
    url: '/pages/register/index'
  })
}
</script>

<style lang="scss" scoped>
.container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.header {
  padding: 40px 30px 20px;
  text-align: center;
}

.title {
  font-size: 28px;
  font-weight: bold;
  color: #ffffff;
  display: block;
  margin-bottom: 8px;
}

.subtitle {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.8);
  display: block;
}

.content {
  flex: 1;
  padding: 20px 20px 40px;
}

.user-card {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 16px;
  padding: 20px;
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 15px;
}

.avatar {
  width: 50px;
  height: 50px;
  border-radius: 25px;
  background: #f0f0f0;
}

.user-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nickname {
  font-size: 16px;
  font-weight: 500;
  color: #333333;
}

.phone {
  font-size: 13px;
  color: #999999;
}

.user-actions {
  display: flex;
  align-items: center;
}

.action-link {
  font-size: 14px;
  color: #667eea;
}

.welcome-card {
  background: #ffffff;
  border-radius: 16px;
  padding: 30px 20px;
  text-align: center;
  margin-bottom: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.logo {
  font-size: 60px;
  margin-bottom: 15px;
}

.welcome-text {
  font-size: 20px;
  font-weight: bold;
  color: #333333;
  margin-bottom: 10px;
  display: block;
}

.description {
  font-size: 14px;
  color: #666666;
  line-height: 1.6;
  display: block;
  padding: 0 10px;
}

.action-buttons {
  margin-bottom: 20px;
}

.btn {
  width: 100%;
  height: 50px;
  border-radius: 25px;
  font-size: 18px;
  font-weight: 500;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #ffffff;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.btn-text {
  background: transparent;
  color: #667eea;
  font-size: 15px;
  height: auto;
  padding: 0;
  display: inline;
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 15px;
  margin-bottom: 20px;
}

.feature-item {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 12px;
  padding: 20px 15px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  transition: transform 0.2s;
}

.feature-item:active {
  transform: scale(0.98);
}

.feature-icon {
  font-size: 36px;
  margin-bottom: 10px;
}

.feature-title {
  font-size: 14px;
  font-weight: 500;
  color: #333333;
  margin-bottom: 5px;
  display: block;
}

.feature-desc {
  font-size: 12px;
  color: #999999;
  display: block;
}

.info-section {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 12px;
  padding: 20px;
  text-align: center;
  backdrop-filter: blur(10px);
}

.info-text {
  font-size: 14px;
  color: #ffffff;
  display: block;
  margin-bottom: 15px;
}

.info-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 15px;
}

.divider {
  color: rgba(255, 255, 255, 0.6);
}

.info-actions .btn-text {
  color: #ffffff;
  font-size: 15px;
}
</style>
