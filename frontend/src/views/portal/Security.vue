<template>
  <div class="legal fade-in">
    <div class="legal__inner">
      <div class="page-header">
        <h1>安全漏洞披露</h1>
        <p>CWFLY 安全问题的提交方式、处理流程、范围边界与我们给出的承诺</p>
      </div>

      <div class="card p-lg mb-lg legal__meta">
        <p class="text-secondary" style="line-height:1.8;margin:0;">
          <strong>政策版本：</strong>v1.0 ·
          <strong>生效日期：</strong>2026 年 11 月 23 日 ·
          <strong>最后更新：</strong>2026 年 11 月 23 日
        </p>
        <p class="text-sm text-muted mt-sm" style="margin:0;">
          相关文档：
          <router-link to="/user-agreement">用户协议</router-link>
          <span class="sep">·</span>
          <router-link to="/privacy-policy">隐私政策</router-link>
          <span class="sep">·</span>
          <a href="/.well-known/security.txt" target="_blank" rel="noopener">security.txt</a>
          <span class="sep">·</span>
          <a href="#changelog">更新记录</a>
        </p>
      </div>

      <!-- 一页速览 -->
      <div class="card p-lg mb-lg sec-summary">
        <h3 class="mb-md">一、一页速览</h3>
        <ul class="sec-facts">
          <li><span class="sec-facts__k">提交渠道</span><span class="sec-facts__v">邮箱 <a href="mailto:support@cwflysim.cn">support@cwflysim.cn</a>，请用 PGP 加密</span></li>
          <li><span class="sec-facts__k">公钥指纹</span><span class="sec-facts__v"><code class="sec-code">2DAF AE10 77CD 6A5B C67B 7707 AE54 C156 2FAE CB9B</code></span></li>
          <li><span class="sec-facts__k">首次回应</span><span class="sec-facts__v">3 个工作日内确认收到</span></li>
          <li><span class="sec-facts__k">保密期</span><span class="sec-facts__v">修复前默认 90 天不公开细节</span></li>
          <li><span class="sec-facts__k">奖励</span><span class="sec-facts__v">公开致谢（可选匿名），暂无金钱奖励</span></li>
          <li><span class="sec-facts__k">善意测试</span><span class="sec-facts__v">不追究法律责任、不封号，范围见第四节</span></li>
        </ul>
      </div>

      <div class="card p-lg mb-lg">
        <h3 class="mb-md">二、如何提交</h3>
        <p class="text-secondary" style="line-height:1.8;">
          请把报告<strong>加密后</strong>发送至 <a href="mailto:support@cwflysim.cn">support@cwflysim.cn</a>，
          邮件标题格式为 <code class="sec-code">[安全披露] 一句话概括问题</code>。
        </p>
        <p class="text-secondary mt-sm" style="line-height:1.8;">
          不要在 QQ 群、论坛、GitHub Issue、社交平台等公开渠道发布未修复的漏洞细节。
          若你无法使用 PGP，也可以直接明文发送，但请只包含必要信息，并在邮件中注明「未加密」。
        </p>
        <p class="text-secondary mt-sm" style="line-height:1.8;">
          机器可读的披露信息见
          <a href="/.well-known/security.txt" target="_blank" rel="noopener">/.well-known/security.txt</a>（RFC 9116）。
        </p>
      </div>

      <div class="card p-lg mb-lg">
        <h3 class="mb-md">三、PGP 公钥</h3>
        <p class="text-secondary" style="line-height:1.8;">
          UID：<strong>CWFLY Security (vulnerability disclosure) &lt;security@cwflysim.cn&gt;</strong><br />
          指纹：<code class="sec-code">2DAF AE10 77CD 6A5B C67B 7707 AE54 C156 2FAE CB9B</code><br />
          算法：ed25519（签名）+ cv25519（加密），有效期至 2029-11-22
        </p>
        <p class="text-secondary mt-sm" style="line-height:1.8;">
          公钥文件：
          <a href="/.well-known/pgp-key.txt" target="_blank" rel="noopener">/.well-known/pgp-key.txt</a>
          <span class="text-sm text-muted">（ASCII armored）</span> ·
          分离签名：
          <a href="/.well-known/security.txt.asc" target="_blank" rel="noopener">security.txt.asc</a>
        </p>
        <pre class="sec-pre"># 1. 导入公钥并核对指纹
gpg --import pgp-key.txt
gpg --fingerprint security@cwflysim.cn

# 2. 加密你的报告
gpg --encrypt --armor --recipient security@cwflysim.cn report.txt

# 3. 把生成的 report.txt.asc 作为附件发到 support@cwflysim.cn</pre>
        <p class="text-sm text-muted" style="margin:0;line-height:1.7;">
          请核对指纹前 8 位 <code class="sec-code">2DAF AE10</code> 与上文一致，避免使用被替换的公钥。
        </p>
      </div>

      <div class="card p-lg mb-lg">
        <h3 class="mb-md">四、报告应包含什么</h3>
        <p class="text-secondary" style="line-height:1.8;">按下面的清单写，能让我们一次看懂，减少来回沟通：</p>
        <ol class="sec-steps">
          <li><strong>问题标题</strong>：一句话说明是什么类型的问题。</li>
          <li><strong>受影响资产</strong>：域名、接口路径、页面地址、功能模块。</li>
          <li><strong>复现步骤</strong>：从零开始的最短路径，包含必要的账号角色（请用你自己注册的账号）。</li>
          <li><strong>验证证据</strong>：请求/响应、截图、脚本。请删除他人数据与你的敏感凭据。</li>
          <li><strong>影响评估</strong>：能读取、修改或删除什么；是否需要登录；影响多少用户。</li>
          <li><strong>测试环境</strong>：浏览器/系统版本、时间（含时区）、是否使用代理。</li>
          <li><strong>披露意向</strong>：是否已告知他人、希望何时公开、如何署名（可要求匿名）。</li>
        </ol>
        <p class="text-sm text-muted" style="margin:10px 0 0;line-height:1.7;">
          报告越接近可直接复现，处理越快；只有一张截图、没有步骤的报告通常会被降级。
        </p>
      </div>

      <div class="card p-lg mb-lg">
        <h3 class="mb-md">五、支持范围</h3>
        <div class="sec-scope">
          <div class="sec-scope__col">
            <h4 class="sec-scope__title">在范围内</h4>
            <ul class="sec-list">
              <li><code class="sec-code">cwflysim.cn</code>、<code class="sec-code">www.cwflysim.cn</code>、<code class="sec-code">api.cwflysim.cn</code> 的业务接口与页面</li>
              <li><code class="sec-code">atc.cwflysim.cn</code>（ATC 管制员中心）</li>
              <li>账号与鉴权：登录、注册、会话、Passkey / WebAuthn、找回密码</li>
              <li>第三方授权：OAuth2 授权服务与授权码、令牌、用户信息接口</li>
              <li>越权与数据隔离：水平/垂直越权、IDOR、信息泄露</li>
              <li>上传与渲染：文件上传、图片/附件处理、存储型 XSS</li>
            </ul>
          </div>
          <div class="sec-scope__col">
            <h4 class="sec-scope__title sec-scope__title--out">不在范围内</h4>
            <ul class="sec-list">
              <li>对实时服务（FSD 连飞、ATC 在线席位）的任何压测或拒绝服务测试</li>
              <li>第三方服务：地图、邮件、人机校验、CDN、云厂商</li>
              <li>社工、钓鱼、物理入侵、尾随、冒充工作人员</li>
              <li>内容合规、垃圾信息、账号交易等非技术问题（请走工单）</li>
              <li>依赖库已公开的 CVE（请直接反馈给上游项目）</li>
              <li>无实际影响的纯信息类问题：版本号暴露、无法利用的缺失响应头</li>
              <li>自动化扫描器的默认输出，未经人工确认可利用性</li>
            </ul>
          </div>
        </div>
      </div>

      <div class="card p-lg mb-lg">
        <h3 class="mb-md">六、响应时限</h3>
        <table class="sec-table">
          <thead>
            <tr><th>时间</th><th>我们会做什么</th></tr>
          </thead>
          <tbody>
            <tr><td>3 个工作日内</td><td>人工确认收到，给出受理编号</td></tr>
            <tr><td>10 个工作日内</td><td>完成初评：是否受理、初步定级、是否需要补充信息</td></tr>
            <tr><td>30 天内</td><td>完成修复，或给出明确的修复计划与预计时间</td></tr>
            <tr><td>90 天内</td><td>默认保密期结束；经你同意可提前公开，也可协商延后</td></tr>
          </tbody>
        </table>
        <p class="text-sm text-muted" style="margin:12px 0 0;line-height:1.7;">
          以上为工作日计时，遇重大故障或节假日顺延；任何一步超时，你可以主动邮件追问。
        </p>
      </div>

      <div class="card p-lg mb-lg">
        <h3 class="mb-md">七、致谢</h3>
        <p class="text-secondary" style="line-height:1.8;">
          修复上线后，经你同意会在本页「致谢名单」与更新记录中署名（昵称 / 主页链接均可），
          你也可以要求完全匿名。我们目前<strong>不提供金钱奖励</strong>，也不承诺礼品；
          请勿以获取奖励为目的进行测试。
        </p>
        <div class="sec-thanks">
          <p class="sec-thanks__empty">暂无公开致谢记录</p>
        </div>
      </div>

      <div class="card p-lg mb-lg">
        <h3 class="mb-md">八、我们的承诺</h3>
        <p class="text-secondary" style="line-height:1.8;">
          对于<strong>遵守本页全部规则</strong>、出于善意、且未造成实质损害的安全测试，我们承诺：
        </p>
        <ul class="sec-list">
          <li>不追究法律责任，不向司法机关或平台举报；</li>
          <li>不因此封禁、限制或标记你的账号；</li>
          <li>仅将你提供的信息用于定位与修复问题，不用于其他用途；</li>
          <li>不要求你提供超出复现所需的个人信息。</li>
        </ul>
        <p class="text-secondary mt-sm" style="line-height:1.8;">
          如果你在测试中意外接触到他人数据或非公开信息：请<strong>立即停止</strong>、不要扩大范围、
          不要保存或传播，并在报告中说明接触范围。超出本页范围的测试不受上述承诺保护。
        </p>
      </div>

      <div class="card p-lg mb-lg">
        <h3 class="mb-md">九、更新记录</h3>
        <table class="sec-table" id="changelog">
          <thead>
            <tr><th>版本</th><th>日期</th><th>变更</th></tr>
          </thead>
          <tbody>
            <tr><td>v1.0</td><td>2026-11-23</td><td>首次发布：披露渠道、PGP 公钥、报告清单、范围与时限、致谢与承诺</td></tr>
          </tbody>
        </table>
      </div>

      <div class="card p-lg">
        <h3 class="mb-md">十、联系方式</h3>
        <p class="text-secondary" style="line-height:1.8;margin:0;">
          安全报告：<a href="mailto:support@cwflysim.cn">support@cwflysim.cn</a>（PGP 加密优先）<br />
          非安全问题（账号、内容、功能）：请走站内工单或反馈入口。
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
// 纯静态披露政策页，无数据请求
</script>

<style scoped>
.legal {
  padding: 40px 20px 80px;
}
.legal__inner {
  max-width: 880px;
  margin: 0 auto;
}

/* 速览 */
.sec-facts {
  margin: 0;
  padding: 0;
  list-style: none;
}
.sec-facts li {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr);
  gap: 18px;
  align-items: baseline;
  padding: 7px 0;
  line-height: 1.7;
}
.sec-facts__k {
  font-size: 12.5px;
  color: var(--c-text-muted);
}
.sec-facts__v {
  font-size: 14px;
  color: var(--c-text-secondary);
}

.sec-code {
  padding: 1px 6px;
  border-radius: 5px;
  /* 实心底色：不跟随卡片/背景图透明，保证代码片段在任何背景上清晰 */
  background: #f3f4f6;
  border: 1px solid #e5e7eb;
  color: #111827;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12.5px;
  word-break: break-all;
}
html[data-theme='dark'] .sec-code {
  background: #1f2937;
  border-color: #334155;
  color: #F1F5F9;
}
.sec-pre {
  margin: 14px 0;
  padding: 14px 16px;
  overflow-x: auto;
  /* 代码块用深色实心底（两套主题一致），不透明、不跟卡片混色 */
  border: 1px solid rgba(255, 255, 255, .10);
  border-radius: 10px;
  background: #0f172a;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12.5px;
  line-height: 1.8;
  color: #e2e8f0;
}

/* 列表 */
.sec-list {
  margin: 0 0 0 18px;
  padding: 0;
  line-height: 1.9;
}
.sec-list li + li {
  margin-top: 6px;
}
.sec-steps {
  margin: 0 0 0 18px;
  padding: 0;
  line-height: 1.9;
}
.sec-steps li + li {
  margin-top: 8px;
}

/* 范围两列 */
.sec-scope {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 28px;
}
.sec-scope__title {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text);
}
.sec-scope__title--out {
  color: var(--c-text-muted);
}
.sec-scope .sec-list {
  margin-left: 16px;
  font-size: 13.5px;
  color: var(--c-text-secondary);
}

/* 表格 */
.sec-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13.5px;
}
.sec-table th,
.sec-table td {
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid var(--glass-border);
  color: var(--c-text-secondary);
  vertical-align: top;
  line-height: 1.7;
}
.sec-table th {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--c-text-muted);
}
.sec-table tr:last-child td {
  border-bottom: none;
}
.sec-table td:first-child {
  white-space: nowrap;
  color: var(--c-text);
}

/* 致谢占位 */
.sec-thanks {
  margin-top: 14px;
  padding: 18px;
  border: 1px solid var(--glass-border);
  border-radius: 10px;
  text-align: center;
}
.sec-thanks__empty {
  margin: 0;
  font-size: 13px;
  color: var(--c-text-muted);
}

@media (max-width: 720px) {
  .sec-scope {
    grid-template-columns: minmax(0, 1fr);
    gap: 20px;
  }
  .sec-facts li {
    grid-template-columns: minmax(0, 1fr);
    gap: 2px;
  }
  .sec-table td:first-child {
    white-space: normal;
  }
}
</style>
