// 首屏主题预置：在 CSS/应用渲染前按 localStorage + 北京时间(AUTO) 决定深/浅。
(function () {
  try {
    var mode = localStorage.getItem('cw_theme') || 'auto';
    var dark = false;
    if (mode === 'dark') dark = true;
    else if (mode === 'light') dark = false;
    else {
      var h = (new Date().getUTCHours() + 8) % 24;
      dark = (h >= 19 || h < 7);
    }
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  } catch (e) {}
})();