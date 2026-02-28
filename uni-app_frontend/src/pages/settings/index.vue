<template>
  <div class="container">
    <div class="header">
      <div class="header-left" @click="goBack">
        <span class="back-icon">←</span>
      </div>
      <span class="header-title">设置</span>
      <div class="header-right"></div>
    </div>

    <div class="content">
      <!-- Account section -->
      <div class="section" v-if="isLoggedIn">
        <div class="section-header">
          <span class="section-title">账号设置</span>
        </div>
        <div class="menu-item" @click="editProfile">
          <div class="item-left">
            <span class="item-icon">👤</span>
            <span class="item-label">个人资料</span>
          </div>
          <div class="item-right">
            <span class="arrow">›</span>
          </div>
        </div>
        <div class="menu-item" @click="changePassword">
          <div class="item-left">
            <span class="item-icon">🔒</span>
            <span class="item-label">修改密码</span>
          </div>
          <div class="item-right">
            <span class="arrow">›</span>
          </div>
        </div>
      </div>

      <!-- General section -->
      <div class="section">
        <div class="section-header">
          <span class="section-title">通用设置</span>
        </div>
        <div class="menu-item">
          <div class="item-left">
            <span class="item-icon">🌙</span>
            <span class="item-label">深色模式</span>
          </div>
          <div class="item-right">
            <input
              type="checkbox"
              class="switch"
              :checked="darkModeEnabled"
              @change="toggleDarkMode"
            />
          </div>
        </div>
        <div class="menu-item" @click="showLanguageModal = true">
          <div class="item-left">
            <span class="item-icon">🌐</span>
            <span class="item-label">{{ t('settings.language') }}</span>
          </div>
          <div class="item-right">
            <span class="item-value">{{ localeDisplayName }}</span>
            <span class="arrow">›</span>
          </div>
        </div>
      </div>

      <!-- Storage section -->
      <div class="section">
        <div class="section-header">
          <span class="section-title">存储与缓存</span>
        </div>
        <div class="menu-item">
          <div class="item-left">
            <span class="item-icon">💾</span>
            <span class="item-label">缓存大小</span>
          </div>
          <div class="item-right">
            <span class="item-value">{{ cacheSize }}</span>
          </div>
        </div>
        <div class="menu-item" @click="clearCache">
          <div class="item-left">
            <span class="item-icon">🗑️</span>
            <span class="item-label">清除缓存</span>
          </div>
          <div class="item-right">
            <span class="arrow">›</span>
          </div>
        </div>
      </div>

      <!-- Legal section -->
      <div class="section">
        <div class="section-header">
          <span class="section-title">法律条款</span>
        </div>
        <div class="menu-item" @click="openPrivacyPolicy">
          <div class="item-left">
            <span class="item-icon">🛡️</span>
            <span class="item-label">隐私政策</span>
          </div>
          <div class="item-right">
            <span class="arrow">›</span>
          </div>
        </div>
        <div class="menu-item" @click="openUserAgreement">
          <div class="item-left">
            <span class="item-icon">📜</span>
            <span class="item-label">用户协议</span>
          </div>
          <div class="item-right">
            <span class="arrow">›</span>
          </div>
        </div>
      </div>

      <!-- About section -->
      <div class="section">
        <div class="section-header">
          <span class="section-title">关于</span>
        </div>
        <div class="menu-item" @click="openAbout">
          <div class="item-left">
            <span class="item-icon">ℹ️</span>
            <span class="item-label">关于我们</span>
          </div>
          <div class="item-right">
            <span class="item-value">v{{ appVersion }}</span>
            <span class="arrow">›</span>
          </div>
        </div>
        <div class="menu-item" @click="openFeedback">
          <div class="item-left">
            <span class="item-icon">💬</span>
            <span class="item-label">意见反馈</span>
          </div>
          <div class="item-right">
            <span class="arrow">›</span>
          </div>
        </div>
      </div>

      <!-- Logout button -->
      <div class="logout-section" v-if="isLoggedIn">
        <button class="btn-logout" @click="handleLogout">退出登录</button>
      </div>

      <!-- Version info -->
      <div class="version-info">
        <span class="version-text">AI 舌诊智能诊断系统 v{{ appVersion }}</span>
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

    <!-- Clear cache modal -->
    <div class="modal-overlay" v-if="showClearCacheModal" @click="showClearCacheModal = false">
      <div class="confirm-modal" @click.stop>
        <div class="confirm-header">
          <span class="confirm-title">{{ t('settings.clearCache') }}</span>
        </div>
        <div class="confirm-content">
          <span class="confirm-message">确定要清除所有缓存吗？</span>
        </div>
        <div class="confirm-actions">
          <button class="btn btn-secondary" @click="showClearCacheModal = false">{{ t('common.cancel') }}</button>
          <button class="btn btn-primary" @click="confirmClearCache">{{ t('common.confirm') }}</button>
        </div>
      </div>
    </div>

    <!-- Language selection modal -->
    <div class="modal-overlay" v-if="showLanguageModal" @click="showLanguageModal = false">
      <div class="language-modal" @click.stop>
        <div class="language-header">
          <span class="language-header-close" @click="showLanguageModal = false">{{ t('common.cancel') }}</span>
          <span class="language-header-title">{{ t('settings.language') }}</span>
          <div class="language-header-spacer"></div>
        </div>
        <div class="language-list">
          <div
            v-for="locale in availableLocalesList"
            :key="locale.code"
            class="language-item"
            :class="{ active: currentLocale === locale.code }"
            @click="handleLanguageChange(locale.code)"
          >
            <span class="language-item-name">{{ locale.name }}</span>
            <span v-if="currentLocale === locale.code" class="language-item-check">✓</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/store'
import { useDarkMode, useLanguage } from '@/composables'

const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()
const { isDark, setDarkMode } = useDarkMode()
const { currentLocale, localeDisplayName, setLanguage, availableLocalesList } = useLanguage()

// State
const isLoggedIn = computed(() => userStore.isLoggedIn)
const darkModeEnabled = computed(() => isDark.value)
const cacheSize = ref('0 MB')
const appVersion = ref('3.0.0')
const showAboutModal = ref(false)
const showClearCacheModal = ref(false)
const showLanguageModal = ref(false)

// Functions
function goBack() {
  router.back()
}

function editProfile() {
  alert('个人资料编辑功能开发中')
}

function changePassword() {
  alert('修改密码功能开发中')
}

function toggleDarkMode(e: Event) {
  const target = e.target as HTMLInputElement
  const newMode = target.checked ? 'dark' : 'auto'
  setDarkMode(newMode)
  alert(target.checked ? '已开启深色模式' : '已关闭深色模式')
}

function clearCache() {
  showClearCacheModal.value = true
}

function confirmClearCache() {
  showClearCacheModal.value = false
  // Simulate clearing cache
  cacheSize.value = '0 MB'
  alert('缓存已清除')
}

function openPrivacyPolicy() {
  router.push('/privacy')
}

function openUserAgreement() {
  router.push('/terms')
}

function openAbout() {
  showAboutModal.value = true
}

function openFeedback() {
  alert('意见反馈功能开发中')
}

function handleLogout() {
  if (confirm(t('settings.logout') + '\n' + t('profile.logoutConfirm'))) {
    userStore.logout()
    alert(t('auth.logoutSuccess'))
    router.back()
  }
}

function handleLanguageChange(localeCode: string) {
  setLanguage(localeCode as any)
  showLanguageModal.value = false
  alert(t('settings.language') + ': ' + localeDisplayName.value)
}

// Calculate cache size on mount
onMounted(() => {
  // Simulate cache size calculation
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
  cursor: pointer;
}

.menu-item:hover {
  background: #f8f8f8;
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

// Custom switch
.switch {
  appearance: none;
  width: 50px;
  height: 28px;
  background: #e0e0e0;
  border-radius: 14px;
  position: relative;
  cursor: pointer;
  transition: background 0.3s;
}

.switch:checked {
  background: #667eea;
}

.switch::before {
  content: '';
  position: absolute;
  width: 24px;
  height: 24px;
  background: #ffffff;
  border-radius: 50%;
  top: 2px;
  left: 2px;
  transition: transform 0.3s;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.switch:checked::before {
  transform: translateX(22px);
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
  cursor: pointer;
}

.btn-logout:hover {
  background: #fff0f0;
}

.version-info {
  padding: 20px;
  text-align: center;
}

.version-text {
  font-size: 12px;
  color: #cccccc;
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

.about-modal,
.confirm-modal {
  background: #ffffff;
  border-radius: 20px;
  padding: 25px;
  width: 280px;
  max-width: 90%;
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

// Language modal
.language-modal {
  background: #ffffff;
  border-radius: 20px 20px 0 0;
  width: 100%;
  max-width: 500px;
  position: fixed;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  max-height: 80vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.language-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px;
  border-bottom: 1px solid #f0f0f0;
}

.language-header-close,
.language-header-title {
  font-size: 15px;
  color: #333333;
  font-weight: 500;
}

.language-header-close {
  color: #667eea;
  cursor: pointer;
}

.language-header-spacer {
  width: 60px;
}

.language-list {
  max-height: 300px;
  overflow-y: auto;
}

.language-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px;
  border-bottom: 1px solid #f5f5f5;
  transition: background-color 0.2s;
  cursor: pointer;
}

.language-item:last-child {
  border-bottom: none;
}

.language-item:hover {
  background: #f8f8f8;
}

.language-item.active {
  background: #f0f4ff;
}

.language-item-name {
  font-size: 15px;
  color: #333333;
}

.language-item.active .language-item-name {
  color: #667eea;
  font-weight: 500;
}

.language-item-check {
  font-size: 18px;
  color: #667eea;
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

:global(.dark-mode) .menu-item:hover {
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

:global(.dark-mode) .btn-logout:hover {
  background: #3a3a3a;
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

:global(.dark-mode) .language-modal {
  background: #2a2a2a;
}

:global(.dark-mode) .language-header {
  border-bottom-color: #3a3a3a;
}

:global(.dark-mode) .language-header-close,
:global(.dark-mode) .language-header-title {
  color: #e0e0e0;
}

:global(.dark-mode) .language-item {
  border-bottom-color: #3a3a3a;
}

:global(.dark-mode) .language-item.active {
  background: #1a2540;
}

:global(.dark-mode) .language-item-name {
  color: #e0e0e0;
}

:global(.dark-mode) .language-item.active .language-item-name {
  color: #667eea;
}
</style>
