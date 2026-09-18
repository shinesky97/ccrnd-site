# -*- coding: utf-8 -*-
"""자동 업데이트 — GitHub 저장소의 최신 desktop-tool 코드를 받아 설치 폴더에 덮어쓴다.

- 사용자 데이터(_audit_tool의 결정값·로그·백업, dist, 진행현황)는 건드리지 않는다.
- 덮어쓰기 전 기존 코드를 _backup/에 보관한다.
- 실행: GUI [업데이트] 버튼, 업데이트.bat, 또는 python -m audit_tool.updater
"""
import io
import os
import re
import shutil
import sys
import tempfile
import zipfile
from urllib.request import Request, urlopen

REPO = 'shinesky97/ccrnd-site'
BRANCH = 'claude/ai-audit-support-design-3vml4o'
SUBDIR = 'desktop-tool'
# 갱신에서 제외 (사용자 데이터·빌드 산출물)
SKIP_TOP = {'_audit_tool', '_backup', 'dist', 'build', '__pycache__', '.git',
            'github_token.txt'}


def install_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _headers():
    h = {'User-Agent': 'audit-tool-updater'}
    tok_path = os.path.join(install_root(), 'github_token.txt')
    if os.path.exists(tok_path):                      # 저장소를 비공개로 바꾼 경우 대비
        tok = open(tok_path, encoding='utf-8').read().strip()
        if tok:
            h['Authorization'] = 'Bearer ' + tok
    return h


def _get(url, accept=None, timeout=120):
    h = dict(_headers())
    if accept:
        h['Accept'] = accept
    with urlopen(Request(url, headers=h), timeout=timeout) as r:
        return r.read()


def local_version():
    from . import __version__
    return __version__


def remote_version():
    url = (f'https://api.github.com/repos/{REPO}/contents/'
           f'{SUBDIR}/audit_tool/__init__.py?ref={BRANCH}')
    txt = _get(url, accept='application/vnd.github.raw').decode('utf-8')
    m = re.search(r"__version__\s*=\s*'([^']+)'", txt)
    return m.group(1) if m else None


def download_and_apply(log=print):
    if getattr(sys, 'frozen', False):
        log('✘ exe 실행 중에는 자동 업데이트할 수 없습니다.')
        log('  실행.bat 방식으로 사용하거나, 소스 폴더에서 업데이트.bat 실행 후 '
            'build_exe.bat로 exe를 다시 만드십시오.')
        return 'failed'
    root = install_root()
    log('최신 코드 다운로드 중...')
    data = _get(f'https://api.github.com/repos/{REPO}/zipball/{BRANCH}', timeout=300)
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            z.extractall(td)
        src = None
        for name in os.listdir(td):
            cand = os.path.join(td, name, SUBDIR)
            if os.path.isdir(cand):
                src = cand
                break
        if src is None:
            log('✘ 다운로드 파일에서 desktop-tool 폴더를 찾지 못했습니다.')
            return 'failed'
        # 기존 코드 백업 후 audit_tool 패키지는 통째로 교체 (잔여 파일 방지 — 클린 재설치)
        bak = os.path.join(root, '_backup')
        shutil.rmtree(bak, ignore_errors=True)
        shutil.copytree(os.path.join(root, 'audit_tool'),
                        os.path.join(bak, 'audit_tool'),
                        ignore=shutil.ignore_patterns('__pycache__'))
        shutil.rmtree(os.path.join(root, 'audit_tool'), ignore_errors=True)
        # 저장소 파일로 갱신 (실패 시 백업에서 자동 복구)
        updated = 0
        try:
            for dirpath, dirnames, filenames in os.walk(src):
                rel = os.path.relpath(dirpath, src)
                if rel != '.' and rel.split(os.sep)[0] in SKIP_TOP:
                    dirnames[:] = []
                    continue
                dirnames[:] = [d for d in dirnames if d not in SKIP_TOP]
                dst_dir = root if rel == '.' else os.path.join(root, rel)
                os.makedirs(dst_dir, exist_ok=True)
                for fn in filenames:
                    if fn in SKIP_TOP:
                        continue
                    shutil.copy2(os.path.join(dirpath, fn), os.path.join(dst_dir, fn))
                    updated += 1
        except Exception as e:
            log(f'✘ 파일 교체 중 오류: {e} — 이전 버전으로 복구합니다.')
            shutil.rmtree(os.path.join(root, 'audit_tool'), ignore_errors=True)
            shutil.copytree(os.path.join(bak, 'audit_tool'),
                            os.path.join(root, 'audit_tool'))
            log('복구 완료 (기존 버전 유지). 인터넷 연결 확인 후 다시 시도하십시오.')
            return 'failed'
    log(f'✔ 업데이트 완료: 파일 {updated}개 갱신 (이전 코드는 _backup/ 보관)')
    log('프로그램을 다시 시작하면 새 버전이 적용됩니다.')
    return 'updated'


def run(log=print, confirm=None):
    """반환: 'latest' | 'updated' | 'cancelled' | 'failed'"""
    lv = local_version()
    log(f'현재 버전: {lv}')
    try:
        rv = remote_version()
    except Exception as e:
        log(f'✘ 최신 버전 확인 실패: {e}')
        log('  인터넷 연결을 확인하십시오. 저장소가 비공개로 바뀐 경우에는 '
            'github_token.txt 파일에 GitHub 토큰을 넣으면 됩니다.')
        return 'failed'
    log(f'최신 버전: {rv}')
    if rv == lv:
        log('이미 최신 버전입니다.')
        return 'latest'
    if confirm and not confirm(f'{lv} → {rv} 업데이트를 진행할까요?\n'
                               '(결정값·로그 등 사용자 데이터는 유지됩니다)'):
        return 'cancelled'
    return download_and_apply(log)


def main():
    auto = '-y' in sys.argv
    confirm = None if auto else (
        lambda m: input(f'\n{m} [y/N] ').strip().lower() == 'y')
    status = run(confirm=confirm)
    return 0 if status in ('latest', 'updated') else 1


if __name__ == '__main__':
    raise SystemExit(main())
