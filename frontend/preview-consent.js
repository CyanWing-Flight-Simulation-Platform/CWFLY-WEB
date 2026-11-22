/**
 * OAuth 授权确认弹窗 · 纯静态预览页（不接任何接口，可随时删除）
 *   /preview-consent.html?theme=dark
 *   /preview-consent.html?theme=light
 */
import { createApp, h, ref } from 'vue'
import OAuthConsentModal from '@/components/oauth/OAuthConsentModal.vue'
import './src/assets/global.css'

const params = new URLSearchParams(location.search)
document.documentElement.setAttribute('data-theme', params.get('theme') === 'light' ? 'light' : 'dark')

createApp({
  setup() {
    const open = ref(true)
    return () =>
      h(OAuthConsentModal, {
        open: open.value,
        'onUpdate:open': (value) => { if (value) open.value = true },
        appName: 'Dubhe Nexus',
        appOrigin: 'merak.dubhenexus.io',
        userName: 'CW-2048',
        cid: '2048',
        scopes: [
          { label: '用户名', value: 'CW-2048' },
          { label: 'CID', value: '2048' },
          { label: '邮箱', value: 'cw2048@cwflysim.cn' },
          { label: '飞行时长', value: '128.5 h' },
        ],
        onApprove: () => {},
        onDeny: () => {},
        onClose: () => {},
      })
  },
}).mount('#preview')