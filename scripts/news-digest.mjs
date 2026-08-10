// 분야별 최신 뉴스를 수집해 "브리핑" 초안(_posts/*.md)을 생성한다.
// - 뉴스 소스: Google News RSS (무료, API 키 불필요)
// - 발행이 아니라 초안 생성만. PR로 올려 검토 후 병합하면 게시됨.
// 로컬 테스트: NEWS_FIXTURE=sample.xml node scripts/news-digest.mjs
import { writeFileSync, readFileSync, existsSync } from 'node:fs';

const CATEGORIES = [
  {
    key: 'tax', label: '세무', tag: '세무',
    query: '세무 OR 종합소득세 OR 부가가치세 OR 법인세 OR 연말정산',
    // 제목에 아래 키워드가 있어야 채택 (엉뚱한 연예·스포츠 기사 배제)
    must: /세무|세금|절세|법인세|종합소득세|종소세|부가가치세|부가세|양도소득세|양도세|상속세|증여세|연말정산|국세|원천징수|세제|세액|과세/,
  },
  {
    key: 'accounting', label: '회계·결산', tag: '회계',
    query: '회계 OR 결산 OR 재무제표 OR "K-IFRS" OR 외부감사',
    must: /회계|재무제표|외부감사|감사인|K-IFRS|IFRS|재무상태표|손익계산서|공인회계사|회계법인|감리|재무보고|결산.*(법인|기업|회사|재무|회계)|(법인|기업|회사|재무|회계).*결산/,
  },
  {
    key: 'settlement', label: '정부보조사업 정산', tag: '보조금',
    query: '국고보조금 OR 보조사업 정산 OR 연구개발비 정산 OR 정산검증',
    must: /보조금|보조사업|국고|정산|연구개발비|R&D|교부금|지원금|부정수급|환수|보조금관리/,
  },
];

const SEEN_PATH = '_data/news_seen.json';
const MAX_PER_CAT = 5;

const pad = (n) => String(n).padStart(2, '0');
function today() {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function decode(s) {
  return String(s)
    .replace(/<!\[CDATA\[|\]\]>/g, '')
    .replace(/<[^>]+>/g, '')
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&apos;/g, "'")
    .replace(/&nbsp;/g, ' ')
    .trim();
}

function parseItems(xml) {
  const items = [];
  const itemRe = /<item>([\s\S]*?)<\/item>/g;
  let m;
  while ((m = itemRe.exec(xml)) && items.length < 25) {
    const block = m[1];
    const pick = (tag) => {
      const mm = block.match(new RegExp(`<${tag}[^>]*>([\\s\\S]*?)<\\/${tag}>`));
      return mm ? mm[1] : '';
    };
    const source = decode(pick('source'));
    let title = decode(pick('title'));
    // Google News 제목 끝의 " - 매체명" 제거
    if (source && title.endsWith(` - ${source}`)) title = title.slice(0, -(source.length + 3)).trim();
    const link = decode(pick('link'));
    if (title && link) items.push({ title, link, source });
  }
  return items;
}

async function fetchItems(query) {
  if (process.env.NEWS_FIXTURE) {
    return parseItems(readFileSync(process.env.NEWS_FIXTURE, 'utf8'));
  }
  const url = `https://news.google.com/rss/search?q=${encodeURIComponent(query)}&hl=ko&gl=KR&ceid=KR:ko`;
  const res = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0 (news-digest bot)' } });
  if (!res.ok) throw new Error(`RSS fetch failed ${res.status} for ${query}`);
  return parseItems(await res.text());
}

const seen = existsSync(SEEN_PATH) ? JSON.parse(readFileSync(SEEN_PATH, 'utf8')) : [];
const seenSet = new Set(seen);
const date = process.env.RUN_DATE || today();
const ymd = date.replace(/-/g, '');
let created = 0;
const todayItems = {}; // 오늘 뽑힌 분야별 기사 (daily-article.mjs가 토픽 선정에 사용)

for (const cat of CATEGORIES) {
  let items;
  try {
    items = await fetchItems(cat.query);
  } catch (e) {
    console.error(`[${cat.key}] ${e.message}`);
    continue;
  }
  const fresh = items
    .filter((it) => !seenSet.has(it.link) && (!cat.must || cat.must.test(it.title)))
    .slice(0, MAX_PER_CAT);
  if (fresh.length === 0) { console.log(`[${cat.key}] 새 뉴스 없음`); continue; }
  fresh.forEach((it) => seenSet.add(it.link));
  todayItems[cat.key] = fresh.map((it) => ({ title: it.title, source: it.source }));

  const lines = [
    '---',
    'layout: post',
    `title: "${date} ${cat.label} 뉴스 브리핑"`,
    `date: ${date}`,
    `category: ${cat.key}`,
    `tags: [뉴스, ${cat.tag}]`,
    `summary: "${cat.label} 분야 최신 뉴스 ${fresh.length}건을 모았습니다. (매일 자동 수집·발행)"`,
    'author: 손슬기',
    '---',
    '',
    `> 최신 **${cat.label}** 관련 뉴스를 자동으로 모은 브리핑입니다. 자세한 내용은 각 원문 출처에서 확인해 주세요.`,
    '',
    '## 주요 소식',
    '',
    ...fresh.map((it) => `- **[${it.title}](${it.link})**${it.source ? ` — ${it.source}` : ''}`),
    '',
    '<div class="callout" markdown="1">',
    '본 브리핑은 외부 뉴스를 자동 수집한 것으로, 개별 사안의 판단은 최신 법령과 원문을 확인하시기 바랍니다. 구체적인 상담은 [문의](/contact/)를 이용해 주세요.',
    '</div>',
    '',
  ];
  writeFileSync(`_posts/${date}-news-${cat.key}-${ymd}.md`, lines.join('\n'));
  console.log(`[${cat.key}] 초안 생성: ${fresh.length}건`);
  created++;
}

// 최근 500개 URL만 유지
writeFileSync(SEEN_PATH, JSON.stringify([...seenSet].slice(-500), null, 2) + '\n');

// 오늘 뽑힌 기사 목록을 임시 파일로 넘김 (daily-article.mjs가 소비, 커밋 대상 아님)
writeFileSync('.news-today.json', JSON.stringify({ date, categories: todayItems }, null, 2) + '\n');

if (process.env.GITHUB_OUTPUT) {
  writeFileSync(process.env.GITHUB_OUTPUT, `created=${created}\n`, { flag: 'a' });
}
console.log(`완료: 초안 ${created}건`);
