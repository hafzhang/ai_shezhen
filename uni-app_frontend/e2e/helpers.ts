/**
 * E2E Test Helpers
 * AI舌诊智能诊断系统 - H5 E2E Testing
 * Phase 4: Testing & Documentation - US-174
 *
 * Helper functions for E2E tests including user management,
 * API interactions, and common test utilities.
 */

import { Page, Locator } from '@playwright/test'

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:9000'

/**
 * Generate a random test phone number
 */
export function generateTestPhone(): string {
  const timestamp = Date.now().toString().slice(-8)
  return `139${timestamp}`
}

/**
 * Generate a random test password
 */
export function generateTestPassword(): string {
  return `Test${Date.now()}!`
}

/**
 * Generate a random test nickname
 */
export function generateTestNickname(): string {
  return `TestUser${Date.now()}`
}

/**
 * Register a test user via API
 */
export async function registerTestUser(phone?: string, password?: string, nickname?: string) {
  const testPhone = phone || generateTestPhone()
  const testPassword = password || generateTestPassword()
  const testNickname = nickname || generateTestNickname()

  const response = await fetch(`${API_BASE_URL}/api/v2/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      phone: testPhone,
      password: testPassword,
      nickname: testNickname,
    }),
  })

  if (!response.ok) {
    throw new Error(`Registration failed: ${response.statusText}`)
  }

  const data = await response.json()
  return {
    phone: testPhone,
    password: testPassword,
    nickname: testNickname,
    userId: data.data.user.id,
    accessToken: data.data.access_token,
    refreshToken: data.data.refresh_token,
  }
}

/**
 * Login a test user via API
 */
export async function loginTestUser(phone: string, password: string) {
  const response = await fetch(`${API_BASE_URL}/api/v2/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone, password }),
  })

  if (!response.ok) {
    throw new Error(`Login failed: ${response.statusText}`)
  }

  const data = await response.json()
  return {
    userId: data.data.user.id,
    accessToken: data.data.access_token,
    refreshToken: data.data.refresh_token,
  }
}

/**
 * Clean up test user via API
 */
export async function cleanupTestUser(accessToken: string) {
  try {
    await fetch(`${API_BASE_URL}/api/v2/users/me`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${accessToken}`,
      },
    })
  } catch (error) {
    console.warn('Failed to cleanup test user:', error)
  }
}

/**
 * Wait for page to be stable (no network requests)
 */
export async function waitForPageStable(page: Page, timeout = 3000) {
  await page.waitForTimeout(timeout)
}

/**
 * Fill form field with validation
 */
export async function fillFormField(
  page: Page,
  selector: string,
  value: string,
  options?: { timeout?: number }
) {
  const element = page.locator(selector).first()
  await element.fill(value)
  // Verify the value was set
  const inputValue = await element.inputValue()
  if (inputValue !== value) {
    throw new Error(`Failed to fill ${selector}. Expected: ${value}, Got: ${inputValue}`)
  }
}

/**
 * Click button and wait for navigation or network idle
 */
export async function clickAndWait(
  page: Page,
  selector: string,
  options?: { timeout?: number; waitForNavigation?: boolean }
) {
  const element = page.locator(selector).first()

  if (options?.waitForNavigation) {
    await Promise.all([
      page.waitForLoadState('networkidle'),
      element.click()
    ])
  } else {
    await element.click()
  }
}

/**
 * Check if element is visible
 */
export async function isElementVisible(page: Page, selector: string): Promise<boolean> {
  try {
    const element = page.locator(selector).first()
    await element.waitFor({ state: 'visible', timeout: 2000 })
    return true
  } catch {
    return false
  }
}

/**
 * Get text content of element
 */
export async function getElementText(page: Page, selector: string): Promise<string> {
  const element = page.locator(selector).first()
  return await element.textContent() || ''
}

/**
 * Take screenshot with description
 */
export async function takeScreenshot(page: Page, name: string) {
  await page.screenshot({
    path: `e2e/screenshots/${name}.png`,
    fullPage: true,
  })
}

/**
 * Mock file upload for testing
 */
export async function mockFileUpload(page: Page, selector: string, fileName: string) {
  const fileInput = page.locator(selector)
  await fileInput.setInputFiles({
    name: fileName,
    mimeType: 'image/jpeg',
    buffer: Buffer.from('mock image content')
  })
}

/**
 * Test user data storage
 */
export class TestUserStorage {
  private static users = new Map<string, any>()

  static set(key: string, userData: any) {
    this.users.set(key, userData)
  }

  static get(key: string): any {
    return this.users.get(key)
  }

  static delete(key: string) {
    this.users.delete(key)
  }

  static async cleanupAll() {
    const cleanupPromises: Promise<void>[] = []

    // Use Array.from for compatibility
    const entries = Array.from(this.users.entries())
    for (const [key, user] of entries) {
      if (user.accessToken) {
        cleanupPromises.push(cleanupTestUser(user.accessToken))
      }
    }

    await Promise.allSettled(cleanupPromises)
    this.users.clear()
  }
}
