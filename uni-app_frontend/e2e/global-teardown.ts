/**
 * Global Test Teardown
 * AI舌诊智能诊断系统 - H5 E2E Testing
 * Phase 4: Testing & Documentation - US-174
 *
 * This file cleans up the test environment after all tests run.
 */

import { FullConfig } from '@playwright/test'

async function globalTeardown(config: FullConfig) {
  console.log('🧹 Cleaning up E2E test environment...')

  // Clean up test data could be done here via API calls
  // For now, we just log completion
  console.log('✅ E2E test cleanup complete')
}

export default globalTeardown
