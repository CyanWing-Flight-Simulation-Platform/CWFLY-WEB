<template>
  <div class="portal">
    <!-- 顶部导航 -->
    <PortalNavbar />

    <!-- 主内容 -->
    <main class="portal__main">
      <router-view />
    </main>

    <!-- Cookie 同意提示 -->
    <CookieConsent />

    <!-- 页脚 -->
    <footer class="portal__footer">
      <div class="portal__footer-inner">
        <div class="footer-top">
          <div class="footer-brand">
            <router-link to="/" class="footer-brand__name">CWFLY</router-link>
            <p>青翼模拟飞行连飞平台。连接飞行员与管制员，在真实的航路和空域中一起飞行。</p>
            <a :href="qqGroupUrl" target="_blank" rel="noopener" class="footer-brand__social">加入 QQ 群 ↗</a>
          </div>

          <div class="footer-columns">
            <div class="footer-column">
              <h4>飞行工具</h4>
              <router-link to="/map">在线地图</router-link>
              <router-link to="/charts">航情查询</router-link>
              <router-link to="/weather">气象报文</router-link>
              <router-link to="/flight-plan">飞行计划</router-link>
            </div>
            <div class="footer-column">
              <h4>社区服务</h4>
              <router-link to="/events">飞行活动</router-link>
              <router-link to="/leaderboard">排行榜</router-link>
              <router-link to="/knowledge">知识库</router-link>
              <a href="https://cwforum.org" target="_blank" rel="noopener">社区论坛 ↗</a>
            </div>
            <div class="footer-column">
              <h4>关于我们</h4>
              <router-link to="/about">关于 CWFLY</router-link>
              <router-link to="/meetings">会议记录</router-link>
              <router-link to="/controller-public">职员公示</router-link>
              <router-link to="/apply/controller">成为管制员</router-link>
            </div>
          </div>
        </div>

        <div class="footer-bottom">
          <p>Copyright © 2026 CWFLY by Tearsvow All rights reserved.</p>
          <div class="footer-links">
            <router-link to="/user-agreement">用户协议</router-link>
            <router-link to="/privacy-policy">隐私政策</router-link>
            <router-link to="/cookie-policy">Cookie 政策</router-link>
            <router-link to="/security">安全披露</router-link>
            <span class="footer-note">仅供模拟飞行使用</span>
          </div>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
import PortalNavbar from './PortalNavbar.vue'
import CookieConsent from '@/components/CookieConsent.vue'
import { QQ_GROUP_URL } from '@/utils/links'

const qqGroupUrl = QQ_GROUP_URL
</script>

<style scoped>
.portal {
  --portal-header-h: 56px;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: transparent;
}

.portal__main {
  flex: 1;
  padding-top: calc(var(--portal-header-h) + 18px);
  padding-bottom: 40px;
}

.portal__footer {
  border-top: 1px solid var(--glass-border-strong);
  background: var(--glass-bg-strong);
  backdrop-filter: blur(var(--glass-blur-lg)) saturate(var(--glass-saturate));
  -webkit-backdrop-filter: blur(var(--glass-blur-lg)) saturate(var(--glass-saturate));
  padding: 36px 0 24px;
}

.portal__footer-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;
  color: var(--c-text-secondary);
}

.footer-top {
  display: flex;
  justify-content: space-between;
  gap: 48px;
}

.footer-brand {
  max-width: 300px;
}

.footer-brand__name {
  color: var(--c-text);
  font-size: 18px;
  font-weight: 750;
  letter-spacing: -.03em;
  text-decoration: none;
}

.footer-brand p {
  margin: 10px 0 14px;
  color: var(--c-text-muted);
  font-size: 12px;
  line-height: 1.8;
}

.footer-brand__social {
  color: var(--c-primary);
  font-size: 12px;
  font-weight: 600;
  text-decoration: none;
}
.footer-brand__social:hover { text-decoration: underline; }

.footer-columns {
  display: flex;
  gap: 64px;
}

.footer-column {
  display: flex;
  flex-direction: column;
  gap: 9px;
  min-width: 80px;
}

.footer-column h4 {
  margin: 0 0 4px;
  color: var(--c-text);
  font-size: 12px;
  font-weight: 700;
}

.footer-column a {
  color: var(--c-text-muted);
  font-size: 12px;
  text-decoration: none;
  transition: color .2s;
}
.footer-column a:hover { color: var(--c-primary); text-decoration: none; }

.footer-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-top: 32px;
  padding-top: 18px;
  border-top: 1px solid var(--panel-border);
}

.footer-bottom p {
  margin: 0;
  color: var(--c-text-muted);
  font-size: 11px;
}

.footer-links {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0;
}

.footer-links a {
  color: var(--c-text-muted);
  font-size: 11px;
  text-decoration: none;
  transition: color .2s;
}
.footer-links a:hover { color: var(--c-primary); text-decoration: none; }
.footer-links a:not(:last-of-type)::after {
  content: "|";
  margin: 0 10px;
  color: var(--c-text-muted);
  opacity: .45;
}

.footer-note {
  margin-left: 12px;
  color: var(--c-text-muted);
  font-size: 11px;
  opacity: .7;
}


/* 浅色模式 Footer：与首页一致的白磨砂玻璃 + 深色文字 */
html[data-theme='light'] .portal__footer {
  border-top: 0;
  background: transparent;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
}
html[data-theme='light'] .portal__footer-inner { color: #4B5563; }
html[data-theme='light'] .footer-brand__name,
html[data-theme='light'] .footer-column h4 { color: #111827; }
html[data-theme='light'] .footer-brand p,
html[data-theme='light'] .footer-column a,
html[data-theme='light'] .footer-bottom p,
html[data-theme='light'] .footer-links a,
html[data-theme='light'] .footer-note { color: #4B5563; }
html[data-theme='light'] .footer-bottom { border-top-color: rgba(15, 23, 42, .08); }

@media (max-width: 860px) {
  .footer-top { flex-direction: column; gap: 28px; }
  .footer-brand { max-width: 420px; }
  .footer-columns { gap: 32px; justify-content: space-between; }
}

@media (max-width: 600px) {
  .portal__footer { padding-top: 28px; }
  .portal__footer-inner { padding: 0 16px; }
  .footer-columns { display: grid; grid-template-columns: repeat(2, 1fr); gap: 24px 20px; }
  .footer-bottom { flex-direction: column; align-items: flex-start; }
  .footer-note { margin-left: 0; }
}
</style>
