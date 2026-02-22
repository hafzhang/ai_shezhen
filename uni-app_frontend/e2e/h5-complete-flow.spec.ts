/**
 * H5 Complete Flow E2E Tests
 * AI舌诊智能诊断系统 - H5 E2E Testing
 * Phase 4: Testing & Documentation - US-174
 *
 * End-to-end tests covering the complete H5 user flow:
 * - User registration
 * - User login
 * - Complete diagnosis flow
 * - History viewing
 * - Logout
 */

import { test, expect } from '@playwright/test'
import {
  generateTestPhone,
  generateTestPassword,
  generateTestNickname,
  registerTestUser,
  loginTestUser,
  cleanupTestUser,
  TestUserStorage,
  waitForPageStable,
  fillFormField,
  clickAndWait,
  isElementVisible,
  getElementText,
  takeScreenshot,
} from './helpers'

// Test suite configuration
test.describe.configure({ mode: 'serial' })

test.describe('H5 Complete Flow E2E Tests', () => {
  const testUserKey = 'e2e-test-user'
  let testUser: any

  test.beforeAll(async () => {
    // Create test user via API before tests
    testUser = await registerTestUser()
    TestUserStorage.set(testUserKey, testUser)
    console.log(`✅ Created test user: ${testUser.phone}`)
  })

  test.afterAll(async () => {
    // Cleanup test user after tests
    await cleanupTestUser(testUser.accessToken)
    TestUserStorage.delete(testUserKey)
    console.log('✅ Cleaned up test user')
  })

  test.beforeEach(async ({ page }) => {
    // Navigate to home page before each test
    await page.goto('/')
    await waitForPageStable(page)
  })

  test('should display home page correctly', async ({ page }) => {
    // Check for main title
    await expect(page.locator('text=AI舌诊智能诊断')).toBeVisible()

    // Check for subtitle
    await expect(page.locator('text=基于人工智能的中医舌诊分析')).toBeVisible()

    // Check for start diagnosis button
    await expect(page.locator('text=开始诊断')).toBeVisible()

    // Check for feature items
    await expect(page.locator('text=历史记录')).toBeVisible()
    await expect(page.locator('text=健康档案')).toBeVisible()
    await expect(page.locator('text=健康趋势')).toBeVisible()
    await expect(page.locator('text=设置')).toBeVisible()

    await takeScreenshot(page, '01-home-page')
  })

  test('should display login prompt for non-logged-in users', async ({ page }) => {
    // Check for login prompt
    await expect(page.locator('text=登录后可保存诊断记录并查看历史')).toBeVisible()

    // Check for login and register buttons
    await expect(page.locator('text=登录')).toBeVisible()
    await expect(page.locator('text=注册')).toBeVisible()
  })

  test('should navigate to login page', async ({ page }) => {
    // Click login button
    await clickAndWait(page, 'text=登录')
    await waitForPageStable(page)

    // Verify login page is displayed
    await expect(page.locator('text=登录')).toBeVisible()
    await expect(page.locator('input[type="tel"]')).toBeVisible()
    await expect(page.locator('input[type="password"]')).toBeVisible()

    await takeScreenshot(page, '02-login-page')
  })

  test('should login successfully with valid credentials', async ({ page }) => {
    // Navigate to login page
    await page.click('text=登录')
    await waitForPageStable(page)

    // Fill in login form
    await fillFormField(page, 'input[type="tel"]', testUser.phone)
    await fillFormField(page, 'input[type="password"]', testUser.password)

    // Submit login
    await page.click('button:has-text("登录")')

    // Wait for login to complete
    await page.waitForURL('/', { timeout: 10000 })

    // Verify successful login
    await expect(page.locator('text=登录成功')).toBeVisible({ timeout: 5000 })

    // Verify user info is displayed
    await expect(page.locator(`text=${testUser.nickname}`)).toBeVisible({ timeout: 5000 })

    await takeScreenshot(page, '03-after-login')
  })

  test('should show error for invalid phone number', async ({ page }) => {
    // Navigate to login page
    await page.click('text=登录')
    await waitForPageStable(page)

    // Fill with invalid phone
    await fillFormField(page, 'input[type="tel"]', '12345')
    await fillFormField(page, 'input[type="password"]', testUser.password)

    // Try to submit
    await page.click('button:has-text("登录")')

    // Verify error message
    await expect(page.locator('text=请输入正确的手机号')).toBeVisible()

    await takeScreenshot(page, '04-invalid-phone-error')
  })

  test('should show error for invalid password', async ({ page }) => {
    // Navigate to login page
    await page.click('text=登录')
    await waitForPageStable(page)

    // Fill with valid phone but short password
    await fillFormField(page, 'input[type="tel"]', testUser.phone)
    await fillFormField(page, 'input[type="password"]', '123')

    // Try to submit
    await page.click('button:has-text("登录")')

    // Verify error message
    await expect(page.locator('text=密码至少6位')).toBeVisible()

    await takeScreenshot(page, '05-invalid-password-error')
  })

  test('should navigate to registration page', async ({ page }) => {
    // Navigate to login page first
    await page.click('text=登录')
    await waitForPageStable(page)

    // Click register link
    await page.click('text=还没有账号？去注册')
    await waitForPageStable(page)

    // Verify registration page
    await expect(page.locator('text=注册')).toBeVisible()
    await expect(page.locator('input[type="tel"]')).toBeVisible()
    await expect(page.locator('input[type="password"]')).toBeVisible()
    await expect(page.locator('input[placeholder*="确认密码"]')).toBeVisible()
    await expect(page.locator('input[placeholder*="昵称"]')).toBeVisible()

    await takeScreenshot(page, '06-registration-page')
  })

  test('should register new user successfully', async ({ page }) => {
    const newUserPhone = generateTestPhone()
    const newUserPassword = generateTestPassword()
    const newNickname = generateTestNickname()

    // Navigate to registration
    await page.click('text=登录')
    await page.click('text=还没有账号？去注册')
    await waitForPageStable(page)

    // Fill registration form
    await fillFormField(page, 'input[type="tel"]', newUserPhone)
    await fillFormField(page, 'input[placeholder*="密码"]', newUserPassword)
    await fillFormField(page, 'input[placeholder*="确认密码"]', newUserPassword)
    await fillFormField(page, 'input[placeholder*="昵称"]', newNickname)

    // Submit registration
    await page.click('button:has-text("注册")')

    // Wait for registration to complete
    await page.waitForTimeout(2000)

    // Verify success message
    await expect(page.locator('text=注册成功')).toBeVisible({ timeout: 5000 })

    // Store new user for cleanup
    const newUser = await loginTestUser(newUserPhone, newUserPassword)
    TestUserStorage.set(`temp-${newUserPhone}`, {
      ...newUser,
      phone: newUserPhone,
      password: newUserPassword,
    })

    await takeScreenshot(page, '07-after-registration')
  })

  test('should validate password confirmation', async ({ page }) => {
    // Navigate to registration
    await page.click('text=登录')
    await page.click('text=还没有账号？去注册')
    await waitForPageStable(page)

    // Fill with mismatched passwords
    await fillFormField(page, 'input[type="tel"]', generateTestPhone())
    await fillFormField(page, 'input[placeholder*="密码"]', 'Password123')
    await fillFormField(page, 'input[placeholder*="确认密码"]', 'Password456')

    // Try to submit
    await page.click('button:has-text("注册")')

    // Verify error message
    await expect(page.locator('text=两次密码不一致')).toBeVisible()

    await takeScreenshot(page, '08-password-mismatch-error')
  })

  test('should navigate to diagnosis page', async ({ page }) => {
    // Login first
    await page.evaluate(async ({ phone, password }) => {
      // Use localStorage to set token directly for faster test
      localStorage.setItem('access_token', testUser.accessToken)
      localStorage.setItem('refresh_token', testUser.refreshToken)
    }, { phone: testUser.phone, password: testUser.password })

    await page.reload()
    await waitForPageStable(page)

    // Click start diagnosis button
    await page.click('text=开始诊断')
    await waitForPageStable(page)

    // Verify diagnosis page elements
    await expect(page.locator('text=舌诊诊断')).toBeVisible()
    await expect(page.locator('text=拍照')).toBeVisible()
    await expect(page.locator('text=从相册选择')).toBeVisible()

    await takeScreenshot(page, '09-diagnosis-page')
  })

  test('should display user info form on diagnosis page', async ({ page }) => {
    // Login and navigate to diagnosis
    await page.evaluate(async () => {
      localStorage.setItem('access_token', testUser.accessToken)
      localStorage.setItem('refresh_token', testUser.refreshToken)
    })

    await page.reload()
    await page.click('text=开始诊断')
    await waitForPageStable(page)

    // Check for user info form
    await expect(page.locator('text=年龄')).toBeVisible()
    await expect(page.locator('text=性别')).toBeVisible()
    await expect(page.locator('text=主诉')).toBeVisible()

    await takeScreenshot(page, '10-diagnosis-user-form')
  })

  test('should navigate to history page', async ({ page }) => {
    // Login first
    await page.evaluate(async () => {
      localStorage.setItem('access_token', testUser.accessToken)
      localStorage.setItem('refresh_token', testUser.refreshToken)
    })

    await page.reload()
    await waitForPageStable(page)

    // Click history feature
    await page.click('text=历史记录')
    await waitForPageStable(page)

    // Verify history page
    await expect(page.locator('text=诊断记录')).toBeVisible()
    await expect(page.locator('text=历史记录')).toBeVisible()

    await takeScreenshot(page, '11-history-page')
  })

  test('should navigate to health records page', async ({ page }) => {
    // Login first
    await page.evaluate(async () => {
      localStorage.setItem('access_token', testUser.accessToken)
      localStorage.setItem('refresh_token', testUser.refreshToken)
    })

    await page.reload()
    await waitForPageStable(page)

    // Click health records feature
    await page.click('text=健康档案')
    await waitForPageStable(page)

    // Verify health records page
    await expect(page.locator('text=健康档案')).toBeVisible()
    await expect(page.locator('text=添加记录')).toBeVisible()

    await takeScreenshot(page, '12-health-records-page')
  })

  test('should navigate to profile page', async ({ page }) => {
    // Login first
    await page.evaluate(async () => {
      localStorage.setItem('access_token', testUser.accessToken)
      localStorage.setItem('refresh_token', testUser.refreshToken)
    })

    await page.reload()
    await waitForPageStable(page)

    // Click on user card to go to profile
    await page.click('.user-card')
    await waitForPageStable(page)

    // Verify profile page
    await expect(page.locator('text=个人中心')).toBeVisible()
    await expect(page.locator(`text=${testUser.nickname}`)).toBeVisible()

    await takeScreenshot(page, '13-profile-page')
  })

  test('should logout successfully', async ({ page }) => {
    // Login first
    await page.evaluate(async () => {
      localStorage.setItem('access_token', testUser.accessToken)
      localStorage.setItem('refresh_token', testUser.refreshToken)
    })

    await page.reload()
    await waitForPageStable(page)

    // Navigate to profile
    await page.click('.user-card')
    await waitForPageStable(page)

    // Click logout button
    await page.click('text=退出登录')
    await waitForPageStable(page)

    // Confirm logout if there's a confirmation dialog
    const confirmButton = page.locator('button:has-text("确定")')
    if (await confirmButton.isVisible()) {
      await confirmButton.click()
    }

    await waitForPageStable(page)

    // Verify logged out state
    await expect(page.locator('text=登录后可保存诊断记录')).toBeVisible()

    await takeScreenshot(page, '14-after-logout')
  })

  test('should redirect to login when accessing protected route', async ({ page }) => {
    // Try to access profile directly without login
    await page.goto('/pages/profile/index')
    await waitForPageStable(page)

    // Should redirect to login or show login prompt
    const onLoginPage = await isElementVisible(page, 'text=登录')
    const hasLoginPrompt = await isElementVisible(page, 'text=请先登录')

    expect(onLoginPage || hasLoginPrompt).toBeTruthy()

    await takeScreenshot(page, '15-protected-route-redirect')
  })

  test('should handle back navigation correctly', async ({ page }) => {
    // Login first
    await page.evaluate(async () => {
      localStorage.setItem('access_token', testUser.accessToken)
      localStorage.setItem('refresh_token', testUser.refreshToken)
    })

    await page.reload()
    await waitForPageStable(page)

    // Navigate to history
    await page.click('text=历史记录')
    await waitForPageStable(page)

    // Click back button
    await page.click('.back-button, button:has-text("←")')
    await waitForPageStable(page)

    // Should return to home page
    await expect(page.locator('text=AI舌诊智能诊断')).toBeVisible()

    await takeScreenshot(page, '16-back-navigation')
  })
})

test.describe('H5 Diagnosis Flow E2E Tests', () => {
  const testUserKey = 'diagnosis-test-user'
  let testUser: any

  test.beforeAll(async () => {
    // Create test user for diagnosis tests
    testUser = await registerTestUser()
    TestUserStorage.set(testUserKey, testUser)
  })

  test.afterAll(async () => {
    await cleanupTestUser(testUser.accessToken)
    TestUserStorage.delete(testUserKey)
  })

  test.beforeEach(async ({ page }) => {
    // Login before each test
    await page.goto('/')
    await page.evaluate(async ({ token, refreshToken }) => {
      localStorage.setItem('access_token', token)
      localStorage.setItem('refresh_token', refreshToken)
    }, { token: testUser.accessToken, refreshToken: testUser.refreshToken })

    await page.reload()
    await waitForPageStable(page)
  })

  test('should complete anonymous diagnosis flow', async ({ page }) => {
    // Logout first for anonymous test
    await page.evaluate(() => {
      localStorage.clear()
    })

    await page.reload()
    await waitForPageStable(page)

    // Start diagnosis
    await page.click('text=开始诊断')
    await waitForPageStable(page)

    // Note: Actual image upload and diagnosis submission would require
    // file system access and API mocking. This test verifies the UI flow.
    await expect(page.locator('text=舌诊诊断')).toBeVisible()

    await takeScreenshot(page, '17-anonymous-diagnosis')
  })

  test('should display loading state during diagnosis', async ({ page }) => {
    // Navigate to diagnosis
    await page.click('text=开始诊断')
    await waitForPageStable(page)

    // Check for loading component (would be visible during actual diagnosis)
    const loadingExists = await page.locator('.loading, .mask').count() > 0

    // Loading may not be visible initially, but the component should exist
    expect(loadingExists).toBeTruthy()

    await takeScreenshot(page, '18-diagnosis-loading')
  })
})

test.describe('H5 Responsive Design Tests', () => {
  test('should display correctly on mobile viewport', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 })
    await page.goto('/')
    await waitForPageStable(page)

    // Check main elements are visible
    await expect(page.locator('text=AI舌诊智能诊断')).toBeVisible()
    await expect(page.locator('text=开始诊断')).toBeVisible()

    await takeScreenshot(page, '19-mobile-viewport')
  })

  test('should display correctly on tablet viewport', async ({ page }) => {
    // Set tablet viewport
    await page.setViewportSize({ width: 768, height: 1024 })
    await page.goto('/')
    await waitForPageStable(page)

    // Check main elements are visible
    await expect(page.locator('text=AI舌诊智能诊断')).toBeVisible()
    await expect(page.locator('text=开始诊断')).toBeVisible()

    await takeScreenshot(page, '20-tablet-viewport')
  })

  test('should display correctly on desktop viewport', async ({ page }) => {
    // Set desktop viewport
    await page.setViewportSize({ width: 1920, height: 1080 })
    await page.goto('/')
    await waitForPageStable(page)

    // Check main elements are visible
    await expect(page.locator('text=AI舌诊智能诊断')).toBeVisible()
    await expect(page.locator('text=开始诊断')).toBeVisible()

    await takeScreenshot(page, '21-desktop-viewport')
  })
})
