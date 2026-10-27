// 회계기준서 열람 (관리자 전용) — cpawork webapp/standards 를 정적 사이트용으로 옮긴 것.
// 원문 데이터는 Firebase Firestore(std_docs·std_meta)에 있고, 관리자 로그인 계정만 읽을 수 있다.
// 북마크·형광펜은 std_marks 에 저장된다. 화면은 해시 라우팅(#/, #/search, #/v/..., #/marks).

const FRAMEWORKS = { kifrs: 'K-IFRS', kgaap: '일반기업회계기준' };
const FW_ORDER = ['kgaap', 'kifrs'];               // 원본 검색 정렬(체계 → 순번 → 문단 순서)과 동일
const AUTH_PARTS = ['본문', '실무지침'];
const COLORS = ['yellow', 'green', 'blue', 'pink'];

const isAuthoritative = (part) => AUTH_PARTS.includes(part) || part.startsWith('부록');
const displayName = (fw, code, title) =>
  /^\d+$/.test(code) ? (fw === 'kifrs' ? `제${code}호 ${title}` : `제${code}장 ${title}`) : title;
const kindLabel = (fw, code) => {
  if (fw === 'kifrs' && /^\d+$/.test(code)) return code.startsWith('2') ? '기업회계기준해석서' : '기업회계기준서';
  if (fw === 'kgaap' && /^\d+$/.test(code)) return '';
  return '기타';
};
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const enc = encodeURIComponent;

// ── 데이터 계층 ───────────────────────────────────────────────────────
// store: { getMeta(), getGz(fw, code) → Uint8Array, putBundle(bundle, onProgress),
//          marks: { load(), add(m), update(id, patch), remove(id) } }

async function gunzipJson(bytes) {
  const ds = new DecompressionStream('gzip');
  const text = await new Response(new Blob([bytes]).stream().pipeThrough(ds)).text();
  return JSON.parse(text);
}

function unitPlain(u) {
  return u.blocks.map((b) => (b.t === 'table' ? b.rows.map((r) => r.join(' | ')).join('\n') : b.text)).join('\n');
}

// IndexedDB 캐시: 같은 sha 면 다시 내려받지 않는다 (실패해도 동작에는 지장 없음)
const cache = {
  db: null,
  async open() {
    if (this.db !== null) return this.db;
    this.db = await new Promise((res) => {
      try {
        const r = indexedDB.open('ccrnd-standards', 1);
        r.onupgradeneeded = () => r.result.createObjectStore('docs');
        r.onsuccess = () => res(r.result);
        r.onerror = () => res(false);
      } catch (_) { res(false); }
    });
    return this.db;
  },
  async get(key) {
    const db = await this.open(); if (!db) return null;
    return new Promise((res) => { try { const q = db.transaction('docs').objectStore('docs').get(key); q.onsuccess = () => res(q.result || null); q.onerror = () => res(null); } catch (_) { res(null); } });
  },
  async put(key, val) {
    const db = await this.open(); if (!db) return;
    try { db.transaction('docs', 'readwrite').objectStore('docs').put(val, key); } catch (_) {}
  },
};

function createLibrary(store) {
  const docs = new Map();   // "fw/code" → { meta, units:[{kind,no,anchor,part,section,blocks,auth,plain}] }
  let meta = null;
  return {
    async meta() {
      if (!meta) meta = await store.getMeta();
      return meta;
    },
    resetMeta() { meta = null; docs.clear(); },
    find(fw, code) { return (meta && meta.items || []).find((i) => i.framework === fw && i.code === code) || null; },
    async doc(fw, code) {
      const key = fw + '/' + code;
      if (docs.has(key)) return docs.get(key);
      const m = this.find(fw, code);
      if (!m) return null;
      let raw = await cache.get(key);
      if (!raw || raw.sha !== m.sha) {
        const bytes = await store.getGz(fw, code);
        if (!bytes) return null;
        raw = { sha: m.sha, doc: await gunzipJson(bytes) };
        cache.put(key, raw);
      }
      const units = raw.doc.units.map((u, seq) => ({
        ...u, seq, auth: isAuthoritative(u.part),
        plain: (u.no ? u.no + ' ' : '') + unitPlain(u),
      }));
      const d = { meta: m, units };
      docs.set(key, d);
      return d;
    },
    async all(onProgress) {
      const items = (await this.meta()).items;
      let n = 0;
      const out = [];
      for (const it of items) {
        out.push(await this.doc(it.framework, it.code));
        if (onProgress) onProgress(++n, items.length);
      }
      return out.filter(Boolean);
    },
  };
}

// ── 검색·바로가기 (cpawork standards.py 와 같은 규칙) ─────────────────────
const JUMP_KIFRS = /^(?:k-?ifrs\s*)?(?:제\s*)?(\d{4})\s*호?(?:\s*(?:문단\s*)?([A-Za-z가-힣]*\d[\w가-힣.]*))?$/i;
const JUMP_KGAAP = /^(?:일반\S*\s*)?(?:제\s*)?(\d{1,2})\s*장(?:\s*(?:문단\s*)?(\S+))?$/;
const JUMP_KGAAP_PARA = /^(?:(실|결)\s*)?(\d{1,2})\.(\d+)$/;

function resolveJump(lib, q) {
  q = q.trim();
  let m = q.match(JUMP_KIFRS);
  if (m && lib.find('kifrs', m[1])) return viewHash('kifrs', m[1], (m[2] || '').toUpperCase());
  m = q.match(JUMP_KGAAP);
  if (m && lib.find('kgaap', m[1])) return viewHash('kgaap', m[1], m[2] || '');
  m = q.match(JUMP_KGAAP_PARA);
  if (m && lib.find('kgaap', m[2])) return viewHash('kgaap', m[2], `${m[1] || ''}${m[2]}.${m[3]}`);
  return null;
}

function viewHash(fw, code, anchor, all) {
  const qs = [];
  if (all) qs.push('scope=all');
  if (anchor) qs.push('p=' + enc(anchor));
  return `#/v/${fw}/${enc(code)}` + (qs.length ? '?' + qs.join('&') : '');
}

function snippet(plain, terms, width = 160) {
  const low = plain.toLowerCase();
  const hits = terms.map((t) => low.indexOf(t.toLowerCase())).filter((i) => i >= 0);
  const pos = hits.length ? Math.min(...hits) : 0;
  const start = Math.max(0, pos - Math.floor(width / 3));
  let out = esc(plain.slice(start, start + width).replace(/\n/g, ' '));
  for (const t of [...new Set(terms)].sort((a, b) => b.length - a.length)) {
    const re = new RegExp(esc(t).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
    out = out.replace(re, (s) => `<mark>${s}</mark>`);
  }
  return (start > 0 ? '…' : '') + out + (start + width < plain.length ? '…' : '');
}

// ── 앱 ───────────────────────────────────────────────────────────────
export function startStandardsApp(root, store, opts = {}) {
  const lib = createLibrary(store);
  let marks = [];             // [{id,type:'bm'|'hl',fw,code,anchor,start,end,quote,color,note,created}]
  let current = null;         // 현재 본문 보기 상태 {fw, code, scope}

  const toastEl = document.createElement('div');
  toastEl.className = 'std-toast'; toastEl.hidden = true;
  document.body.appendChild(toastEl);
  function toast(msg) {
    toastEl.textContent = msg; toastEl.hidden = false;
    clearTimeout(toast.t); toast.t = setTimeout(() => { toastEl.hidden = true; }, 1800);
  }

  function parseHash() {
    const h = location.hash.replace(/^#/, '') || '/';
    const [path, qs] = h.split('?');
    const params = new URLSearchParams(qs || '');
    const seg = path.split('/').filter(Boolean).map(decodeURIComponent);
    return { seg, params };
  }

  const bmCount = () => marks.filter((m) => m.type === 'bm').length;
  const hlCount = () => marks.filter((m) => m.type === 'hl').length;

  function searchForm(q = '', fw = '', auth = '', code = '') {
    return `<form class="std-search" data-search>
      <input type="search" name="q" value="${esc(q)}" placeholder="검색어 또는 바로가기 (예: 리스부채 재평가 · 1116 22 · 13장 · 실13.2)" ${q ? '' : 'autofocus'}>
      <select name="fw"><option value="">전체</option>${Object.entries(FRAMEWORKS).map(([k, v]) => `<option value="${k}" ${fw === k ? 'selected' : ''}>${v}</option>`).join('')}</select>
      <label class="std-check"><input type="checkbox" name="auth" value="1" ${auth === '1' ? 'checked' : ''}> 기준서 본문만</label>
      ${code ? `<input type="hidden" name="code" value="${esc(code)}">` : ''}
      <button class="std-btn">검색</button>
    </form>`;
  }

  root.addEventListener('submit', (e) => {
    const f = e.target.closest('form[data-search]');
    if (!f) return;
    e.preventDefault();
    const fd = new FormData(f);
    const q = String(fd.get('q') || '').trim();
    if (!q) return;
    const code = String(fd.get('code') || '');
    if (!code) {
      const jump = resolveJump(lib, q);
      if (jump) { location.hash = jump; return; }
    }
    const qs = new URLSearchParams({ q });
    if (fd.get('fw')) qs.set('fw', fd.get('fw'));
    if (fd.get('auth')) qs.set('auth', '1');
    if (code) qs.set('code', code);
    location.hash = '#/search?' + qs.toString();
  });

  // ── 목록 ──
  async function renderIndex() {
    const meta = await lib.meta();
    const items = meta.items || [];
    const groups = {};
    for (const fw of Object.keys(FRAMEWORKS)) groups[fw] = items.filter((i) => i.framework === fw).sort((a, b) => a.sort - b.sort || String(a.code).localeCompare(String(b.code)));
    root.innerHTML = `
      <div class="std-toolbar"><h1>회계기준서</h1><div class="std-spacer"></div>
        <a class="std-btn ghost" href="#/marks">내 북마크 ${bmCount()} · 형광펜 ${hlCount()}</a></div>
      <div class="std-card">${searchForm()}</div>
      ${items.length ? '' : `<div class="std-card std-warn">아직 기준서 데이터가 없습니다. 아래 <b>데이터 올리기</b>에서 번들 파일(standards-bundle.json)을 올려 주세요.</div>`}
      <div class="std-grid2">${Object.entries(FRAMEWORKS).map(([fw, label]) => `
        <div class="std-card"><h2>${label} <span class="std-muted">(${groups[fw].length})</span></h2>
          <table class="std-list">${groups[fw].map((s) => `<tr>
            <td class="std-code">${/^\d+$/.test(s.code) ? esc(s.code) : '—'}</td>
            <td><a href="${viewHash(s.framework, s.code)}">${esc(s.title)}</a><div class="std-muted std-ver">${esc(s.version || '개정 표기 없음')}</div></td>
          </tr>`).join('')}</table></div>`).join('')}
      </div>
      <details class="std-card std-admin-upload"${items.length ? '' : ' open'}>
        <summary>데이터 올리기 · 현황 <span class="std-muted">${meta.updated ? '— 기준일 ' + esc(meta.updated) : ''} · ${items.length}건</span></summary>
        <p class="std-muted">cpawork의 <code>webapp/app/standards_data</code>를 <code>scripts/build_standards_bundle.py</code>로 묶은 번들 파일을 고르세요. 같은 기준서는 새 내용으로 교체됩니다.</p>
        <input type="file" accept=".json,application/json" data-bundle>
        <div class="std-progress" data-progress hidden><div></div></div>
        <p class="std-muted" data-upmsg></p>
      </details>
      <p class="std-muted std-foot">원문 출처: 한국회계기준원(KASB). 관리자 업무용 열람 페이지로, 로그인한 관리자에게만 표시됩니다.</p>`;
    root.querySelector('[data-bundle]').addEventListener('change', onBundle);
  }

  async function onBundle(e) {
    const file = e.target.files[0];
    if (!file) return;
    const msg = root.querySelector('[data-upmsg]');
    const bar = root.querySelector('[data-progress]');
    try {
      const bundle = JSON.parse(await file.text());
      if (bundle.format !== 'ccrnd-standards-bundle') throw new Error('번들 형식이 아닙니다');
      bar.hidden = false;
      await store.putBundle(bundle, (n, total) => {
        bar.firstElementChild.style.width = Math.round((n / total) * 100) + '%';
        msg.textContent = `올리는 중… ${n}/${total}`;
      });
      lib.resetMeta();
      msg.textContent = `${bundle.items.length}건 올리기 완료`;
      toast('기준서 데이터를 올렸습니다');
      setTimeout(route, 600);
    } catch (err) {
      msg.textContent = '올리기 실패: ' + (err && err.message ? err.message : err);
    }
  }

  // ── 검색 ──
  async function renderSearch(params) {
    const q = (params.get('q') || '').trim();
    const fw = FRAMEWORKS[params.get('fw')] ? params.get('fw') : '';
    const auth = params.get('auth') === '1' ? '1' : '';
    const code = params.get('code') || '';
    root.innerHTML = `<div class="std-toolbar"><h1><a href="#/" class="std-crumb">회계기준서</a> › 검색</h1></div>
      <div class="std-card">${searchForm(q, fw, auth, code)}</div>
      <div class="std-card" data-results><p class="std-muted" data-loading>기준서를 불러오는 중…</p></div>`;
    if (!q) { root.querySelector('[data-results]').remove(); return; }
    const box = root.querySelector('[data-results]');
    const terms = q.split(/\s+/).filter(Boolean).slice(0, 6).map((t) => t.toLowerCase());
    await lib.meta();
    let docs;
    if (code && fw) docs = [await lib.doc(fw, code)].filter(Boolean);
    else docs = await lib.all((n, t) => { const l = box.querySelector('[data-loading]'); if (l) l.textContent = `기준서를 불러오는 중… ${n}/${t}`; });
    docs = docs.filter((d) => (!fw || d.meta.framework === fw) && (!code || d.meta.code === code));
    docs.sort((a, b) => FW_ORDER.indexOf(a.meta.framework) - FW_ORDER.indexOf(b.meta.framework) || a.meta.sort - b.meta.sort);
    const rows = [];
    outer: for (const d of docs) {
      for (const u of d.units) {
        if (auth && !u.auth) continue;
        const low = u.plain.toLowerCase();
        if (terms.every((t) => low.includes(t))) { rows.push([u, d]); if (rows.length >= 200) break outer; }
      }
    }
    let last = null;
    box.innerHTML = `<h2>“${esc(q)}” 검색 결과 ${rows.length}건${rows.length >= 200 ? ' <span class="std-muted">(앞 200건만 표시 — 검색어를 더 구체적으로 입력하세요)</span>' : ''}</h2>
      ${rows.length ? '' : '<p class="std-muted">결과가 없습니다. 띄어쓰기를 바꾸거나 기준서 용어로 다시 검색해 보세요.</p>'}
      ${rows.map(([u, d]) => {
        const s = d.meta;
        let head = '';
        if (last !== s) { head = `<h3 class="std-result-std">${FRAMEWORKS[s.framework]} ${esc(displayName(s.framework, s.code, s.title))}</h3>`; last = s; }
        const body = u.no && u.plain.startsWith(u.no + ' ') ? u.plain.slice(u.no.length + 1) : u.plain;
        return head + `<a class="std-result" href="${viewHash(s.framework, s.code, u.anchor, !u.auth)}">
          <span class="std-result-no">${esc(u.no || (u.kind === 'h' ? '제목' : '—'))}</span>
          ${u.auth ? '' : `<span class="std-tag">${esc(u.part)}</span>`}
          <span class="std-result-text">${snippet(body, terms)}</span></a>`;
      }).join('')}`;
  }

  // ── 본문 ──
  async function renderView(fw, code, params) {
    const scope = params.get('scope') === 'all' ? 'all' : '';
    const target = params.get('p') || '';
    if (current && current.fw === fw && current.code === code && current.scope === scope) {
      flashTarget(target);
      return;
    }
    root.innerHTML = '<div class="std-card"><p class="std-muted">기준서를 불러오는 중…</p></div>';
    await lib.meta();
    const d = await lib.doc(fw, code);
    if (!d) { root.innerHTML = '<div class="std-card">기준서를 찾을 수 없습니다. <a href="#/">목록으로</a></div>'; current = null; return; }
    const s = d.meta;
    const showAll = scope === 'all';
    const hasRef = d.units.some((u) => !u.auth);
    const units = showAll ? d.units : d.units.filter((u) => u.auth);
    const others = (lib.meta && (await lib.meta()).items || []).filter((i) => i.framework === fw).sort((a, b) => a.sort - b.sort);
    const bms = new Set(marks.filter((m) => m.type === 'bm' && m.fw === fw && m.code === code).map((m) => m.anchor));
    const name = displayName(fw, code, s.title);
    const kind = kindLabel(fw, code);

    const toc = [];
    let lastPart = null;
    for (const u of units) {
      if (u.kind !== 'h') continue;
      if (u.part !== lastPart) { toc.push(`<div class="std-toc-part">${esc(u.part)}</div>`); lastPart = u.part; }
      toc.push(`<a href="${viewHash(fw, code, u.anchor, showAll)}" data-anchor="${esc(u.anchor)}">${esc(u.plain)}</a>`);
    }

    let part = '본문';
    const body = [];
    for (const u of units) {
      if (u.part !== part) {
        part = u.part;
        body.push(`<div class="std-part ${u.auth ? '' : 'ref'}">${esc(u.part)}${u.auth ? '' : ' <span>— 기준서를 구성하지 않는 참고자료</span>'}</div>`);
      }
      if (u.kind === 'h') { body.push(`<h3 class="std-h" id="p-${esc(u.anchor)}">${esc(u.plain)}</h3>`); continue; }
      const blocks = u.blocks.map((b) => b.t === 'table'
        ? `<table class="std-tbl">${b.rows.map((r) => `<tr>${r.map((c) => `<td>${esc(c)}</td>`).join('')}</tr>`).join('')}</table>`
        : `<p${b.fn ? ' class="fn"' : ''}>${esc(b.text)}</p>`).join('');
      const on = bms.has(u.anchor);
      body.push(`<section class="std-p${u.auth ? '' : ' ref'}${on ? ' bookmarked' : ''}" id="p-${esc(u.anchor)}" data-anchor="${esc(u.anchor)}" data-no="${esc(u.no || '')}">
        <div class="std-no">${esc(u.no || '')}</div><div class="pbody">${blocks}</div>
        <div class="std-tools"><button type="button" class="bm-btn${on ? ' on' : ''}" title="북마크">★</button><button type="button" class="copy-btn" title="인용 복사">⧉</button></div></section>`);
    }

    root.innerHTML = `<div class="std-layout">
      <aside class="std-side"><div class="std-side-head">
        <a href="#/" class="std-crumb">회계기준서</a> › ${FRAMEWORKS[fw]}
        <select class="std-jump" data-jump>${others.map((o) => `<option value="${esc(viewHash(o.framework, o.code))}" ${o.code === code ? 'selected' : ''}>${esc(displayName(o.framework, o.code, o.title))}</option>`).join('')}</select>
        ${searchForm('', fw, '', code).replace('class="std-search"', 'class="std-search std-side-search"').replace(/placeholder="[^"]*"/, 'placeholder="이 기준서에서 검색"').replace(/ autofocus/, '')}
      </div><nav class="std-toc">${toc.join('')}</nav></aside>
      <article class="std-doc" id="std-doc">
        <header class="std-head">
          <div class="std-muted">${FRAMEWORKS[fw]}${kind ? ' · ' + kind : ''}</div>
          <h1>${esc(name)}</h1>
          <div class="std-muted std-ver">${esc(s.version || '개정 표기 없음')} · 원문 ${esc(s.source_file || '')}</div>
          <div class="std-head-tools">
            ${hasRef ? (showAll
              ? `<a class="std-btn sm ghost" href="${viewHash(fw, code)}">기준서 본문만 보기</a><span class="std-muted">적용사례·결론도출근거 등 참고자료 포함</span>`
              : `<a class="std-btn sm ghost" href="${viewHash(fw, code, '', true)}">적용사례·결론도출근거까지 보기</a><span class="std-muted">기준서 본문(부록·실무지침 포함)만 표시 중</span>`) : ''}
            <span class="std-muted std-help">글자를 드래그하면 형광펜 · ★ 북마크 · ⧉ 인용 복사</span>
          </div>
        </header>
        ${body.join('')}
      </article></div>`;
    root.querySelector('[data-jump]').addEventListener('change', (e) => { location.hash = e.target.value; });
    current = { fw, code, scope, name, label: FRAMEWORKS[fw] };
    marks.filter((m) => m.type === 'hl' && m.fw === fw && m.code === code).forEach(paint);
    flashTarget(target);
  }

  function flashTarget(anchor) {
    if (!anchor) { window.scrollTo(0, 0); return; }
    const el = document.getElementById('p-' + anchor);
    if (!el) return;
    el.scrollIntoView({ block: 'start', behavior: 'instant' });
    el.classList.remove('target'); void el.offsetWidth; el.classList.add('target');
  }

  // ── 형광펜 ──
  function wrapRange(pbody, start, end, h) {
    const walker = document.createTreeWalker(pbody, NodeFilter.SHOW_TEXT);
    const targets = []; let pos = 0, node;
    while ((node = walker.nextNode())) {
      const len = node.nodeValue.length;
      const s = Math.max(start, pos), e = Math.min(end, pos + len);
      if (s < e) targets.push([node, s - pos, e - pos]);
      pos += len; if (pos >= end) break;
    }
    for (const [textNode, s, e] of targets) {
      let mid = textNode;
      if (s > 0) mid = mid.splitText(s);
      if (e - s < mid.nodeValue.length) mid.splitText(e - s);
      const mark = document.createElement('mark');
      mark.className = 'hl hl-' + h.color + (h.note ? ' has-note' : '');
      mark.dataset.id = h.id;
      if (h.note) mark.title = h.note;
      mid.parentNode.insertBefore(mark, mid); mark.appendChild(mid);
    }
  }
  function unwrap(id) {
    root.querySelectorAll('mark.hl[data-id="' + id + '"]').forEach((m) => {
      const p = m.parentNode; while (m.firstChild) p.insertBefore(m.firstChild, m); p.removeChild(m); p.normalize();
    });
  }
  function paint(h) {
    const sec = document.getElementById('p-' + h.anchor);
    if (!sec) return;
    const pbody = sec.querySelector('.pbody'); if (!pbody) return;
    const full = pbody.textContent;
    let s = h.start, e = h.end;
    if (h.quote && full.slice(s, e) !== h.quote) {       // 개정본 등으로 위치가 바뀌면 같은 문구를 다시 찾는다
      const idx = full.indexOf(h.quote); if (idx < 0) return;
      s = idx; e = idx + h.quote.length; h.start = s; h.end = e;
      store.marks.update(h.id, { start: s, end: e }).catch(() => {});
    }
    wrapRange(pbody, s, e, h);
  }

  const bar = document.createElement('div');
  bar.className = 'hl-bar'; bar.hidden = true;
  bar.innerHTML = COLORS.map((c) => `<button type="button" data-color="${c}" class="sw sw-${c}" title="${c}"></button>`).join('') +
    '<button type="button" data-color="yellow" data-memo="1" class="std-btn sm ghost">+메모</button>';
  const pop = document.createElement('div');
  pop.className = 'hl-pop'; pop.hidden = true;
  pop.innerHTML = `<div class="hl-pop-colors">${COLORS.map((c) => `<button type="button" data-color="${c}" class="sw sw-${c}"></button>`).join('')}</div>
    <textarea rows="3" placeholder="메모"></textarea>
    <div class="hl-pop-actions"><button type="button" class="std-btn sm" data-act="save">저장</button>
    <button type="button" class="std-btn sm danger" data-act="delete">형광펜 삭제</button>
    <button type="button" class="std-btn sm ghost" data-act="close">닫기</button></div>`;
  document.body.append(bar, pop);
  const note = pop.querySelector('textarea');
  let pending = null, active = null;

  function placeAt(el, rect) {
    el.hidden = false;
    const top = window.scrollY + rect.top - el.offsetHeight - 8;
    el.style.top = Math.max(window.scrollY + 4, top) + 'px';
    el.style.left = Math.min(window.scrollX + rect.left, window.scrollX + document.documentElement.clientWidth - el.offsetWidth - 8) + 'px';
  }
  const hideBar = () => { bar.hidden = true; pending = null; };

  root.addEventListener('mouseup', () => setTimeout(() => {
    const doc = document.getElementById('std-doc'); if (!doc || !current) return hideBar();
    const sel = window.getSelection();
    if (!sel.rangeCount || sel.isCollapsed) return hideBar();
    const range = sel.getRangeAt(0);
    const el = range.startContainer.nodeType === 1 ? range.startContainer : range.startContainer.parentElement;
    const sec = el && el.closest('.std-p'); if (!sec) return hideBar();
    const pbody = sec.querySelector('.pbody');
    if (!pbody.contains(range.startContainer)) return hideBar();
    if (!pbody.contains(range.endContainer)) range.setEnd(pbody, pbody.childNodes.length);   // 한 문단 안으로 자름
    const pre = document.createRange(); pre.setStart(pbody, 0); pre.setEnd(range.startContainer, range.startOffset);
    const start = pre.toString().length, quote = range.toString();
    if (!quote.trim()) return hideBar();
    pending = { anchor: sec.dataset.anchor, start, end: start + quote.length, quote };
    placeAt(bar, range.getBoundingClientRect());
  }, 0));
  bar.addEventListener('mousedown', (e) => e.preventDefault());
  bar.addEventListener('click', async (e) => {
    const btn = e.target.closest('button'); if (!btn || !pending || !current) return;
    const memo = btn.dataset.memo ? (window.prompt('메모') || '') : '';
    const m = { type: 'hl', fw: current.fw, code: current.code, color: btn.dataset.color, note: memo, ...pending };
    try {
      m.id = await store.marks.add(m); marks.push(m); paint(m);
      window.getSelection().removeAllRanges(); hideBar();
    } catch (_) { toast('형광펜 저장에 실패했습니다'); }
  });
  document.addEventListener('mousedown', (e) => {
    if (!bar.hidden && !bar.contains(e.target)) setTimeout(() => { if (window.getSelection().isCollapsed) hideBar(); }, 0);
    if (!pop.hidden && !pop.contains(e.target) && !e.target.closest('mark.hl')) pop.hidden = true;
  });
  const markColor = (c) => pop.querySelectorAll('.sw').forEach((b) => b.classList.toggle('on', b.dataset.color === c));
  pop.addEventListener('click', async (e) => {
    const btn = e.target.closest('button'); if (!btn || !active) return;
    if (btn.dataset.color) { active.color = btn.dataset.color; markColor(active.color); return; }
    if (btn.dataset.act === 'close') { pop.hidden = true; return; }
    try {
      if (btn.dataset.act === 'delete') {
        await store.marks.remove(active.id); unwrap(active.id); marks = marks.filter((m) => m.id !== active.id); pop.hidden = true;
      } else if (btn.dataset.act === 'save') {
        active.note = note.value;
        await store.marks.update(active.id, { color: active.color, note: active.note });
        unwrap(active.id); paint(active); pop.hidden = true; toast('저장했습니다');
      }
    } catch (_) { toast('저장에 실패했습니다'); }
  });

  root.addEventListener('click', async (e) => {
    const mark = e.target.closest('mark.hl');
    if (mark && window.getSelection().isCollapsed) {
      active = marks.find((m) => String(m.id) === mark.dataset.id); if (!active) return;
      note.value = active.note || ''; markColor(active.color); placeAt(pop, mark.getBoundingClientRect());
      return;
    }
    const tocLink = e.target.closest('.std-toc a');
    if (tocLink) {                                     // 같은 기준서 안 이동은 다시 그리지 않고 스크롤만
      e.preventDefault(); history.replaceState(null, '', tocLink.getAttribute('href')); flashTarget(tocLink.dataset.anchor); return;
    }
    const bm = e.target.closest('.bm-btn');
    if (bm && current) {
      const sec = bm.closest('.std-p'); const anchor = sec.dataset.anchor;
      const ex = marks.find((m) => m.type === 'bm' && m.fw === current.fw && m.code === current.code && m.anchor === anchor);
      try {
        if (ex) { await store.marks.remove(ex.id); marks = marks.filter((m) => m !== ex); }
        else { const m = { type: 'bm', fw: current.fw, code: current.code, anchor, note: '' }; m.id = await store.marks.add(m); marks.push(m); }
        bm.classList.toggle('on', !ex); sec.classList.toggle('bookmarked', !ex);
        toast(ex ? '북마크를 해제했습니다' : '북마크에 추가했습니다');
      } catch (_) { toast('북마크 저장에 실패했습니다'); }
      return;
    }
    const cp = e.target.closest('.copy-btn');
    if (cp && current) {
      const sec = cp.closest('.std-p');
      const no = sec.dataset.no ? ' 문단 ' + sec.dataset.no : '';
      const text = current.label + ' ' + current.name + no + '\n' + sec.querySelector('.pbody').innerText.trim();
      navigator.clipboard.writeText(text).then(() => toast('인용문을 복사했습니다'), () => toast('복사에 실패했습니다'));
    }
  });

  // ── 내 북마크·형광펜 ──
  async function renderMarks() {
    await lib.meta();
    const bms = marks.filter((m) => m.type === 'bm').sort((a, b) => (b.created || 0) - (a.created || 0));
    const hls = marks.filter((m) => m.type === 'hl').sort((a, b) => (b.created || 0) - (a.created || 0));
    const need = new Set(bms.map((m) => m.fw + '/' + m.code));
    const loaded = {};
    for (const k of need) { const [fw, ...rest] = k.split('/'); loaded[k] = await lib.doc(fw, rest.join('/')); }
    const para = (m) => { const d = loaded[m.fw + '/' + m.code]; return d ? d.units.find((u) => u.anchor === m.anchor) : null; };
    const row = (m, inner) => {
      const s = lib.find(m.fw, m.code);
      if (!s) return `<div class="std-result"><span class="std-result-text std-muted">${esc(FRAMEWORKS[m.fw] || m.fw)} ${esc(m.code)} ${esc(m.anchor)} — 기준서가 아직 올라와 있지 않습니다</span></div>`;
      const u = m.type === 'bm' ? para(m) : null;
      return `<a class="std-result" href="${viewHash(m.fw, m.code, m.anchor, u ? !u.auth : false)}">
        <span class="std-result-no">${esc(m.code)} · ${esc((u && u.no) || m.anchor)}</span>
        <span class="std-result-text">${inner(s, u)}</span></a>`;
    };
    root.innerHTML = `<div class="std-toolbar"><h1><a href="#/" class="std-crumb">회계기준서</a> › 내 북마크·형광펜</h1></div>
      <div class="std-card"><h2>북마크 ${bms.length}</h2>
        ${bms.length ? '' : '<p class="std-muted">기준서 문단 오른쪽의 ★ 를 누르면 여기에 모입니다.</p>'}
        ${bms.map((m) => row(m, (s, u) => {
          const t = u ? (u.no && u.plain.startsWith(u.no + ' ') ? u.plain.slice(u.no.length + 1) : u.plain) : '';
          return `<strong>${esc(displayName(s.framework, s.code, s.title))}</strong> — ${u ? esc(t.slice(0, 180)) + (t.length > 180 ? '…' : '') : '(문단을 찾을 수 없음 — 개정으로 문단번호가 바뀌었을 수 있습니다)'}`;
        })).join('')}</div>
      <div class="std-card"><h2>형광펜 ${hls.length}</h2>
        ${hls.length ? '' : '<p class="std-muted">기준서 본문에서 글자를 드래그하고 색을 고르면 여기에 모입니다.</p>'}
        ${hls.map((m) => row(m, (s) => `<mark class="hl hl-${esc(m.color)}">${esc(m.quote)}</mark>
          ${m.note ? `<br><span class="std-muted">메모: ${esc(m.note)}</span>` : ''}
          <br><span class="std-muted">${esc(displayName(s.framework, s.code, s.title))}</span>`)).join('')}</div>`;
  }

  async function route() {
    hideBar(); pop.hidden = true;
    const { seg, params } = parseHash();
    try {
      if (seg[0] === 'v' && seg[1] && seg[2]) return await renderView(seg[1], seg.slice(2).join('/'), params);
      current = null;
      if (seg[0] === 'search') return await renderSearch(params);
      if (seg[0] === 'marks') return await renderMarks();
      return await renderIndex();
    } catch (err) {
      console.error(err);
      root.innerHTML = `<div class="std-card std-warn">불러오기에 실패했습니다: ${esc(err && err.message ? err.message : err)}<br><span class="std-muted">로그인 상태와 Firestore 보안 규칙(std_docs·std_meta·std_marks)을 확인해 주세요.</span></div>`;
    }
  }

  (async () => {
    try { marks = await store.marks.load(); } catch (_) { marks = []; }
    window.addEventListener('hashchange', route);
    await route();
  })();
}

// ── Firebase 저장소 ───────────────────────────────────────────────────
export function firebaseStore(fb, db, uid) {
  const { doc, getDoc, setDoc, collection, getDocs, addDoc, updateDoc, deleteDoc, serverTimestamp, Bytes, writeBatch } = fb;
  const docId = (fw, code) => `${fw}__${code}`;
  return {
    async getMeta() {
      const s = await getDoc(doc(db, 'std_meta', 'manifest'));
      return s.exists() ? s.data() : { updated: '', items: [] };
    },
    async getGz(fw, code) {
      const s = await getDoc(doc(db, 'std_docs', docId(fw, code)));
      return s.exists() ? s.data().gz.toUint8Array() : null;
    },
    async putBundle(bundle, onProgress) {
      const items = bundle.items;
      let n = 0;
      for (const it of items) {
        const bin = Uint8Array.from(atob(it.gz), (c) => c.charCodeAt(0));
        await setDoc(doc(db, 'std_docs', docId(it.framework, it.code)), {
          framework: it.framework, code: it.code, sha: it.sha, gz: Bytes.fromUint8Array(bin), uploaded: serverTimestamp(),
        });
        onProgress(++n, items.length);
      }
      await setDoc(doc(db, 'std_meta', 'manifest'), {
        updated: bundle.updated || '', uploaded: serverTimestamp(),
        items: items.map(({ gz, ...rest }) => rest),
      });
    },
    marks: {
      async load() {
        const s = await getDocs(collection(db, 'std_marks'));
        return s.docs.map((d) => { const v = d.data(); return { ...v, id: d.id, created: v.created && v.created.toMillis ? v.created.toMillis() : 0 }; });
      },
      async add(m) {
        const { id, ...rest } = m;
        const r = await addDoc(collection(db, 'std_marks'), { ...rest, created: serverTimestamp() });
        m.created = Date.now();
        return r.id;
      },
      update(id, patch) { return updateDoc(doc(db, 'std_marks', id), patch); },
      remove(id) { return deleteDoc(doc(db, 'std_marks', id)); },
    },
  };
}
