/**
 * Pinia Store Index
 * Central export point for all Pinia stores
 */

export { useUserStore } from './modules/user'
export { useDiagnosisStore } from './modules/diagnosis'

// Re-export types for convenience
export type { UserInfo } from './modules/user'
export type {
  DiagnosisState,
  DiagnosisResult,
  DiagnosisHistory,
  DiagnosisFilters
} from './modules/diagnosis'
