/**
 * Global Test Setup
 * AI舌诊智能诊断系统 - H5 E2E Testing
 * Phase 4: Testing & Documentation - US-174
 *
 * This file sets up the test environment before all tests run.
 * It ensures the API server is running and creates test data.
 */

import { FullConfig } from '@playwright/test'

async function globalSetup(config: FullConfig) {
  console.log('🔧 Setting up E2E test environment...')

  // Check if API server is running
  const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:9000'
  const HEALTH_URL = `${API_BASE_URL}/api/v2/health`

  try {
    const response = await fetch(HEALTH_URL)
    if (response.ok) {
      console.log('✅ API server is running')
    } else {
      console.warn('⚠️ API server health check failed')
    }
  } catch (error) {
    console.error('❌ API server is not running. Please start it with:')
    console.error('   cd api_service && python -m app.main')
    throw new Error('API server not available')
  }

  // Set up test environment variables
  process.env.TEST_MODE = 'e2e'
  process.env.TEST_PHONE_PREFIX = '+86139'

  console.log('✅ E2E test environment ready')
}

export default globalSetup
