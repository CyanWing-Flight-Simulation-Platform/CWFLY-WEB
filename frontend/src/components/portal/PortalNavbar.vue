<template>
  <nav class="portal-nav">
    <div class="portal-nav__inner">
      <router-link to="/" class="portal-nav__logo" aria-label="CWFLY 首页">
        <span class="portal-nav__brand">CWFLY</span>
      </router-link>

      <button
        class="portal-nav__hamburger"
        :aria-expanded="mobileOpen"
        :aria-label="mobileOpen ? '关闭菜单' : '打开菜单'"
        @click="mobileOpen = !mobileOpen"
      >
        <span></span><span></span><span></span>
      </button>

      <div class="portal-nav__right" :class="{ 'portal-nav__right--open': mobileOpen }" ref="navRef">
        <div
          v-for="group in navGroups"
          :key="group.id"
          class="portal-nav__item dropdown"
          @mouseenter="openMenu = group.id"
          @mouseleave="openMenu = null"
        >
          <button
            type="button"
            class="portal-nav__link dropdown__trigger"
            :class="{ 'portal-nav__link--active': openMenu === group.id }"
            :aria-expanded="openMenu === group.id"
            @click.stop="toggleMenu(group.id)"
          >
            <span>{{ group.label }}</span>
            <svg
              class="dropdown__arrow"
              :class="{ 'dropdown__arrow--up': openMenu === group.id }"
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2.5"
              aria-hidden="true"
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>

          <Transition name="drop">
            <div v-if="openMenu === group.id" class="dropdown__menu card" @click="closeMenu">
              <div class="dropdown__heading">{{ group.label }}</div>
              <template v-for="item in group.items" :key="item.label">
                <a
                  v-if="item.href"
                  :href="item.href"
                  class="dropdown__item"
                  target="_blank"
                  rel="noopener"
                >
                  <span>{{ item.label }}</span>
                  <small>{{ item.desc }}</small>
                </a>
                <router-link v-else :to="item.to" class="dropdown__item">
                  <span>{{ item.label }}</span>
                  <small>{{ item.desc }}</small>
                </router-link>
              </template>
            </div>
          </Transition>
        </div>

        <div class="portal-nav__spacer"></div>

        <div class="portal-nav__auth">
          <router-link v-if="userStore.isLoggedIn" to="/dashboard" class="portal-nav__login" @click="closeMenu">控制台</router-link>
          <template v-else>
            <router-link to="/login" class="portal-nav__login" @click="closeMenu">登录</router-link>
            <router-link to="/register" class="portal-nav__register" @click="closeMenu">注册</router-link>
          </template>
        </div>

        <div class="theme-toggle" role="group" aria-label="主题切换">
          <button
            v-for="t in themeOptions"
            :key="t.id"
            type="button"
            class="theme-btn"
            :class="{ active: themeMode === t.id }"
            @click="setTheme(t.id)"
          >
            {{ t.label }}
          </button>
        </div>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { themeMode, setThemeMode } from '@/utils/theme'
import { useUserStore } from '@/store/user'

const userStore = useUserStore()

const themeOptions = [
  { id: 'auto', label: 'Auto' },
  { id: 'light', label: '浅色' },
  { id: 'dark', label: '深色' },
]

const navGroups = [
  {
    id: 'tools',
    label: '飞行工具',
    items: [
      { to: '/map', label: '在线地图', desc: '实时机组、航迹与空域' },
      { to: '/charts', label: '航情查询', desc: '机场航图与航路资料' },
      { to: '/weather', label: '气象报文', desc: 'METAR / TAF 查询' },
      { to: '/flight-plan', label: '飞行计划', desc: '提交与同步连飞计划' },
    ],
  },
  {
    id: 'community',
    label: '社区服务',
    items: [
      { to: '/events', label: '飞行活动', desc: '近期活动与报名' },
      { to: '/leaderboard', label: '排行榜', desc: '积分与飞行贡献榜' },
      { to: '/knowledge', label: '知识库', desc: '飞行与管制资料' },
      { href: 'https://cwforum.org', label: '社区论坛', desc: '前往独立论坛' },
    ],
  },
  {
    id: 'join',
    label: '加入我们',
    items: [
      { to: '/apply/controller', label: '成为管制员', desc: '加入管制团队' },
      { to: '/apply/staff', label: '职员申请', desc: '参与平台运营' },
      { to: '/controller-public', label: '职员公示', desc: '查看现任职员' },
    ],
  },
  {
    id: 'about',
    label: '关于我们',
    items: [
      { to: '/about', label: '关于 CWFLY', desc: '了解平台与团队' },
      { to: '/meetings', label: '会议记录', desc: '公开会议与决议' },
      { to: '/user-agreement', label: '用户协议', desc: '平台使用规则' },
      { to: '/privacy-policy', label: '隐私政策', desc: '数据与隐私说明' },
    ],
  },
]

const openMenu = ref(null)
const mobileOpen = ref(false)
const navRef = ref(null)

function setTheme(mode) {
  setThemeMode(mode)
}

function toggleMenu(id) {
  openMenu.value = openMenu.value === id ? null : id
}

function closeMenu() {
  openMenu.value = null
  mobileOpen.value = false
}

function handleClickOutside(e) {
  const target = e.target
  const clickedHamburger = target instanceof Element && target.closest('.portal-nav__hamburger')
  if (clickedHamburger) return
  if (navRef.value && !navRef.value.contains(target)) {
    openMenu.value = null
    mobileOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', handleClickOutside))
onUnmounted(() => document.removeEventListener('click', handleClickOutside))
</script>

<style scoped>
.portal-nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: var(--portal-header-h, 56px);
  background: linear-gradient(180deg, rgba(255, 255, 255, .26), rgba(255, 255, 255, 0) 92%);
  backdrop-filter: blur(8px) saturate(130%);
  -webkit-backdrop-filter: blur(8px) saturate(130%);
  border-bottom: 0;
  z-index: 1000;
  box-shadow: none;
}
html[data-theme='dark'] .portal-nav {
  background: linear-gradient(180deg, rgba(0, 0, 0, .24), rgba(0, 0, 0, 0) 92%);
}

.portal-nav__inner {
  display: flex;
  align-items: center;
  gap: 26px;
  max-width: 1200px;
  height: 100%;
  margin: 0 auto;
  padding: 0 24px;
}

.portal-nav__logo {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  color: var(--c-text);
  text-decoration: none;
}
.portal-nav__logo:hover { text-decoration: none; }
.portal-nav__brand {
  color: var(--c-text);
  font-family: "Segoe UI Variable Display", "Avenir Next", "SF Pro Display", "PingFang SC", "Microsoft YaHei", sans-serif;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -.035em;
}

.portal-nav__right {
  display: flex;
  align-items: center;
  flex: 1;
  gap: 2px;
}
.portal-nav__spacer { flex: 1; }

.portal-nav__link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--c-text);
  cursor: pointer;
  font-family: inherit;
  font-size: 12.5px;
  font-weight: 500;
  letter-spacing: .01em;
  white-space: nowrap;
  transition: background .2s ease, color .2s ease;
}
.portal-nav__link:hover,
.portal-nav__link--active {
  background: rgba(255, 255, 255, .34);
  color: var(--c-primary);
}
html[data-theme='dark'] .portal-nav__link:hover,
html[data-theme='dark'] .portal-nav__link--active {
  background: rgba(255, 255, 255, .10);
}
.portal-nav__link--active { color: var(--c-primary); }

.portal-nav__auth {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-right: 8px;
}
.portal-nav__login {
  padding: 6px 10px;
  color: var(--c-text-secondary);
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
}
.portal-nav__login:hover { color: var(--c-primary); text-decoration: none; }
.portal-nav__register {
  padding: 5px 11px;
  border-radius: 999px;
  background: var(--c-primary);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  text-decoration: none;
  transition: opacity .2s, transform .2s;
}
.portal-nav__register:hover {
  opacity: .9;
  text-decoration: none;
  transform: translateY(-1px);
}

/* 主题切换 */
.theme-toggle {
  display: flex;
  align-items: center;
  gap: 1px;
  padding: 0;
  border: 0;
  border-radius: 8px;
  background: transparent;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
}
.theme-btn {
  padding: 4px 7px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--c-text-secondary);
  cursor: pointer;
  font-size: 10px;
  font-weight: 500;
  line-height: 1.4;
  transition: background .15s, color .15s;
}
.theme-btn:hover { background: rgba(15, 23, 42, .05); color: var(--c-text); }
.theme-btn.active { background: rgba(15, 23, 42, .075); color: #111827; box-shadow: none; }
html[data-theme='dark'] .theme-btn:hover { background: rgba(255, 255, 255, .08); color: var(--c-text); }
html[data-theme='dark'] .theme-btn.active {
  background: rgba(255, 255, 255, .12);
  color: rgba(255, 255, 255, .95);
  box-shadow: none;
}

/* 下拉 */
.dropdown { position: relative; }
.dropdown__trigger { font-size: 13px; }
.dropdown__arrow { transition: transform .2s; }
.dropdown__arrow--up { transform: rotate(180deg); }
.dropdown__menu {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  min-width: 230px;
  padding: 7px;
  z-index: 1001;
  border: 1px solid var(--panel-border);
  border-radius: 14px;
  background: var(--panel-bg-solid);
  box-shadow: var(--shadow-md);
}
.dropdown__heading {
  padding: 6px 10px 7px;
  color: var(--c-text-muted);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .1em;
  text-transform: uppercase;
}
.dropdown__item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 9px 10px;
  border-radius: 9px;
  color: var(--c-text);
  text-decoration: none;
  transition: background var(--transition);
}
.dropdown__item span { font-size: 13px; font-weight: 600; }
.dropdown__item small { color: var(--c-text-muted); font-size: 11px; font-weight: 400; }
.dropdown__item:hover { background: var(--c-bg); text-decoration: none; }
.drop-enter-active, .drop-leave-active { transition: opacity .16s ease, transform .16s ease; }
.drop-enter-from, .drop-leave-to { opacity: 0; transform: translateY(-5px); }

/* 汉堡 */
.portal-nav__hamburger {
  display: none;
  flex-direction: column;
  gap: 4px;
  margin-left: auto;
  padding: 4px;
  border: none;
  background: none;
  cursor: pointer;
}
.portal-nav__hamburger span {
  display: block;
  width: 22px;
  height: 2px;
  border-radius: 2px;
  background: var(--c-text);
  transition: all .3s;
}

@media (max-width: 920px) {
  .portal-nav__inner { gap: 16px; }
  .portal-nav__link { padding: 6px 8px; font-size: 12px; }
  .portal-nav__login { display: none; }
}

@media (max-width: 768px) {
  .portal-nav__hamburger { display: flex; }
  .portal-nav__right {
    position: absolute;
    top: var(--portal-header-h, 56px);
    right: 0;
    left: 0;
    display: none;
    flex-direction: column;
    align-items: stretch;
    gap: 2px;
    max-height: calc(100vh - var(--portal-header-h, 56px));
    overflow-y: auto;
    padding: 12px 16px 18px;
    border-bottom: 1px solid var(--panel-border);
    background: var(--c-white);
    box-shadow: var(--shadow-md);
  }
  .portal-nav__right--open { display: flex; }
  .portal-nav__item { width: 100%; }
  .portal-nav__link { width: 100%; justify-content: space-between; padding: 10px 12px; }
  .dropdown__menu {
    position: static;
    min-width: 0;
    margin: 2px 0 6px;
    padding: 4px;
    border: none;
    box-shadow: none;
    background: var(--c-bg);
  }
  .dropdown__heading { display: none; }
  .dropdown__item { padding: 8px 10px; }
  .portal-nav__spacer { display: none; }
  .portal-nav__auth { width: 100%; margin: 8px 0 4px; }
  .portal-nav__auth a { flex: 1; text-align: center; }
  .portal-nav__login { display: block; padding: 9px 10px; }
  .portal-nav__register { padding: 9px 10px; }
  .theme-toggle { align-self: flex-start; margin-top: 4px; }
}
</style>
