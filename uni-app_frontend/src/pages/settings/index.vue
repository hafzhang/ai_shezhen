<template>
  <view class="container">
    <view class="header">
      <view class="header-left" @click="goBack">
        <text class="back-icon">←</text>
      </view>
      <text class="header-title">设置</text>
      <view class="header-right"></view>
    </view>

    <view class="content">
      <!-- Account section -->
      <view class="section" v-if="isLoggedIn">
        <view class="section-header">
          <text class="section-title">账号设置</text>
        </view>
        <view class="menu-item" @click="editProfile">
          <view class="item-left">
            <text class="item-icon">👤</text>
            <text class="item-label">个人资料</text>
          </view>
          <view class="item-right">
            <text class="arrow">›</text>
          </view>
        </view>
        <view class="menu-item" @click="changePassword">
          <view class="item-left">
            <text class="item-icon">🔒</text>
            <text class="item-label">修改密码</text>
          </view>
          <view class="item-right">
            <text class="arrow">›</text>
          </view>
        </view>
      </view>

      <!-- General section -->
      <view class="section">
        <view class="section-header">
          <text class="section-title">通用设置</text>
        </view>
        <view class="menu-item">
          <view class="item-left">
            <text class="item-icon">🌙</text>
            <text class="item-label">深色模式</text>
          </view>
          <view class="item-right">
            <switch
              :checked="darkModeEnabled"
              @change="toggleDarkMode"
              color="#667eea"
              style="transform: scale(0.8)"
            />
          </view>
        </view>
        <view class="menu-item">
          <view class="item-left">
            <text class="item-icon">🌐</text>
            <text class="item-label">语言</text>
          </view>
          <view class="item-right">
            <text class="item-value">简体中文</text>
            <text class="arrow">›</text>
          </view>
        </view>
      </view>

      <!-- Storage section -->
      <view class="section">
        <view class="section-header">
          <text class="section-title">存储与缓存</text>
        </view>
        <view class="menu-item">
          <view class="item-left">
            <text class="item-icon">💾</text>
            <text class="item-label">缓存大小</text>
          </view>
          <view class="item-right">
            <text class="item-value">{{ cacheSize }}</text>
          </view>
        </view>
        <view class="menu-item" @click="clearCache">
          <view class="item-left">
            <text class="item-icon">🗑️</text>
            <text class="item-label">清除缓存</text>
          </view>
          <view class="item-right">
            <text class="arrow">›</text>
          </view>
        </view>
      </view>

      <!-- Legal section -->
      <view class="section">
        <view class="section-header">
          <text class="section-title">法律条款</text>
        </view>
        <view class="menu-item" @click="openPrivacyPolicy">
          <view class="item-left">
            <text class="item-icon">🛡️</text>
            <text class="item-label">隐私政策</text>
          </view>
          <view class="item-right">
            <text class="arrow">›</text>
          </view>
        </view>
        <view class="menu-item" @click="openUserAgreement">
          <view class="item-left">
            <text class="item-icon">📜</text>
            <text class="item-label">用户协议</text>
          </view>
          <view class="item-right">
            <text class="arrow">›</text>
          </view>
        </view>
      </view>

      <!-- About section -->
      <view class="section">
        <view class="section-header">
          <text class="section-title">关于</text>
        </view>
        <view class="menu-item" @click="openAbout">
          <view class="item-left">
            <text class="item-icon">ℹ️</text>
            <text class="item-label">关于我们</text>
          </view>
          <view class="item-right">
            <text class="item-value">v{{ appVersion }}</text>
            <text class="arrow">›</text>
          </view>
        </view>
        <view class="menu-item" @click="openFeedback">
          <view class="item-left">
            <text class="item-icon">💬</text>
            <text class="item-label">意见反馈</text>
          </view>
          <view class="item-right">
            <text class="arrow">›</text>
          </view>
        </view>
      </view>

      <!-- Logout button -->
      <view class="logout-section" v-if="isLoggedIn">
        <button class="btn-logout" @click="handleLogout">退出登录</button>
      </view>

      <!-- Version info -->
      <view class="version-info">
        <text class="version-text">AI 舌诊智能诊断系统 v{{ appVersion }}</text>
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

    <!-- Clear cache modal -->
    <u-popup v-model:show="showClearCacheModal" mode="center" :round="20">
      <view class="confirm-modal">
        <view class="confirm-header">
          <text class="confirm-title">清除缓存</text>
        </view>
        <view class="confirm-content">
          <text class="confirm-message">确定要清除所有缓存吗？</text>
        </view>
        <view class="confirm-actions">
          <button class="btn btn-secondary" @click="showClearCacheModal = false">取消</button>
          <button class="btn btn-primary" @click="confirmClearCache">确定</button>
        </view>
      </view>
    </u-popup>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useUserStore } from '@/store'
import { useDarkMode } from '@/composables'

const userStore = useUserStore()
const { isDark, setDarkMode } = useDarkMode()

// State
const isLoggedIn = computed(() => userStore.isLoggedIn)
const darkModeEnabled = computed(() => isDark.value)
const cacheSize = ref('0 MB')
const appVersion = ref('3.0.0')
const showAboutModal = ref(false)
const showClearCacheModal = ref(false)

// Functions
function goBack() {
  uni.navigateBack()
}

function editProfile() {
  uni.showToast({
    title: '个人资料编辑功能开发中',
    icon: 'none'
  })
}

function changePassword() {
  uni.showToast({
    title: '修改密码功能开发中',
    icon: 'none'
  })
}

function toggleDarkMode(e: any) {
  const newMode = e.detail.value ? 'dark' : 'auto'
  setDarkMode(newMode)
  uni.showToast({
    title: e.detail.value ? '已开启深色模式' : '已关闭深色模式',
    icon: 'none'
  })
}

function clearCache() {
  showClearCacheModal.value = true
}

function confirmClearCache() {
  showClearCacheModal.value = false
  // Simulate clearing cache
  uni.showLoading({
    title: '清除中...'
  })
  setTimeout(() => {
    uni.hideLoading()
    cacheSize.value = '0 MB'
    uni.showToast({
      title: '缓存已清除',
      icon: 'success'
    })
  }, 1000)
}

function openPrivacyPolicy() {
  uni.navigateTo({
    url: '/pages/privacy/index'
  })
}

function openUserAgreement() {
  uni.navigateTo({
    url: '/pages/terms/index'
  })
}

function openAbout() {
  showAboutModal.value = true
}

function openFeedback() {
  uni.showToast({
    title: '意见反馈功能开发中',
    icon: 'none'
  })
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
        setTimeout(() => {
          uni.navigateBack()
        }, 1500)
      }
    }
  })
}

// Calculate cache size on mount
onMounted(() => {
  // Simulate cache size calculation
  // In real app, calculate actual storage size
  const mockSize = (Math.random() * 50).toFixed(1)
  cacheSize.value = `${mockSize} MB`
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
  padding: 15px 0;
}

.section {
  background: #ffffff;
  margin-bottom: 10px;
}

.section-header {
  padding: 15px 20px 10px;
}

.section-title {
  font-size: 13px;
  color: #999999;
  font-weight: 500;
}

.menu-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 20px;
  border-bottom: 1px solid #f5f5f5;
}

.menu-item:last-child {
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
  padding: 20px 15px;
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

.version-info {
  padding: 20px;
  text-align: center;
}

.version-text {
  font-size: 12px;
  color: #cccccc;
}

.about-modal,
.confirm-modal {
  background: #ffffff;
  border-radius: 20px;
  padding: 25px;
  width: 280px;
}

.about-header,
.confirm-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.about-title,
.confirm-title {
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

.confirm-content {
  padding: 10px 0;
}

.confirm-message {
  font-size: 15px;
  color: #333333;
  text-align: center;
  line-height: 1.6;
}

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

/* Dark mode styles */
:global(.dark-mode) .container {
  background: #1a1a1a;
}

:global(.dark-mode) .header {
  background: #2a2a2a;
  border-bottom-color: #3a3a3a;
}

:global(.dark-mode) .back-icon,
:global(.dark-mode) .header-title {
  color: #e0e0e0;
}

:global(.dark-mode) .section {
  background: #2a2a2a;
}

:global(.dark-mode) .section-title {
  color: #888888;
}

:global(.dark-mode) .menu-item {
  border-bottom-color: #3a3a3a;
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

:global(.dark-mode) .about-modal,
:global(.dark-mode) .confirm-modal {
  background: #2a2a2a;
}

:global(.dark-mode) .about-title,
:global(.dark-mode) .confirm-title {
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

:global(.dark-mode) .confirm-message {
  color: #e0e0e0;
}

:global(.dark-mode) .btn-secondary {
  background: #3a3a3a;
  color: #aaaaaa;
}

:global(.dark-mode) .version-text {
  color: #666666;
}
</style>
