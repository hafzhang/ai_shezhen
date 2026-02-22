/**
 * WeChat Mini-Program E2E Test Helpers
 * AI舌诊智能诊断系统 - WeChat E2E Testing Utilities
 * Phase 4: Testing & Documentation - US-175
 *
 * Helper functions for WeChat mini-program testing
 */

/**
 * WeChat API mock for H5 testing environment
 * This allows testing WeChat-specific flows in a browser
 */
export interface WeChatLoginResult {
  code: string
  errMsg: string
}

export interface WeChatUserInfo {
  nickName: string
  avatarUrl: string
  gender: number
  city: string
  province: string
  country: string
  language: string
}

export interface WeChatChooseImageResult {
  tempFilePaths: string[]
  tempFiles: Array<{
    path: string
    size: number
  }>
  errMsg: string
}

/**
 * Mock WeChat login for H5 testing
 */
export async function mockWxLogin(): Promise<WeChatLoginResult> {
  // Simulate network delay
  await new Promise(resolve => setTimeout(resolve, 100))

  // Return mock code (in real environment, this comes from WeChat server)
  return {
    code: `mock_code_${Date.now()}`,
    errMsg: 'login:ok'
  }
}

/**
 * Mock WeChat getUserProfile for H5 testing
 */
export async function mockWxGetUserProfile(): Promise<{ userInfo: WeChatUserInfo }> {
  await new Promise(resolve => setTimeout(resolve, 100))

  return {
    userInfo: {
      nickName: 'Test User',
      avatarUrl: 'https://picsum.photos/seed/avatar/200/200.jpg',
      gender: 0,
      city: 'Beijing',
      province: 'Beijing',
      country: 'China',
      language: 'zh_CN'
    }
  }
}

/**
 * Mock WeChat chooseImage for H5 testing
 */
export async function mockWxChooseImage(options: {
  sourceType: Array<'camera' | 'album'>
  count?: number
}): Promise<WeChatChooseImageResult> {
  await new Promise(resolve => setTimeout(resolve, 200))

  // Return mock image path
  return {
    tempFilePaths: ['/mock/tongue_image.jpg'],
    tempFiles: [{
      path: '/mock/tongue_image.jpg',
      size: 123456
    }],
    errMsg: 'chooseImage:ok'
  }
}

/**
 * Mock WeChat saveImageToPhotosAlbum for H5 testing
 */
export async function mockWxSaveImageToPhotosAlbum(filePath: string): Promise<{ errMsg: string }> {
  await new Promise(resolve => setTimeout(resolve, 150))

  return {
    errMsg: 'saveImageToPhotosAlbum:ok'
  }
}

/**
 * Mock WeChat shareAppMessage for H5 testing
 */
export function mockWxShareAppMessage(options: {
  title: string
  path: string
  imageUrl?: string
}): boolean {
  console.log('Share triggered:', options)
  return true
}

/**
 * Test data generator for WeChat mini-program tests
 */
export class WeChatTestDataGenerator {
  private static counter = 0

  /**
   * Generate a unique test user ID
   */
  static generateTestUserId(): string {
    return `wechat_test_${Date.now()}_${++this.counter}`
  }

  /**
   * Generate a test OpenID (WeChat user identifier)
   */
  static generateTestOpenId(): string {
    return `oABC123_${Date.now()}_${++this.counter}_xyz`
  }

  /**
   * Generate test user info
   */
  static generateTestUserInfo(overrides?: Partial<WeChatUserInfo>): WeChatUserInfo {
    return {
      nickName: `TestUser${this.counter}`,
      avatarUrl: `https://picsum.photos/seed/user${this.counter}/200/200.jpg`,
      gender: 0,
      city: 'Beijing',
      province: 'Beijing',
      country: 'China',
      language: 'zh_CN',
      ...overrides
    }
  }

  /**
   * Generate test image data (base64)
   */
  static generateTestImageBase64(): string {
    // Return a minimal 1x1 transparent PNG in base64
    return 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
  }

  /**
   * Generate test diagnosis data
   */
  static generateTestDiagnosisData() {
    return {
      age: Math.floor(Math.random() * 50) + 20,
      gender: Math.random() > 0.5 ? 'male' : 'female',
      chief_complaint: 'Test complaint for automated testing',
      image_base64: this.generateTestImageBase64()
    }
  }
}

/**
 * WeChat mini-program test assertions
 */
export class WeChatTestAssertions {
  /**
   * Assert WeChat login was successful
   */
  static assertLoginSuccess(result: any): void {
    expect(result).toBeDefined()
    expect(result.success).toBe(true)
    expect(result.data).toBeDefined()
    expect(result.data.access_token).toBeDefined()
    expect(result.data.refresh_token).toBeDefined()
    expect(result.data.user).toBeDefined()
    expect(result.data.user.openid).toBeDefined()
    expect(result.data.user.openid_type).toBe('wechat')
  }

  /**
   * Assert diagnosis result structure
   */
  static assertDiagnosisResult(result: any): void {
    expect(result).toBeDefined()
    expect(result.success).toBe(true)
    expect(result.data).toBeDefined()
    expect(result.data.diagnosis_id).toBeDefined()
    expect(result.data.features).toBeDefined()
    expect(result.data.results).toBeDefined()
    expect(result.data.syndromes).toBeDefined()
  }

  /**
   * Assert history list structure
   */
  static assertHistoryList(result: any): void {
    expect(result).toBeDefined()
    expect(result.success).toBe(true)
    expect(result.data).toBeDefined()
    expect(result.data.items).toBeDefined()
    expect(Array.isArray(result.data.items)).toBe(true)
    expect(result.data.total).toBeDefined()
    expect(typeof result.data.total).toBe('number')
  }

  /**
   * Assert WeChat mini-program API is available
   */
  static assertWeChatAPIAvailable(): boolean {
    if (typeof window === 'undefined') {
      return false
    }

    // Check for uni-app environment
    // @ts-ignore
    return typeof uni !== 'undefined' && uni.getSystemInfoSync !== undefined
  }
}

/**
 * WeChat mini-program test scenarios
 */
export class WeChatTestScenarios {
  /**
   * Scenario 1: First-time user registration via WeChat
   */
  static async scenarioFirstTimeWeChatUser() {
    const testUserId = WeChatTestDataGenerator.generateTestUserId()
    const testOpenId = WeChatTestDataGenerator.generateTestOpenId()
    const testUserInfo = WeChatTestDataGenerator.generateTestUserInfo()

    return {
      userId: testUserId,
      openId: testOpenId,
      userInfo: testUserInfo,
      scenario: 'First-time WeChat user registration'
    }
  }

  /**
   * Scenario 2: Returning WeChat user login
   */
  static async scenarioReturningWeChatUser() {
    const testOpenId = WeChatTestDataGenerator.generateTestOpenId()

    return {
      openId: testOpenId,
      scenario: 'Returning WeChat user login'
    }
  }

  /**
   * Scenario 3: Complete diagnosis flow
   */
  static async scenarioCompleteDiagnosisFlow() {
    const diagnosisData = WeChatTestDataGenerator.generateTestDiagnosisData()

    return {
      ...diagnosisData,
      scenario: 'Complete diagnosis flow from photo selection to result'
    }
  }

  /**
   * Scenario 4: Share diagnosis result
   */
  static async scenarioShareDiagnosisResult(diagnosisId: string) {
    return {
      diagnosisId,
      title: 'AI舌诊诊断结果',
      path: `/pages/detail/index?id=${diagnosisId}`,
      scenario: 'Share diagnosis result to WeChat contacts'
    }
  }

  /**
   * Scenario 5: View diagnosis history
   */
  static async scenarioViewDiagnosisHistory(userId: string) {
    return {
      userId,
      page: 1,
      pageSize: 20,
      scenario: 'View and paginate diagnosis history'
    }
  }
}

/**
 * WeChat mini-program specific wait conditions
 */
export class WeChatWaitConditions {
  /**
   * Wait for WeChat login to complete
   */
  static async waitForLogin(timeout: number = 5000): Promise<boolean> {
    const startTime = Date.now()

    while (Date.now() - startTime < timeout) {
      // Check if user is logged in
      const token = uni.getStorageSync('access_token')
      if (token) {
        return true
      }
      await new Promise(resolve => setTimeout(resolve, 100))
    }

    return false
  }

  /**
   * Wait for image to be selected
   */
  static async waitForImageSelection(timeout: number = 10000): Promise<boolean> {
    const startTime = Date.now()

    while (Date.now() - startTime < timeout) {
      // Check if image is in global state or storage
      const selectedImage = uni.getStorageSync('selected_image')
      if (selectedImage) {
        return true
      }
      await new Promise(resolve => setTimeout(resolve, 100))
    }

    return false
  }

  /**
   * Wait for diagnosis to complete
   */
  static async waitForDiagnosis(timeout: number = 30000): Promise<boolean> {
    const startTime = Date.now()

    while (Date.now() - startTime < timeout) {
      const diagnosisResult = uni.getStorageSync('last_diagnosis_result')
      if (diagnosisResult) {
        return true
      }
      await new Promise(resolve => setTimeout(resolve, 200))
    }

    return false
  }
}

/**
 * Initialize WeChat API mocks for H5 testing
 * Call this in test setup to mock WeChat APIs
 */
export function initWeChatMocks(): void {
  if (typeof window !== 'undefined') {
    // @ts-ignore
    window.wx = {
      login: (options: any) => {
        setTimeout(() => {
          options.success?.({ code: 'mock_code', errMsg: 'login:ok' })
        }, 100)
      },
      getUserProfile: (options: any) => {
        setTimeout(() => {
          options.success?.({
            userInfo: WeChatTestDataGenerator.generateTestUserInfo()
          })
        }, 100)
      },
      chooseImage: (options: any) => {
        setTimeout(() => {
          options.success?.({
            tempFilePaths: ['/mock/image.jpg'],
            tempFiles: [{ path: '/mock/image.jpg', size: 12345 }],
            errMsg: 'chooseImage:ok'
          })
        }, 200)
      },
      saveImageToPhotosAlbum: (options: any) => {
        setTimeout(() => {
          options.success?.({ errMsg: 'saveImageToPhotosAlbum:ok' })
        }, 150)
      },
      shareAppMessage: (options: any) => {
        console.log('Share triggered:', options)
        return true
      },
      request: (options: any) => {
        // Mock wx.request to use standard fetch
        fetch(options.url, {
          method: options.method,
          headers: options.header,
          body: options.data ? JSON.stringify(options.data) : undefined
        })
          .then(response => response.json())
          .then(data => {
            options.success?.({ data, errMsg: 'request:ok' })
          })
          .catch(error => {
            options.fail?.({ errMsg: `request:fail ${error.message}` })
          })
      }
    }

    console.log('WeChat API mocks initialized for H5 testing')
  }
}

export default {
  mockWxLogin,
  mockWxGetUserProfile,
  mockWxChooseImage,
  mockWxSaveImageToPhotosAlbum,
  mockWxShareAppMessage,
  WeChatTestDataGenerator,
  WeChatTestAssertions,
  WeChatTestScenarios,
  WeChatWaitConditions,
  initWeChatMocks
}
