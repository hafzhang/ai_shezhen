# WeChat Mini-Program E2E Testing Guide

## Overview

This guide covers end-to-end testing for the WeChat mini-program version of the AI Tongue Diagnosis System.

## Testing Approach

WeChat mini-programs run in a specialized environment within WeChat. Unlike H5 applications, they cannot be tested directly with standard browser automation tools like Playwright. Instead, we use a hybrid approach:

1. **Automated Tests**: Playwright tests for H5 version with WeChat-specific API mocks
2. **Manual Testing**: Step-by-step verification in WeChat DevTools
3. **Automated Testing**: WeChat DevTools automation with CLI tools

## Prerequisites

### 1. WeChat Developer Account

- Register at [WeChat Open Platform](https://open.weixin.qq.com/)
- Create a mini-program application
- Get your `appid`

### 2. WeChat DevTools

- Download [WeChat DevTools](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)
- Install and login with your WeChat account

### 3. Build the Mini-Program

```bash
cd uni-app_frontend

# Install dependencies
npm install

# Build for WeChat mini-program
npm run build:mp-weixin

# The output will be in dist/dev/mp-weixin or dist/build/mp-weixin
```

### 4. Load in WeChat DevTools

1. Open WeChat DevTools
2. Select "Mini-Program" tab
3. Click "Import" or "Import Project"
4. Select the `dist/dev/mp-weixin` directory
5. Enter your appid (use test appid for development)
6. Click "Import"

## Manual Testing Checklist

### Test Suite 1: WeChat Login Flow

#### TC-001: First Launch Display
- [ ] Mini-program launches successfully
- [ ] Home page is displayed
- [ ] "微信登录" button is visible
- [ ] Button is properly styled with WeChat green color

#### TC-002: WeChat Authorization
- [ ] Click "微信登录" button
- [ ] `wx.login()` is called (check Console)
- [ ] Code is successfully obtained
- [ ] Backend API `/api/v2/auth/wechat` is called
- [ ] JWT tokens are received and stored
- [ ] User is redirected to home page
- [ ] User nickname and avatar are displayed

#### TC-003: Login Error Handling
- [ ] Disable network connection
- [ ] Click "微信登录" button
- [ ] Error message is displayed: "网络连接失败，请检查网络设置"
- [ ] User can retry after reconnection
- [ ] Reconnection works correctly

#### TC-004: User Profile Authorization
- [ ] After `wx.login()`, `wx.getUserProfile()` is called
- [ ] Authorization modal is displayed
- [ ] User can authorize nickname and avatar
- [ ] If user declines, default values are used
- [ ] Data is correctly sent to backend

### Test Suite 2: Diagnosis Flow

#### TC-201: Navigation to Diagnosis
- [ ] From home, tap "开始诊断" button
- [ ] Navigation to diagnosis page is smooth
- [ ] Camera component is displayed
- [ ] Photo guide frame overlay is visible

#### TC-202: Take Photo
- [ ] Tap "拍照" button
- [ ] `wx.chooseImage()` is called with `sourceType: ['camera']`
- [ ] Camera interface opens
- [ ] Photo is captured successfully
- [ ] Image preview is displayed
- [ ] Image quality is acceptable

#### TC-203: Select from Album
- [ ] Tap "相册" button
- [ ] `wx.chooseImage()` is called with `sourceType: ['album']`
- [ ] Album picker opens
- [ ] Image can be selected
- [ ] Selected image is displayed in preview

#### TC-204: Fill User Form
- [ ] After image selection, user form is displayed
- [ ] Age field accepts numeric input (0-150)
- [ ] Gender selector shows 男/女 options
- [ ] Only one gender can be selected
- [ ] Chief complaint textarea accepts text input
- [ ] Form validation works correctly

#### TC-205: Submit Diagnosis
- [ ] Fill all required fields
- [ ] Tap "提交诊断" button
- [ ] Loading indicator is displayed
- [ ] Image is converted to base64
- [ ] API request is sent to `/api/v2/diagnosis`
- [ ] Response is received
- [ ] Navigation to result page

#### TC-206: Display Results
- [ ] Tongue image with mask overlay is displayed
- [ ] 6-dimension features are shown with confidence bars
- [ ] Syndrome analysis card is displayed
- [ ] Health recommendations are shown (collapsed by default)
- [ ] Tapping recommendations expands them
- [ ] Risk alert is displayed if applicable

### Test Suite 3: History View

#### TC-301: Navigation to History
- [ ] Tap "历史" tab in tab bar
- [ ] History page is displayed
- [ ] Tab bar shows "历史" as active

#### TC-302: Display History List
- [ ] Diagnosis history list is displayed
- [ ] Each item shows: date, syndrome, confidence
- [ ] Items are ordered by date (newest first)
- [ ] Empty state is displayed if no history

#### TC-303: Pull to Refresh
- [ ] Pull down on history page
- [ ] Loading indicator is shown
- [ ] List refreshes with latest data
- [ ] Loading indicator disappears

#### TC-304: Load More
- [ ] Scroll to bottom of list
- [ ] "加载更多" indicator appears
- [ ] More items are loaded
- [ ] "没有更多了" message when all loaded

#### TC-305: View Detail
- [ ] Tap on a history item
- [ ] Detail page opens
- [ ] All diagnosis information is displayed
- [ ] Back button returns to history list

### Test Suite 4: Profile & Settings

#### TC-401: Display Profile
- [ ] Tap "我的" tab
- [ ] Profile page is displayed
- [ ] WeChat nickname is shown
- [ ] WeChat avatar is shown
- [ ] Menu items are displayed

#### TC-402: Health Records
- [ ] Tap "健康档案" menu item
- [ ] Health records page opens
- [ ] Records list is displayed
- [ ] "添加记录" button is visible

#### TC-403: Settings
- [ ] Tap "设置" menu item
- [ ] Settings page opens
- [ ] Language selector is displayed
- [ ] Dark mode toggle is displayed
- [ ] Privacy policy link is displayed

#### TC-404: Logout
- [ ] Tap "退出登录" button
- [ ] Confirmation dialog is displayed
- [ ] Confirm logout
- [ ] Tokens are cleared
- [ ] User is redirected to login page
- [ ] User info is not displayed

### Test Suite 5: Mini-Program Features

#### TC-501: Share Result
- [ ] On result page, tap "分享" button
- [ ] `wx.shareAppMessage()` is called
- [ ] Share modal is displayed
- [ ] Share can be sent to WeChat contacts
- [ ] Share image is correctly generated

#### TC-502: Save to Album
- [ ] On result page, tap "保存" button
- [ ] `wx.saveImageToPhotosAlbum()` is called
- [ ] Authorization is requested (first time)
- [ ] Success message is displayed
- [ ] Image is saved to album

#### TC-503: Tab Bar Navigation
- [ ] Tab bar is displayed at bottom
- [ ] 3 tabs: 首页, 历史, 我的
- [ ] Active tab is highlighted
- [ ] Tapping tabs switches pages
- [ ] Tab navigation is smooth

#### TC-504: App Lifecycle
- [ ] Mini-program handles `onLaunch` event
- [ ] Mini-program handles `onShow` event
- [ ] Mini-program handles `onHide` event
- [ ] User session persists across app close/open
- [ ] Auto-login works on app launch

## Automated Testing with WeChat DevTools CLI

WeChat DevTools provides CLI tools for automated testing:

### 1. Headless Mode

```bash
# WeChat DevTools CLI (path may vary)
/path/to/wechat-devtools/cli \
  --login \
  --upload \
  --project /path/to/dist/dev/mp-weixin \
  --version 1.0.0 \
  --desc "Automated test build"
```

### 2. Automated Preview

```bash
# Generate preview QR code for testing
/path/to/wechat-devtools/cli \
  --preview \
  --project /path/to/dist/dev/mp-weixin \
  --qr-output /path/to/qr-code.png
```

### 3. Integration with CI/CD

```yaml
# .github/workflows/wechat-test.yml
name: WeChat Mini-Program Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Node.js
        uses: actions/setup-node@v2
        with:
          node-version: '20'
      - name: Install dependencies
        run: npm install
      - name: Build WeChat mini-program
        run: npm run build:mp-weixin
      - name: Upload to WeChat
        run: |
          # Use WeChat DevTools CLI to upload
          # Requires WECHAT_APP_ID and WECHAT_PRIVATE_KEY secrets
```

## API Mocking for WeChat Tests

When testing in H5 environment, WeChat APIs need to be mocked:

```typescript
// Mock wx APIs for H5 testing
if (typeof wx === 'undefined') {
  global.wx = {
    login: (options) => {
      setTimeout(() => {
        options.success?.({ code: 'mock_code' })
      }, 100)
    },
    getUserProfile: (options) => {
      setTimeout(() => {
        options.success?.({
          userInfo: {
            nickName: 'Test User',
            avatarUrl: 'https://example.com/avatar.png'
          }
        })
      }, 100)
    },
    chooseImage: (options) => {
      setTimeout(() => {
        options.success?.({
          tempFilePaths: ['/mock/image.png'],
          tempFiles: [{ path: '/mock/image.png', size: 12345 }]
        })
      }, 100)
    },
    chooseMessageFile: (options) => {
      // Mock implementation
    },
    saveImageToPhotosAlbum: (options) => {
      setTimeout(() => {
        options.success?.()
      }, 100)
    },
    shareAppMessage: (options) => {
      // Mock implementation
    },
    request: (options) => {
      // Mock implementation
    }
  }
}
```

## Common Issues and Solutions

### Issue 1: AppID Configuration

**Problem**: Mini-program fails to load with appid error

**Solution**:
1. Check `src/manifest.json` mp-weixin.appid
2. Use test appid for development: `touristappid`
3. Ensure appid is registered in WeChat Open Platform

### Issue 2: Permission Denied

**Problem**: Camera or album access denied

**Solution**:
1. Check `requiredPrivateInfos` in manifest.json
2. Ensure permissions are requested in WeChat DevTools
3. Check privacy policy settings

### Issue 3: API Call Fails

**Problem**: Backend API calls fail in mini-program

**Solution**:
1. Check server domain whitelist in WeChat MP admin
2. Ensure HTTPS is used (required for production)
3. Check request URL is correct
4. Verify API server is accessible from WeChat

### Issue 4: Image Upload Too Large

**Problem**: Image upload fails due to size

**Solution**:
1. Compress image before upload (implemented)
2. Check mini-program upload limit (default 10MB)
3. Use image compression API

## Test Report Template

```markdown
## WeChat Mini-Program E2E Test Report

**Date**: [Test Date]
**Tester**: [Tester Name]
**WeChat Version**: [Version]
**DevTools Version**: [Version]
**Mini-Program Version**: [Version]

### Test Summary
- Total Test Cases: XX
- Passed: XX
- Failed: XX
- Skipped: XX
- Pass Rate: XX%

### Test Results by Suite

#### Login Flow
- TC-001: [PASS/FAIL]
- TC-002: [PASS/FAIL]
- ...

#### Diagnosis Flow
- TC-201: [PASS/FAIL]
- TC-202: [PASS/FAIL]
- ...

### Issues Found
1. [Issue Description]
   - Severity: [Critical/Major/Minor]
   - Steps to Reproduce: [...]
   - Expected: [...]
   - Actual: [...]

### Recommendations
1. [Recommendation 1]
2. [Recommendation 2]
...

### Screenshots
[Attach screenshots for failed tests]
```

## Continuous Improvement

- Regularly update test cases as features evolve
- Maintain test data (test users, test images)
- Review and update test checklist monthly
- Incorporate user feedback into test cases
- Monitor WeChat API updates for breaking changes

## References

- [WeChat Mini-Program Documentation](https://developers.weixin.qq.com/miniprogram/dev/framework/)
- [WeChat DevTools Documentation](https://developers.weixin.qq.com/miniprogram/dev/devtools/devtools.html)
- [uni-app WeChat Mini-Program Guide](https://uniapp.dcloud.net.cn/tutorial/mp-weixin.html)
