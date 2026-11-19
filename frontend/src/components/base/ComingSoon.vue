<template>
  <div class="coming-soon fade-in">
    <div class="coming-soon__card">
      <span class="coming-soon__eyebrow">{{ tag }}</span>
      <h1 class="coming-soon__title">COMING SOON</h1>
      <p class="coming-soon__subtitle">{{ title }}</p>
      <p class="coming-soon__desc">{{ description }}</p>
      <router-link to="/dashboard" class="btn btn-primary btn-sm">返回仪表盘</router-link>
    </div>
  </div>
</template>

<script setup>
defineProps({
  tag: { type: String, default: 'CWFLY' },
  title: { type: String, default: '功能正在准备中' },
  description: { type: String, default: '我们正在完善这一部分，敬请期待。' }
})
</script>

<style scoped>
.coming-soon {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 58vh;
  padding: 40px 24px;
}

.coming-soon__card {
  width: 100%;
  max-width: 560px;
  padding: 44px 36px;
  border: 1px solid var(--c-border, rgba(15, 23, 42, .10));
  border-radius: 22px;
  background: var(--c-surface, rgba(255, 255, 255, .82));
  box-shadow: 0 18px 46px rgba(15, 23, 42, .08);
  text-align: center;
  backdrop-filter: blur(18px) saturate(130%);
  -webkit-backdrop-filter: blur(18px) saturate(130%);
}

.coming-soon__eyebrow {
  display: inline-block;
  color: var(--c-primary);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .18em;
  text-transform: uppercase;
}

.coming-soon__title {
  margin: 14px 0 8px;
  color: var(--c-text);
  font-family: "Inter", "PingFang SC", "OPPO Sans", "Source Han Sans SC", "Noto Sans SC", sans-serif;
  font-size: clamp(30px, 5vw, 46px);
  font-weight: 700;
  letter-spacing: .06em;
  line-height: 1.1;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.coming-soon__subtitle {
  margin: 0;
  color: var(--c-text);
  font-size: 17px;
  font-weight: 600;
}

.coming-soon__desc {
  max-width: 380px;
  margin: 12px auto 24px;
  color: var(--c-text-muted);
  font-size: 13px;
  line-height: 1.8;
}

html[data-theme='dark'] .coming-soon__card {
  border-color: rgba(255, 255, 255, .09);
  background: rgba(15, 23, 42, .58);
  box-shadow: 0 18px 46px rgba(0, 0, 0, .22);
}

html[data-theme='dark'] .coming-soon__title,
html[data-theme='dark'] .coming-soon__subtitle {
  color: #fff;
}

html[data-theme='dark'] .coming-soon__desc {
  color: rgba(255, 255, 255, .58);
}

@media (max-width: 560px) {
  .coming-soon {
    padding: 24px 16px;
  }

  .coming-soon__card {
    padding: 34px 22px;
  }
}
</style>
