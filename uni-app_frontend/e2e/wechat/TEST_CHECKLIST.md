# WeChat Mini-Program E2E Test Checklist

## Test Execution Information

| Field | Value |
|-------|-------|
| **Date** | ___________ |
| **Tester** | ___________ |
| **WeChat Version** | ___________ |
| **DevTools Version** | ___________ |
| **Mini-Program Version** | ___________ |
| **Build Type** | Dev / Production |
| **Device** | ___________ |
| **OS Version** | ___________ |

---

## 1. WeChat Login Flow (Priority: HIGH)

### TC-WX-001: First Launch Display
- [ ] Mini-program launches successfully in WeChat
- [ ] Home page displays correctly
- [ ] "微信登录" button is visible and centered
- [ ] Button uses WeChat brand color (#07C160)
- [ ] Button has appropriate size for touch (min 44x44px)

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

### TC-WX-002: WeChat Authorization Flow
- [ ] Tapping "微信登录" triggers wx.login()
- [ ] Code is successfully obtained from WeChat server
- [ ] Backend API `/api/v2/auth/wechat` is called
- [ ] Request includes: code, nickname, avatar_url
- [ ] Response includes: access_token, refresh_token, user
- [ ] Tokens are stored in uni.storage
- [ ] User object contains: id, openid, openid_type='wechat', nickname, avatar_url
- [ ] User is redirected to home page
- [ ] User info displays in profile page

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

### TC-WX-003: User Profile Authorization
- [ ] After wx.login(), wx.getUserProfile() is called
- [ ] Authorization modal displays with correct text
- [ ] Modal includes: privacy notice, agree/disagree buttons
- [ ] Tapping "同意" returns user info (nickname, avatar)
- [ ] Tapping "拒绝" uses default values
- [ ] User info is correctly sent to backend
- [ ] Profile page displays WeChat nickname and avatar

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

### TC-WX-004: Login Error Handling
- [ ] Network error displays user-friendly message
- [ ] Error message: "网络连接失败，请检查网络设置"
- [ ] User can retry login by tapping "重试"
- [ ] Reconnection after network restore works correctly
- [ ] Server error (500) displays appropriate message
- [ ] Timeout after 10 seconds displays timeout message
- [ ] Error state doesn't crash the mini-program

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

### TC-WX-005: Auto-Login on App Launch
- [ ] Opening mini-program checks for stored tokens
- [ ] Valid token auto-logs in user
- [ ] User info is fetched and displayed
- [ ] Invalid token clears storage and shows login
- [ ] Expired token triggers refresh flow
- [ ] Auto-login is smooth without flicker

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

## 2. Diagnosis Flow (Priority: HIGH)

### TC-WX-101: Navigation to Diagnosis Page
- [ ] "开始诊断" button on home page is visible
- [ ] Tapping button navigates to diagnosis page
- [ ] Navigation transition is smooth
- [ ] Diagnosis page title displays: "舌诊诊断"
- [ ] Back button returns to home page

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

### TC-WX-102: Camera Component Display
- [ ] Camera preview area displays correctly
- [ ] Photo guide frame overlay is visible
- [ ] Guide frame has corner markers
- [ ] Center instruction text: "请将舌体放入框内"
- [ ] "拍照" button is visible at bottom
- [ ] "相册" button is visible next to camera
- [ ] Both buttons are properly sized for touch

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

### TC-WX-103: Take Photo with Camera
- [ ] Tapping "拍照" triggers wx.chooseImage({sourceType: ['camera']})
- [ ] WeChat camera interface opens
- [ ] Camera interface has all controls (capture, switch camera, flash)
- [ ] Capturing photo returns to diagnosis page
- [ ] Captured image displays in preview area
- [ ] Image quality is acceptable (not blurry)
- [ ] Image dimensions are correct (not stretched)
- [ ] "重新拍照" and "确认使用" buttons appear

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

### TC-WX-104: Select Photo from Album
- [ ] Tapping "相册" triggers wx.chooseImage({sourceType: ['album']})
- [ ] WeChat album picker opens
- [ ] Recent photos are displayed
- [ ] User can navigate to all photos
- [ ] Selecting photo returns to diagnosis page
- [ ] Selected image displays in preview
- [ ] Image can be deselected

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

### TC-WX-105: Image Preview Actions
- [ ] Preview area displays selected image
- [ ] Tapping image shows full-screen preview
- [ ] Full-screen preview can be closed
- [ ] "删除" button removes selected image
- [ ] After deletion, camera component reappears
- [ ] "更换" button returns to camera/album selection

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

### TC-WX-106: User Info Form Display
- [ ] After image selection, user info form displays
- [ ] Age field label: "年龄"
- [ ] Age field accepts numeric keyboard
- [ ] Age range validation: 0-150
- [ ] Gender selector label: "性别"
- [ ] Gender options: "男", "女"
- [ ] Only one gender can be selected
- [ ] Chief complaint label: "主诉 (选填)"
- [ ] Chief complaint accepts multi-line text
- [ ] All fields have appropriate input focus

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

### TC-WX-107: Form Validation
- [ ] Age field rejects negative numbers
- [ ] Age field rejects numbers > 150
- [ ] Gender field shows error if not selected
- [ ] Validation error messages are clear
- [ ] Submit button is disabled when form is invalid
- [ ] Real-time validation feedback

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

### TC-WX-108: Submit Diagnosis
- [ ] "提交诊断" button is visible at bottom
- [ ] Button is enabled when all required fields are filled
- [ ] Tapping button shows loading indicator
- [ ] Loading indicator: circular spinner with "诊断中..."
- [ ] Image is converted to base64 before upload
- [ ] API request to `/api/v2/diagnosis` includes all data
- [ ] Request includes: user_id, image_base64, age, gender, chief_complaint
- [ ] Success response navigates to result page
- [ ] Error response displays error message

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

### TC-WX-109: Diagnosis Result Display
- [ ] Result page title: "诊断结果"
- [ ] Tongue image displays at top
- [ ] Mask overlay is visible on tongue image
- [ ] 6-dimension features section displays
- [ ] Each feature shows: name, confidence bar, percentage
- [ ] Features include: 舌色, 苔色, 舌形, 舌质, 特征, 整体
- [ ] Syndrome analysis card displays
- [ ] Syndrome card shows: name, description, confidence
- [ ] Health recommendations section displays (collapsed)
- [ ] Tapping recommendations expands them
- [ ] Risk alert displays if applicable

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

### TC-WX-110: Result Page Actions
- [ ] "有帮助" button is visible
- [ ] "无帮助" button is visible
- [ ] Tapping feedback button sends API request
- [ ] Success message displays after feedback
- [ ] "保存图片" button is visible
- [ ] Tapping save triggers wx.saveImageToPhotosAlbum()
- [ ] Save authorization is requested (first time)
- [ ] Success message displays after save
- [ ] "分享" button is visible
- [ ] Tapping share triggers wx.shareAppMessage()

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

## 3. History View (Priority: MEDIUM)

### TC-WX-201: Navigation to History
- [ ] "历史" tab in tab bar is visible
- [ ] Tapping tab navigates to history page
- [ ] History page title: "诊断历史"
- [ ] Tab bar highlights "历史" as active
- [ ] Navigation transition is smooth

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

### TC-WX-202: History List Display
- [ ] Diagnosis history list displays
- [ ] Each item shows: date, syndrome name, confidence score
- [ ] Date format is readable (YYYY-MM-DD HH:mm)
- [ ] Items are ordered by date (newest first)
- [ ] Empty state displays when no history
- [ ] Empty state message: "暂无诊断记录，快去体验吧"
- [ ] Empty state has illustration/icon

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

### TC-WX-203: Pull to Refresh
- [ ] Pulling down on list shows loading indicator
- [ ] Loading indicator is at top of list
- [ ] Releasing triggers refresh
- [ ] List updates with latest data
- [ ] Loading indicator disappears
- [ ] Refresh shows "最后更新: [time]" message

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

### TC-WX-204: Load More Pagination
- [ ] Scrolling to bottom shows "加载更多" indicator
- [ ] Indicator displays small spinner
- [ ] More items load automatically
- [ ] Loading completes and spinner disappears
- [ ] When all items loaded: "没有更多了" message
- [ ] "加载更多" doesn't show when no more items

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

### TC-WX-205: View Diagnosis Detail
- [ ] Tapping history item navigates to detail page
- [ ] Detail page title: "诊断详情"
- [ ] Tongue image displays at top
- [ ] All features are displayed
- [ ] Syndrome analysis is displayed
- [ ] Health recommendations are displayed
- [ ] Diagnosis timestamp is displayed
- [ ] Back button returns to history list
- [ ] Back button position is correct

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

## 4. Profile & Settings (Priority: MEDIUM)

### TC-WX-301: Profile Page Display
- [ ] "我的" tab in tab bar is visible
- [ ] Tapping tab navigates to profile page
- [ ] Profile page title: "我的"
- [ ] Tab bar highlights "我的" as active
- [ ] User avatar displays at top
- [ ] User nickname displays below avatar
- [ ] Avatar is circular and properly sized
- [ ] Avatar can be tapped to change (optional)

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

### TC-WX-302: Menu Items Display
- [ ] "健康档案" menu item is visible
- [ ] "设置" menu item is visible
- [ ] "隐私政策" menu item is visible
- [ ] "用户协议" menu item is visible
- [ ] "关于我们" menu item is visible
- [ ] All items have appropriate icons
- [ ] Items are evenly spaced
- [ ] Tapping item navigates correctly
- [ ] Navigation transitions are smooth

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

### TC-WX-303: Health Records Navigation
- [ ] Tapping "健康档案" navigates to records page
- [ ] Records page title: "健康档案"
- [ ] Records list displays (or empty state)
- [ ] "添加记录" button is visible (FAB or header)
- [ ] Back button returns to profile

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

### TC-WX-304: Settings Navigation
- [ ] Tapping "设置" navigates to settings page
- [ ] Settings page title: "设置"
- [ ] "语言" setting is visible
- [ ] "深色模式" setting is visible
- [ ] "清除缓存" setting is visible
- [ ] Each setting can be tapped
- [ ] Setting changes persist
- [ ] Back button returns to profile

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

### TC-WX-305: Logout Flow
- [ ] "退出登录" button is visible
- [ ] Button is red/warning color
- [ ] Tapping button shows confirmation dialog
- [ ] Dialog message: "确定要退出登录吗？"
- [ ] Dialog has "取消" and "确定" buttons
- [ ] Tapping "取消" closes dialog
- [ ] Tapping "确定" logs out user
- [ ] Tokens are cleared from storage
- [ ] User info is cleared
- [ ] User is redirected to login page
- [ ] Navigation is smooth

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

## 5. Mini-Program Features (Priority: LOW)

### TC-WX-401: Share Functionality
- [ ] "分享" button is visible on result page
- [ ] Tapping button triggers wx.shareAppMessage()
- [ ] Share title includes diagnosis result
- [ ] Share path includes diagnosis ID
- [ ] Share image is generated
- [ ] Share modal displays
- [ ] Share can be sent to WeChat contacts
- [ ] Share can be posted to Moments
- [ ] Share preview is correct

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

### TC-WX-402: Save to Album
- [ ] "保存图片" button is visible on result page
- [ ] Tapping button triggers wx.saveImageToPhotosAlbum()
- [ ] Image includes diagnosis result visualization
- [ ] Authorization is requested (first time)
- [ ] Authorization message is clear
- [ ] Save progress indicator displays
- [ ] Success message displays after save
- [ ] Failure message displays on error
- [ ] User can retry on failure

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

### TC-WX-403: Tab Bar
- [ ] Tab bar displays at bottom of all pages
- [ ] Tab bar has 3 tabs: 首页, 历史, 我的
- [ ] Active tab is highlighted (WeChat green)
- [ ] Inactive tabs are gray
- [ ] Tab icons are correct
- [ ] Tab labels are correct
- [ ] Tapping tab switches page
- [ ] Page transition is smooth
- [ ] Tab bar doesn't overlap content

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

### TC-WX-404: App Lifecycle
- [ ] Mini-program handles onLaunch event
- [ ] Mini-program handles onShow event
- [ ] Mini-program handles onHide event
- [ ] User session persists across app close
- [ ] Reopening app restores user session
- [ ] Auto-login works on app launch
- [ ] No data loss on app background

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

## 6. Performance & UX (Priority: MEDIUM)

### TC-WX-501: Page Load Performance
- [ ] First screen renders in < 2 seconds
- [ ] Page transitions are smooth (no jank)
- [ ] Images load progressively
- [ ] Loading states are shown during fetch
- [ ] No visible layout shifts

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

### TC-WX-502: Touch Response
- [ ] All buttons respond within 100ms
- [ ] Touch feedback is visible (button highlight)
- [ ] No double-tap issues
- [ ] Scroll performance is smooth (60fps)
- [ ] No lag on list rendering

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

### TC-WX-503: Error States
- [ ] Network errors show user-friendly message
- [ ] Empty states show helpful illustrations
- [ ] Error messages include retry options
- [ ] No raw error codes are displayed
- [ ] Errors don't crash the mini-program

**Pass/Fail**: _____
**Notes**: ___________
**Screenshot**: Attached / Not Required

---

## Summary

| Category | Total | Passed | Failed | Skipped | Pass Rate |
|----------|-------|--------|--------|---------|-----------|
| Login Flow | 5 | ___ | ___ | ___ | ___% |
| Diagnosis Flow | 10 | ___ | ___ | ___ | ___% |
| History View | 5 | ___ | ___ | ___ | ___% |
| Profile & Settings | 5 | ___ | ___ | ___ | ___% |
| Mini-Program Features | 4 | ___ | ___ | ___ | ___% |
| Performance & UX | 3 | ___ | ___ | ___ | ___% |
| **TOTAL** | **32** | **___** | **___** | **___** | **___%** |

---

## Overall Assessment

**Does the mini-program meet all requirements?** [ ] Yes [ ] No

**Critical Issues Found**: _____
**Major Issues Found**: _____
**Minor Issues Found**: _____

**Recommendations**:
1. ___________
2. ___________
3. ___________

**Tester Signature**: ___________
**Date**: ___________
