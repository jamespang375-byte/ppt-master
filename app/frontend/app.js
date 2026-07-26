/* PPT Master Agent — zero-build SPA (vanilla JS, no deps, offline-safe) */
(function () {
  'use strict';

  /* ============================== state ============================== */
  var TOKEN_KEY = 'pptsaas_token';
  var USER_KEY = 'pptsaas_user';

  var state = {
    token: localStorage.getItem(TOKEN_KEY) || null,
    user: readJSON(localStorage.getItem(USER_KEY)),
    themes: [],
    wizard: {          // step 1+2 draft, survives back/forth inside the wizard
      files: [], inputMode: 'files', topic: '', title: '',
      slideCount: 12, brief: '', themeId: null,
      styleReturnProject: null  // when set, style step updates this project instead of creating one
    },
    outline: null,        // editable outline of current project
    outlineProject: null, // project detail for outline view
    expandedPage: 0,      // which outline card is expanded
    preview: {            // preview view state
      project: null,
      status: null,
      currentPage: 1,
      pollTimer: null,
      pollFails: 0,
      svgCache: {},       // page_number -> svg text (thumbs + stage share it)
      svgDirty: {},       // page_number -> true when click-edited but not yet saved
      stageReq: 0         // race guard for stage loads
    }
  };

  var app = document.getElementById('app');

  function readJSON(s) { try { return s ? JSON.parse(s) : null; } catch (e) { return null; } }

  /* ============================== icons (inline SVG) ============================== */
  function ico(path, size) {
    size = size || 16;
    return '<svg width="' + size + '" height="' + size + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
      'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + path + '</svg>';
  }
  var ICONS = {
    upload: ico('<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>', 26),
    check: ico('<polyline points="20 6 9 17 4 12"/>', 13),
    checkCircle: ico('<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>'),
    xCircle: ico('<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>'),
    info: ico('<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>'),
    warn: ico('<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>'),
    chevronDown: ico('<polyline points="6 9 12 15 18 9"/>', 15),
    chevronRight: ico('<polyline points="9 18 15 12 9 6"/>', 14),
    grip: ico('<circle cx="9" cy="6" r="1.4" fill="currentColor" stroke="none"/><circle cx="15" cy="6" r="1.4" fill="currentColor" stroke="none"/><circle cx="9" cy="12" r="1.4" fill="currentColor" stroke="none"/><circle cx="15" cy="12" r="1.4" fill="currentColor" stroke="none"/><circle cx="9" cy="18" r="1.4" fill="currentColor" stroke="none"/><circle cx="15" cy="18" r="1.4" fill="currentColor" stroke="none"/>', 15),
    sparkles: ico('<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>'),
    refresh: ico('<polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>', 14),
    code: ico('<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>', 14),
    zoom: ico('<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/>', 14),
    download: ico('<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>', 14),
    image: ico('<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>', 18),
    doc: ico('<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>', 28),
    trash: ico('<polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>', 22),
    zap: ico('<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>', 14),
    layers: ico('<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>', 14),
    edit: ico('<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4z"/>', 14),
    save: ico('<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>', 14),
    share: ico('<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>', 14),
    link: ico('<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>', 14)
  };
  /* layout hint icons (16px) */
  var LAYOUT_ICONS = {
    cover:   ico('<rect x="3" y="4" width="18" height="16" rx="2"/><line x1="8" y1="10" x2="16" y2="10"/><line x1="10" y1="14" x2="14" y2="14"/>', 14),
    toc:     ico('<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>', 14),
    content: ico('<rect x="3" y="3" width="18" height="18" rx="2"/><line x1="7" y1="8" x2="13" y2="8"/><line x1="7" y1="12" x2="13" y2="12"/><line x1="7" y1="16" x2="11" y2="16"/><rect x="15" y="12" width="5" height="5" rx="1"/>', 14),
    data:    ico('<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/><line x1="2" y1="20" x2="22" y2="20"/>', 14),
    closing: ico('<circle cx="12" cy="12" r="10"/><polyline points="8 12 11 15 16 9"/>', 14)
  };

  /* ============================== utils ============================== */
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function fmtNum(n) {
    if (n == null || isNaN(Number(n))) return '0';
    return Number(n).toLocaleString('zh-CN');
  }

  function fmtTime(iso) {
    if (!iso) return '—';
    var d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso);
    return d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
  }

  function fmtSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1024 / 1024).toFixed(1) + ' MB';
  }

  /* relative time, e.g. "2 小时前" */
  function fmtRelTime(iso) {
    if (!iso) return '—';
    var d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso);
    var diff = Date.now() - d.getTime();
    if (diff < 0) diff = 0;
    var min = Math.floor(diff / 60000);
    if (min < 1) return '刚刚';
    if (min < 60) return min + ' 分钟前';
    var hour = Math.floor(min / 60);
    if (hour < 24) return hour + ' 小时前';
    var day = Math.floor(hour / 24);
    if (day < 30) return day + ' 天前';
    return fmtTime(iso);
  }

  /* ---------- toast (dedup: same message within 2s is dropped) ---------- */
  var lastToast = { msg: null, time: 0 };
  function toast(msg, type) {
    type = type || 'info';
    var now = Date.now();
    if (lastToast.msg === type + '|' + msg && now - lastToast.time < 2000) return;
    lastToast = { msg: type + '|' + msg, time: now };
    var root = document.getElementById('toast-root');
    var el = document.createElement('div');
    el.className = 'toast ' + type;
    var ic = type === 'success' ? ICONS.checkCircle : type === 'error' ? ICONS.xCircle : ICONS.info;
    el.innerHTML = '<span class="t-ico">' + ic + '</span><span class="t-msg">' + esc(msg) + '</span>';
    root.appendChild(el);
    setTimeout(function () {
      el.classList.add('out');
      setTimeout(function () { el.remove(); }, 320);
    }, type === 'error' ? 5200 : 3400);
  }

  /* ---------- modal ---------- */
  function openModal(opts) {
    var root = document.getElementById('modal-root');
    var mask = document.createElement('div');
    mask.className = 'modal-mask';
    mask.innerHTML =
      '<div class="modal' + (opts.wide ? ' wide' : '') + '" role="dialog">' +
        '<div class="modal-head"><h3>' + esc(opts.title) + '</h3>' +
        '<button class="icon-btn" data-close title="关闭">✕</button></div>' +
        '<div class="modal-body"></div>' +
        (opts.footer === false ? '' : '<div class="modal-foot"></div>') +
      '</div>';
    root.appendChild(mask);
    var body = mask.querySelector('.modal-body');
    var foot = mask.querySelector('.modal-foot');
    function close() { mask.remove(); }
    mask.addEventListener('mousedown', function (e) { if (e.target === mask) close(); });
    mask.querySelector('[data-close]').addEventListener('click', close);
    if (typeof opts.render === 'function') opts.render(body, foot, close);
    return close;
  }

  /* danger confirm dialog (delete etc.) */
  function confirmDanger(opts) {
    openModal({
      title: opts.title || '确认操作',
      render: function (body, foot, close) {
        body.innerHTML =
          '<div style="text-align:center;padding:6px 0 2px">' +
            '<div class="danger-ill">' + ICONS.trash + '</div>' +
            '<div style="font-weight:600;font-size:15px;margin-bottom:6px">' + esc(opts.heading || opts.title || '确认操作') + '</div>' +
            '<div style="color:var(--text-2);font-size:13.5px">' + esc(opts.message || '此操作不可恢复。') + '</div>' +
          '</div>';
        var cancel = document.createElement('button');
        cancel.className = 'btn btn-outline'; cancel.textContent = '取消';
        cancel.addEventListener('click', close);
        var ok = document.createElement('button');
        ok.className = 'btn btn-danger-solid'; ok.textContent = opts.okText || '确认删除';
        ok.addEventListener('click', function () {
          ok.disabled = true;
          Promise.resolve(opts.onOk()).then(function (done) {
            if (done !== false) close();
          }).catch(function () { ok.disabled = false; });
        });
        foot.appendChild(cancel); foot.appendChild(ok);
      }
    });
  }

  /* ---------- API wrapper ---------- */
  function api(path, opts) {
    opts = opts || {};
    var headers = {};
    if (state.token) headers['Authorization'] = 'Bearer ' + state.token;
    var fetchOpts = { method: opts.method || 'GET', headers: headers };

    if (opts.formData) {
      fetchOpts.body = opts.formData; // browser sets multipart boundary
    } else if (opts.rawBody != null) {
      headers['Content-Type'] = opts.rawType || 'text/plain';
      fetchOpts.body = opts.rawBody;
    } else if (opts.body != null) {
      headers['Content-Type'] = 'application/json';
      fetchOpts.body = JSON.stringify(opts.body);
    }

    return fetch(path, fetchOpts).then(function (res) {
      if (res.status === 401) {
        clearAuth();
        toast('登录已过期，请重新登录', 'error');
        location.hash = '#/login';
        throw new Error('unauthorized');
      }
      if (!res.ok) {
        return res.text().then(function (t) {
          var msg = '请求失败 (' + res.status + ')';
          try {
            var j = JSON.parse(t);
            if (typeof j.detail === 'string') msg = j.detail;
            else if (Array.isArray(j.detail) && j.detail[0] && j.detail[0].msg) msg = j.detail[0].msg;
            else if (j.message) msg = j.message;
          } catch (e) { if (t) msg = t.slice(0, 200); }
          var err = new Error(msg);
          err.status = res.status;
          throw err;
        });
      }
      var ct = res.headers.get('Content-Type') || '';
      if (ct.indexOf('application/json') !== -1) return res.json();
      return res.text();
    });
  }

  function apiSVG(path) {
    return api(path).then(function (t) { return typeof t === 'string' ? t : ''; });
  }

  /* ---------- auth ---------- */
  function setAuth(token, user) {
    state.token = token;
    state.user = user;
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    syncTopbar();
  }

  function clearAuth() {
    state.token = null;
    state.user = null;
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    syncTopbar();
  }

  function isAdmin() { return state.user && state.user.role === 'admin'; }

  function syncTopbar() {
    var bar = document.getElementById('topbar');
    if (!state.token) { bar.classList.add('hidden'); return; }
    bar.classList.remove('hidden');
    var name = state.user && state.user.username ? state.user.username : '';
    document.getElementById('current-username').textContent = name;
    document.getElementById('current-avatar').textContent = name ? name.charAt(0).toUpperCase() : '';
    document.getElementById('ud-username').textContent = name || '—';
    document.getElementById('ud-role').textContent = isAdmin() ? '管理员' : '普通用户';
    document.getElementById('ud-settings').classList.toggle('hidden', !isAdmin());
    document.getElementById('nav-admin').classList.toggle('hidden', !isAdmin());
    document.getElementById('nav-settings').classList.toggle('hidden', !isAdmin());
  }

  /* avatar dropdown: toggle + close on outside click / navigation */
  document.getElementById('user-trigger').addEventListener('click', function (e) {
    e.stopPropagation();
    document.getElementById('user-dropdown').classList.toggle('hidden');
  });
  document.addEventListener('click', function (e) {
    var dd = document.getElementById('user-dropdown');
    var menu = document.getElementById('user-menu');
    if (dd && !dd.classList.contains('hidden') && menu && !menu.contains(e.target)) {
      dd.classList.add('hidden');
    }
  });
  window.addEventListener('hashchange', function () {
    document.getElementById('user-dropdown').classList.add('hidden');
  });

  document.getElementById('btn-logout').addEventListener('click', function () {
    api('/api/auth/logout', { method: 'POST' }).catch(function () {}).then(function () {
      clearAuth();
      location.hash = '#/login';
    });
  });

  /* ============================== badges ============================== */
  var PROJECT_STATUS = {
    draft:      ['草稿', 'gray'],
    outline:    ['待确认大纲', 'blue'],
    confirmed:  ['已确认', 'indigo'],
    generating: ['生成中', 'blue'],
    ready:      ['已完成', 'green'],
    exported:   ['已导出', 'green'],
    failed:     ['失败', 'red']
  };
  var PAGE_STATUS = {
    pending:    ['排队中', 'gray'],
    generating: ['生成中', 'amber'],
    done:       ['完成', 'green'],
    failed:     ['失败', 'red']
  };
  /* project card top-bar fallback color when the project carries no theme info */
  var STATUS_BAR_COLOR = {
    draft: '#9ca3af', outline: '#3b82f6', confirmed: '#6366f1',
    generating: '#2563eb', ready: '#16a34a', exported: '#16a34a', failed: '#dc2626'
  };

  function badge(map, key) {
    var b = map[key] || [key || '未知', 'gray'];
    var pulse = key === 'generating' ? ' badge-pulse' : '';
    return '<span class="badge badge-' + b[1] + pulse + '">' + esc(b[0]) + '</span>';
  }

  /* ============================== themes ============================== */
  var THEME_FALLBACK = {
    'business-blue': ['#2563eb', '#93c5fd', '#1e293b', '#eff6ff'],
    'tech-dark':     ['#22d3ee', '#a855f7', '#0f172a', '#334155'],
    'consult-red':   ['#c00000', '#d4a843', '#003366', '#f5f5f5'],
    'fresh-green':   ['#16a34a', '#86efac', '#166534', '#f0fdf4'],
    'minimal-white': ['#111827', '#6b7280', '#e5e7eb', '#f9fafb']
  };
  var DEFAULT_PALETTE = ['#2563eb', '#93c5fd', '#1e293b', '#eff6ff'];

  /* theme shape: {id, name, description, palette[], builtin} — palette optional for backward compat */
  function themePalette(t) {
    if (t && Array.isArray(t.palette) && t.palette.length) {
      return t.palette.slice(0, 5).map(function (c) { return String(c); });
    }
    if (t && t.style_md) {
      var m = String(t.style_md).match(/#[0-9a-fA-F]{6}\b/g);
      if (m && m.length) {
        var uniq = [];
        for (var i = 0; i < m.length && uniq.length < 5; i++) {
          var c = m[i].toLowerCase();
          if (uniq.indexOf(c) === -1) uniq.push(c);
        }
        return uniq;
      }
    }
    var key = t && (t.key || t.name);
    return (THEME_FALLBACK[key] || DEFAULT_PALETTE).slice();
  }

  function hexLum(hex) {
    var h = String(hex || '').replace('#', '');
    if (h.length === 3) h = h.charAt(0) + h.charAt(0) + h.charAt(1) + h.charAt(1) + h.charAt(2) + h.charAt(2);
    if (!/^[0-9a-fA-F]{6}$/.test(h)) return 0.5;
    var r = parseInt(h.substr(0, 2), 16) / 255,
        g = parseInt(h.substr(2, 2), 16) / 255,
        b = parseInt(h.substr(4, 2), 16) / 255;
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }

  /* mini slide preview built purely from palette colors */
  function miniSlideHTML(t) {
    var pal = themePalette(t);
    var primary = pal[0] || '#2563eb';
    var secondary = pal[1] || primary;
    var third = pal[2] || secondary;
    /* pick background: lightest color if light enough, otherwise darkest (dark theme) */
    var lightest = null, lightestLum = -1, darkest = null, darkestLum = 2;
    pal.forEach(function (c) {
      var l = hexLum(c);
      if (l > lightestLum) { lightestLum = l; lightest = c; }
      if (l < darkestLum) { darkestLum = l; darkest = c; }
    });
    var darkTheme = lightestLum < 0.75;
    var bg = darkTheme ? darkest : lightest;
    /* dark bg: keep text layers semi-transparent white so the mini slide stays clean;
     * accent colors only appear in the top bar / block / cards */
    var titleColor = darkTheme ? 'rgba(255,255,255,.88)' : 'rgba(15,23,42,.85)';
    var lineColor = darkTheme ? 'rgba(255,255,255,.38)' : 'rgba(15,23,42,.18)';
    var blockColor = (darkTheme && hexLum(secondary) < darkestLum + 0.18) ? 'rgba(255,255,255,.22)' : secondary;
    return '<div class="theme-mini" style="background:' + esc(bg) + '">' +
      '<div class="tm-bar" style="background:' + esc(primary) + '"></div>' +
      '<div class="tm-title" style="background:' + esc(titleColor) + '"></div>' +
      '<div class="tm-row">' +
        '<div class="tm-block" style="background:' + esc(blockColor) + '"></div>' +
        '<div class="tm-lines">' +
          '<i style="background:' + esc(lineColor) + '"></i>' +
          '<i style="background:' + esc(lineColor) + ';width:82%"></i>' +
          '<i style="background:' + esc(lineColor) + ';width:60%"></i>' +
        '</div>' +
      '</div>' +
      '<div class="tm-cards">' +
        '<i style="background:' + esc(primary) + '"></i>' +
        '<i style="background:' + esc(third) + '"></i>' +
        '<i style="background:' + esc(secondary) + '"></i>' +
      '</div>' +
    '</div>';
  }

  function swatchHTML(t) {
    var colors = themePalette(t);
    var html = '<span class="swatch">';
    colors.forEach(function (c) { html += '<i style="background:' + esc(c) + '"></i>'; });
    return html + '</span>';
  }

  function themeName(t) { return t.name || t.key || ('主题 #' + t.id); }
  function themeDesc(t) { return (t && t.description) || '内置视觉主题，自动注入排版与配色规范'; }

  function loadThemes() {
    return api('/api/themes').then(function (list) {
      state.themes = Array.isArray(list) ? list : (list.themes || []);
      return state.themes;
    }).catch(function (e) {
      if (e.message !== 'unauthorized') toast('获取主题列表失败：' + e.message, 'error');
      state.themes = [];
      return [];
    });
  }

  /* ============================== stepper ============================== */
  var WIZARD_STEPS = ['输入材料', '选择风格', '确认大纲', '生成与预览'];

  function stepperHTML(active) {
    var html = '<div class="stepper">';
    WIZARD_STEPS.forEach(function (label, i) {
      var n = i + 1;
      var cls = n < active ? 'done' : n === active ? 'active' : '';
      html += '<div class="step ' + cls + '">' +
        '<div class="dot">' + (n < active ? ICONS.check : n) + '</div>' +
        '<div class="s-label">' + esc(label) + '</div></div>';
      if (n < WIZARD_STEPS.length) {
        html += '<div class="step-line' + (n < active ? ' done' : '') + '"></div>';
      }
    });
    return html + '</div>';
  }

  /* ============================== router ============================== */
  function stopPolling() {
    if (state.preview.pollTimer) {
      clearInterval(state.preview.pollTimer);
      state.preview.pollTimer = null;
    }
  }

  function route() {
    stopPolling();
    closeSvgTextEditor();
    var hash = location.hash || '#/projects';
    var parts = hash.replace(/^#\//, '').split('/');

    if (!state.token && parts[0] !== 'login') { location.hash = '#/login'; return; }
    if (state.token && parts[0] === 'login') { location.hash = '#/projects'; return; }

    /* unsaved SVG edits guard when leaving the preview route */
    if (parts[0] !== 'project' && state.preview.project) {
      var dirtyCount = 0;
      for (var dk in state.preview.svgDirty) { if (state.preview.svgDirty[dk]) dirtyCount++; }
      if (dirtyCount) {
        if (confirm('有 ' + dirtyCount + ' 页存在未保存的 SVG 修改，离开后修改将丢失，确定离开吗？')) {
          /* drop the edited copies from cache so the server version is refetched */
          for (var dp in state.preview.svgDirty) {
            if (state.preview.svgDirty[dp]) delete state.preview.svgCache[dp];
          }
          state.preview.svgDirty = {};
        } else {
          location.hash = '#/project/' + state.preview.project.id;
          return;
        }
      }
    }

    var navKey = { projects: 'projects', new: 'new', usage: 'usage', admin: 'admin', settings: 'settings' }[parts[0]];
    var links = document.querySelectorAll('#main-nav a');
    for (var i = 0; i < links.length; i++) {
      links[i].classList.toggle('active', links[i].getAttribute('data-nav') === navKey);
    }

    switch (parts[0]) {
      case 'login':    renderLogin(); break;
      case 'projects': renderProjects(); break;
      case 'new':
        if (parts[1] === 'style') renderStepStyle(parts[2]); else renderStepInput();
        break;
      case 'outline':  renderOutline(parts[1]); break;
      case 'project':  renderPreview(parts[1]); break;
      case 'usage':    renderUsage(); break;
      case 'admin':    renderAdmin(); break;
      case 'settings': renderSettings(); break;
      default:         location.hash = '#/projects';
    }
  }

  window.addEventListener('hashchange', route);

  function loadingHTML(text) {
    return '<div class="loading-block"><span class="spinner"></span>' + esc(text || '加载中…') + '</div>';
  }

  /* ============================== 1. login / register ============================== */
  function renderLogin() {
    syncTopbar();
    var mode = 'login';
    app.innerHTML =
      '<div class="view auth-scene">' +
        '<div class="auth-brand-panel">' +
          '<div class="bp-inner">' +
            '<div class="bp-logo"><svg width="34" height="34" viewBox="0 0 32 32">' +
              '<rect width="32" height="32" rx="7" fill="#fff"/>' +
              '<rect x="7" y="8" width="18" height="12" rx="2" fill="#2563eb"/>' +
              '<rect x="7" y="23" width="10" height="2.5" rx="1.2" fill="#2563eb" opacity=".75"/></svg></div>' +
            '<h1>PPT Master Agent</h1>' +
            '<div class="bp-slogan">上传一份文档，AI 为你生成专业级演示文稿</div>' +
            '<div class="bp-feats">' +
              '<div class="bp-feat"><span class="bf-ico">' + ICONS.sparkles + '</span>' +
                '<div><b>AI 大纲与逐页生成</b><span>从文档到完整演示，分钟级完成</span></div></div>' +
              '<div class="bp-feat"><span class="bf-ico">' + ICONS.layers + '</span>' +
                '<div><b>多套内置视觉主题</b><span>配色与版式规范自动注入每一页</span></div></div>' +
              '<div class="bp-feat"><span class="bf-ico">' + ICONS.zap + '</span>' +
                '<div><b>导出可编辑 PPTX</b><span>原生 PowerPoint 形状，随处可改</span></div></div>' +
            '</div>' +
            '<div class="bp-foot">v1.0 · 本地优先，数据不出你的机器</div>' +
          '</div>' +
        '</div>' +
        '<div class="auth-side">' +
          '<div class="card auth-card">' +
            '<div class="auth-tabs">' +
              '<button data-mode="login" class="active">登录</button>' +
              '<button data-mode="register">注册</button>' +
            '</div>' +
            '<div class="field"><label>用户名</label><input type="text" id="auth-username" autocomplete="username" placeholder="请输入用户名"></div>' +
            '<div class="field"><label>密码</label><input type="password" id="auth-password" autocomplete="current-password" placeholder="请输入密码"></div>' +
            '<button class="btn btn-primary btn-lg" id="auth-submit" style="width:100%">登录</button>' +
            '<div id="auth-hint" style="text-align:center;margin-top:12px;color:var(--text-3);font-size:12px;min-height:18px"></div>' +
          '</div>' +
        '</div>' +
      '</div>';

    var tabs = app.querySelectorAll('.auth-tabs button');
    var submitBtn = document.getElementById('auth-submit');
    var hint = document.getElementById('auth-hint');

    tabs.forEach(function (b) {
      b.addEventListener('click', function () {
        mode = b.getAttribute('data-mode');
        tabs.forEach(function (x) { x.classList.toggle('active', x === b); });
        submitBtn.textContent = mode === 'login' ? '登录' : '注册';
        hint.textContent = mode === 'register' ? '首个注册的用户将自动成为管理员' : '';
      });
    });

    function submit() {
      var username = document.getElementById('auth-username').value.trim();
      var password = document.getElementById('auth-password').value;
      if (!username || !password) { toast('请输入用户名和密码', 'error'); return; }
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="spinner"></span>请稍候…';
      api('/api/auth/' + mode, { method: 'POST', body: { username: username, password: password } })
        .then(function (data) {
          setAuth(data.token, data.user);
          toast(mode === 'login' ? '欢迎回来，' + username : '注册成功，已自动登录', 'success');
          location.hash = '#/projects';
        })
        .catch(function (e) {
          if (e.message !== 'unauthorized') {
            toast(mode === 'register' ? '注册失败：' + e.message : '登录失败：' + e.message, 'error');
          }
        })
        .then(function () {
          submitBtn.disabled = false;
          submitBtn.textContent = mode === 'login' ? '登录' : '注册';
        });
    }

    submitBtn.addEventListener('click', submit);
    document.getElementById('auth-password').addEventListener('keydown', function (e) {
      if (e.key === 'Enter') submit();
    });
    document.getElementById('auth-username').addEventListener('keydown', function (e) {
      if (e.key === 'Enter') document.getElementById('auth-password').focus();
    });
  }

  /* ============================== 2. project list ============================== */
  var EMPTY_ART =
    '<svg width="150" height="104" viewBox="0 0 150 104" fill="none" aria-hidden="true">' +
      '<rect x="22" y="16" width="106" height="68" rx="9" fill="#eff6ff" stroke="#bfdbfe" stroke-width="2"/>' +
      '<rect x="34" y="30" width="46" height="7" rx="3.5" fill="#2563eb"/>' +
      '<rect x="34" y="45" width="80" height="5" rx="2.5" fill="#bfdbfe"/>' +
      '<rect x="34" y="56" width="66" height="5" rx="2.5" fill="#dbeafe"/>' +
      '<rect x="34" y="67" width="72" height="5" rx="2.5" fill="#dbeafe"/>' +
      '<path d="M122 6l2.2 5.8 5.8 2.2-5.8 2.2L122 22l-2.2-5.8-5.8-2.2 5.8-2.2z" fill="#f59e0b"/>' +
      '<path d="M16 66l1.5 4 4 1.5-4 1.5-1.5 4-1.5-4-4-1.5 4-1.5z" fill="#93c5fd"/>' +
      '<circle cx="132" cy="76" r="5" fill="#dbeafe"/>' +
    '</svg>';

  function renderProjects() {
    app.innerHTML = loadingHTML('加载项目列表…');
    Promise.all([api('/api/projects'), loadThemes()]).then(function (results) {
      var data = results[0];
      var projects = Array.isArray(data) ? data : (data.projects || []);
      /* newest first */
      projects.sort(function (a, b) {
        return String(b.updated_at || '').localeCompare(String(a.updated_at || ''));
      });
      var html = '<div class="view">' +
        '<div class="page-head"><div><h1>我的项目</h1>' +
        '<div class="sub">共 ' + projects.length + ' 个项目</div></div>' +
        '<a class="btn btn-primary" href="#/new">＋ 新建项目</a></div>';

      if (!projects.length) {
        html += '<div class="empty">' +
          '<div class="e-art">' + EMPTY_ART + '</div>' +
          '<div class="e-title">开始你的第一份演示文稿</div>' +
          '<div class="e-desc">上传文档或输入一个主题，AI 会帮你规划大纲并逐页生成精美幻灯片</div>' +
          '<a class="btn btn-primary btn-lg" href="#/new">立即创建</a>' +
        '</div>';
      } else {
        html += '<div class="project-grid">';
        projects.forEach(function (p) {
          var progressTxt = '';
          var miniBar = '';
          if (p.progress && typeof p.progress === 'object') {
            var done = p.progress.done || 0;
            var total = p.progress.total || p.slide_count || 0;
            progressTxt = '<span>' + done + '/' + (total || '?') + ' 页</span>';
            if (p.status === 'generating' && total) {
              miniBar = '<div class="progress thin mini-progress"><i style="width:' + Math.round(done / total * 100) + '%"></i></div>';
            }
          } else if (p.slide_count) {
            progressTxt = '<span>' + p.slide_count + ' 页</span>';
          }
          /* error line for failed projects (list API may not carry error; detail page shows it too) */
          var errLine = '';
          if (p.status === 'failed' && p.error) {
            errLine = '<div class="card-error" title="' + esc(p.error) + '">' + esc(p.error) + '</div>';
          }
          /* action row */
          var actions = '<div class="card-actions">';
          if (p.status === 'failed') {
            actions += '<button class="btn btn-primary btn-sm" data-retry="' + esc(p.id) + '">' + ICONS.refresh + '重试生成</button>';
          }
          if (p.pptx_ready || p.status === 'exported') {
            actions += '<button class="btn btn-outline btn-sm" data-dl="' + esc(p.id) + '">' + ICONS.download + '下载 PPTX</button>';
          }
          actions += '<button class="btn btn-danger btn-sm" data-del="' + esc(p.id) + '">删除</button></div>';
          /* 4px top bar: theme palette primary when known, otherwise status color */
          var barColor = STATUS_BAR_COLOR[p.status] || '#9ca3af';
          if (p.theme_id != null) {
            var th = null;
            for (var ti = 0; ti < state.themes.length; ti++) {
              if (String(state.themes[ti].id) === String(p.theme_id)) { th = state.themes[ti]; break; }
            }
            if (th) barColor = themePalette(th)[0] || barColor;
          }
          html +=
            '<div class="card card-hover project-card" data-id="' + esc(p.id) + '" data-status="' + esc(p.status) + '">' +
              '<i class="pc-bar" style="background:' + esc(barColor) + '"></i>' +
              '<div class="card-top"><h3>' + esc(p.title || '未命名项目') + '</h3>' + badge(PROJECT_STATUS, p.status) + '</div>' +
              '<div class="meta">' + progressTxt + '<span>' + fmtRelTime(p.updated_at) + '</span></div>' +
              errLine +
              miniBar +
              actions +
            '</div>';
        });
        html += '</div>';
      }
      html += '</div>';
      app.innerHTML = html;

      app.querySelectorAll('.project-card').forEach(function (card) {
        card.addEventListener('click', function (e) {
          if (e.target.closest('[data-del]') || e.target.closest('[data-retry]') || e.target.closest('[data-dl]')) return;
          var id = card.getAttribute('data-id');
          var st = card.getAttribute('data-status');
          location.hash = (st === 'draft' || st === 'outline') ? '#/outline/' + id : '#/project/' + id;
        });
      });
      /* retry generation for failed projects */
      app.querySelectorAll('[data-retry]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var id = btn.getAttribute('data-retry');
          btn.disabled = true;
          btn.innerHTML = '<span class="spinner"></span>启动中…';
          api('/api/projects/' + id + '/generate', { method: 'POST' }).then(function () {
            toast('已重新开始生成', 'success');
            location.hash = '#/project/' + id;
          }).catch(function (e) {
            if (e.message !== 'unauthorized') toast('重试失败：' + e.message, 'error');
            btn.disabled = false;
            btn.innerHTML = ICONS.refresh + '重试生成';
          });
        });
      });
      /* direct download from card */
      app.querySelectorAll('[data-dl]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          downloadPPTX(btn.getAttribute('data-dl'));
        });
      });
      app.querySelectorAll('[data-del]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var id = btn.getAttribute('data-del');
          confirmDanger({
            title: '删除项目',
            heading: '确定删除该项目？',
            message: '项目文件、已生成的页面与导出结果都会被删除，此操作不可恢复。',
            okText: '确认删除',
            onOk: function () {
              return api('/api/projects/' + id, { method: 'DELETE' }).then(function () {
                toast('项目已删除', 'success');
                renderProjects();
              }).catch(function (e) {
                if (e.message !== 'unauthorized') toast('删除失败：' + e.message, 'error');
                return false;
              });
            }
          });
        });
      });
    }).catch(function (e) {
      if (e.message === 'unauthorized') return;
      app.innerHTML = '<div class="empty"><div class="e-title">加载失败</div><div class="e-desc">' + esc(e.message) + '</div></div>';
    });
  }

  /* ============================== 3. wizard step 1: input ============================== */
  var ACCEPT_EXT = ['.md', '.docx', '.pdf', '.pptx', '.txt'];
  var EXT_LABEL = { '.md': 'MD', '.docx': 'DOCX', '.pdf': 'PDF', '.pptx': 'PPTX', '.txt': 'TXT' };
  var EXT_CLASS = { '.md': 'ext-md', '.docx': 'ext-docx', '.pdf': 'ext-pdf', '.pptx': 'ext-pptx', '.txt': 'ext-txt' };
  var COUNT_PRESETS = [8, 12, 16, 20];

  function fileExt(name) { return ('.' + name.split('.').pop()).toLowerCase(); }

  function renderStepInput() {
    var w = state.wizard;

    app.innerHTML =
      '<div class="view">' + stepperHTML(1) +
      '<div class="wizard-wrap">' +
        '<div class="page-head" style="justify-content:center;text-align:center;display:block">' +
          '<h1>输入材料</h1>' +
          '<div class="sub">上传源文档，或直接输入一段详细提示词</div>' +
        '</div>' +
        '<div class="card card-pad">' +
          '<div class="tabs">' +
            '<button data-tab="files"' + (w.inputMode === 'files' ? ' class="active"' : '') + '>上传文件</button>' +
            '<button data-tab="topic"' + (w.inputMode === 'topic' ? ' class="active"' : '') + '>输入提示词</button>' +
          '</div>' +
          '<div id="tab-files"' + (w.inputMode !== 'files' ? ' class="hidden"' : '') + '>' +
            '<div class="dropzone" id="dropzone">' +
              '<div class="dz-icon">' + ICONS.upload + '</div>' +
              '<div class="dz-title">点击选择文件，或拖拽到此处</div>' +
              '<div class="dz-sub">支持 ' + ACCEPT_EXT.join(' / ') + ' · 最多 10 个文件 · 单个不超过 50MB</div>' +
            '</div>' +
            '<input type="file" id="file-input" multiple accept="' + ACCEPT_EXT.join(',') + '" class="hidden">' +
            '<div class="file-list" id="file-list"></div>' +
          '</div>' +
          '<div id="tab-topic"' + (w.inputMode !== 'topic' ? ' class="hidden"' : '') + '>' +
            '<div class="field" style="margin-bottom:4px"><label>演示提示词<span class="opt">当前版本无联网检索，提示词越详细（背景、受众、核心观点、关键数据、章节偏好），大纲越准确（支持粘贴最长 10 万字的长文）</span></label>' +
            '<textarea id="topic-text" rows="7" placeholder="例如：面向公司管理层的 2026 年新能源汽车行业趋势汇报。受众为投资委员会，重点关注市场规模与增速、竞争格局、政策走向三方面；核心观点是“插混增速首次超过纯电”；请包含 2023–2025 年销量数据、主要厂商份额对比，并设独立章节讨论出海机会与风险。">' +
            esc(w.topic) + '</textarea>' +
            '<div class="char-count" id="topic-count">已输入 0 字 · 支持最长 10 万字，内容越详细大纲越准</div></div>' +
          '</div>' +
          '<div class="field" style="margin-top:18px"><label>项目标题<span class="opt">可选，留空则由 AI 自动生成</span></label>' +
            '<input type="text" id="np-title" placeholder="例如：Q3 市场战略汇报" value="' + esc(w.title) + '"></div>' +
          '<div class="field"><label>页数</label>' +
            '<div style="display:flex;align-items:center;flex-wrap:wrap">' +
              '<div class="seg" id="np-count-seg">' +
                COUNT_PRESETS.map(function (n) {
                  return '<button data-v="' + n + '"' + (w.slideCount === n ? ' class="active"' : '') + '>' + n + ' 页</button>';
                }).join('') +
                '<button data-v="custom"' + (COUNT_PRESETS.indexOf(w.slideCount) === -1 ? ' class="active"' : '') + '>自定义</button>' +
              '</div>' +
              '<input type="number" id="np-count-custom" class="seg-custom' + (COUNT_PRESETS.indexOf(w.slideCount) === -1 ? '' : ' hidden') + '"' +
                ' min="4" max="30" value="' + esc(w.slideCount) + '">' +
            '</div>' +
            '<div class="hint">页数越多，每页内容越精炼；一般汇报推荐 12 页</div>' +
          '</div>' +
          '<div class="collapse-head" id="adv-toggle">' +
            '<span class="chev">' + ICONS.chevronRight + '</span>高级选项<span class="opt" style="font-weight:400;color:var(--text-3)">（风格补充说明）</span>' +
          '</div>' +
          '<div class="collapse-body" id="adv-body">' +
            '<div class="field" style="margin-top:10px"><label>风格补充说明<span class="opt">可选</span></label>' +
            '<textarea id="np-brief" rows="2" placeholder="例如：面向高管汇报，数据驱动，语气正式，少用大段文字">' + esc(w.brief) + '</textarea></div>' +
          '</div>' +
        '</div>' +
        '<div class="wizard-foot">' +
          '<a class="btn btn-ghost" href="#/projects">取消</a>' +
          '<div class="right"><button class="btn btn-primary btn-lg" id="np-next">下一步：选择风格</button></div>' +
        '</div>' +
      '</div></div>';

    /* tabs */
    var tabBtns = app.querySelectorAll('.tabs button');
    tabBtns.forEach(function (b) {
      b.addEventListener('click', function () {
        w.inputMode = b.getAttribute('data-tab');
        tabBtns.forEach(function (x) { x.classList.toggle('active', x === b); });
        document.getElementById('tab-files').classList.toggle('hidden', w.inputMode !== 'files');
        document.getElementById('tab-topic').classList.toggle('hidden', w.inputMode !== 'topic');
        if (w.inputMode === 'topic') document.getElementById('topic-text').focus();
      });
    });

    /* file picker + dnd */
    var dz = document.getElementById('dropzone');
    var fi = document.getElementById('file-input');
    dz.addEventListener('click', function () { fi.click(); });
    fi.addEventListener('change', function () {
      addFiles(Array.prototype.slice.call(fi.files));
      fi.value = '';
    });
    ['dragenter', 'dragover'].forEach(function (ev) {
      dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.add('dragover'); });
    });
    ['dragleave', 'drop'].forEach(function (ev) {
      dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.remove('dragover'); });
    });
    dz.addEventListener('drop', function (e) {
      addFiles(Array.prototype.slice.call(e.dataTransfer.files));
    });

    function addFiles(incoming) {
      incoming.forEach(function (f) {
        var ext = fileExt(f.name);
        if (ACCEPT_EXT.indexOf(ext) === -1) { toast('不支持的文件类型：' + f.name, 'error'); return; }
        if (f.size > 50 * 1024 * 1024) { toast('文件超过 50MB：' + f.name, 'error'); return; }
        if (w.files.length >= 10) { toast('最多上传 10 个文件', 'error'); return; }
        if (w.files.some(function (x) { return x.name === f.name && x.size === f.size; })) return;
        w.files.push(f);
      });
      renderFileList();
    }

    function renderFileList() {
      var list = document.getElementById('file-list');
      if (!list) return;
      list.innerHTML = '';
      w.files.forEach(function (f, i) {
        var ext = fileExt(f.name);
        var item = document.createElement('div');
        item.className = 'file-item';
        item.innerHTML =
          '<span class="ficon ' + (EXT_CLASS[ext] || 'ext-txt') + '">' + esc(EXT_LABEL[ext] || 'TXT') + '</span>' +
          '<span class="fname">' + esc(f.name) + '</span>' +
          '<span class="fsize">' + fmtSize(f.size) + '</span>' +
          '<button class="fdel" title="移除">✕</button>';
        item.querySelector('.fdel').addEventListener('click', function () {
          w.files.splice(i, 1);
          renderFileList();
        });
        list.appendChild(item);
      });
    }
    renderFileList();

    /* topic char counter */
    var topicTa = document.getElementById('topic-text');
    var topicCount = document.getElementById('topic-count');
    function updateCount() {
      var n = topicTa.value.trim().length;
      topicCount.textContent = '已输入 ' + n + ' 字 · 支持最长 10 万字，内容越详细大纲越准';
      w.topic = topicTa.value;
    }
    topicTa.addEventListener('input', updateCount);
    updateCount();
    /* default focus so the user can start typing immediately */
    if (w.inputMode === 'topic') topicTa.focus();

    /* title / brief persistence */
    document.getElementById('np-title').addEventListener('input', function (e) { w.title = e.target.value; });
    document.getElementById('np-brief').addEventListener('input', function (e) { w.brief = e.target.value; });

    /* slide count segmented */
    var seg = document.getElementById('np-count-seg');
    var customInput = document.getElementById('np-count-custom');
    seg.querySelectorAll('button').forEach(function (b) {
      b.addEventListener('click', function () {
        seg.querySelectorAll('button').forEach(function (x) { x.classList.toggle('active', x === b); });
        var v = b.getAttribute('data-v');
        if (v === 'custom') {
          customInput.classList.remove('hidden');
          customInput.focus();
          w.slideCount = clampCount(customInput.value);
        } else {
          customInput.classList.add('hidden');
          w.slideCount = Number(v);
        }
      });
    });
    customInput.addEventListener('input', function () { w.slideCount = clampCount(customInput.value); });
    function clampCount(v) {
      var n = parseInt(v, 10);
      if (isNaN(n)) return 12;
      return Math.max(4, Math.min(30, n));
    }

    /* advanced options collapse */
    var advToggle = document.getElementById('adv-toggle');
    var advBody = document.getElementById('adv-body');
    advToggle.addEventListener('click', function () {
      advToggle.classList.toggle('open');
      advBody.classList.toggle('open');
    });

    /* next */
    document.getElementById('np-next').addEventListener('click', function () {
      if (w.inputMode === 'files') {
        if (!w.files.length) { toast('请先选择至少一个文件', 'error'); return; }
      } else {
        var topic = topicTa.value.trim();
        if (topic.length < 4) { toast('请输入更具体的演示提示词（至少 4 个字）', 'error'); return; }
        w.topic = topic;
      }
      location.hash = '#/new/style';
    });
  }

  /* ============================== 4. wizard step 2: style ============================== */
  function renderStepStyle(projectId) {
    var w = state.wizard;
    w.styleReturnProject = projectId || null;
    var returning = !!w.styleReturnProject;

    app.innerHTML =
      '<div class="view">' + stepperHTML(2) +
      '<div class="wizard-wrap wide">' +
        '<div class="page-head" style="justify-content:center;text-align:center;display:block">' +
          '<h1>选择风格</h1>' +
          '<div class="sub">为这份演示文稿挑选一个视觉主题，生成时会自动应用对应配色与版式规范</div>' +
        '</div>' +
        '<div id="theme-grid-wrap">' + loadingHTML('加载主题…') + '</div>' +
        '<div class="wizard-foot">' +
          '<a class="btn btn-outline" href="' + (returning ? '#/outline/' + encodeURIComponent(projectId) : '#/new') + '">上一步</a>' +
          '<div class="right"><button class="btn btn-primary btn-lg" id="st-submit">' +
            (returning ? '保存并返回大纲' : '生成大纲') + '</button></div>' +
        '</div>' +
      '</div></div>';

    var submitBtn = document.getElementById('st-submit');

    /* when coming back from an existing project, preload its theme + outline for context */
    var ready = returning
      ? api('/api/projects/' + projectId).then(function (p) {
          w.themeId = p.theme_id || w.themeId;
          if (!state.outlineProject || String(state.outlineProject.id) !== String(p.id)) {
            var ol = null;
            try { ol = typeof p.outline_json === 'string' ? JSON.parse(p.outline_json) : p.outline_json; } catch (e) {}
            if (p.outline) ol = p.outline;
            if (ol && Array.isArray(ol.pages)) {
              state.outline = ol;
              state.outlineProject = p;
            }
          }
        }).catch(function (e) {
          if (e.message !== 'unauthorized') toast('加载项目信息失败：' + e.message, 'error');
        })
      : Promise.resolve();

    ready.then(function () {
      return loadThemes();
    }).then(function () {
      var wrap = document.getElementById('theme-grid-wrap');
      if (!wrap) return;
      if (!state.themes.length) {
        wrap.innerHTML = '<div class="empty"><div class="e-title">暂无可用主题</div>' +
          '<div class="e-desc">将使用默认商务蓝主题生成</div></div>';
        return;
      }
      if (!w.themeId || !state.themes.some(function (t) { return String(t.id) === String(w.themeId); })) {
        /* default to 商务蓝 (business-blue) when present, else first builtin, else first theme */
        var dt = null;
        for (var di = 0; di < state.themes.length; di++) {
          var dk = state.themes[di].key || state.themes[di].name;
          if (dk === 'business-blue') { dt = state.themes[di]; break; }
          if (!dt && state.themes[di].builtin) dt = state.themes[di];
        }
        w.themeId = (dt || state.themes[0]).id;
      }
      /* group themes by category: brand / deck / layout / generic (missing -> generic) */
      var CAT_ORDER = [
        ['brand', '品牌风格', '品牌', 'badge-indigo'],
        ['deck', '机构模板', '机构', 'badge-amber'],
        ['layout', '版式风格', '版式', 'badge-green'],
        ['generic', '通用风格', '内置', 'badge-blue']
      ];
      function catOf(t) {
        var c = t.category;
        return (c === 'brand' || c === 'deck' || c === 'layout') ? c : 'generic';
      }
      function catBadge(t) {
        var c = catOf(t);
        if (c === 'generic' && !t.builtin) return ['自定义', 'badge-gray'];
        for (var i = 0; i < CAT_ORDER.length; i++) {
          if (CAT_ORDER[i][0] === c) return [CAT_ORDER[i][2], CAT_ORDER[i][3]];
        }
        return ['内置', 'badge-blue'];
      }

      function makeThemeCard(t) {
        var bdg = catBadge(t);
        var card = document.createElement('div');
        card.className = 'theme-card' + (String(t.id) === String(w.themeId) ? ' selected' : '');
        card.setAttribute('data-id', t.id);
        var palHtml = (Array.isArray(t.palette) && t.palette.length)
          ? themePalette(t).map(function (c) {
              return '<i style="background:' + esc(c) + '" title="' + esc(c) + '"></i>';
            }).join('')
          : '<span class="pal-free">自由配色</span>';
        card.innerHTML =
          '<span class="check">' + ICONS.check + '</span>' +
          miniSlideHTML(t) +
          '<div class="t-body">' +
            '<div class="t-name">' + esc(themeName(t)) +
              '<span class="badge ' + bdg[1] + '" style="font-size:11px;padding:2px 7px">' + bdg[0] + '</span>' +
            '</div>' +
            '<div class="t-desc">' + esc(themeDesc(t)) + '</div>' +
            '<div class="t-pal">' + palHtml + '</div>' +
          '</div>';
        card.addEventListener('click', function () {
          w.themeId = t.id;
          wrap.querySelectorAll('.theme-card').forEach(function (x) { x.classList.toggle('selected', x === card); });
        });
        return card;
      }

      var groups = [];
      CAT_ORDER.forEach(function (c) {
        var items = state.themes.filter(function (t) { return catOf(t) === c[0]; });
        if (items.length) groups.push({ key: c[0], label: c[1], items: items });
      });

      wrap.innerHTML = '';
      /* sticky anchor chips for quick jumping between groups */
      if (groups.length > 1) {
        var chips = document.createElement('div');
        chips.className = 'theme-chips';
        groups.forEach(function (g) {
          var chip = document.createElement('button');
          chip.className = 'theme-chip';
          chip.textContent = g.label;
          chip.addEventListener('click', function () {
            var sec = document.getElementById('theme-cat-' + g.key);
            if (sec && sec.scrollIntoView) sec.scrollIntoView({ behavior: 'smooth', block: 'start' });
          });
          chips.appendChild(chip);
        });
        wrap.appendChild(chips);
      }
      groups.forEach(function (g) {
        var sec = document.createElement('div');
        sec.className = 'theme-group';
        sec.id = 'theme-cat-' + g.key;
        var head = document.createElement('div');
        head.className = 'tg-head';
        head.innerHTML = esc(g.label) + '<span class="tg-count">' + g.items.length + '</span>';
        sec.appendChild(head);
        var grid = document.createElement('div');
        grid.className = 'theme-grid';
        g.items.forEach(function (t) { grid.appendChild(makeThemeCard(t)); });
        sec.appendChild(grid);
        wrap.appendChild(sec);
      });
    });

    submitBtn.addEventListener('click', function () {
      /* returning from an existing project: PUT the outline with the new theme, then go back */
      if (w.styleReturnProject) {
        var pid = w.styleReturnProject;
        if (!state.outline) { toast('大纲数据缺失，请返回大纲页重试', 'error'); return; }
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner"></span>保存中…';
        api('/api/projects/' + pid + '/outline', {
          method: 'PUT',
          body: { outline: state.outline, theme_id: w.themeId ? Number(w.themeId) : undefined }
        }).then(function () {
          toast('风格已更新', 'success');
          w.styleReturnProject = null;
          location.hash = '#/outline/' + pid;
        }).catch(function (e) {
          if (e.message !== 'unauthorized') toast('保存失败：' + e.message, 'error');
          submitBtn.disabled = false;
          submitBtn.textContent = '保存并返回大纲';
        });
        return;
      }

      var fd = new FormData();
      if (w.inputMode === 'files') {
        if (!w.files.length) { toast('材料已丢失，请返回上一步重新选择文件', 'error'); return; }
        w.files.forEach(function (f) { fd.append('files', f, f.name); });
      } else {
        if (!w.topic || !w.topic.trim()) { toast('主题已丢失，请返回上一步重新输入', 'error'); return; }
        fd.append('topic', w.topic.trim());
      }
      if (w.title && w.title.trim()) fd.append('title', w.title.trim());
      if (w.themeId) fd.append('theme_id', w.themeId);
      fd.append('slide_count', w.slideCount || 12);
      if (w.brief && w.brief.trim()) fd.append('style_brief', w.brief.trim());

      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="spinner"></span>AI 正在规划大纲…';
      api('/api/projects', { method: 'POST', formData: fd }).then(function (data) {
        toast('大纲生成完成，请确认', 'success');
        var pid = data.project && data.project.id;
        /* creation succeeded — clear file handles so a "back" does not double-submit */
        w.files = [];
        location.hash = '#/outline/' + pid;
      }).catch(function (e) {
        if (e.message !== 'unauthorized') toast('创建失败：' + e.message, 'error');
        submitBtn.disabled = false;
        submitBtn.innerHTML = '生成大纲';
      });
    });
  }

  /* ============================== 5. wizard step 3: outline ============================== */
  var LAYOUT_HINTS = [
    ['cover', '封面'], ['toc', '目录'], ['content', '内容页'], ['data', '数据页'], ['closing', '收尾页']
  ];

  function renderOutline(projectId) {
    if (!projectId) { location.hash = '#/projects'; return; }
    app.innerHTML = loadingHTML('加载大纲…');
    Promise.all([api('/api/projects/' + projectId), loadThemes()]).then(function (results) {
      var p = results[0];
      var outline = null;
      try {
        outline = typeof p.outline_json === 'string' ? JSON.parse(p.outline_json) : (p.outline_json || p.outline);
      } catch (e) { outline = null; }
      if (p.outline && !outline) outline = p.outline;
      if (!outline || !Array.isArray(outline.pages)) {
        app.innerHTML = '<div class="empty"><div class="e-title">大纲数据异常</div>' +
          '<div class="e-desc">该项目尚无有效大纲，请返回列表重新创建</div></div>';
        return;
      }
      state.outlineProject = p;
      state.outline = outline;
      state.expandedPage = 0;
      drawOutline(p);
    }).catch(function (e) {
      if (e.message === 'unauthorized') return;
      app.innerHTML = '<div class="empty"><div class="e-title">加载失败</div><div class="e-desc">' + esc(e.message) + '</div></div>';
    });
  }

  function drawOutline(p) {
    var ol = state.outline;
    app.innerHTML =
      '<div class="view">' + stepperHTML(3) +
      '<div class="page-head"><div><h1>确认大纲</h1>' +
      '<div class="sub">点击页面卡片展开编辑，拖动左侧手柄调整顺序</div></div>' +
      '<a class="btn btn-outline btn-sm" href="#/new/style/' + encodeURIComponent(p.id) + '">← 上一步：选择风格</a></div>' +
      '<div class="outline-layout">' +
        '<div class="outline-side">' +
          '<div class="card card-pad">' +
            '<div class="field"><label>演示文稿标题</label>' +
            '<input type="text" id="ol-title" value="' + esc(ol.deck_title || p.title || '') + '"></div>' +
            '<div class="field"><label>视觉主题</label>' +
            '<div style="display:flex;align-items:center;gap:6px"><select id="ol-theme" style="flex:1"></select>' +
            '<span id="ol-theme-swatch"></span></div></div>' +
            '<div class="field" style="margin-bottom:0"><label>页数统计</label>' +
            '<div id="ol-count" style="color:var(--text-2);font-size:13px"></div></div>' +
          '</div>' +
          '<button class="btn btn-outline" id="ol-add" style="width:100%">＋ 添加一页</button>' +
        '</div>' +
        '<div>' +
          '<div class="outline-pages" id="ol-pages"></div>' +
          '<div class="outline-footer">' +
            '<a class="btn btn-ghost" href="#/new">返回重做</a>' +
            '<span style="color:var(--text-2);font-size:13px;flex:1">确认后 AI 将逐页生成幻灯片，可在下一步实时预览</span>' +
            '<button class="btn btn-primary btn-lg" id="ol-confirm">确认并开始生成</button>' +
          '</div>' +
        '</div>' +
      '</div></div>';

    document.getElementById('ol-title').addEventListener('input', function (e) {
      state.outline.deck_title = e.target.value;
    });

    /* theme select */
    var themeSel = document.getElementById('ol-theme');
    state.themes.forEach(function (t) {
      var opt = document.createElement('option');
      opt.value = t.id;
      opt.textContent = themeName(t) + (t.builtin ? '（内置）' : '');
      if (String(t.id) === String(p.theme_id)) opt.selected = true;
      themeSel.appendChild(opt);
    });
    var olSwatch = document.getElementById('ol-theme-swatch');
    function olUpdateSwatch() {
      var t = state.themes.find(function (x) { return String(x.id) === themeSel.value; });
      olSwatch.innerHTML = t ? swatchHTML(t) : '';
    }
    themeSel.addEventListener('change', olUpdateSwatch);
    olUpdateSwatch();

    drawPages();

    document.getElementById('ol-add').addEventListener('click', function () {
      state.outline.pages.push({
        page_number: state.outline.pages.length + 1,
        title: '新页面', key_message: '', content_summary: '',
        visual_suggestion: '', image_query: '', layout_hint: 'content', bullets: []
      });
      state.expandedPage = state.outline.pages.length - 1;
      drawPages();
    });

    document.getElementById('ol-confirm').addEventListener('click', function () {
      /* regeneration over existing pages needs an explicit confirmation */
      var hasResults = ['generating', 'ready', 'exported', 'failed'].indexOf(p.status) !== -1;
      if (hasResults) {
        confirmDanger({
          title: '重新生成',
          heading: '重新生成将覆盖现有页面',
          message: '该项目已有生成结果，重新生成会覆盖所有已生成的页面与导出文件，确定继续吗？',
          okText: '覆盖并重新生成',
          onOk: function () { submitOutlineAndGenerate(); }
        });
        return;
      }
      submitOutlineAndGenerate();
    });

    function submitOutlineAndGenerate() {
      var btn = document.getElementById('ol-confirm');
      state.outline.deck_title = document.getElementById('ol-title').value.trim() || state.outline.deck_title;
      renumberPages();
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner"></span>提交中…';
      api('/api/projects/' + p.id + '/outline', {
        method: 'PUT',
        body: { outline: state.outline, theme_id: themeSel.value ? Number(themeSel.value) : undefined }
      }).then(function () {
        return api('/api/projects/' + p.id + '/generate', { method: 'POST' });
      }).then(function () {
        toast('已开始生成', 'success');
        location.hash = '#/project/' + p.id;
      }).catch(function (e) {
        if (e.message !== 'unauthorized') toast('操作失败：' + e.message, 'error');
        btn.disabled = false;
        btn.innerHTML = '确认并开始生成';
      });
    }
  }

  function renumberPages() {
    state.outline.pages.forEach(function (pg, i) { pg.page_number = i + 1; });
  }

  function layoutLabel(key) {
    for (var i = 0; i < LAYOUT_HINTS.length; i++) if (LAYOUT_HINTS[i][0] === key) return LAYOUT_HINTS[i][1];
    return '内容页';
  }

  var dragIndex = null;

  function drawPages() {
    var wrap = document.getElementById('ol-pages');
    if (!wrap) return;
    var pages = state.outline.pages;
    document.getElementById('ol-count').textContent = '共 ' + pages.length + ' 页';
    wrap.innerHTML = '';
    pages.forEach(function (pg, i) {
      var expanded = i === state.expandedPage;
      var card = document.createElement('div');
      card.className = 'ol-card' + (expanded ? ' expanded' : '');
      card.setAttribute('data-index', i);

      var lhIcon = LAYOUT_ICONS[pg.layout_hint] || LAYOUT_ICONS.content;
      card.innerHTML =
        '<div class="oc-head">' +
          '<span class="drag-handle" title="拖动排序">' + ICONS.grip + '</span>' +
          '<span class="page-num">' + (i + 1) + '</span>' +
          '<div class="oc-main">' +
            '<div class="oc-title">' + esc(pg.title || '（无标题）') + '</div>' +
            '<div class="oc-key">' + esc(pg.key_message || '暂无核心信息') + '</div>' +
          '</div>' +
          '<span class="lh-badge">' + lhIcon + esc(layoutLabel(pg.layout_hint)) + '</span>' +
          '<button class="icon-btn danger" data-act="del" title="删除此页">✕</button>' +
          '<span class="icon-btn chev-btn" data-act="toggle" title="展开/收起">' + ICONS.chevronDown + '</span>' +
        '</div>' +
        '<div class="oc-body' + (expanded ? '' : ' hidden') + '">' +
          '<div class="field"><label>页面标题</label><input type="text" data-f="title" value="' + esc(pg.title) + '"></div>' +
          '<div class="field"><label>核心信息（key_message）</label><input type="text" data-f="key_message" value="' + esc(pg.key_message) + '"></div>' +
          '<div class="field"><label>内容摘要（content_summary）</label><textarea data-f="content_summary">' + esc(pg.content_summary) + '</textarea></div>' +
          '<div class="field"><label>版式（layout_hint）</label><div class="layout-picker">' +
            LAYOUT_HINTS.map(function (lh) {
              return '<button data-lh="' + lh[0] + '"' + (pg.layout_hint === lh[0] ? ' class="active"' : '') + '>' +
                LAYOUT_ICONS[lh[0]] + lh[1] + '</button>';
            }).join('') +
          '</div></div>' +
          '<div class="field" style="margin-bottom:0"><label>配图关键词（image_query）</label>' +
          '<input type="text" data-f="image_query" value="' + esc(pg.image_query) + '" placeholder="2–5 个英文关键词，留空则不配图"></div>' +
        '</div>';
      wrap.appendChild(card);

      /* expand / collapse via head click */
      var head = card.querySelector('.oc-head');
      head.addEventListener('click', function (e) {
        if (e.target.closest('[data-act="del"]') || e.target.closest('.drag-handle')) return;
        state.expandedPage = expanded ? -1 : i;
        drawPages();
      });

      /* field edits */
      card.querySelectorAll('[data-f]').forEach(function (input) {
        input.addEventListener('input', function () {
          pg[input.getAttribute('data-f')] = input.value;
          if (input.getAttribute('data-f') === 'title') {
            card.querySelector('.oc-title').textContent = input.value || '（无标题）';
          }
          if (input.getAttribute('data-f') === 'key_message') {
            card.querySelector('.oc-key').textContent = input.value || '暂无核心信息';
          }
        });
      });

      /* layout picker */
      card.querySelectorAll('[data-lh]').forEach(function (b) {
        b.addEventListener('click', function () {
          pg.layout_hint = b.getAttribute('data-lh');
          card.querySelectorAll('[data-lh]').forEach(function (x) { x.classList.toggle('active', x === b); });
          card.querySelector('.lh-badge').innerHTML =
            (LAYOUT_ICONS[pg.layout_hint] || LAYOUT_ICONS.content) + esc(layoutLabel(pg.layout_hint));
        });
      });

      /* delete */
      card.querySelector('[data-act="del"]').addEventListener('click', function () {
        if (state.outline.pages.length <= 1) { toast('至少保留一页', 'error'); return; }
        state.outline.pages.splice(i, 1);
        state.expandedPage = Math.min(state.expandedPage, state.outline.pages.length - 1);
        drawPages();
      });

      /* HTML5 drag & drop reorder (via handle) */
      var handle = card.querySelector('.drag-handle');
      handle.setAttribute('draggable', 'true');
      handle.addEventListener('dragstart', function (e) {
        dragIndex = i;
        card.classList.add('dragging');
        try { e.dataTransfer.setData('text/plain', String(i)); } catch (err) {}
        e.dataTransfer.effectAllowed = 'move';
      });
      handle.addEventListener('dragend', function () {
        dragIndex = null;
        wrap.querySelectorAll('.ol-card').forEach(function (c) { c.classList.remove('dragging', 'drag-over'); });
      });
      card.addEventListener('dragover', function (e) {
        if (dragIndex === null || dragIndex === i) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        card.classList.add('drag-over');
      });
      card.addEventListener('dragleave', function () { card.classList.remove('drag-over'); });
      card.addEventListener('drop', function (e) {
        e.preventDefault();
        if (dragIndex === null || dragIndex === i) return;
        var moved = state.outline.pages.splice(dragIndex, 1)[0];
        state.outline.pages.splice(i, 0, moved);
        state.expandedPage = i;
        dragIndex = null;
        drawPages();
      });
    });
  }

  /* ============================== 6. wizard step 4: generate / preview ============================== */
  var POLL_MAX_FAILS = 3;

  function renderPreview(projectId) {
    if (!projectId) { location.hash = '#/projects'; return; }
    /* re-entering the same project keeps the svg cache + unsaved click edits */
    var sameProject = state.preview.project && String(state.preview.project.id) === String(projectId);
    if (!sameProject) {
      state.preview.project = null;
      state.preview.status = null;
      state.preview.currentPage = 1;
      state.preview.pollFails = 0;
      state.preview.svgCache = {};
      state.preview.svgDirty = {};
      state.preview.stageReq = 0;
    }
    state.preview.stageInit = false; // first stage paint guard
    app.innerHTML = loadingHTML('加载项目…');

    api('/api/projects/' + projectId).then(function (p) {
      if (p.status === 'draft' || p.status === 'outline') {
        location.hash = '#/outline/' + projectId;
        return null;
      }
      state.preview.project = p;
      drawPreviewShell(p);
      startPolling(projectId);
      return null;
    }).catch(function (e) {
      if (e.message === 'unauthorized') return;
      app.innerHTML = '<div class="empty"><div class="e-title">加载失败</div><div class="e-desc">' + esc(e.message) + '</div></div>';
    });
  }

  function startPolling(projectId) {
    stopPolling();
    pollStatus(projectId);
    state.preview.pollTimer = setInterval(function () { pollStatus(projectId); }, 1500);
  }

  function previewOutlinePages() {
    var p = state.preview.project;
    if (!p) return [];
    var ol = null;
    try { ol = typeof p.outline_json === 'string' ? JSON.parse(p.outline_json) : p.outline_json; } catch (e) {}
    if (p.outline) ol = p.outline;
    return (ol && Array.isArray(ol.pages)) ? ol.pages : [];
  }

  function drawPreviewShell(p) {
    app.innerHTML =
      '<div class="view">' + stepperHTML(4) +
      '<div class="page-head"><div><h1>' + esc(p.title || '项目预览') + '</h1>' +
      '<div class="sub" id="pv-sub">' + badge(PROJECT_STATUS, p.status) + '</div></div>' +
      '<div style="display:flex;gap:10px">' +
        '<a class="btn btn-outline" href="#/outline/' + encodeURIComponent(p.id) + '">← 返回修改大纲</a>' +
        '<a class="btn btn-outline" href="#/projects">返回列表</a>' +
        '<button class="btn btn-primary" id="pv-export" disabled>导出 PPTX</button>' +
        '<button class="btn btn-outline hidden" id="pv-download">' + ICONS.download + '下载 PPTX</button>' +
      '</div></div>' +
      '<div id="pv-banner"></div>' +
      '<div class="gen-progress-wrap" id="pv-progress-wrap">' +
        '<div class="gen-progress-meta">' +
          '<span class="gen-status-text" id="pv-progress-text">正在获取状态…</span>' +
          '<span style="display:inline-flex;align-items:center;gap:10px">' +
            '<button class="btn btn-outline btn-sm hidden" id="pv-retry">' + ICONS.refresh + '重试</button>' +
            '<span class="pct" id="pv-progress-pct"></span>' +
          '</span>' +
        '</div>' +
        '<div class="progress"><i id="pv-progress-bar" style="width:0%"></i></div>' +
      '</div>' +
      '<div class="gen-layout">' +
        '<div class="gen-side card" id="pv-thumbs"></div>' +
        '<div>' +
          '<div class="svg-stage" id="pv-stage"><div class="svg-empty"><span class="spinner"></span>加载预览…</div></div>' +
          '<div class="page-toolbar">' +
            '<button class="btn btn-outline btn-sm" id="pv-prev">‹ 上一页</button>' +
            '<button class="btn btn-outline btn-sm" id="pv-next">下一页 ›</button>' +
            '<span style="width:1px;height:20px;background:var(--border)"></span>' +
            '<button class="btn btn-outline btn-sm" id="pv-regen">' + ICONS.refresh + '重新生成</button>' +
            '<button class="btn btn-outline btn-sm" id="pv-edit">' + ICONS.code + '源码</button>' +
            '<button class="btn btn-primary btn-sm hidden" id="pv-save-svg">' + ICONS.save + '保存修改</button>' +
            '<button class="btn btn-outline btn-sm hidden" id="pv-discard-svg">放弃修改</button>' +
            '<button class="btn btn-outline btn-sm" id="pv-zoom">' + ICONS.zoom + '查看大图</button>' +
            '<button class="btn btn-outline btn-sm" id="pv-share">' + ICONS.share + '分享</button>' +
            '<span style="color:var(--text-3);font-size:12px">点击页面中的文字可直接编辑</span>' +
            '<span class="spacer"></span>' +
            '<span class="page-label" id="pv-page-label"></span>' +
            '<span class="kbd-hint"><kbd>←</kbd><kbd>→</kbd>翻页</span>' +
          '</div>' +
          '<div id="pv-page-error"></div>' +
        '</div>' +
      '</div></div>';

    document.getElementById('pv-regen').addEventListener('click', function () {
      openRegenModal(p.id, state.preview.currentPage);
    });
    document.getElementById('pv-edit').addEventListener('click', function () {
      openEditSVGModal(p.id, state.preview.currentPage);
    });
    document.getElementById('pv-zoom').addEventListener('click', function () {
      openZoomModal(p.id, state.preview.currentPage);
    });
    document.getElementById('pv-share').addEventListener('click', function () {
      openShareModal(p.id);
    });
    document.getElementById('pv-save-svg').addEventListener('click', function () {
      saveSvgEdits(p.id, state.preview.currentPage);
    });
    document.getElementById('pv-discard-svg').addEventListener('click', function () {
      discardSvgEdits(p.id, state.preview.currentPage);
    });
    /* click-to-edit on stage text (delegation survives innerHTML swaps) */
    var stageEl = document.getElementById('pv-stage');
    var hoverText = null;
    stageEl.addEventListener('mouseover', function (e) {
      if (hoverText) { hoverText.classList.remove('svg-text-hover'); hoverText = null; }
      var t = e.target && e.target.closest ? e.target.closest('text') : null;
      if (t && stageEl.contains(t) && stageEl.querySelector('svg')) {
        hoverText = t;
        t.classList.add('svg-text-hover');
      }
    });
    stageEl.addEventListener('mouseleave', function () {
      if (hoverText) { hoverText.classList.remove('svg-text-hover'); hoverText = null; }
    });
    stageEl.addEventListener('click', function (e) {
      var t = e.target && e.target.closest ? e.target.closest('text') : null;
      if (!t || !stageEl.contains(t) || !stageEl.querySelector('svg')) return;
      e.preventDefault();
      openSvgTextEditor(stageEl, t, p.id, state.preview.currentPage);
    });
    document.getElementById('pv-prev').addEventListener('click', function () { stepPage(p.id, -1); });
    document.getElementById('pv-next').addEventListener('click', function () { stepPage(p.id, 1); });
    document.getElementById('pv-export').addEventListener('click', function () { exportPPTX(p.id); });
    document.getElementById('pv-download').addEventListener('click', function () { downloadPPTX(p.id); });
    document.getElementById('pv-retry').addEventListener('click', function () {
      state.preview.pollFails = 0;
      document.getElementById('pv-retry').classList.add('hidden');
      startPolling(p.id);
    });
    /* failed-project banner: retry generation (event delegation, banner re-renders per poll) */
    document.getElementById('pv-banner').addEventListener('click', function (e) {
      var btn = e.target.closest('[data-retry-gen]');
      if (!btn) return;
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner"></span>启动中…';
      api('/api/projects/' + p.id + '/generate', { method: 'POST' }).then(function () {
        toast('已重新开始生成', 'success');
        state.preview.pollFails = 0;
        startPolling(p.id);
      }).catch(function (err) {
        if (err.message !== 'unauthorized') toast('重试失败：' + err.message, 'error');
        btn.disabled = false;
        btn.innerHTML = ICONS.refresh + '重试生成';
      });
    });
  }

  function pageTotal() {
    var st = state.preview.status;
    if (st && st.pages && st.pages.length) return st.pages.length;
    var outlinePages = previewOutlinePages();
    if (outlinePages.length) return outlinePages.length;
    return (state.preview.project && state.preview.project.slide_count) || 1;
  }

  function stepPage(projectId, dir) {
    var total = pageTotal();
    var n = state.preview.currentPage + dir;
    if (n < 1 || n > total) return;
    if (state.preview.svgDirty[state.preview.currentPage]) {
      if (!confirm('第 ' + state.preview.currentPage + ' 页有未保存的修改。修改仍保留在本地，可稍后返回该页点击「保存修改」，确定翻页吗？')) return;
    }
    closeSvgTextEditor();
    state.preview.currentPage = n;
    if (state.preview.status) updatePreviewStatus(projectId, state.preview.status);
    loadPageSVG(projectId, n);
  }

  function pollStatus(projectId) {
    api('/api/projects/' + projectId + '/status').then(function (st) {
      state.preview.pollFails = 0;
      state.preview.status = st;
      updatePreviewStatus(projectId, st);
      /* first paint of the big stage (also covers leaving & re-entering the route) */
      if (!state.preview.stageInit) {
        state.preview.stageInit = true;
        loadPageSVG(projectId, state.preview.currentPage);
      }
      if (st.status === 'ready' || st.status === 'exported' || st.status === 'failed') {
        stopPolling();
      }
    }).catch(function (e) {
      if (e.message === 'unauthorized') { stopPolling(); return; }
      state.preview.pollFails++;
      if (state.preview.pollFails >= POLL_MAX_FAILS) {
        stopPolling();
        toast('网络异常，已停止自动刷新。请检查网络后点击「重试」', 'error');
        var retry = document.getElementById('pv-retry');
        if (retry) retry.classList.remove('hidden');
        var txt = document.getElementById('pv-progress-text');
        if (txt) txt.textContent = '网络异常，进度可能不是最新';
      }
    });
  }

  function friendlyStatusText(st, done, total, failed) {
    var pages = st.pages || [];
    var cur = null;
    for (var i = 0; i < pages.length; i++) {
      if (pages[i].status === 'generating') { cur = (pages[i].n != null ? pages[i].n : pages[i].page_number); break; }
    }
    if (st.status === 'generating') {
      if (st.stage === 'images') return '正在搜集配图（这一步通常最慢，约 1–3 分钟）…';
      if (st.stage === 'export') return '页面已全部生成，正在导出 PPTX…';
      /* stage === 'pages' or unknown */
      if (cur) return 'AI 正在构思第 ' + cur + ' 页…（已完成 ' + done + '/' + total + (failed ? '，' + failed + ' 页失败' : '') + '）';
      return 'AI 正在奋笔疾书…（已完成 ' + done + '/' + total + (failed ? '，' + failed + ' 页失败' : '') + '）';
    }
    if (st.status === 'failed') return '生成失败：' + (st.error || '未知错误');
    if (st.status === 'ready' || st.status === 'exported') {
      return failed ? ('生成完成：' + done + '/' + total + ' 页（' + failed + ' 页失败，可单独重新生成）')
                    : '全部 ' + total + ' 页生成完成，可以导出了';
    }
    if (st.status === 'confirmed') return '排队等待中，即将开始生成…';
    return '正在获取状态…';
  }

  function updatePreviewStatus(projectId, st) {
    var pages = st.pages || [];
    var done = pages.filter(function (x) { return x.status === 'done'; }).length;
    var failed = pages.filter(function (x) { return x.status === 'failed'; }).length;
    var total = pages.length || pageTotal();
    var pct = total ? Math.round(done / total * 100) : 0;

    var bar = document.getElementById('pv-progress-bar');
    if (!bar) return; // view changed
    var isDone = st.status === 'ready' || st.status === 'exported';
    var stageBusy = st.status === 'generating' && (st.stage === 'images' || st.stage === 'export');
    bar.style.width = (isDone ? 100 : pct) + '%';
    bar.parentElement.classList.toggle('green', isDone);
    bar.parentElement.classList.toggle('indet', stageBusy && pct === 0);
    document.getElementById('pv-progress-wrap').classList.toggle('done', isDone);
    document.getElementById('pv-progress-pct').textContent = (isDone ? 100 : pct) + '%';
    document.getElementById('pv-progress-text').textContent = friendlyStatusText(st, done, total, failed);
    document.getElementById('pv-sub').innerHTML = badge(PROJECT_STATUS, st.status);

    /* failed-project banner with retry */
    var banner = document.getElementById('pv-banner');
    if (st.status === 'failed') {
      banner.innerHTML =
        '<div class="error-banner">' +
          '<span class="eb-ico">' + ICONS.warn + '</span>' +
          '<div class="eb-main"><b>生成失败</b>' +
          '<div class="eb-msg" title="' + esc(st.error || '未知错误') + '">' + esc(st.error || '未知错误') + '</div></div>' +
          '<button class="btn btn-primary btn-sm" data-retry-gen>' + ICONS.refresh + '重试生成</button>' +
        '</div>';
    } else {
      banner.innerHTML = '';
    }

    /* thumbnails: real SVG for done pages, skeleton for the rest */
    var outlinePages = previewOutlinePages();
    var thumbs = document.getElementById('pv-thumbs');
    thumbs.innerHTML = '';
    var list = pages.length ? pages : outlinePages.map(function (pg, i) {
      return { n: pg.page_number || i + 1, status: 'pending' };
    });
    list.forEach(function (pg) {
      var n = pg.n != null ? pg.n : pg.page_number;
      var o = outlinePages.find(function (x) { return x.page_number === n; });
      var item = document.createElement('div');
      item.className = 'thumb-item' + (n === state.preview.currentPage ? ' active' : '') +
        (pg.status === 'failed' ? ' failed' : '') + (pg.status === 'done' ? '' : ' skel');
      var boxInner;
      if (pg.status === 'done' && state.preview.svgCache[n]) {
        boxInner = state.preview.svgCache[n];
      } else if (pg.status === 'done') {
        boxInner = ''; // will be filled async below
      } else {
        var label;
        if (pg.status === 'generating') {
          label = '<span class="spinner"></span>生成中';
        } else if (pg.status === 'failed') {
          label = '生成失败';
        } else if (st.stage === 'images') {
          label = '<span class="tb-img-ico">' + ICONS.image + '</span>搜图中';
        } else {
          label = '排队中';
        }
        boxInner = '<div class="tb-status">' + label + '</div>';
      }
      item.innerHTML =
        '<div class="thumb-box' + (pg.status === 'done' ? '' : ' skeleton') + '">' + boxInner + '</div>' +
        '<div class="thumb-cap"><span class="tc-num">' + n + '</span>' +
        '<span class="tc-title">' + esc((o && o.title) || ('第 ' + n + ' 页')) + '</span></div>';
      item.addEventListener('click', function () {
        state.preview.currentPage = n;
        updatePreviewStatus(projectId, st);
        loadPageSVG(projectId, n);
      });
      thumbs.appendChild(item);
      if (pg.status === 'done' && !state.preview.svgCache[n]) {
        fillThumb(projectId, n);
      }
    });

    /* export / download buttons */
    var allDone = total > 0 && done === total;
    var exportBtn = document.getElementById('pv-export');
    var dlBtn = document.getElementById('pv-download');
    exportBtn.disabled = !(allDone || isDone);
    dlBtn.classList.toggle('hidden', !st.pptx_ready && st.status !== 'exported' && st.status !== 'ready');

    /* page label & error */
    var curPage = pages.find(function (x) { return (x.n != null ? x.n : x.page_number) === state.preview.currentPage; });
    document.getElementById('pv-page-label').innerHTML = '第 ' + state.preview.currentPage + ' / ' + total + ' 页' +
      (curPage ? ' · ' + esc(PAGE_STATUS[curPage.status] ? PAGE_STATUS[curPage.status][0] : curPage.status) : '') +
      (state.preview.svgDirty[state.preview.currentPage] ? ' · <span style="color:var(--warning);font-weight:600">未保存</span>' : '');
    refreshSvgDirtyUI(state.preview.currentPage);
    var errBox = document.getElementById('pv-page-error');
    errBox.innerHTML = (curPage && curPage.error) ? '<div class="page-error">本页生成失败：' + esc(curPage.error) + '</div>' : '';
  }

  function fillThumb(projectId, n) {
    apiSVG('/api/projects/' + projectId + '/pages/' + n + '/svg').then(function (svg) {
      if (!svg || svg.indexOf('<svg') === -1) return;
      state.preview.svgCache[n] = svg;
      /* refresh thumbs + stage if still on this view */
      if (state.preview.status && document.getElementById('pv-thumbs')) {
        updatePreviewStatus(projectId, state.preview.status);
        if (state.preview.currentPage === n) paintStage(n);
      }
    }).catch(function () { /* thumb stays skeleton; stage load shows its own error */ });
  }

  function paintStage(n) {
    var stage = document.getElementById('pv-stage');
    if (!stage) return;
    var svg = state.preview.svgCache[n];
    if (svg && svg.indexOf('<svg') !== -1) {
      stage.innerHTML = svg;
    } else {
      stage.innerHTML = '<div class="svg-empty">该页尚未生成</div>';
    }
  }

  function loadPageSVG(projectId, n) {
    var stage = document.getElementById('pv-stage');
    if (!stage) return;
    var req = ++state.preview.stageReq;
    if (state.preview.svgCache[n]) { paintStage(n); return; }
    stage.innerHTML = '<div class="svg-empty"><span class="spinner"></span>加载预览…</div>';
    apiSVG('/api/projects/' + projectId + '/pages/' + n + '/svg').then(function (svg) {
      if (req !== state.preview.stageReq || !stage.isConnected) return;
      if (svg && svg.indexOf('<svg') !== -1) {
        state.preview.svgCache[n] = svg;
        paintStage(n);
      } else {
        stage.innerHTML = '<div class="svg-empty">该页尚未生成</div>';
      }
    }).catch(function () {
      if (req !== state.preview.stageReq || !stage.isConnected) return;
      stage.innerHTML = '<div class="svg-empty">该页暂无预览（可能尚未生成）</div>';
    });
  }

  /* ---------- SVG click-to-edit (visual mode) ---------- */
  function serializeStageSvg() {
    var stage = document.getElementById('pv-stage');
    if (!stage) return '';
    var svg = stage.querySelector('svg');
    if (!svg) return '';
    try { return new XMLSerializer().serializeToString(svg); } catch (e) { return ''; }
  }

  function markSvgDirty(n) {
    state.preview.svgDirty[n] = true;
    refreshSvgDirtyUI(n);
  }

  function refreshSvgDirtyUI(n) {
    var saveBtn = document.getElementById('pv-save-svg');
    if (!saveBtn) return;
    var dirty = !!state.preview.svgDirty[n];
    saveBtn.classList.toggle('hidden', !dirty);
    document.getElementById('pv-discard-svg').classList.toggle('hidden', !dirty);
  }

  function saveSvgEdits(projectId, n) {
    if (!state.preview.svgDirty[n]) return;
    var svg = serializeStageSvg();
    if (!svg || svg.indexOf('<svg') === -1) { toast('无法序列化当前页面，请改用「源码」模式编辑', 'error'); return; }
    var btn = document.getElementById('pv-save-svg');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>保存中…';
    api('/api/projects/' + projectId + '/pages/' + n + '/svg', {
      method: 'PUT', rawBody: svg, rawType: 'image/svg+xml'
    }).then(function () {
      toast('第 ' + n + ' 页修改已保存', 'success');
      delete state.preview.svgDirty[n];
      state.preview.svgCache[n] = svg;
      if (state.preview.status) updatePreviewStatus(projectId, state.preview.status);
    }).catch(function (e) {
      if (e.message !== 'unauthorized') toast('保存失败：' + e.message, 'error');
    }).then(function () {
      btn.disabled = false;
      btn.innerHTML = ICONS.save + '保存修改';
    });
  }

  function discardSvgEdits(projectId, n) {
    if (!state.preview.svgDirty[n]) return;
    delete state.preview.svgDirty[n];
    delete state.preview.svgCache[n];
    closeSvgTextEditor();
    loadPageSVG(projectId, n);
    if (state.preview.status) updatePreviewStatus(projectId, state.preview.status);
    toast('已放弃第 ' + n + ' 页的未保存修改', 'info');
  }

  /* floating mini editor for one <text> element */
  var svgTextPop = null;
  var svgTextPopDocHandler = null;

  function closeSvgTextEditor() {
    if (svgTextPop) { svgTextPop.remove(); svgTextPop = null; }
    if (svgTextPopDocHandler) {
      document.removeEventListener('mousedown', svgTextPopDocHandler);
      svgTextPopDocHandler = null;
    }
  }

  function openSvgTextEditor(stageEl, textEl, projectId, n) {
    closeSvgTextEditor();
    var tspans = textEl.getElementsByTagName('tspan');
    var lines = [];
    if (tspans.length) {
      for (var i = 0; i < tspans.length; i++) lines.push(tspans[i].textContent);
    } else {
      lines.push(textEl.textContent || '');
    }

    var pop = document.createElement('div');
    pop.className = 'svg-text-pop';
    pop.innerHTML =
      '<div class="pop-title">编辑文本' + (tspans.length > 1 ? '（每行对应一个 tspan，共 ' + tspans.length + ' 行）' : '') + '</div>' +
      '<textarea spellcheck="false" rows="' + Math.min(6, Math.max(2, lines.length)) + '"></textarea>' +
      '<div class="pop-actions">' +
        '<button class="btn btn-outline btn-sm" data-cancel>取消</button>' +
        '<button class="btn btn-primary btn-sm" data-ok>确定</button>' +
      '</div>';
    document.body.appendChild(pop);
    svgTextPop = pop;

    var ta = pop.querySelector('textarea');
    ta.value = lines.join('\n');
    ta.focus();
    ta.select();

    /* position near the clicked text, clamped into the viewport */
    var rect = textEl.getBoundingClientRect();
    var pw = pop.offsetWidth, ph = pop.offsetHeight;
    var left = Math.max(8, Math.min(rect.left, window.innerWidth - pw - 8));
    var top = rect.bottom + 8;
    if (top + ph > window.innerHeight - 8) top = Math.max(8, rect.top - ph - 8);
    pop.style.left = left + 'px';
    pop.style.top = top + 'px';

    function apply() {
      var newLines = ta.value.split('\n');
      while (newLines.length > 1 && newLines[newLines.length - 1] === '') newLines.pop();
      if (!newLines.length) newLines = [''];
      var tsp = textEl.getElementsByTagName('tspan');
      var i;
      if (tsp.length) {
        if (newLines.length === tsp.length) {
          for (i = 0; i < tsp.length; i++) tsp[i].textContent = newLines[i];
        } else if (newLines.length < tsp.length) {
          /* fewer lines: fill the leading tspans, drop the rest (keeps original positions) */
          for (i = 0; i < newLines.length; i++) tsp[i].textContent = newLines[i];
          while (tsp.length > newLines.length) textEl.removeChild(tsp[tsp.length - 1]);
          toast('行数少于原有文本行，多余的 tspan 已移除', 'info');
        } else {
          /* more lines: extra lines are merged into the last tspan */
          for (i = 0; i < tsp.length - 1; i++) tsp[i].textContent = newLines[i];
          tsp[tsp.length - 1].textContent = newLines.slice(tsp.length - 1).join(' ');
          toast('行数多于原有文本行，多余内容已合并到最后一行', 'info');
        }
      } else {
        textEl.textContent = newLines.join(' ');
      }
      markSvgDirty(n);
      state.preview.svgCache[n] = serializeStageSvg();
      if (state.preview.status) updatePreviewStatus(projectId, state.preview.status);
      closeSvgTextEditor();
    }

    pop.querySelector('[data-ok]').addEventListener('click', apply);
    pop.querySelector('[data-cancel]').addEventListener('click', closeSvgTextEditor);
    ta.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { e.preventDefault(); closeSvgTextEditor(); }
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); apply(); }
    });

    /* click anywhere outside the popup cancels */
    svgTextPopDocHandler = function (e) {
      if (svgTextPop && !svgTextPop.contains(e.target)) closeSvgTextEditor();
    };
    setTimeout(function () {
      if (svgTextPopDocHandler) document.addEventListener('mousedown', svgTextPopDocHandler);
    }, 0);
  }

  /* keyboard ← / → on preview route */
  document.addEventListener('keydown', function (e) {
    if ((location.hash || '').indexOf('#/project/') !== 0) return;
    if (document.getElementById('modal-root').children.length) return;
    var tag = (e.target && e.target.tagName) || '';
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    var p = state.preview.project;
    if (!p) return;
    e.preventDefault();
    stepPage(p.id, e.key === 'ArrowLeft' ? -1 : 1);
  });

  function openRegenModal(projectId, n) {
    openModal({
      title: '重新生成第 ' + n + ' 页',
      render: function (body, foot, close) {
        body.innerHTML =
          '<div class="field" style="margin-bottom:0"><label>修改反馈（告诉 AI 需要调整什么，留空则直接重画）</label>' +
          '<textarea id="rg-feedback" rows="4" placeholder="例如：标题改为红色；增加一个数据卡片；减少文字量，突出核心结论"></textarea></div>';
        var cancel = document.createElement('button');
        cancel.className = 'btn btn-outline'; cancel.textContent = '取消';
        cancel.addEventListener('click', close);
        var ok = document.createElement('button');
        ok.className = 'btn btn-primary'; ok.textContent = '开始重新生成';
        ok.addEventListener('click', function () {
          var feedback = document.getElementById('rg-feedback').value.trim();
          ok.disabled = true;
          ok.innerHTML = '<span class="spinner"></span>生成中…';
          api('/api/projects/' + projectId + '/pages/' + n + '/regenerate', {
            method: 'POST', body: { feedback: feedback || undefined }
          }).then(function (data) {
            toast('第 ' + n + ' 页已重新生成', 'success');
            close();
            delete state.preview.svgDirty[n];
            if (data && data.svg) {
              state.preview.svgCache[n] = data.svg;
              paintStage(n);
            } else {
              delete state.preview.svgCache[n];
              loadPageSVG(projectId, n);
            }
            pollStatus(projectId);
          }).catch(function (e) {
            if (e.message !== 'unauthorized') toast('重新生成失败：' + e.message, 'error');
            ok.disabled = false; ok.textContent = '开始重新生成';
          });
        });
        foot.appendChild(cancel); foot.appendChild(ok);
      }
    });
  }

  function openEditSVGModal(projectId, n) {
    openModal({
      title: '编辑第 ' + n + ' 页 SVG 源码',
      wide: true,
      render: function (body, foot, close) {
        body.innerHTML = loadingHTML('加载源码…');
        apiSVG('/api/projects/' + projectId + '/pages/' + n + '/svg').then(function (svg) {
          body.innerHTML = '<textarea class="code" id="svg-editor" spellcheck="false"></textarea>' +
            '<div class="hint" style="font-size:12px;color:var(--text-3);margin-top:6px">直接修改 SVG 源码，保存后立即生效（viewBox 应为 0 0 1280 720）</div>';
          body.querySelector('#svg-editor').value = svg || '';
        }).catch(function (e) {
          body.innerHTML = '<div class="page-error">加载失败：' + esc(e.message) + '</div>';
        });

        var cancel = document.createElement('button');
        cancel.className = 'btn btn-outline'; cancel.textContent = '取消';
        cancel.addEventListener('click', close);
        var ok = document.createElement('button');
        ok.className = 'btn btn-primary'; ok.textContent = '保存';
        ok.addEventListener('click', function () {
          var ta = body.querySelector('#svg-editor');
          if (!ta) return;
          var svg = ta.value;
          if (svg.indexOf('<svg') === -1) { toast('内容不像有效的 SVG', 'error'); return; }
          ok.disabled = true; ok.innerHTML = '<span class="spinner"></span>保存中…';
          api('/api/projects/' + projectId + '/pages/' + n + '/svg', {
            method: 'PUT', rawBody: svg, rawType: 'image/svg+xml'
          }).then(function () {
            toast('已保存', 'success');
            close();
            delete state.preview.svgDirty[n];
            state.preview.svgCache[n] = svg;
            paintStage(n);
            pollStatus(projectId);
          }).catch(function (e) {
            if (e.message !== 'unauthorized') toast('保存失败：' + e.message, 'error');
            ok.disabled = false; ok.textContent = '保存';
          });
        });
        foot.appendChild(cancel); foot.appendChild(ok);
      }
    });
  }

  function openZoomModal(projectId, n) {
    openModal({
      title: '第 ' + n + ' 页 · 大图预览',
      wide: true,
      footer: false,
      render: function (body) {
        body.innerHTML = '<div class="zoom-stage">' + loadingHTML('加载中…') + '</div>';
        var show = function (svg) {
          var stage = body.querySelector('.zoom-stage');
          if (!stage) return;
          stage.innerHTML = (svg && svg.indexOf('<svg') !== -1) ? svg : '<div class="svg-empty">该页暂无预览</div>';
        };
        if (state.preview.svgCache[n]) { show(state.preview.svgCache[n]); return; }
        apiSVG('/api/projects/' + projectId + '/pages/' + n + '/svg').then(function (svg) {
          if (svg && svg.indexOf('<svg') !== -1) state.preview.svgCache[n] = svg;
          show(svg);
        }).catch(function () { show(''); });
      }
    });
  }

  function exportPPTX(projectId) {
    var btn = document.getElementById('pv-export');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>导出中…';
    api('/api/projects/' + projectId + '/export', { method: 'POST' }).then(function () {
      downloadPPTX(projectId);
      toast('导出成功，已开始下载', 'success');
      pollStatus(projectId);
    }).catch(function (e) {
      if (e.message !== 'unauthorized') toast('导出失败：' + e.message, 'error');
    }).then(function () {
      btn.disabled = false;
      btn.textContent = '导出 PPTX';
    });
  }

  function downloadPPTX(projectId) {
    var headers = {};
    if (state.token) headers['Authorization'] = 'Bearer ' + state.token;
    fetch('/api/projects/' + projectId + '/download', { headers: headers }).then(function (res) {
      if (res.status === 401) { clearAuth(); location.hash = '#/login'; throw new Error('unauthorized'); }
      if (!res.ok) throw new Error('下载失败 (' + res.status + ')');
      var dispo = res.headers.get('Content-Disposition') || '';
      var m = dispo.match(/filename\*?=(?:UTF-8'')?"?([^";]+)/i);
      var fname = m ? decodeURIComponent(m[1]) : 'presentation.pptx';
      return res.blob().then(function (blob) {
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url; a.download = fname;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(function () { URL.revokeObjectURL(url); }, 4000);
      });
    }).catch(function (e) {
      if (e.message !== 'unauthorized') toast(e.message, 'error');
    });
  }

  /* ---------- share link (public read-only viewer) ---------- */
  function copyShareLink(input, btn) {
    function done() {
      btn.textContent = '已复制';
      toast('链接已复制到剪贴板', 'success');
      setTimeout(function () { btn.textContent = '复制链接'; }, 2000);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(input.value).then(done, function () {
        input.select();
        document.execCommand('copy');
        done();
      });
    } else {
      input.select();
      document.execCommand('copy');
      done();
    }
  }

  function openShareModal(projectId) {
    api('/api/projects/' + projectId + '/share', { method: 'POST' }).then(function (d) {
      var url = location.origin + d.share_url;
      openModal({
        title: '分享项目 · 已开启分享',
        render: function (body, foot, close) {
          body.innerHTML =
            '<div style="color:var(--text-2);font-size:13.5px;margin-bottom:12px">' +
              '任何人通过此链接都能只读浏览该演示文稿（无需登录）：</div>' +
            '<input id="share-url-input" readonly style="width:100%;padding:9px 12px;font-size:13px;' +
              'border:1px solid var(--border-strong);border-radius:9px;background:var(--bg);' +
              'color:var(--text);font-family:var(--mono)" value="' + esc(url) + '">' +
            '<div style="color:var(--text-3);font-size:12px;margin-top:10px">' +
              '再次打开此弹窗链接保持不变；撤销后链接立即失效。</div>';
          var input = body.querySelector('#share-url-input');
          input.addEventListener('focus', function () { input.select(); });
          var revoke = document.createElement('button');
          revoke.className = 'btn btn-danger-solid';
          revoke.textContent = '撤销分享';
          revoke.addEventListener('click', function () {
            confirmDanger({
              title: '撤销分享',
              heading: '确定撤销分享吗？',
              message: '撤销后该链接立即失效，已收到链接的人将无法再访问。',
              okText: '撤销分享',
              onOk: function () {
                return api('/api/projects/' + projectId + '/share', { method: 'DELETE' }).then(function () {
                  toast('分享已撤销', 'success');
                  close();
                }).catch(function (e) {
                  if (e.message !== 'unauthorized') toast('撤销失败：' + e.message, 'error');
                });
              }
            });
          });
          var copy = document.createElement('button');
          copy.className = 'btn btn-primary';
          copy.textContent = '复制链接';
          copy.addEventListener('click', function () { copyShareLink(input, copy); });
          foot.appendChild(revoke);
          foot.appendChild(copy);
        }
      });
    }).catch(function (e) {
      if (e.message !== 'unauthorized') toast('开启分享失败：' + e.message, 'error');
    });
  }

  /* ============================== 7. usage ============================== */
  function renderUsage() {
    app.innerHTML = loadingHTML('加载用量数据…');
    api('/api/usage').then(function (d) {
      d = d || {};
      var totalUsed = d.token_used != null ? d.token_used
        : (d.total_tokens != null ? d.total_tokens : (d.totals && d.totals.total_tokens) || 0);
      var quota = d.token_quota != null ? d.token_quota : (d.quota != null ? d.quota : 0);
      var perProject = d.per_project || d.projects || d.by_project || [];
      var recent = d.recent || d.records || [];
      var pct = quota > 0 ? Math.min(100, Math.round(totalUsed / quota * 100)) : 0;

      var html = '<div class="view">' +
        '<div class="page-head"><div><h1>用量统计</h1>' +
        '<div class="sub">LLM token 消耗与配额</div></div></div>' +
        '<div class="stat-grid">' +
          '<div class="card stat-card"><div class="s-label">已用 Token</div>' +
            '<div class="s-value">' + fmtNum(totalUsed) + '</div></div>' +
          '<div class="card stat-card"><div class="s-label">配额</div>' +
            '<div class="s-value">' + (quota > 0 ? fmtNum(quota) : '不限') + '</div>' +
            (quota > 0 ? '<div class="s-sub">剩余 ' + fmtNum(Math.max(0, quota - totalUsed)) + '</div>' : '') +
          '</div>' +
          '<div class="card stat-card"><div class="s-label">配额使用</div>' +
            '<div class="s-value">' + (quota > 0 ? pct + '%' : '—') + '</div>' +
            (quota > 0 ? '<div class="progress thin" style="margin-top:10px"><i style="width:' + pct + '%"></i></div>' : '') +
          '</div>' +
        '</div>';

      html += '<div class="card" style="margin-bottom:20px"><div class="card-pad" style="padding-bottom:8px"><b>按项目拆分</b></div><div class="table-wrap">';
      if (!perProject.length) {
        html += '<div class="card-pad" style="color:var(--text-3)">暂无记录</div>';
      } else {
        html += '<table class="data"><thead><tr><th>项目</th><th>总 Token</th><th>Prompt</th><th>Completion</th><th>调用次数</th></tr></thead><tbody>';
        perProject.forEach(function (r) {
          /* new shape: {project_id, title, total_tokens, prompt, completion, calls};
           * keep prompt_tokens/completion_tokens fallbacks for older backends */
          html += '<tr><td>' + esc(r.title || r.project_title || r.project_id || '—') + '</td>' +
            '<td>' + fmtNum(r.total_tokens) + '</td>' +
            '<td>' + fmtNum(r.prompt != null ? r.prompt : r.prompt_tokens) + '</td>' +
            '<td>' + fmtNum(r.completion != null ? r.completion : r.completion_tokens) + '</td>' +
            '<td>' + fmtNum(r.calls != null ? r.calls : r.count) + '</td></tr>';
        });
        html += '</tbody></table>';
      }
      html += '</div></div>';

      if (recent.length) {
        html += '<div class="card"><div class="card-pad" style="padding-bottom:8px"><b>最近调用记录</b></div><div class="table-wrap">' +
          '<table class="data"><thead><tr><th>时间</th><th>阶段</th><th>模型</th><th>Token</th></tr></thead><tbody>';
        recent.slice(0, 20).forEach(function (r) {
          html += '<tr><td>' + fmtTime(r.created_at) + '</td>' +
            '<td>' + esc(r.stage || '—') + '</td>' +
            '<td>' + esc(r.model || '—') + '</td>' +
            '<td>' + fmtNum(r.total_tokens) + '</td></tr>';
        });
        html += '</tbody></table></div></div>';
      }
      html += '</div>';

      app.innerHTML = html;
    }).catch(function (e) {
      if (e.message === 'unauthorized') return;
      app.innerHTML = '<div class="empty"><div class="e-title">加载失败</div><div class="e-desc">' + esc(e.message) + '</div></div>';
    });
  }

  /* ============================== 8. admin ============================== */
  function renderAdmin() {
    if (!isAdmin()) {
      app.innerHTML = '<div class="empty"><div class="e-title">无权限</div><div class="e-desc">该页面仅管理员可见</div></div>';
      return;
    }
    app.innerHTML = loadingHTML('加载管理数据…');
    Promise.all([
      api('/api/admin/users'),
      api('/api/admin/stats')
    ]).then(function (results) {
      var users = Array.isArray(results[0]) ? results[0] : (results[0].users || []);
      var stats = results[1] || {};

      var html = '<div class="view">' +
        '<div class="page-head"><div><h1>系统管理</h1>' +
        '<div class="sub">用户与全局用量</div></div></div>' +
        '<div class="stat-grid">' +
          '<div class="card stat-card"><div class="s-label">用户数</div>' +
            '<div class="s-value">' + fmtNum(stats.users != null ? stats.users : stats.user_count) + '</div></div>' +
          '<div class="card stat-card"><div class="s-label">项目数</div>' +
            '<div class="s-value">' + fmtNum(stats.projects != null ? stats.projects : stats.project_count) + '</div></div>' +
          '<div class="card stat-card"><div class="s-label">今日 Token</div>' +
            '<div class="s-value">' + fmtNum(stats.tokens_today != null ? stats.tokens_today : stats.today_tokens) + '</div></div>' +
          '<div class="card stat-card"><div class="s-label">累计 Token</div>' +
            '<div class="s-value">' + fmtNum(stats.tokens_total != null ? stats.tokens_total : stats.total_tokens) + '</div></div>' +
        '</div>' +
        '<div class="card"><div class="card-pad" style="padding-bottom:8px"><b>用户管理</b></div>' +
        '<div class="table-wrap"><table class="data"><thead><tr>' +
          '<th>用户名</th><th>角色</th><th>已用 Token</th><th>配额（0 = 不限）</th><th>启用</th><th>操作</th>' +
        '</tr></thead><tbody id="admin-users"></tbody></table></div></div></div>';
      app.innerHTML = html;

      var tbody = document.getElementById('admin-users');
      users.forEach(function (u) {
        var tr = document.createElement('tr');
        var usedPct = u.token_quota > 0 ? Math.min(100, Math.round((u.token_used || 0) / u.token_quota * 100)) : 0;
        tr.innerHTML =
          '<td>' + esc(u.username) + (state.user && u.id === state.user.id ? ' <span style="color:var(--text-3)">(我)</span>' : '') + '</td>' +
          '<td><select data-role>' +
            '<option value="user"' + (u.role !== 'admin' ? ' selected' : '') + '>用户</option>' +
            '<option value="admin"' + (u.role === 'admin' ? ' selected' : '') + '>管理员</option>' +
          '</select></td>' +
          '<td>' + fmtNum(u.token_used) + (u.token_quota > 0 ? ' <span style="color:var(--text-3)">(' + usedPct + '%)</span>' : '') + '</td>' +
          '<td><input type="number" min="0" step="100000" value="' + (u.token_quota || 0) + '" data-quota></td>' +
          '<td><label class="switch"><input type="checkbox" data-enabled' + (u.disabled ? '' : ' checked') + '><span class="track"></span></label></td>' +
          '<td><button class="btn btn-outline btn-sm" data-save>保存</button></td>';
        tbody.appendChild(tr);

        tr.querySelector('[data-save]').addEventListener('click', function () {
          var body = {
            token_quota: Number(tr.querySelector('[data-quota]').value) || 0,
            disabled: tr.querySelector('[data-enabled]').checked ? 0 : 1,
            role: tr.querySelector('[data-role]').value
          };
          var btn = tr.querySelector('[data-save]');
          btn.disabled = true;
          api('/api/admin/users/' + u.id, { method: 'PATCH', body: body }).then(function () {
            toast('已保存用户设置', 'success');
            renderAdmin();
          }).catch(function (e) {
            if (e.message !== 'unauthorized') toast('保存失败：' + e.message, 'error');
            btn.disabled = false;
          });
        });
      });
    }).catch(function (e) {
      if (e.message === 'unauthorized') return;
      app.innerHTML = '<div class="empty"><div class="e-title">加载失败</div><div class="e-desc">' + esc(e.message) + '</div></div>';
    });
  }

  /* ============================== 9. admin settings ============================== */
  function sourceLabel(src) {
    return src === 'db' ? '界面' : src === 'env' ? '环境变量' : '未配置';
  }

  function keyPlaceholder(set, tail, src) {
    if (!set) return '未配置';
    return '已配置 ' + (tail || '') + '（来源：' + sourceLabel(src) + '）';
  }

  function renderSettings() {
    if (!isAdmin()) {
      app.innerHTML = '<div class="empty"><div class="e-title">无权限</div><div class="e-desc">该页面仅管理员可见</div></div>';
      return;
    }
    app.innerHTML = loadingHTML('加载设置…');
    api('/api/admin/settings').then(function (s) {
      drawSettings(s || {});
    }).catch(function (e) {
      if (e.message === 'unauthorized') return;
      app.innerHTML = '<div class="empty"><div class="e-title">加载失败</div><div class="e-desc">' + esc(e.message) + '</div></div>';
    });
  }

  function drawSettings(s) {
    app.innerHTML =
      '<div class="view">' +
        '<div class="page-head"><div><h1>系统设置</h1>' +
        '<div class="sub">模型与搜图服务配置，保存在界面上的值会覆盖环境变量</div></div></div>' +
        (s.mock_mode ?
          '<div class="warn-banner"><span class="eb-ico">' + ICONS.warn + '</span>' +
          '<div class="eb-main"><b>当前为演示模式（未配置模型 key）</b>' +
          '<div class="eb-msg">配置模型 API Key 后即可使用真实的 AI 生成能力</div></div>' +
          '<button class="btn btn-primary btn-sm" id="set-goto-llm">去配置 →</button></div>' : '') +

        '<div class="card card-pad" id="set-card-llm" style="margin-bottom:20px">' +
          '<div class="set-card-head"><h3 style="margin:0;font-size:15px">模型配置</h3>' +
          '<button class="btn btn-ghost btn-sm" id="set-llm-guide-toggle">' + ICONS.info + '如何获取？</button></div>' +
          '<div class="guide-panel hidden" id="set-llm-guide">' +
            '<div class="guide-item">' +
              '<div class="gi-head"><b>DeepSeek</b><span class="badge badge-green">推荐</span></div>' +
              '<div class="gi-body">申请地址 <a href="https://platform.deepseek.com" target="_blank" rel="noopener">platform.deepseek.com</a>（控制台 → API keys → 创建）' +
              '<br>base_url <code>https://api.deepseek.com/v1</code> · 模型 <code>deepseek-chat</code>' +
              '<br><span class="gi-note">12 页 PPT 约几毛钱，需先充值</span></div>' +
              '<button class="btn btn-outline btn-sm" data-fill-llm data-base="https://api.deepseek.com/v1" data-model="deepseek-chat">填入此配置</button>' +
            '</div>' +
            '<div class="guide-item">' +
              '<div class="gi-head"><b>智谱 GLM</b></div>' +
              '<div class="gi-body">申请地址 <a href="https://open.bigmodel.cn" target="_blank" rel="noopener">open.bigmodel.cn</a>（控制台 → API 密钥）' +
              '<br>base_url <code>https://open.bigmodel.cn/api/paas/v4</code> · 模型 <code>glm-5.2</code>' +
              '<br><span class="gi-note">新用户通常有免费额度</span></div>' +
              '<button class="btn btn-outline btn-sm" data-fill-llm data-base="https://open.bigmodel.cn/api/paas/v4" data-model="glm-5.2">填入此配置</button>' +
            '</div>' +
            '<div class="guide-item">' +
              '<div class="gi-head"><b>阿里百炼</b></div>' +
              '<div class="gi-body">申请地址 <a href="https://bailian.console.aliyun.com" target="_blank" rel="noopener">bailian.console.aliyun.com</a>（右上角头像 → API-KEY）' +
              '<br>base_url <code>https://dashscope.aliyuncs.com/compatible-mode/v1</code> · 模型 <code>qwen3.7-max</code> / <code>qwen-plus</code>' +
              '<br><span class="gi-note">按模型分别计费 / 给额度</span></div>' +
              '<button class="btn btn-outline btn-sm" data-fill-llm data-base="https://dashscope.aliyuncs.com/compatible-mode/v1" data-model="qwen-plus">填入此配置</button>' +
            '</div>' +
            '<div class="guide-item">' +
              '<div class="gi-head"><b>本地模型</b><span class="badge badge-gray">离线</span></div>' +
              '<div class="gi-body">Ollama 执行 <code>ollama run qwen3:8b</code> 后用 <code>http://127.0.0.1:11434/v1</code>；llama.cpp / vLLM 同理（OpenAI 兼容端口），API Key 随便填一个非空字符串即可' +
              '<br><span class="gi-note">建议 8B 以上模型，无需联网、不产生费用</span></div>' +
              '<button class="btn btn-outline btn-sm" data-fill-llm data-base="http://127.0.0.1:11434/v1" data-model="qwen3:8b">填入此配置</button>' +
            '</div>' +
          '</div>' +
          '<div class="field"><label>Base URL<span class="opt">当前来源：' + esc(sourceLabel(s.llm_base_url_source)) + '</span></label>' +
            '<input type="text" id="set-base-url" value="' + esc(s.llm_base_url || '') + '" placeholder="例如 http://localhost:11434/v1"></div>' +
          '<div class="field"><label>模型名称<span class="opt">当前来源：' + esc(sourceLabel(s.llm_model_source)) + '</span></label>' +
            '<input type="text" id="set-model" value="' + esc(s.llm_model || '') + '" placeholder="例如 qwen2.5:14b / gpt-4o-mini"></div>' +
          '<div class="field"><label>API Key<span class="opt">留空提交 = 不修改</span></label>' +
            '<input type="password" id="set-llm-key" autocomplete="new-password" placeholder="' + esc(keyPlaceholder(s.llm_api_key_set, s.llm_api_key_tail, s.llm_api_key_source)) + '"></div>' +
          '<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">' +
            '<button class="btn btn-primary" id="set-llm-save">保存模型配置</button>' +
            '<button class="btn btn-outline" id="set-llm-clear">清除 Key 覆盖</button>' +
            '<button class="btn btn-outline" id="set-llm-test">' + ICONS.zap + '测试连接</button>' +
          '</div>' +
          '<div id="set-llm-test-result" style="margin-top:12px"></div>' +
        '</div>' +

        '<div class="card card-pad">' +
          '<div class="set-card-head"><h3 style="margin:0;font-size:15px">搜图配置</h3>' +
          '<button class="btn btn-ghost btn-sm" id="set-img-guide-toggle">' + ICONS.info + '如何获取？</button></div>' +
          '<div class="guide-panel hidden" id="set-img-guide">' +
            '<div class="guide-item">' +
              '<div class="gi-head"><b>Pexels</b><span class="badge badge-green">首选</span></div>' +
              '<div class="gi-body">打开 <a href="https://www.pexels.com/api/" target="_blank" rel="noopener">pexels.com/api</a> →「Get Started」注册 → 邮箱验证后点「Your API Key」即可看到（随时可查，不会过期）' +
              '<br><span class="gi-note">免费 200 次/小时、2 万次/月；Pexels License 可免费商用、无需署名</span></div>' +
            '</div>' +
            '<div class="guide-item">' +
              '<div class="gi-head"><b>Pixabay</b><span class="badge badge-gray">备选</span></div>' +
              '<div class="gi-body">注册 Pixabay 账号 → 打开 <a href="https://pixabay.com/api/docs/" target="_blank" rel="noopener">API 文档页</a> → 页面中即显示你的 key</div>' +
            '</div>' +
            '<div class="guide-item" style="border-bottom:none">' +
              '<div class="gi-head"><b>都不配置（零成本）</b></div>' +
              '<div class="gi-body">自动使用 Wikimedia Commons / Openverse 免费图源，无需任何 key；系统按 pexels → pixabay → openverse → wikimedia 顺序自动降级</div>' +
            '</div>' +
          '</div>' +
          '<div style="color:var(--text-2);font-size:13px;margin-bottom:16px">留空则使用 Wikimedia / Openverse 免费图源</div>' +
          '<div class="field"><label>图源提供方<span class="opt">当前来源：' + esc(sourceLabel(s.image_provider_source)) + '</span></label>' +
            '<select id="set-image-provider">' +
              [['auto', '自动（优先 Pexels/Pixabay，无 key 时用免费源）【默认】'],
               ['pexels', '仅 Pexels（需配置 key）'],
               ['pixabay', '仅 Pixabay（需配置 key）'],
               ['wikimedia', '仅 Wikimedia Commons（免费，无需 key）'],
               ['openverse', '仅 Openverse（免费，无需 key）']].map(function (o) {
                return '<option value="' + o[0] + '"' +
                  ((s.image_provider || 'auto') === o[0] ? ' selected' : '') + '>' + esc(o[1]) + '</option>';
              }).join('') +
            '</select>' +
            '<div class="hint">自动模式按 pexels → pixabay → openverse → wikimedia 顺序降级；选择后立即保存生效</div></div>' +
          '<div class="field"><label>Pexels API Key<span class="opt">留空提交 = 不修改</span></label>' +
            '<input type="password" id="set-pexels-key" autocomplete="new-password" placeholder="' + esc(keyPlaceholder(s.pexels_api_key_set, s.pexels_api_key_tail, s.pexels_api_key_source)) + '"></div>' +
          '<div class="field"><label>Pixabay API Key<span class="opt">留空提交 = 不修改</span></label>' +
            '<input type="password" id="set-pixabay-key" autocomplete="new-password" placeholder="' + esc(keyPlaceholder(s.pixabay_api_key_set, s.pixabay_api_key_tail, s.pixabay_api_key_source)) + '"></div>' +
          '<div style="display:flex;gap:10px;flex-wrap:wrap">' +
            '<button class="btn btn-primary" id="set-img-save">保存搜图配置</button>' +
            '<button class="btn btn-outline" id="set-pexels-clear">清除 Pexels 覆盖</button>' +
            '<button class="btn btn-outline" id="set-pixabay-clear">清除 Pixabay 覆盖</button>' +
          '</div>' +
        '</div>' +
      '</div>';

    /* API guide panels */
    function bindGuideToggle(btnId, panelId) {
      var btn = document.getElementById(btnId);
      if (!btn) return;
      btn.addEventListener('click', function () {
        document.getElementById(panelId).classList.toggle('hidden');
      });
    }
    bindGuideToggle('set-llm-guide-toggle', 'set-llm-guide');
    bindGuideToggle('set-img-guide-toggle', 'set-img-guide');

    /* fill a provider preset into the form (key still pasted by the user) */
    app.querySelectorAll('[data-fill-llm]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        document.getElementById('set-base-url').value = btn.getAttribute('data-base') || '';
        document.getElementById('set-model').value = btn.getAttribute('data-model') || '';
        document.getElementById('set-llm-guide').classList.add('hidden');
        document.getElementById('set-llm-key').focus();
        toast('已填入 base_url 和模型，请粘贴 API Key 后保存', 'success');
      });
    });

    /* mock-mode banner shortcut: scroll to the model card and open its guide */
    var gotoBtn = document.getElementById('set-goto-llm');
    if (gotoBtn) {
      gotoBtn.addEventListener('click', function () {
        document.getElementById('set-llm-guide').classList.remove('hidden');
        var card = document.getElementById('set-card-llm');
        if (card.scrollIntoView) card.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    }

    function saveSettings(body, btn, okText) {
      btn.disabled = true;
      var orig = btn.innerHTML;
      btn.innerHTML = '<span class="spinner"></span>保存中…';
      api('/api/admin/settings', { method: 'PUT', body: body }).then(function () {
        toast(okText || '设置已保存', 'success');
        renderSettings();
      }).catch(function (e) {
        if (e.message !== 'unauthorized') toast('保存失败：' + e.message, 'error');
        btn.disabled = false;
        btn.innerHTML = orig;
      });
    }

    document.getElementById('set-llm-save').addEventListener('click', function () {
      var body = {
        llm_base_url: document.getElementById('set-base-url').value.trim(),
        llm_model: document.getElementById('set-model').value.trim()
      };
      var key = document.getElementById('set-llm-key').value;
      if (key) body.llm_api_key = key;
      saveSettings(body, this, '模型配置已保存');
    });
    document.getElementById('set-llm-clear').addEventListener('click', function () {
      saveSettings({ llm_api_key: '' }, this, '已清除 Key 覆盖，回退到环境变量');
    });
    /* image provider select: saved immediately on change */
    var provSel = document.getElementById('set-image-provider');
    provSel.addEventListener('change', function () {
      var v = provSel.value;
      provSel.disabled = true;
      api('/api/admin/settings', { method: 'PUT', body: { image_provider: v === 'auto' ? '' : v } }).then(function () {
        toast('图源已更新', 'success');
        if (v === 'pexels' && !s.pexels_api_key_set) toast('尚未配置 Pexels key，搜图会失败', 'error');
        if (v === 'pixabay' && !s.pixabay_api_key_set) toast('尚未配置 Pixabay key，搜图会失败', 'error');
        renderSettings();
      }).catch(function (e) {
        if (e.message !== 'unauthorized') toast('保存失败：' + e.message, 'error');
        provSel.disabled = false;
      });
    });

    document.getElementById('set-img-save').addEventListener('click', function () {
      var pexels = document.getElementById('set-pexels-key').value;
      var pixabay = document.getElementById('set-pixabay-key').value;
      if (!pexels && !pixabay) { toast('两个 Key 都为空，未做任何修改（如需清除请用「清除覆盖」按钮）', 'info'); return; }
      var body = {};
      if (pexels) body.pexels_api_key = pexels;
      if (pixabay) body.pixabay_api_key = pixabay;
      saveSettings(body, this, '搜图配置已保存');
    });
    document.getElementById('set-pexels-clear').addEventListener('click', function () {
      saveSettings({ pexels_api_key: '' }, this, '已清除 Pexels 覆盖，回退到环境变量');
    });
    document.getElementById('set-pixabay-clear').addEventListener('click', function () {
      saveSettings({ pixabay_api_key: '' }, this, '已清除 Pixabay 覆盖，回退到环境变量');
    });

    var testBtn = document.getElementById('set-llm-test');
    testBtn.addEventListener('click', function () {
      var result = document.getElementById('set-llm-test-result');
      testBtn.disabled = true;
      testBtn.innerHTML = '<span class="spinner"></span>测试中…';
      result.innerHTML = '';
      api('/api/admin/settings/test-llm', { method: 'POST' }).then(function (r) {
        r = r || {};
        if (r.ok) {
          result.innerHTML = '<div class="test-result ok">' + ICONS.checkCircle +
            '<span>连接成功' + (r.model ? ' · 模型 ' + esc(r.model) : '') +
            (r.latency_ms != null ? ' · 延迟 ' + esc(r.latency_ms) + ' ms' : '') + '</span></div>';
        } else {
          result.innerHTML = '<div class="test-result fail">' + ICONS.xCircle +
            '<span>连接失败：' + esc(r.error || '未知错误') + '</span></div>';
        }
      }).catch(function (e) {
        if (e.message !== 'unauthorized') {
          result.innerHTML = '<div class="test-result fail">' + ICONS.xCircle + '<span>请求失败：' + esc(e.message) + '</span></div>';
        }
      }).then(function () {
        testBtn.disabled = false;
        testBtn.innerHTML = ICONS.zap + '测试连接';
      });
    });
  }

  /* ============================== boot ============================== */
  syncTopbar();
  if (!location.hash) location.hash = state.token ? '#/projects' : '#/login';
  route();
})();
