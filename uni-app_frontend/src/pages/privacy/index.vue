<template>
  <view class="container">
    <view class="header">
      <view class="header-left" @click="goBack">
        <text class="back-icon">←</text>
      </view>
      <text class="header-title">隐私政策</text>
      <view class="header-right"></view>
    </view>

    <view class="content">
      <view class="document">
        <text class="doc-title">隐私政策</text>
        <text class="doc-date">更新日期：2026年2月</text>

        <view class="doc-section">
          <text class="section-title">1. 信息收集</text>
          <text class="section-text">
            我们收集您在使用服务过程中主动提供或因为使用我们服务而产生的信息。包括但不限于：
          </text>
          <text class="section-text">• 舌象图像：用于AI诊断分析</text>
          <text class="section-text">• 基本健康信息：年龄、性别、主诉等</text>
          <text class="section-text">• 诊断历史记录</text>
          <text class="section-text">• 设备信息和日志信息</text>
        </view>

        <view class="doc-section">
          <text class="section-title">2. 信息使用</text>
          <text class="section-text">我们使用收集的信息用于：</text>
          <text class="section-text">• 提供舌诊AI诊断服务</text>
          <text class="section-text">• 改进和优化我们的服务</text>
          <text class="section-text">• 向您发送健康建议和服务通知</text>
          <text class="section-text">• 保护账号安全和防范欺诈</text>
        </view>

        <view class="doc-section">
          <text class="section-title">3. 信息共享</text>
          <text class="section-text">
            除以下情况外，我们不会与任何第三方共享您的个人信息：
          </text>
          <text class="section-text">• 获得您的明确同意</text>
          <text class="section-text">• 根据法律法规或政府要求</text>
          <text class="section-text">• 为保护用户或社会公众的重大利益</text>
          <text class="section-text">• 与我们的关联公司或合作伙伴共享（仅限于必要范围）</text>
        </view>

        <view class="doc-section">
          <text class="section-title">4. 信息存储</text>
          <text class="section-text">
            我们在中华人民共和国境内收集和产生的个人信息，将存储在中华人民共和国境内。
          </text>
          <text class="section-text">
            我们会采取合理的技术措施保护您的信息安全，防止信息丢失、泄露或被窃取。
          </text>
        </view>

        <view class="doc-section">
          <text class="section-title">5. 您的权利</text>
          <text class="section-text">您对自己的个人信息享有以下权利：</text>
          <text class="section-text">• 访问和获取您的个人信息</text>
          <text class="section-text">• 更正或补充您的个人信息</text>
          <text class="section-text">• 删除您的个人信息</text>
          <text class="section-text">• 注销账号</text>
          <text class="section-text">• 撤回同意</text>
        </view>

        <view class="doc-section">
          <text class="section-title">6. 未成年人保护</text>
          <text class="section-text">
            我们的服务主要面向成年人。如果您是未成年人，请在监护人的陪同下使用我们的服务。
          </text>
        </view>

        <view class="doc-section">
          <text class="section-title">7. 政策更新</text>
          <text class="section-text">
            我们可能会不时更新本隐私政策。更新后，我们会在应用内通知您。
          </text>
        </view>

        <view class="doc-section">
          <text class="section-title">8. 联系我们</text>
          <text class="section-text">如您对本隐私政策有任何疑问，请通过以下方式联系我们：</text>
          <text class="section-text">• 邮箱：privacy@aishezhen.com</text>
          <text class="section-text">• 电话：400-XXX-XXXX</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
function goBack() {
  uni.navigateBack()
}
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
  padding: 50px 15px 15px;
  border-bottom: 1px solid #f0f0f0;
}

.header-left,
.header-right {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
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
  padding: 15px;
}

.document {
  background: #ffffff;
  border-radius: 12px;
  padding: 25px;
}

.doc-title {
  font-size: 20px;
  font-weight: 500;
  color: #333333;
  margin-bottom: 5px;
  display: block;
}

.doc-date {
  font-size: 13px;
  color: #999999;
  margin-bottom: 25px;
  display: block;
}

.doc-section {
  margin-bottom: 25px;
}

.section-title {
  font-size: 16px;
  font-weight: 500;
  color: #333333;
  margin-bottom: 12px;
  display: block;
}

.section-text {
  font-size: 14px;
  color: #666666;
  line-height: 1.8;
  display: block;
  margin-bottom: 8px;
}
</style>
