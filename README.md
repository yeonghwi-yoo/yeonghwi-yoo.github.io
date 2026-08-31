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

## 수익화 관련 메모 (중요)

**현재 이 블로그는 광고 없는 비수익 학습 기록으로 운영한다.**
`_includes/head/custom.html`의 애드센스 코드 자리는 주석 처리된 상태로 두며, 해제하지 않는다.

광고를 붙이는 것은 지속적인 영리행위로 해석될 수 있어, **재직 중에는 사내 준법감시·인사 부서의 확인과 승인 절차가 선행되어야 한다.** 확인 없이 애드센스를 신청하거나 광고 코드를 활성화하지 않는다.

### 콘텐츠 작성 시 지킬 것

- 직무에서 알게 된 정보, 소속 기관의 운용 방식·시각을 연상시키는 내용은 쓰지 않는다.
- 공개된 학술 연구, 공개 데이터, 오픈소스 도구만 소재로 삼는다.
- 특정 종목·상품 추천이나 투자 권유로 읽힐 표현을 쓰지 않는다 (각 글 하단 면책 문구 유지).

### 수익화가 승인된 이후에 밟을 순서

1. [ ] 글 20~30편 쌓기 (각 1,000자 이상, 검색해서 들어올 만한 주제)
2. [ ] [Google 서치콘솔](https://search.google.com/search-console) 등록 + 사이트맵 제출 (`https://yeonghwi-yoo.github.io/sitemap.xml` — 자동 생성됨)
3. [ ] [네이버 서치어드바이저](https://searchadvisor.naver.com) 등록 (국내 유입)
4. [ ] (권장) 커스텀 도메인 연결 — 승인율과 SEO에 유리
5. [ ] **사내 확인·승인 완료** ← 아래 단계의 전제 조건
6. [ ] [애드센스](https://adsense.google.com) 가입 → 사이트 추가 → 발급받은 코드를 `_includes/head/custom.html`에 넣고 주석 해제
7. [ ] 심사 통과 후: 루트에 `ads.txt` 파일 추가 (애드센스 안내에 나오는 한 줄)

## 로컬 미리보기 (선택)

Ruby가 설치되어 있다면:

```bash
bundle install
bundle exec jekyll serve
# http://localhost:4000
```
