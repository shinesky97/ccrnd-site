// 매일: 그날 수집된 뉴스에서 토픽 1개를 뽑아 AI 해설 글을 자동 생성한다.
// - 입력: .news-today.json (news-digest.mjs가 생성). 없거나 비면 essay-topics.json 백로그로 폴백.
// - 모델: 공식 Anthropic SDK (ANTHROPIC_API_KEY 필요)
// - 뉴스 기사를 옮겨 쓰지 않고, 그 주제/키워드에 대한 '독립적 실무 해설'을 생성한다.
// 로컬 테스트(키·네트워크 없이): ARTICLE_FIXTURE=1 node scripts/daily-article.mjs
import { readFileSync, writeFileSync, existsSync } from 'node:fs';

const NEWS_TODAY = '.news-today.json';
const TOPICS_PATH = 'scripts/essay-topics.json';
const MODEL = process.env.ARTICLE_MODEL || 'claude-opus-5';

const CAT_LABEL = { tax: '세무', accounting: '회계·결산', settlement: '정부보조사업 정산' };
const CAT_TAG = { tax: '세무', accounting: '회계', settlement: '정산실무' };
const ROTATION = ['tax', 'accounting', 'settlement'];

const pad = (n) => String(n).padStart(2, '0');
function today() {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
function slugify(s) {
  return s.toLowerCase().replace(/[^a-z0-9가-힣]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40);
}
function dayIndex(date) {
  const [y, m, d] = date.split('-').map(Number);
  return (y * 372 + m * 31 + d); // 날짜별로 회전시키기 위한 단조 증가 정수
}

const SYSTEM = `당신은 한국의 공인회계사 "손슬기"의 홈페이지 인사이트에 실릴 실무 해설 글을 쓰는 조력자입니다.
독자는 사업자·기관 담당자 등 비전문가입니다. 아래 규칙을 반드시 지키세요.

- 한국어. 분량 900~1400자. 마크다운 사용. 소제목은 '##'.
- 주어진 '오늘의 토픽'은 방향 힌트일 뿐입니다. 뉴스 기사를 요약·전재하지 말고,
  그 주제·키워드와 관련해 오래 두고 볼 수 있는 '실무 해설(evergreen)'을 쓰세요.
- 정확하고 일반적인 정보 수준으로 씁니다. 단정적 조언·확정적 절세 보장은 피하고,
  "개별 사안·최신 법령에 따라 달라질 수 있어 확인이 필요하다"는 취지를 자연스럽게 담습니다.
- 구체적 세율·금액·시행일 등 변동 가능한 수치는 단정하지 말고 '확인이 필요하다'는 전제로 씁니다.
- 검색 노출을 고려해 제목에는 핵심 키워드를 자연스럽게 포함합니다. 과장·홍보성 표현은 금지.
- 표나 체크리스트를 1개 이상 넣어 실무에 바로 쓰이게 합니다.
- 본문 끝에 상담을 부드럽게 안내하는 한 문장을 포함할 수 있습니다.

출력 형식(반드시 이 순서, 각 줄):
첫 줄: "TITLE: <검색 친화적 제목, 25~45자>"
둘째 줄: "SUMMARY: <목록에 보일 한 줄 요약>"
셋째 줄: 빈 줄
넷째 줄부터: 마크다운 본문 (H1 금지, '##'부터 시작)`;

function pickTopic(date) {
  // 1) 오늘 뉴스가 있으면 회전 순서에 따라 기사 있는 분야를 고르고 대표 헤드라인을 시드로
  if (existsSync(NEWS_TODAY)) {
    try {
      const data = JSON.parse(readFileSync(NEWS_TODAY, 'utf8'));
      const cats = data.categories || {};
      const available = ROTATION.filter((k) => Array.isArray(cats[k]) && cats[k].length);
      if (available.length) {
        const focus = available[dayIndex(date) % available.length];
        const seed = cats[focus][0].title;
        return { category: focus, seed, source: 'news' };
      }
    } catch (e) {
      console.error(`뉴스 파일 파싱 실패: ${e.message}`);
    }
  }
  // 2) 폴백: 에세이 토픽 백로그의 첫 미사용 주제
  if (existsSync(TOPICS_PATH)) {
    const topics = JSON.parse(readFileSync(TOPICS_PATH, 'utf8'));
    const idx = topics.findIndex((t) => !t.used);
    if (idx !== -1) {
      return { category: topics[idx].category, seed: topics[idx].title, source: 'backlog', idx, topics };
    }
  }
  return null;
}

function buildUserPrompt(pick) {
  const label = CAT_LABEL[pick.category] || '세무';
  return `분야: ${label}
오늘의 토픽(방향 힌트): ${pick.seed}

위 토픽과 관련해, 사업자·기관 담당자가 실무에 바로 활용할 수 있는 해설 글을 작성해 주세요.
뉴스 기사 자체를 옮기지 말고, 배경·핵심 개념·유의점을 설명하는 독립적인 글로 써 주세요.`;
}

async function generate(pick) {
  if (process.env.ARTICLE_FIXTURE) {
    return {
      title: `${CAT_LABEL[pick.category]} 실무 해설 — ${pick.seed.slice(0, 20)}`,
      summary: `${pick.seed} 관련 핵심을 실무 관점에서 정리했습니다. (테스트)`,
      body: `## 들어가며\n\n(테스트 픽스처) ${pick.seed}\n\n## 핵심 포인트\n\n| 항목 | 내용 |\n|------|------|\n| 1 | ... |\n\n<div class="callout" markdown="1">\n개별 사안은 최신 법령과 함께 확인하시기 바랍니다.\n</div>`,
    };
  }
  if (!process.env.ANTHROPIC_API_KEY) {
    throw new Error('ANTHROPIC_API_KEY 미설정 — 해설 글 생성을 건너뜁니다.');
  }
  const { default: Anthropic } = await import('@anthropic-ai/sdk');
  const client = new Anthropic();
  const message = await client.messages.create({
    model: MODEL,
    max_tokens: 4096,
    output_config: { effort: 'medium' },
    system: SYSTEM,
    messages: [{ role: 'user', content: buildUserPrompt(pick) }],
  });
  if (message.stop_reason === 'refusal') throw new Error('모델이 요청을 거절했습니다(refusal).');
  const text = message.content.filter((b) => b.type === 'text').map((b) => b.text).join('\n').trim();
  const lines = text.split('\n');
  let title = '', summary = '';
  let i = 0;
  for (; i < lines.length; i++) {
    const l = lines[i].trim();
    if (/^TITLE:/i.test(l)) title = l.replace(/^TITLE:\s*/i, '').trim();
    else if (/^SUMMARY:/i.test(l)) { summary = l.replace(/^SUMMARY:\s*/i, '').trim(); i++; break; }
  }
  const body = lines.slice(i).join('\n').replace(/^\s*\n+/, '').trim();
  if (!title || !summary || !body) throw new Error('생성 결과 형식이 올바르지 않습니다.');
  return { title, summary, body };
}

async function main() {
  const date = process.env.RUN_DATE || today();
  const pick = pickTopic(date);
  if (!pick) {
    console.log('토픽을 찾지 못했습니다(뉴스·백로그 모두 없음). 건너뜁니다.');
    if (process.env.GITHUB_OUTPUT) writeFileSync(process.env.GITHUB_OUTPUT, 'created=0\n', { flag: 'a' });
    return;
  }

  let result;
  try {
    result = await generate(pick);
  } catch (e) {
    console.error(`생성 실패: ${e.message}`);
    if (process.env.GITHUB_OUTPUT) writeFileSync(process.env.GITHUB_OUTPUT, 'created=0\n', { flag: 'a' });
    return; // 워크플로우는 실패시키지 않음 (뉴스 브리핑은 그대로 발행)
  }

  const fm = [
    '---',
    'layout: post',
    `title: "${result.title.replace(/"/g, '\\"')}"`,
    `date: ${date}`,
    `category: ${pick.category}`,
    `tags: [해설, ${CAT_TAG[pick.category] || '세무'}]`,
    `summary: "${result.summary.replace(/"/g, '\\"')}"`,
    'author: 손슬기',
    '---',
    '',
    result.body,
    '',
    '---',
    '',
    '*이 글은 최신 이슈를 바탕으로 자동 작성된 실무 해설이며, 구체적 사안은 최신 법령과 전문가 확인이 필요합니다.*',
    '',
  ].join('\n');

  writeFileSync(`_posts/${date}-article-${slugify(result.title)}.md`, fm);
  console.log(`해설 글 생성(${pick.source}): ${result.title}`);

  // 백로그 주제를 썼다면 사용 처리
  if (pick.source === 'backlog') {
    pick.topics[pick.idx].used = true;
    writeFileSync(TOPICS_PATH, JSON.stringify(pick.topics, null, 2) + '\n');
  }
  if (process.env.GITHUB_OUTPUT) writeFileSync(process.env.GITHUB_OUTPUT, 'created=1\n', { flag: 'a' });
}

main();
