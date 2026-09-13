# 퀀트 노트 — 블로그 소스

Jekyll + [Minimal Mistakes](https://mmistakes.github.io/minimal-mistakes/) 테마 기반 GitHub Pages 블로그입니다.
`yeonghwi-yoo.github.io` 리포지토리의 `main` 브랜치에 푸시하면 GitHub이 자동으로 빌드·배포합니다 (별도 CI 설정 불필요).

## 구조

```
_config.yml          사이트 설정 (제목, 테마 스킨, 작성자 정보 등)
_data/navigation.yml 상단 메뉴
_pages/              소개, 개인정보처리방침, 글 목록, 404
_posts/              블로그 글 (파일명: YYYY-MM-DD-제목.md)
_includes/head/custom.html  애드센스·서치콘솔 코드 넣는 자리
```

## 글 쓰는 법

`_posts/` 폴더에 `2026-09-01-my-post.md` 형식으로 파일을 만들고 맨 위에 front matter를 씁니다.

```markdown
---
title: "글 제목"
categories:
  - 퀀트투자
tags:
  - 백테스트
---

본문을 마크다운으로 작성합니다.
```

푸시하면 1~2분 안에 사이트에 반영됩니다.

## 수익화 관련 메모

**2026-09-13부로 애드센스 심사 준비 상태다.** 아래 파일들이 사이트에 들어가 있으며, 글 발행 자동화가 이 파일들을 건드리면 안 된다.

- `_includes/head/custom.html` — 애드센스 스크립트(`ca-pub-7635369920244942`)가 모든 페이지 `<head>`에 삽입됨. 목록 페이지(`/page2/` 등)에는 `noindex,follow` 메타가 붙는다.
- `ads.txt` — 루트에 게시자 ID 한 줄
- `sitemap.xml` — jekyll-sitemap 기본 템플릿을 대체하는 커스텀 사이트맵. 목록 페이지를 제외한다.

애드센스 계정의 "사이트 추가"로 이 도메인을 등록하는 시점부터 심사가 시작된다.

### 콘텐츠 작성 시 지킬 것

- **익명 블로그다.** 글쓴이의 실명·직장·직업·소속을 어떤 형태로도 언급하지 않는다.
- 공개되지 않은 정보나 특정 기관 내부의 시각을 연상시키는 내용은 쓰지 않는다.
- 공개된 학술 연구, 공개 데이터, 오픈소스 도구만 소재로 삼는다.
- 특정 종목·상품 추천이나 투자 권유로 읽힐 표현을 쓰지 않는다 (각 글 하단 면책 문구 유지).

### 애드센스 심사 체크리스트

1. [x] 커스텀 도메인 연결 (`quant-note.com`), HTTPS 강제
2. [x] [Google 서치콘솔](https://search.google.com/search-console) 등록 + 사이트맵 제출 (`https://quant-note.com/sitemap.xml`)
3. [x] 소개·개인정보처리방침 페이지
4. [x] 애드센스 스크립트 삽입 (`_includes/head/custom.html`)
5. [x] `ads.txt` 배치
6. [x] 목록 페이지를 사이트맵에서 제외하고 `noindex,follow` 처리 — 본문이 얇은 페이지가 심사에 잡히지 않도록
7. [ ] 글 30편 이상 확보 후 애드센스 "사이트 추가"
8. [ ] (선택) [네이버 서치어드바이저](https://searchadvisor.naver.com) 등록

## 로컬 미리보기 (선택)

Ruby가 설치되어 있다면:

```bash
bundle install
bundle exec jekyll serve
# http://localhost:4000
```
