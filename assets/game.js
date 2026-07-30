/* game.js — 학습 진도 위에 얹는 게임 레이어
 *
 * 왜 있는가
 *   공부를 게임처럼 만들어 앉아 있게 하는 것이 목적이다.
 *   책 내용에는 일절 관여하지 않는다. 진도(localStorage) 를 읽어
 *   레벨·세계 성장·도감·이펙트로 바꿔 보여줄 뿐이다.
 *
 * app.js 와의 접점은 셋뿐이다.
 *   PyGame.sync()        진도가 바뀔 때마다 (레벨/세계/EXP 바 갱신)
 *   PyGame.celebrate(id) 절을 완료했을 때 (이펙트·레벨업·도감 획득)
 *   PyGame.homeHtml()    표지에 끼울 플레이어 카드 + 도감
 * 이 파일이 없어도 app.js 는 그대로 돌아간다.
 */
(function () {
  'use strict';

  var BOOK = window.BOOK || { toc: [], docs: {} };
  var $ = function (s, r) { return (r || document).querySelector(s); };

  var LS = {
    get: function (k, d) {
      try { var v = localStorage.getItem('pybook:' + k); return v === null ? d : JSON.parse(v); }
      catch (e) { return d; }
    },
    set: function (k, v) {
      try { localStorage.setItem('pybook:' + k, JSON.stringify(v)); } catch (e) { /* 사생활 모드 */ }
    }
  };

  /* ---------------- 진도 읽기 ---------------- */

  var PARTS = (BOOK.toc || []).filter(function (p) { return (p.chapters || []).length; });
  var TOTAL = PARTS.reduce(function (n, p) { return n + p.chapters.length; }, 0);

  function doneMap() { return LS.get('done', {}); }
  function doneCount() {
    var d = doneMap(), n = 0;
    PARTS.forEach(function (p) {
      p.chapters.forEach(function (c) { if (d[c.id]) n++; });
    });
    return n;
  }
  function partDone(part) {
    var d = doneMap();
    return part.chapters.every(function (c) { return d[c.id]; });
  }

  /* ---------------- 레벨 ----------------
   * 앞쪽을 촘촘하게 두는 곡선이다. 처음 몇 절에서 레벨이 빨리 올라야
   * 계속하게 된다. 뒤로 갈수록 간격이 벌어진다. */
  var CURVE = [0, 1, 3, 6, 10, 15, 21, 28, 36, 45, 55, 66, 78, 91, 105, 120, 136, 148];
  var TITLES = [
    '빈 화면 앞의 사람', '첫 줄을 쓴 자', '들여쓰기 견습', '리스트 사냥꾼',
    '딕셔너리 도굴꾼', '예외 조련사', '데코레이터 술사', '타입 계약자',
    '동시성 항해사', '프로파일러', '복잡도 심판관', '그래프 개척자',
    '점화식 연금술사', '입출력 밀수꾼', '로봇 조종사', '백지 정복자',
    '설계 장인', '완전 정복'
  ];

  function levelOf(n) {
    var lv = 1;
    for (var i = 0; i < CURVE.length; i++) if (n >= CURVE[i]) lv = i + 1;
    return Math.min(lv, CURVE.length);
  }
  function levelSpan(lv) {
    var lo = CURVE[lv - 1] || 0;
    var hi = lv < CURVE.length ? CURVE[lv] : CURVE[CURVE.length - 1];
    return { lo: lo, hi: hi };
  }

  /* ---------------- 세계 성장 단계 ----------------
   * 진도가 오르면 사이드바 지면과 표지 풍경에 하나씩 생물이 늘어난다.
   * 황무지 -> 풀 -> 새싹 -> 숲 -> 동굴 생태 -> 만개. */
  function stageOf(n) {
    var r = TOTAL ? n / TOTAL : 0;
    if (n === 0) return 0;
    if (r < 0.15) return 1;
    if (r < 0.35) return 2;
    if (r < 0.60) return 3;
    if (r < 0.85) return 4;
    return 5;
  }

  /* ---------------- 도감 ----------------
   * 파트를 전부 읽으면 동료 하나를 얻는다.
   * 모양 5종에 색상 회전을 섞어 13마리를 만든다. 같은 뼈대에 다른 색을
   * 입히는 것은 도트 게임이 오래 써 온 방법이다. */
  var DEX = [
    { shape: 'slime', hue: 0,   name: '모시' },
    { shape: 'golem', hue: 0,   name: '바우' },
    { shape: 'ghost', hue: 0,   name: '히노' },
    { shape: 'bat',   hue: 0,   name: '쿠로' },
    { shape: 'bird',  hue: 0,   name: '삐용' },
    { shape: 'slime', hue: 305, name: '베리' },
    { shape: 'golem', hue: 130, name: '이끼' },
    { shape: 'ghost', hue: 195, name: '푸름' },
    { shape: 'bat',   hue: 110, name: '리프' },
    { shape: 'bird',  hue: 165, name: '민트' },
    { shape: 'slime', hue: 190, name: '아쿠아' },
    { shape: 'golem', hue: 265, name: '보라' },
    { shape: 'ghost', hue: 45,  name: '노을' }
  ];
  function dexFor(i) { return DEX[i % DEX.length]; }

  /* 회색·흰색 도트는 hue-rotate 만으로 색이 안 바뀐다.
     변종에는 sepia 로 한 번 물들인 뒤 회전시킨다. 기본색(hue 0)은 건드리지 않는다. */
  function monStyle(c) {
    return c.hue
      ? 'style="--hue:' + c.hue + 'deg;--sep:.7;--sat:2.4"'
      : '';
  }

  function ownedParts() {
    var out = [];
    PARTS.forEach(function (p, i) { if (partDone(p)) out.push(i); });
    return out;
  }

  /* ---------------- 연속 학습 ---------------- */
  function today() {
    var d = new Date();
    return d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate();
  }
  function yesterday() {
    var d = new Date(Date.now() - 864e5);
    return d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate();
  }
  function touchStreak() {
    var s = LS.get('streak', { last: '', n: 0 });
    var t = today();
    if (s.last === t) return s;
    s.n = s.last === yesterday() ? s.n + 1 : 1;
    s.last = t;
    LS.set('streak', s);
    return s;
  }
  function streak() { return LS.get('streak', { last: '', n: 0 }); }

  /* ---------------- 이펙트 ---------------- */

  function reduced() {
    return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  function burst(x, y, count) {
    if (reduced()) return;
    var layer = fxLayer();
    for (var i = 0; i < count; i++) {
      var s = document.createElement('i');
      s.className = 'fx-star';
      var ang = (Math.PI * 2 * i) / count + Math.random() * 0.5;
      var dist = 40 + Math.random() * 55;
      s.style.left = x + 'px';
      s.style.top = y + 'px';
      s.style.setProperty('--dx', Math.cos(ang) * dist + 'px');
      s.style.setProperty('--dy', (Math.sin(ang) * dist - 20) + 'px');
      s.style.animationDelay = (Math.random() * 90) + 'ms';
      layer.appendChild(s);
      // 애니메이션이 끝나면 스스로 사라진다. 노드가 쌓이면 안 된다.
      s.addEventListener('animationend', function () { this.remove(); });
    }
  }

  function floatText(x, y, text, cls) {
    var layer = fxLayer();
    var el = document.createElement('div');
    el.className = 'fx-float ' + (cls || '');
    el.textContent = text;
    el.style.left = x + 'px';
    el.style.top = y + 'px';
    layer.appendChild(el);
    el.addEventListener('animationend', function () { this.remove(); });
    if (reduced()) setTimeout(function () { el.remove(); }, 1200);
  }

  function fxLayer() {
    var l = $('#fx-layer');
    if (!l) {
      l = document.createElement('div');
      l.id = 'fx-layer';
      l.setAttribute('aria-hidden', 'true');
      document.body.appendChild(l);
    }
    return l;
  }

  var toastQueue = [];
  var toastBusy = false;

  function toast(html, cls) {
    toastQueue.push({ html: html, cls: cls });
    pumpToast();
  }
  function pumpToast() {
    if (toastBusy || !toastQueue.length) return;
    toastBusy = true;
    var t = toastQueue.shift();
    var el = document.createElement('div');
    el.className = 'fx-toast ' + (t.cls || '');
    el.innerHTML = t.html;
    fxLayer().appendChild(el);
    setTimeout(function () {
      el.classList.add('out');
      setTimeout(function () { el.remove(); toastBusy = false; pumpToast(); }, 320);
    }, 2600);
  }

  /* ---------------- 화면 반영 ---------------- */

  function sync() {
    var n = doneCount();
    var lv = levelOf(n);
    var sp = levelSpan(lv);
    var into = n - sp.lo;
    var need = Math.max(1, sp.hi - sp.lo);
    var pct = lv >= CURVE.length ? 100 : Math.round(into / need * 100);

    var badge = $('#lv-badge');
    if (badge) badge.textContent = 'LV ' + lv;
    var bar = $('#lv-bar > i');
    if (bar) bar.style.width = pct + '%';
    var ttl = $('#lv-title');
    if (ttl) ttl.textContent = TITLES[lv - 1] || '';

    var st = String(stageOf(n));
    ['#pixel-field', '.home-scene'].forEach(function (sel) {
      var el = $(sel);
      if (el) el.dataset.stage = st;
    });
    return { n: n, lv: lv };
  }

  /* 절 완료 축하. 버튼 위치에서 별이 튄다. */
  function celebrate(id) {
    var before = LS.get('_lv', 1);
    var st = sync();
    var s = touchStreak();

    var btn = $('#btn-done');
    var x = window.innerWidth / 2, y = window.innerHeight * 0.6;
    if (btn) {
      var r = btn.getBoundingClientRect();
      x = r.left + r.width / 2;
      y = r.top + r.height / 2;
    }
    burst(x, y, 10);
    floatText(x, y - 18, '+1 EXP');

    if (st.lv > before) {
      LS.set('_lv', st.lv);
      burst(window.innerWidth / 2, window.innerHeight * 0.32, 18);
      toast(
        '<span class="ft-kicker">LEVEL UP</span>' +
        '<strong class="ft-title">LV ' + st.lv + ' · ' + (TITLES[st.lv - 1] || '') + '</strong>',
        'lv'
      );
    } else {
      LS.set('_lv', st.lv);
    }

    // 파트를 막 끝냈다면 동료를 얻는다.
    var owned = LS.get('dex', []);
    PARTS.forEach(function (p, i) {
      if (partDone(p) && owned.indexOf(i) === -1) {
        owned.push(i);
        var c = dexFor(i);
        toast(
          '<i class="fx-mon spr-' + c.shape + '" ' + monStyle(c) + '></i>' +
          '<span class="ft-kicker">동료 합류</span>' +
          '<strong class="ft-title">' + c.name + '</strong>' +
          '<span class="ft-sub">' + esc(p.num) + ' ' + esc(p.title) + ' 완주</span>',
          'dex'
        );
      }
    });
    LS.set('dex', owned);

    if (s.n > 1 && s.n % 3 === 0) {
      toast('<span class="ft-kicker">STREAK</span><strong class="ft-title">' + s.n + '일 연속</strong>', 'streak');
    }
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  /* ---------------- 표지에 끼울 조각 ---------------- */

  function homeHtml() {
    var n = doneCount();
    var lv = levelOf(n);
    var sp = levelSpan(lv);
    var into = n - sp.lo;
    var need = Math.max(1, sp.hi - sp.lo);
    var pct = lv >= CURVE.length ? 100 : Math.round(into / need * 100);
    var s = streak();
    var owned = ownedParts();

    var cells = PARTS.map(function (p, i) {
      var c = dexFor(i);
      var got = owned.indexOf(i) !== -1;
      var d = doneMap();
      var doneN = p.chapters.filter(function (ch) { return d[ch.id]; }).length;
      return '<div class="dex-cell' + (got ? ' got' : '') + '" title="' +
        esc(p.num + ' ' + p.title) + '">' +
        '<i class="dex-mon spr-' + c.shape + '" ' + monStyle(c) + '></i>' +
        '<span class="dex-name">' + (got ? esc(c.name) : '???') + '</span>' +
        '<span class="dex-sub">' + doneN + '/' + p.chapters.length + '</span>' +
        '</div>';
    }).join('');

    return '<div class="player-card">' +
      '<div class="pc-lv"><span id="lv-badge">LV ' + lv + '</span></div>' +
      '<div class="pc-mid">' +
      '<div class="pc-name" id="lv-title">' + esc(TITLES[lv - 1] || '') + '</div>' +
      '<div id="lv-bar" class="lv-bar"><i style="width:' + pct + '%"></i></div>' +
      '<div class="pc-exp">' + (lv >= CURVE.length ? '최고 레벨' : into + ' / ' + need + ' → LV ' + (lv + 1)) + '</div>' +
      '</div>' +
      '<div class="pc-streak"><span class="st-n">' + (s.n || 0) + '</span><span class="st-l">일 연속</span></div>' +
      '</div>' +
      '<div class="dex-wrap">' +
      '<div class="dex-head">동료 도감 <span>' + owned.length + ' / ' + PARTS.length + '</span></div>' +
      '<div class="dex-grid">' + cells + '</div>' +
      '</div>';
  }

  window.PyGame = {
    sync: sync,
    celebrate: celebrate,
    homeHtml: homeHtml,
    stageOf: stageOf,
    levelOf: levelOf
  };

  // 첫 진입 시 레벨 기준선을 맞춰 둔다. 안 그러면 이미 읽은 사람에게
  // 다음 완료 한 번에 레벨업 배너가 몰아친다.
  if (LS.get('_lv', null) === null) LS.set('_lv', levelOf(doneCount()));
})();
