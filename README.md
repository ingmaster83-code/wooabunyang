# 우아분양 (wooabunyang.wooahouse.com)
한국부동산원 청약홈 APT 분양정보(15101046)·주택형별 분양정보(15101047, 2020-02~2025-11 공고 2,594단지) + 지역별 청약 경쟁률(15110988)·평균 분양가(15128701)·연령별 당첨자(15110981) 기반 정적 사이트(약 4,300페이지).
- `data/bunyang.json`(커밋) → `python scripts/build_site.py` → `_site/`, 검증 `python scripts/check_site.py`
- 갱신: 파일데이터 새 버전이 올라오면 `_pubdata_dl.py`로 재다운로드 후 data 재생성(생성 스크립트는 세션에서 인라인 실행, 필요 시 scripts/로 이동)
