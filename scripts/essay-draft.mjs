// 테마 백로그에서 다음 주제 1개를 골라 AI로 에세이 초안을 생성한다.
// - 모델: claude-opus-5 (공식 Anthropic SDK)
// - 발행이 아니라 초안 생성. PR로 올려 검토 후 병합하면 게시됨.
// 로컬 테스트(키·네트워크 없이): ESSAY_FIXTURE=1 node scripts/essay-draft.mjs
import { readFileSync, writeFileSync, existsSync } from 'node:fs';

const TOPICS_PATH = 'scripts/essay-topics.json';
const CAT_LABEL = { tax: '세무 정보', accounting: '회계·결산 정보', settlement: '사업비·정산 실무' };
const CAT_TAG = { tax: '세무', accounting: '회계', settlement: '정산실무' };

const pad = (n) => String(n).padStart(2, '0');
function today() {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
function slugify(s) {
  return s.toLowerCase().replace(/[^a-z0-9가-힣]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40);
}

const SYSTEM = `당신은 한국의 공인회계사 "손슬기"의 블로그에 실릴 실무 에세이 초안을 쓰는 조력자입니다.
독자는 사업자·기관 담당자 등 비전문가입니다. 아래 규칙을 지키세요.

- 한국어. 분량 800~1200자 내외. 마크다운 사용.
- 제목(H1)은 넣지 마세요. 바로 도입 문단으로 시작합니다. 소제목은 '##'를 사용합니다.
- 정확하고 일반적인 정보 수준으로 씁니다. 단정적 조언·확정적 절세 보장은 피하고,
  "개별 사안·최신 법령에 따라 달라질 수 있으니 확인이 필요하다"는 취지를 본문에 자연스럽게 담습니다.
- 실무에 바로 도움이 되는 예시·체크포인트를 포함하되, 과장·홍보성 표현은 쓰지 않습니다.
- 구체적인 세율·금액·연도별 수치는 "변동될 수 있다"는 전제 없이는 단정하지 않습니다.
- 글 말미에 상담을 부드럽게 안내하는 한 문장을 포함할 수 있습니다.

출력 형식(반드시 지킬 것):
첫 줄에 "SUMMARY: <목록에 보일 한 줄 요약>"
그다음 빈 줄 하나
그다음부터 마크다운 본문.`;

function buildUserPrompt(topic) {
  return `분야: ${CAT_LABEL[topic.category]}
제목: ${topic.title}
다룰 내용(개요): ${topic.outline}

위 주제로 블로그 에세이 초안을 작성해 주세요.`;
}

async function generate(topic) {
  if (process.env.ESSAY_FIXTURE) {
    return {
      summary: `${topic.title} — 핵심을 실무 관점에서 정리했습니다. (테스트)`,
      body: `## 들어가며\n\n(테스트 픽스처) ${topic.outline}\n\n## 핵심 포인트\n\n- 항목 1\n- 항목 2\n\n<div class="callout" markdown="1">\n개별 사안은 최신 법령과 함께 확인하시기 바랍니다.\n</div>`,
    };
  }
  const { default: Anthropic } = await import('@anthropic-ai/sdk');
  const client = new Anthropic(); // ANTHROPIC_API_KEY 사용
  const message = await client.messages.create({
    model: 'claude-opus-5',
    max_tokens: 4096,
    output_config: { effort: 'medium' },
    system: SYSTEM,
    messages: [{ role: 'user', content: buildUserPrompt(topic) }],
  });
  if (message.stop_reason === 'refusal') {
    throw new Error('모델이 요청을 거절했습니다(refusal).');
  }
  const text = message.content.filter((b) => b.type === 'text').map((b) => b.text).join('\n').trim();
  const nl = text.indexOf('\n');
  const firstLine = (nl === -1 ? text : text.slice(0, nl)).trim();
  const summary = firstLine.replace(/^SUMMARY:\s*/i, '').trim();
  const body = (nl === -1 ? '' : text.slice(nl + 1)).replace(/^\s*\n/, '').trim();
  if (!summary || !body) throw new Error('생성 결과 형식이 올바르지 않습니다.');
  return { summary, body };
}

async function main() {
  const topics = JSON.parse(readFileSync(TOPICS_PATH, 'utf8'));
  const idx = topics.findIndex((t) => !t.used);
  if (idx === -1) {
    console.log('사용 가능한 미사용 주제가 없습니다. essay-topics.json에 주제를 추가하세요.');
    if (process.env.GITHUB_OUTPUT) writeFileSync(process.env.GITHUB_OUTPUT, 'created=0\n', { flag: 'a' });
    return;
  }
  const topic = topics[idx];
  const date = process.env.RUN_DATE || today();
  let result;
  try {
    result = await generate(topic);
  } catch (e) {
    console.error(`생성 실패: ${e.message}`);
    if (process.env.GITHUB_OUTPUT) writeFileSync(process.env.GITHUB_OUTPUT, 'created=0\n', { flag: 'a' });
    process.exitCode = 0; // 워크플로우는 실패시키지 않고 초안 없음으로 처리
    return;
  }

  const fm = [
    '---',
    'layout: post',
    `title: "${topic.title.replace(/"/g, '\\"')}"`,
    `date: ${date}`,
    `category: ${topic.category}`,
    `tags: [에세이, ${CAT_TAG[topic.category]}]`,
    `summary: "${result.summary.replace(/"/g, '\\"')}"`,
    'author: 손슬기',
    '---',
    '',
    result.body,
    '',
  ].join('\n');

  const file = `_posts/${date}-essay-${slugify(topic.title)}.md`;
  writeFileSync(file, fm);
  topics[idx].used = true;
  writeFileSync(TOPICS_PATH, JSON.stringify(topics, null, 2) + '\n');
  console.log(`에세이 초안 생성: ${file}`);
  if (process.env.GITHUB_OUTPUT) writeFileSync(process.env.GITHUB_OUTPUT, 'created=1\n', { flag: 'a' });
}

main();
