---
name: stacked-pr
description: Build and manage GitHub stacked pull requests with the official gh-stack extension. Use when asked to make PRs stacked, add a PR to a stack, view or merge a stack, or split work into a chain of dependent PRs.
---

# Stacked PR Skill

GitHub 공식 스택드 PR 기능(`gh stack`)으로 PR 체인을 만들고 관리한다.

## 가장 먼저 읽을 것 — base 체이닝은 스택이 아니다

`gh pr create --base <앞 브랜치>` 로 base 를 수동으로 이어 붙이는 것과, GitHub 이 스택으로 **링크**하는 것은 다르다.

- base 만 이어 붙이면 머지 순서는 맞지만 GitHub 은 그 PR 들을 한 스택으로 취급하지 않는다
- 스택 UI(스택 맵·스택 아이콘·`gh stack merge`)는 링크된 PR 에만 붙는다
- base 가 정렬돼 있으면 GitHub 이 "체인을 발견했다"는 배너를 띄우지만, 그 배너를 눌러야 비로소 링크된다

그래서 "스택이 일부만 보인다"는 상황은 표시 문제가 아니라 **링크되지 않은 PR 이 있는 것**이다. 표시 한계로 넘겨짚지 말고 `gh stack link` 로 확인한다.

## 전제 — 확장 설치

```bash
gh extension install github/gh-stack
```

미설치 상태에서 `gh stack` 을 부르면 설치 안내만 나오고 실패한다. 먼저 확인한다.

> **rtk 사용 환경 주의**: `gh` 가 rtk 로 래핑돼 있으면 `gh stack --help` 가 rtk 도움말을 낸다. 실제 출력은 `rtk proxy gh stack ...` 로 본다.

## 명령 지도

| 목적 | 명령 |
| -- | -- |
| 이미 열린 PR 들을 스택으로 묶기 | `gh stack link` |
| 기존 스택 맨 위에 얹기 | `gh stack link <스택번호> <PR...>` |
| 스택 보기 | `gh stack view` / `--short` / `--json` |
| 스택 체크아웃 | `gh stack checkout <스택번호\|PR번호\|URL\|브랜치>` |
| 스택 통째 머지 | `gh stack merge` |
| 스택 리베이스·동기화 | `gh stack rebase` / `gh stack sync` |
| 새 스택 시작 | `gh stack init` |
| 로컬에서 위에 브랜치 추가 | `gh stack add <브랜치>` |
| 스택 해제 | `gh stack unstack` |
| 이동 | `gh stack top` / `bottom` / `up` / `down` / `switch` / `trunk` |

## 시나리오 1 — 이미 열린 PR 들을 스택으로 만들기

가장 흔한 경우다. 수동 base 체이닝으로 만들어 둔 PR 이 이미 있을 때 쓴다.

```bash
gh stack link --base <에픽브랜치> <PR1> <PR2> <PR3> ...
```

- 인자는 **아래에서 위로**(bottom → top) 나열한다
- 브랜치 이름 · PR 번호 · PR URL 을 섞어 쓸 수 있다
- `--base` 를 생략하면 레포 기본 브랜치가 바닥이 된다. 에픽 브랜치 위에 쌓는 구조라면 반드시 지정한다
- 일부가 이미 스택이면 기존 스택을 갱신한다. 기존 PR 이 빠지는 일은 없다
- PR 이 없는 브랜치는 자동으로 push 하고 PR 을 만들어 base 를 이어 준다

성공하면 스택 번호를 돌려준다. 그 번호를 기억해 둔다.

```
✓ Updated stack to 12 PRs (stack #2056)
```

## 시나리오 2 — 스택 맨 위에 추가

스택 번호를 첫 인자로 주면 기존 목록을 다시 적지 않아도 된다.

```bash
gh stack link <스택번호> <PR> <PR>
```

- 이미 스택에 있는 인자는 건너뛴다
- 다른 스택 소속 PR 은 거부된다
- 스택 번호와 PR 번호는 겹치지 않으므로 첫 인자가 숫자여도 안전하게 구분된다

base 가 자동으로 바뀐다. 실행 후 반드시 확인한다.

```bash
gh pr view <PR> --json baseRefName,mergeable,additions,deletions,files
```

`mergeable` 이 `MERGEABLE` 이 아니거나 파일 수 · 증감 라인이 예상과 다르면 리베이스가 어긋난 것이다.

## 무엇을 스택에 넣을지 — 파일 겹침으로 판정한다

티켓이 다르다고 무조건 독립으로 두지 않는다. **같은 파일을 건드리면 스택으로 순서를 정하는 편이 낫다.**

```bash
gh pr view <PR> --json files --jq '[.files[].path] | join("\n")'
```

- 겹치는 파일이 있고 그 파일을 스택이 크게 고친다 → 스택에 편입한다. 안 그러면 나중에 머지되는 쪽이 반드시 충돌한다
- 겹침이 `ci.yml` 에 줄 추가하는 정도 → 독립 유지가 낫다. 스택에 얹으면 그 작업이 스택 전체 리뷰가 끝날 때까지 묶인다
- 겹침이 없다 → 독립 유지

성격이 다른 변경(문서 스택에 코드 버그픽스)을 얹으면 급한 수정이 느린 리뷰에 종속된다. 겹침이 없으면 넣지 않는다.

## 머지

스택은 바닥부터 머지한다. `gh stack merge` 가 순서와 리베이스를 대신한다.

squash 레포에서 손으로 머지하면 아래 PR 이 머지되는 순간 위 브랜치들이 base 를 잃어 `git rebase --onto` 로 다시 꿰야 한다. 스택 기능을 쓰면 그 수작업이 없어진다. 손으로 리베이스 루프를 돌리기 전에 `gh stack merge` 를 먼저 검토한다.

## 안전 규칙

- `gh stack link` 는 **열린 PR 의 base 를 바꾸는 작업**이다. 실행 전에 무엇이 어떻게 바뀌는지 사용자에게 알리고, 되돌리기 어려운 규모면 확인을 받는다
- 실행 후 각 PR 의 `mergeable` 과 파일 목록을 확인한다
- `gh stack view` 는 현재 로컬 브랜치가 스택에 속해야 동작한다. 다른 브랜치에 있으면 `gh stack checkout <스택번호>` 로 잡거나, `gh pr list` 의 `baseRefName` 으로 체인을 확인한다
- `gh stack unstack` 은 GitHub 쪽 스택도 지운다. 사용자가 명시적으로 요청할 때만 쓴다

## 확인 흐름

```bash
gh pr list --repo <owner>/<repo> --state open --limit 40 \
  --json number,headRefName,baseRefName \
  --jq '.[] | select(.headRefName | startswith("<접두>")) | "\(.number)\t\(.headRefName) -> \(.baseRefName)"'
```

각 행의 base 가 바로 앞 브랜치를 가리키면 체인이 온전하다. 체인이 온전해도 링크는 별개이므로, 스택 UI 가 필요하면 `gh stack link` 를 돌린다.

## 참고

- [About stacked pull requests](https://docs.github.com/en/pull-requests/get-started/about-stacked-prs)
- [Creating stacked pull requests](https://docs.github.com/en/pull-requests/how-tos/create-pull-requests/creating-stacked-pull-requests)
- [Stacked pull requests are now in public preview](https://github.blog/changelog/2026-07-30-stacked-pull-requests-are-now-in-public-preview/) — 2026-07-30 공개 프리뷰, 변경될 수 있다
