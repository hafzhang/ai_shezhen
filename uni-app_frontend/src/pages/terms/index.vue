<template>
  <view class="container">
    <view class="header">
      <view class="header-left" @click="goBack">
        <text class="back-icon">←</text>
      </view>
      <text class="header-title">用户协议</text>
      <view class="header-right"></view>
    </view>

    <view class="content">
      <view class="document">
        <text class="doc-title">用户协议</text>
        <text class="doc-date">更新日期：2026年2月</text>

        <view class="doc-section">
          <text class="section-title">1. 服务说明</text>
          <text class="section-text">
            AI舌诊智能诊断系统（以下简称"本服务"）是基于深度学习的中医舌诊辅助诊断工具。
            本服务提供的诊断结果仅供参考，不构成医疗建议或诊断结论。
          </text>
        </view>

        <view class="doc-section">
          <text class="section-title">2. 用户资格</text>
          <text class="section-text">您确认并承诺：</text>
          <text class="section-text">• 年满18周岁，具有完全民事行为能力</text>
          <text class="section-text">• 未满18周岁需在监护人陪同下使用</text>
          <text class="section-text">• 具备使用本服务所需的设备和网络条件</text>
        </view>

        <view class="doc-section">
          <text class="section-title">3. 用户账号</text>
          <text class="section-text">• 用户有责任妥善保管账号和密码</text>
          <text class="section-text">• 用户对账号下发生的所有活动承担责任</text>
          <text class="section-text">• 禁止将账号转让、出借或分享给他人使用</text>
          <text class="section-text">• 如发现账号被盗用，应立即通知我们</text>
        </view>

        <view class="doc-section">
          <text class="section-title">4. 服务使用</text>
          <text class="section-text">用户在使用本服务时应遵守：</text>
          <text class="section-text">• 遵守相关法律法规和本协议规定</text>
          <text class="section-text">• 不得利用本服务从事任何违法或侵权活动</text>
          <text class="section-text">• 不得上传虚假、误导性或有害信息</text>
          <text class="section-text">• 不得干扰或破坏本服务的正常运行</text>
        </view>

        <view class="doc-section">
          <text class="section-title">5. 知识产权</text>
          <text class="section-text">
            本服务的所有内容，包括但不限于文字、图片、软件、算法等，均受知识产权法保护。
            未经授权，不得复制、传播或用于商业目的。
          </text>
        </view>

        <view class="doc-section">
          <text class="section-title">6. 免责声明</text>
          <text class="section-text">• 本服务仅供参考，不替代专业医疗建议</text>
          <text class="section-text">• 我们不对诊断结果的准确性做任何保证</text>
          <text class="section-text">• 因使用本服务而产生的任何后果，由用户自行承担</text>
          <text class="section-text">• 因不可抗力导致的服务中断，我们不承担责任</text>
        </view>

        <view class="doc-section">
          <text class="section-title">7. 服务变更</text>
          <text class="section-text">
            我们保留随时修改、中断或终止本服务的权利，无需对用户或第三方承担责任。
          </text>
        </view>

        <view class="doc-section">
          <text class="section-title">8. 争议解决</text>
          <text class="section-text">
            因本协议引起的任何争议，双方应友好协商解决。协商不成的，任何一方可向我们所在地人民法院提起诉讼。
          </text>
        </view>

        <view class="doc-section">
          <text class="section-title">9. 协议更新</text>
          <text class="section-text">
            我们可能会不时更新本协议。更新后的协议一旦公布即代替原协议。
            继续使用本服务即表示您接受修改后的协议。
          </text>
        </view>

        <view class="doc-section">
          <text class="section-title">10. 联系我们</text>
          <text class="section-text">如您对本协议有任何疑问，请通过以下方式联系我们：</text>
          <text class="section-text">• 邮箱：legal@aishezhen.com</text>
          <text class="section-text">• 电话：400-XXX-XXXX</text>
        </view>

        <view class="agreement-section">
          <text class="agreement-text">
            使用本服务即表示您已阅读、理解并同意本用户协议的全部内容。
          </text>
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

.agreement-section {
  margin-top: 30px;
  padding-top: 20px;
  border-top: 1px solid #f0f0f0;
}

.agreement-text {
  font-size: 13px;
  color: #999999;
  line-height: 1.6;
  display: block;
}
</style>
