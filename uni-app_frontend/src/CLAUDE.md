# uni-app_frontend/src - Codebase Patterns

## H5 Local Storage

- H5 uses `localStorage` for token and user info persistence
- Storage abstraction in `utils/request.ts` handles both uni-app (uni.getStorageSync) and H5 (localStorage)
- Use `getUserInfo()` and `setUserInfo()` functions for user info persistence
- Call `initializeAuth()` on app startup (in App.vue onMounted) to restore user session
- Token validation on startup: fetch fresh user info to verify token is still valid
- Clear all auth data (tokens + user_info) on logout via `clearTokens()`

## User Store Patterns

- Initialize `token` and `userInfo` from storage on store creation
- Use `persist: true` in Pinia store for additional persistence layer
- Auto-login: `isLoggedIn` is true only when both token and userInfo exist
- When updating userInfo, always persist to storage via `saveUserInfo()`

## Platform Detection

- Use `typeof uni !== 'undefined'` to detect uni-app environment
- Use `isUniApp` flag from `@/utils/request` for conditional logic
- H5 (web) and mini-programs may have different APIs (e.g., login methods)
