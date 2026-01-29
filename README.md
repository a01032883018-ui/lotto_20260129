# 뉴스 검색 챗봇

키워드를 입력하면 구글에서 관련 뉴스 10개를 찾아서 요약해주는 챗봇입니다.

## 기능

- 🔍 구글 뉴스 검색 (최대 10개)
- 📝 뉴스 자동 요약
- 🌐 웹 기반 사용자 인터페이스
- ⚡ 실시간 검색 및 요약

## 설치 방법

1. Python 3.7 이상이 설치되어 있어야 합니다.

2. 필요한 패키지 설치:
```bash
pip install -r requirements.txt
```

3. (선택사항) Gemini API를 사용한 요약·대화 기능:
   - **로컬**: `.env` 파일에 `GEMINI_API_KEY=your_key` 추가 (파일은 .gitignore에 포함되어 있어 커밋되지 않음)
   - **Vercel 배포**: 코드에 API 키를 넣지 말고, Vercel 대시보드 → 프로젝트 → Settings → Environment Variables에서 `GEMINI_API_KEY`만 설정하세요.
   - API 키가 없어도 기본 요약·대화 기능은 사용할 수 있습니다.

## 실행 방법

```bash
python app.py
```

브라우저에서 `http://localhost:5000`으로 접속하세요.

## 사용 방법

1. 웹 페이지에서 검색하고 싶은 키워드를 입력합니다.
2. "검색" 버튼을 클릭하거나 Enter 키를 누릅니다.
3. 뉴스 검색 및 요약 결과를 확인합니다.

## Vercel 배포 시 API 키 보안

- **API 키는 코드에 넣지 마세요.** 환경변수만 사용합니다.
- Vercel: Settings → Environment Variables에 `GEMINI_API_KEY` 추가 (Value에 키 입력, Production/Preview/Development 원하는 환경 선택).
- `.env` 파일은 로컬 개발용이며, `.gitignore`에 포함되어 저장소에 올라가지 않습니다.

## 주의사항

- 구글 검색은 웹 스크래핑을 사용하므로, 구글의 정책 변경 시 동작하지 않을 수 있습니다.
- Gemini API 키가 없으면 기본 요약·대화 기능만 사용됩니다.
- 대량의 요청을 보내면 IP 차단될 수 있으니 주의하세요.
