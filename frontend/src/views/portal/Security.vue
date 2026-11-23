<template>
  <div class="legal fade-in">
    <div class="legal__inner">
      <div class="page-header">
        <h1>安全漏洞披露</h1>
        <p>CWFLY 安全问题的提交方式、处理流程与承诺</p>
      </div>

      <div class="card p-lg mb-lg legal__meta">
        <p class="text-secondary" style="line-height:1.8;margin:0;">
          <strong>最后更新：</strong>2026 年 11 月 23 日
        </p>
        <p class="text-sm text-muted mt-sm" style="margin:0;">
          相关文档：
          <router-link to="/user-agreement">用户协议</router-link>
          <span class="sep">·</span>
          <router-link to="/privacy-policy">隐私政策</router-link>
          <span class="sep">·</span>
          <a href="/.well-known/security.txt" target="_blank" rel="noopener">security.txt</a>
        </p>
      </div>

      <div class="card p-lg mb-lg">
        <h3 class="mb-md">一、如何提交</h3>
        <p class="text-secondary" style="line-height:1.8;">
          请把漏洞详情<strong>加密后</strong>发送至
          <a href="mailto:support@cwflysim.cn">support@cwflysim.cn</a>，
          邮件标题注明「安全披露」。未加密的普通邮件也可以，但请不要在公开渠道
          （QQ 群、论坛、GitHub Issue 等）发布未修复的漏洞细节。
        </p>
        <p class="text-secondary mt-sm" style="line-height:1.8;">
          机器可读的披露信息见
          <a href="/.well-known/security.txt" target="_blank" rel="noopener">/.well-known/security.txt</a>
          （RFC 9116）。
        </p>
      </div>

      <div class="card p-lg mb-lg">
        <h3 class="mb-md">二、PGP 公钥</h3>
        <p class="text-secondary" style="line-height:1.8;">
          UID：<strong>CWFLY Security (vulnerability disclosure) &lt;security@cwflysim.cn&gt;</strong><br />
          指纹：
          <code class="sec-code">2DAF AE10 77CD 6A5B C67B 7707 AE54 C156 2FAE CB9B</code><br />
          算法：ed25519（签名）+ cv25519（加密），有效期至 2029-11-22
        </p>
        <p class="text-secondary mt-sm" style="line-height:1.8;">
          公钥文件：
          <a href="/.well-known/pgp-key.txt" target="_blank" rel="noopener">/.well-known/pgp-key.txt</a>
          <span class="text-sm text-muted">（ASCII armored）</span>
        </p>
        <pre class="sec-pre"># 1. 导入公钥并核对指纹
gpg --import pgp-key.txt
gpg --fingerprint security@cwflysim.cn

# 2. 加密你的报告
gpg --encrypt --armor --recipient security@cwflysim.cn report.txt

# 3. 把生成的 report.txt.asc 发到 support@cwflysim.cn</pre>
        <p class="text-sm text-muted" style="margin:0;line-height:1.7;">
          请务必核对指纹前 8 位 <code class="sec-code">2DAF AE10</code> 与上文一致，
          避免使用被替换的公钥。
        </p>
      </div>

      <div class="card p-lg mb-lg">
        <h3 class="mb-md">三、我们的承诺</h3>
        <ul class="text-secondary sec-list">
          <li>收到报告后 <strong>3 个工作日内</strong>确认收到，<strong>10 个工作日内</strong>给出初步评估。</li>
          <li>仅修复所需的最小范围使用你提供的信息，不用于其他目的。</li>
          <li>修复上线后，经你同意会在本页致谢（也可完全匿名）。</li>
          <li>对符合本页要求、且未造成实际损害的善意测试，我们不会追究法律责任，也不会因此封禁账号。</li>
          <li>修复前默认 <strong>90 天</strong>不公开细节；双方可协商提前或延后。</li>
        </ul>
      </div>

      <div class="card p-lg mb-lg">
        <h3 class="mb-md">四、测试边界</h3>
        <p class="text-secondary" style="line-height:1.8;">
          允许：对你自己注册的账号进行测试，或使用我们明确提供的测试账号。
        </p>
        <p class="text-secondary mt-sm" style="line-height:1.8;">
          禁止：对他人账号/数据的访问与破坏、拒绝服务与压测（含 FSD、ATC 等实时服务）、
          社工与钓鱼、物理入侵、以及任何影响平台正常连飞的操作。
        </p>
      </div>

      <div class="card p-lg">
        <h3 class="mb-md">五、不在范围内</h3>
        <ul class="text-secondary sec-list" style="margin-bottom:0;">
          <li>依赖库自身已公开的 CVE（请直接反馈给上游项目）。</li>
          <li>无实际影响的纯信息类问题（如版本号暴露、缺少某条安全响应头且无法利用）。</li>
          <li>第三方服务（地图、邮件、人机校验、CDN）的问题。</li>
          <li>社会工程、垃圾邮件、内容合规类问题（请走工单或反馈渠道）。</li>
        </ul>
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
  max-width: 860px;
  margin: 0 auto;
}
.sec-code {
  padding: 1px 6px;
  border-radius: 5px;
  background: color-mix(in srgb, var(--c-text) 6%, transparent);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12.5px;
  word-break: break-all;
}
.sec-pre {
  margin: 14px 0;
  padding: 14px 16px;
  overflow-x: auto;
  border: 1px solid var(--glass-border-strong);
  border-radius: 10px;
  background: color-mix(in srgb, var(--c-text) 4%, transparent);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12.5px;
  line-height: 1.8;
  color: var(--c-text-secondary);
}
.sec-list {
  margin: 0 0 0 18px;
  padding: 0;
  line-height: 1.9;
}
.sec-list li + li {
  margin-top: 6px;
}
</style>
