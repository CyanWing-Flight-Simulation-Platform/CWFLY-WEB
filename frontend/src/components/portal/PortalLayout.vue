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

    <!--页脚 -->
    <footer class="portal__footer">
      <div class="portal__footer-inner">
        <p>Copyright © 2026 CWFLY by Tearsvow All rights reserved.</p>
        <div class="footer-links">
          <router-link to="/user-agreement">用户协议</router-link>
          <router-link to="/privacy-policy">隐私政策</router-link>
          <router-link to="/cookie-policy">Cookie 政策</router-link>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
import PortalNavbar from './PortalNavbar.vue'
import CookieConsent from '@/components/CookieConsent.vue'
</script>

<style scoped>
.portal {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: transparent;
}

.portal__main {
  flex: 1;
  padding-top: calc(var(--header-h) + 16px);
  padding-bottom: 40px;
}

.portal__footer {
  background: var(--glass-bg-strong);
  backdrop-filter: blur(var(--glass-blur-lg)) saturate(var(--glass-saturate));
  -webkit-backdrop-filter: blur(var(--glass-blur-lg)) saturate(var(--glass-saturate));
  border-top: 1px solid var(--glass-border-strong);
  padding: 24px 0;
  text-align: center;
}

.portal__footer-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;
  color: var(--c-text-secondary);
}

/* --- 核心修改区域 --- */
.footer-links {
  margin-top: 12px; /* 稍微加大了与上方版权文字的间距 */
  
  /* 使用 Flexbox 布局解决挤压问题 */
  display: flex;
  justify-content: center; /* 居中对齐 */
  align-items: center;     /* 垂直居中 */
  flex-wrap: wrap;         /* 小屏幕下允许换行 */
}

.footer-links a {
  color: var(--c-text-muted);
  text-decoration: none;
  font-size: 13px;
  transition: color .2s;
}

.footer-links a:hover {
  color: var(--c-primary);
  text-decoration: underline;
}

/* 使用伪元素添加竖线分割，视觉更美观（最后一个元素不加） */
.footer-links a:not(:last-child)::after {
  content: "|";
  display: inline-block;
  margin: 0 12px; /* 竖线左右各 12px 间距 */
  color: var(--c-text-muted);
  opacity: 0.5;   /* 让竖线颜色稍微淡一点，不喧宾夺主 */
}
</style>