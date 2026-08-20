# Game Brand Fandom Collector

PlayStation, Xbox, Nintendo 세 게임 브랜드의 공개 유튜브 영상 메타데이터와 공개 댓글을
YouTube Data API v3로 수집하여 CSV로 저장하는 데이터 수집 파이프라인입니다.

수집된 데이터는 이후 감성 분석(sentiment analysis), 팬덤 유형 분류(fandom classification),
Brand Fandom Index 산출 등 후속 분석에 사용하기 위한 원본(raw) 데이터입니다.
이 프로젝트는 **수집 계층**만 담당하며, 분석 로직은 포함하지 않습니다.

```text
YouTube API
    ↓
Raw Data Collection (이 프로젝트)
    ↓
CSV
    ↓
Data Cleaning
    ↓
Comment NLP / LLM Classification
    ↓
Brand Fandom Index
    ↓
Visualization Dashboard
```

---

## 프로젝트 목적

PlayStation, Xbox, Nintendo 세 브랜드에 대해 **동일한 조건**(관찰 기간, 영상 수,
영상당 최대 댓글 수, 콘텐츠 카테고리)으로 데이터를 수집하여, 브랜드 간 온라인 팬덤을
공정하게 비교할 수 있는 기초 데이터를 만드는 것이 목적입니다.

---

## 프로젝트 구조

```text
game-brand-fandom-collector/
│
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
│
├── config/
│   └── brands.json          # 브랜드별 채널명/채널 ID 설정
│
├── data/
│   ├── raw/
│   │   ├── videos/          # 브랜드별 + 통합 영상 CSV
│   │   └── comments/        # 브랜드별 + 통합 댓글 CSV
│   └── processed/           # 이후 분석 단계에서 사용할 가공 데이터
│
├── logs/
│   └── collector.log
│
└── src/
    ├── main.py              # CLI 진입점
    ├── config.py            # 기본값 및 경로 설정
    ├── youtube_client.py    # YouTube Data API v3 래퍼 (재시도/에러 분류)
    ├── channel_service.py   # 채널 ID 검색 및 brands.json 캐싱
    ├── video_collector.py   # 영상 메타데이터 수집 및 파생 지표 계산
    ├── comment_collector.py # 최상위 댓글 수집
    ├── csv_manager.py       # 중복 방지 CSV 저장/병합
    └── utils.py             # 공통 유틸 함수
```

---

## 설치

### 1. 가상환경 생성

```bash
python -m venv .venv
```

Mac/Linux:

```bash
source .venv/bin/activate
```

Windows:

```bash
.venv\Scripts\activate
```

### 2. 패키지 설치

```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정

`.env.example`을 복사해 `.env` 파일을 만들고 API 키를 입력합니다.

```bash
cp .env.example .env
```

```env
YOUTUBE_API_KEY=YOUR_API_KEY_HERE
```

`.env` 파일은 `.gitignore`에 포함되어 있어 Git에 커밋되지 않습니다.
**실제 API 키를 저장소에 절대 포함하지 마세요.**

---

## YouTube Data API v3 키 발급 방법

1. [Google Cloud Console](https://console.cloud.google.com/)에 접속해 새 프로젝트를 만들거나 기존 프로젝트를 선택합니다.
2. 좌측 메뉴에서 **APIs & Services → Library**로 이동합니다.
3. `YouTube Data API v3`를 검색해 **Enable(사용 설정)**합니다.
4. **APIs & Services → Credentials**로 이동해 **Create Credentials → API key**를 선택합니다.
5. 발급된 키를 `.env` 파일의 `YOUTUBE_API_KEY`에 붙여넣습니다.
6. 필요 시 API 키에 YouTube Data API v3 전용 제한(Restriction)을 설정해 보안을 강화하세요.

> YouTube Data API는 기본적으로 하루 10,000 유닛의 무료 쿼터를 제공합니다.
> 영상/댓글 수집량이 많을 경우 쿼터 초과(quota exceeded) 에러가 발생할 수 있으며,
> 이 경우 프로그램은 중단되지 않고 로그를 남긴 뒤 남은 데이터는 다음 실행에서 이어서 수집합니다.

---

## 실행

### 기본 실행 (모든 브랜드, 기본값 사용)

```bash
python -m src.main
```

### 특정 브랜드만 수집

```bash
python -m src.main --brand PlayStation
```

### 전체 브랜드 명시적으로 수집

```bash
python -m src.main --brand all
```

### 영상 수 / 댓글 수 조정

```bash
python -m src.main --videos 30 --comments 100
```

### 기간 지정 (증분 수집)

```bash
python -m src.main --start-date 2025-01-01 --end-date 2025-12-31
```

같은 명령을 기간만 바꿔 다시 실행하면(예: 2025-07-01 ~ 2025-12-31), 기존에 수집된
`video_id` / `comment_id`는 건너뛰고 새 데이터만 추가됩니다.

### 기타 옵션

```bash
python -m src.main --include-shorts        # Shorts 포함
python -m src.main --no-anonymize           # 댓글 작성자명 유지 (기본은 익명화)
python -m src.main --keywords "trailer,announcement"
```

---

## 실시간 진행 상황 대시보드 (웹)

수집이 진행되는 과정(브랜드별 영상/댓글 수집 개수, 실시간 로그)을 브라우저에서 볼 수 있습니다.

**터미널 1 — 대시보드 서버 실행**

```bash
python -m http.server 8787 --directory web --bind 127.0.0.1
```

브라우저에서 `http://localhost:8787` 접속.

**터미널 2 — 수집 실행**

```bash
source .venv/bin/activate
python -m src.main --brand all
```

수집기가 진행되는 동안 `web/progress.json`을 계속 갱신하고, 대시보드 페이지가 1초마다
이를 읽어와 브랜드별 영상/댓글 진행률 바와 최근 로그를 실시간으로 보여줍니다.

> `--directory web` 지정으로 `web/` 폴더만 웹에 노출되며, `.env`나 소스 코드는 노출되지
> 않습니다. `--bind 127.0.0.1`은 내 컴퓨터에서만 접속 가능하도록 제한합니다.

---

## 브랜드 설정 (`config/brands.json`)

```json
{
  "brands": [
    { "brand": "PlayStation", "channel_name": "PlayStation", "channel_id": "" },
    { "brand": "Xbox", "channel_name": "Xbox", "channel_id": "" },
    { "brand": "Nintendo", "channel_name": "Nintendo of America", "channel_id": "" }
  ]
}
```

`channel_id`가 비어 있으면 실행 시 `channel_name`으로 공식 채널을 검색해 자동으로
채널 ID를 확인하고 이 파일에 저장합니다. 채널을 추가하려면 배열에 항목을 추가하면 됩니다.

---

## 출력 파일

### 영상 CSV (`data/raw/videos/`)

```text
brand,channel_name,channel_id,video_id,video_title,video_description,
published_at,video_url,duration,view_count,like_count,comment_count,
category_id,tags,thumbnail_url,content_type,like_rate,comment_rate,
engagement_rate,collected_at
```

파생 지표 계산식:

```text
like_rate       = like_count / view_count
comment_rate    = comment_count / view_count
engagement_rate = (like_count + comment_count) / view_count
```

`view_count`가 0이거나 없으면 세 지표 모두 null로 저장됩니다.

### 댓글 CSV (`data/raw/comments/`)

```text
brand,channel_name,video_id,video_title,comment_id,author_name,comment_text,
like_count,published_at,updated_at,reply_count,comment_url,language,
sentiment,attachment,loyalty,advocacy,purchase_intention,competitor_mention,
fandom_category,collected_at
```

`sentiment`, `attachment`, `loyalty`, `advocacy`, `purchase_intention`,
`competitor_mention`, `fandom_category`, `language`는 이후 분석 단계에서 채워질
빈 컬럼입니다. Version 1에서는 값을 채우지 않습니다.

`anonymize_authors=true`(기본값)일 때는 `author_name`을 저장하지 않습니다.
이메일, 위치 정보, 계정 식별자 등 공개적으로 노출되지 않는 개인정보는 수집하지 않습니다.

### 통합 파일

```text
data/raw/videos/all_brand_videos.csv
data/raw/comments/all_brand_comments.csv
```

모든 브랜드의 데이터를 하나로 합친 파일이며, 브랜드별 파일이 갱신될 때마다 함께 재생성됩니다.

모든 CSV는 `encoding="utf-8-sig"`로 저장되어 Excel에서 한글이 깨지지 않고 열립니다.

---

## 에러 처리

다음과 같은 상황에서도 전체 수집 과정이 중단되지 않고, 문제가 된 항목만 건너뛴 뒤
로그(`logs/collector.log`)에 기록하고 계속 진행합니다.

- API 쿼터 초과 (quota exceeded)
- 댓글 비활성화된 영상 (comments disabled)
- 삭제되었거나 비공개인 영상
- 통계 정보 일부 누락
- 네트워크 오류 (지수 백오프로 재시도)
- 잘못된 채널 ID
- 검색 결과 없음
- API 키 누락

---

## Version 1 완료 기준

- [x] `.env`에서 API 키 로드
- [x] PlayStation, Xbox, Nintendo 채널 자동 설정
- [x] 기간 기반 영상 수집
- [x] 영상 통계 CSV 저장
- [x] 공개 댓글 수집 및 CSV 저장
- [x] 브랜드별 CSV + 통합 CSV 생성
- [x] 중복 수집 방지
- [x] 댓글 비활성화 영상에서도 프로그램 정상 동작
- [x] 진행 상황 표시 (tqdm)
- [x] 에러 로깅
- [x] macOS / Windows 모두 동작 (표준 라이브러리 + pathlib 사용)

Brand Fandom Index 계산 및 감성 분석은 이 버전에 포함되어 있지 않으며,
이 프로젝트가 생성하는 CSV를 입력으로 하는 별도 분석 파이프라인에서 다룹니다.
