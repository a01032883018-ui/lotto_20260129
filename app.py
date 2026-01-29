from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import os
from dotenv import load_dotenv
import json
import re
from urllib.parse import quote_plus, urlparse, parse_qs
import time
from datetime import datetime

load_dotenv()

app = Flask(__name__)

# Gemini API 키: 환경변수에서만 로드 (배포 시 Vercel 환경변수에 GEMINI_API_KEY 설정)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# 최근 검색 결과 (대화 기능용, 프로세스 메모리 기준)
last_search = {
    "keyword": None,
    "news": [],
    "summary": ""
}

# 검색 히스토리 저장 파일
HISTORY_FILE = os.path.join(os.path.dirname(__file__), "history.json")


def save_history(keyword, news_items, summary):
    """키워드와 수집한 뉴스들을 로컬 JSON 파일에 저장"""
    record = {
        "keyword": keyword,
        "summary": summary,
        "news": news_items,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    data = []
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, list):
                    data = loaded
    except Exception as e:
        # 파일 읽기 실패 시 새로 생성
        print(f"히스토리 읽기 오류: {e}")

    data.append(record)

    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"히스토리 저장 오류: {e}")

def extract_news_content(url):
    """뉴스 URL에서 본문 내용 추출"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9'
        }
        
        # 구글 뉴스 리다이렉트 URL 처리
        if 'news.google.com/rss/articles' in url:
            # 구글 뉴스 링크는 실제 URL로 리다이렉트 필요
            response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            url = response.url
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 불필요한 태그 제거
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'noscript']):
            tag.decompose()
        
        # 본문 내용 추출 - 여러 패턴 시도
        content = ""
        
        # 패턴 1: article 태그
        article = soup.find('article')
        if article:
            paragraphs = article.find_all(['p', 'div'], class_=re.compile(r'(article|content|body|text|post)', re.I))
            if paragraphs:
                content = '\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
        
        # 패턴 2: 본문 클래스 찾기
        if not content:
            content_divs = soup.find_all(['div', 'section'], class_=re.compile(r'(article|content|body|text|post|main)', re.I))
            for div in content_divs:
                paragraphs = div.find_all('p')
                if len(paragraphs) > 3:  # 최소 3개 이상의 문단이 있어야 본문으로 인정
                    content = '\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
                    break
        
        # 패턴 3: 일반 p 태그들
        if not content:
            paragraphs = soup.find_all('p')
            if len(paragraphs) > 3:
                # 너무 짧은 문단 제외
                valid_paragraphs = [p.get_text(strip=True) for p in paragraphs 
                                  if len(p.get_text(strip=True)) > 50]
                if len(valid_paragraphs) > 2:
                    content = '\n'.join(valid_paragraphs[:10])  # 최대 10개 문단
        
        # 패턴 4: 메타 태그에서 설명 가져오기
        if not content:
            meta_desc = soup.find('meta', property='og:description')
            if meta_desc:
                content = meta_desc.get('content', '')
        
        # 내용 정리
        if content:
            # 연속된 공백 제거
            content = re.sub(r'\s+', ' ', content)
            # 최대 2000자로 제한
            content = content[:2000]
            return content.strip()
        
        return ""
        
    except Exception as e:
        print(f"본문 추출 오류 ({url}): {e}")
        return ""

def search_google_news(keyword, num_results=10):
    """구글 뉴스 검색 - RSS 피드와 웹 스크래핑 조합"""
    news_items = []
    
    # 방법 1: 구글 뉴스 RSS 피드 시도
    try:
        encoded_keyword = quote_plus(keyword)
        rss_url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl=ko&gl=KR&ceid=KR:ko"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(rss_url, headers=headers, timeout=10)
        if response.status_code == 200:
            # XML을 정규표현식으로 직접 파싱 (lxml 없이도 작동)
            import re
            content = response.text
            
            # <item> 태그 찾기
            items = re.findall(r'<item>(.*?)</item>', content, re.DOTALL)
            
            for item_xml in items[:num_results]:
                try:
                    # title 추출
                    title_match = re.search(r'<title>(.*?)</title>', item_xml, re.DOTALL)
                    # link 추출
                    link_match = re.search(r'<link>(.*?)</link>', item_xml, re.DOTALL)
                    # description 추출
                    desc_match = re.search(r'<description>(.*?)</description>', item_xml, re.DOTALL)
                    
                    if title_match and link_match:
                        title_text = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
                        link_text = link_match.group(1).strip()
                        snippet_text = ""
                        
                        if desc_match:
                            snippet_text = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()
                        
                        if title_text and link_text:
                            # 뉴스 본문 추출
                            content = extract_news_content(link_text)
                            news_items.append({
                                'title': title_text,
                                'link': link_text,
                                'snippet': snippet_text[:200] if snippet_text else "",
                                'content': content
                            })
                            time.sleep(0.5)  # 요청 간격 조절
                except Exception as e:
                    continue
            
            if news_items:
                return news_items[:num_results]
    except Exception as e:
        print(f"RSS 피드 오류: {e}")
    
    # 방법 2: 구글 뉴스 웹 검색 (개선된 파싱)
    try:
        encoded_keyword = quote_plus(keyword)
        search_url = f"https://news.google.com/search?q={encoded_keyword}&hl=ko&gl=KR&ceid=KR:ko"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9',
            'Referer': 'https://www.google.com/'
        }
        
        response = requests.get(search_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 구글 뉴스의 다양한 구조 시도
        # 최신 구조: article 태그
        articles = soup.find_all('article')
        
        if articles:
            for article in articles[:num_results * 2]:
                try:
                    # 제목과 링크 찾기
                    link_elem = article.find('a', href=True)
                    if not link_elem:
                        continue
                    
                    href = link_elem.get('href', '')
                    if href.startswith('./'):
                        href = 'https://news.google.com' + href[1:]
                    elif not href.startswith('http'):
                        continue
                    
                    # 제목 찾기
                    title_elem = (
                        link_elem.find('h3') or
                        link_elem.find('h4') or
                        article.find('h3') or
                        article.find('h4')
                    )
                    
                    if not title_elem:
                        title_text = link_elem.get_text(strip=True)
                    else:
                        title_text = title_elem.get_text(strip=True)
                    
                    # 스니펫 찾기
                    snippet_elem = (
                        article.find('div', class_='Y3v8qd') or
                        article.find('div', class_='GI74Re') or
                        article.find('span', class_='aCOpRe')
                    )
                    snippet_text = snippet_elem.get_text(strip=True) if snippet_elem else ""
                    
                    if title_text and len(title_text) > 3:
                        # 뉴스 본문 추출
                        content = extract_news_content(href)
                        news_items.append({
                            'title': title_text,
                            'link': href,
                            'snippet': snippet_text[:200] if snippet_text else "",
                            'content': content
                        })
                        time.sleep(0.5)  # 요청 간격 조절
                        
                        if len(news_items) >= num_results:
                            break
                except:
                    continue
        
        # 방법 3: 일반 구글 검색 페이지에서 뉴스 섹션 찾기
        if not news_items:
            search_url = f"https://www.google.com/search?q={encoded_keyword}&tbm=nws&num={num_results}&hl=ko"
            response = requests.get(search_url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 더 정확한 파싱: 뉴스 결과 컨테이너 찾기
                # 최신 구글 구조: div.MjjYud 또는 div.g
                containers = soup.find_all(['div'], class_=['MjjYud', 'g', 'SoaBEf', 'Ww4FFb'])
                
                for container in containers[:num_results * 3]:
                    try:
                        # 제목 찾기 - 여러 패턴 시도
                        title_elem = (
                            container.find('h3') or
                            container.find('h2') or
                            container.find('h4') or
                            container.find('a', {'role': 'heading'})
                        )
                        
                        if not title_elem:
                            # h3가 없으면 텍스트가 있는 링크 찾기
                            link_elem = container.find('a', href=True)
                            if link_elem:
                                title_text = link_elem.get_text(strip=True)
                                if title_text and len(title_text) > 3:
                                    href = link_elem.get('href', '')
                                    if '/url?q=' in href:
                                        url_part = href.split('/url?q=')[1].split('&')[0]
                                        url_part = requests.utils.unquote(url_part)
                                    elif href.startswith('http'):
                                        url_part = href
                                    else:
                                        continue
                                    
                                    if url_part.startswith('http') and 'google.com' not in url_part:
                                        snippet_elem = container.find('div', class_='VwiC3b') or container.find('span', class_='aCOpRe')
                                        snippet_text = snippet_elem.get_text(strip=True) if snippet_elem else ""
                                        
                                        if not any(item['link'] == url_part for item in news_items):
                                            # 뉴스 본문 추출
                                            content = extract_news_content(url_part)
                                            news_items.append({
                                                'title': title_text,
                                                'link': url_part,
                                                'snippet': snippet_text[:200] if snippet_text else "",
                                                'content': content
                                            })
                                            time.sleep(0.5)  # 요청 간격 조절
                                            
                                            if len(news_items) >= num_results:
                                                break
                            continue
                        
                        title_text = title_elem.get_text(strip=True)
                        if not title_text or len(title_text) < 3:
                            continue
                        
                        # 링크 찾기
                        link_elem = title_elem.find_parent('a', href=True)
                        if not link_elem:
                            link_elem = container.find('a', href=True)
                        
                        if link_elem:
                            href = link_elem.get('href', '')
                            if '/url?q=' in href:
                                url_part = href.split('/url?q=')[1].split('&')[0]
                                url_part = requests.utils.unquote(url_part)
                            elif href.startswith('http'):
                                url_part = href
                            else:
                                continue
                            
                            if url_part.startswith('http') and 'google.com' not in url_part:
                                # 스니펫 찾기
                                snippet_elem = (
                                    container.find('div', class_='VwiC3b') or
                                    container.find('div', class_='Y3v8qd') or
                                    container.find('span', class_='aCOpRe') or
                                    container.find('div', class_='GI74Re') or
                                    container.find('div', class_='s')
                                )
                                snippet_text = snippet_elem.get_text(strip=True) if snippet_elem else ""
                                
                                # 중복 체크
                                if not any(item['link'] == url_part for item in news_items):
                                    # 뉴스 본문 추출
                                    content = extract_news_content(url_part)
                                    news_items.append({
                                        'title': title_text,
                                        'link': url_part,
                                        'snippet': snippet_text[:200] if snippet_text else "",
                                        'content': content
                                    })
                                    time.sleep(0.5)  # 요청 간격 조절
                                    
                                    if len(news_items) >= num_results:
                                        break
                    except Exception as e:
                        continue
                
                # 여전히 결과가 없으면 모든 링크에서 찾기
                if not news_items:
                    for link in soup.find_all('a', href=True):
                        try:
                            href = link.get('href', '')
                            if '/url?q=' in href:
                                url_part = href.split('/url?q=')[1].split('&')[0]
                                url_part = requests.utils.unquote(url_part)
                                
                                if url_part.startswith('http') and 'google.com' not in url_part:
                                    title_text = link.get_text(strip=True)
                                    
                                    if title_text and len(title_text) > 3:
                                        # 중복 체크
                                        if not any(item['link'] == url_part for item in news_items):
                                            # 뉴스 본문 추출
                                            content = extract_news_content(url_part)
                                            news_items.append({
                                                'title': title_text,
                                                'link': url_part,
                                                'snippet': "",
                                                'content': content
                                            })
                                            time.sleep(0.5)  # 요청 간격 조절
                                            
                                            if len(news_items) >= num_results:
                                                break
                        except:
                            continue
        
        return news_items[:num_results]
        
    except Exception as e:
        print(f"웹 검색 오류: {e}")
        import traceback
        traceback.print_exc()
        return news_items[:num_results] if news_items else []

def summarize_news(news_items, keyword):
    """뉴스 요약 - Gemini API 사용"""
    if not news_items:
        return "검색된 뉴스가 없습니다."
    
    # 뉴스 정보를 텍스트로 정리
    news_text = f"키워드: {keyword}\n\n"
    for i, item in enumerate(news_items, 1):
        news_text += f"{i}. {item['title']}\n"
        if item.get('content'):
            news_text += f"   내용: {item['content'][:500]}\n"  # 본문 내용 사용
        elif item.get('snippet'):
            news_text += f"   요약: {item['snippet']}\n"
        news_text += f"   링크: {item['link']}\n\n"
    
    # Gemini API를 사용한 요약 (환경변수 GEMINI_API_KEY가 있을 때만)
    if not GEMINI_API_KEY:
        return simple_summarize(news_items, keyword)
    try:
        model = genai.GenerativeModel('gemini-pro')
        prompt = f"""당신은 뉴스 요약 전문가입니다. 주어진 뉴스들을 간결하고 명확하게 요약해주세요.

다음 뉴스들을 요약해주세요:

{news_text}

위 뉴스들을 종합하여 핵심 내용을 간결하게 요약해주세요."""
        
        response = model.generate_content(
            prompt,
            generation_config={
                'max_output_tokens': 800,
                'temperature': 0.7,
            }
        )
        return response.text
    except Exception as e:
        print(f"Gemini API 오류: {e}")
        import traceback
        traceback.print_exc()
        return simple_summarize(news_items, keyword)

def simple_summarize(news_items, keyword):
    """간단한 요약 (OpenAI API 없이)"""
    summary = f"'{keyword}' 관련 뉴스 {len(news_items)}개를 찾았습니다:\n\n"
    
    for i, item in enumerate(news_items, 1):
        summary += f"【{i}】 {item['title']}\n"
        if item.get('content'):
            summary += f"   {item['content'][:300]}...\n"  # 본문 내용 표시
        elif item.get('snippet'):
            summary += f"   {item['snippet']}\n"
        summary += f"   링크: {item['link']}\n\n"
    
    return summary


def build_news_context(news_items, max_items=6):
    """대화용 뉴스 컨텍스트 문자열 생성"""
    lines = []
    for i, item in enumerate(news_items[:max_items], 1):
        title = item.get("title", "")
        content = item.get("content") or item.get("snippet") or ""
        content = (content or "")[:600]
        lines.append(f"{i}. 제목: {title}\n   내용: {content}")
    return "\n\n".join(lines)


def simple_chat_answer(question, news_items, keyword):
    """API 없이 동작하는 Q&A - 질문에 따라 답변 형식을 다르게"""
    question_lower = question.strip().lower()
    scored = []
    for item in news_items:
        text = (item.get("title", "") + " " + (item.get("content") or "")).lower()
        score = sum(1 for w in question_lower.split() if len(w) > 1 and w in text)
        scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)

    top = [it for s, it in scored if s > 0][:4] or [it for _, it in scored[:4]]
    if not top:
        return f"'{keyword}' 관련 뉴스는 있는데, 이 질문과 딱 맞는 내용은 찾기 어려워요. 다른 방식으로 물어보시거나, 더 구체적인 질문을 주시면 도와드릴게요."

    # 질문 유형에 따라 인사/도입 문구를 다르게
    q = question.strip()
    if any(w in q for w in ["요약", "총정리", "한번에", "전체"]):
        intro = "요약해드릴게요. "
    elif any(w in q for w in ["왜", "이유", "원인", "왜"]):
        intro = "이유나 배경 위주로 정리해볼게요. "
    elif any(w in q for w in ["어떻게", "방법", "대응", "대처"]):
        intro = "방법이나 대응 쪽으로 말씀드릴게요. "
    elif any(w in q for w in ["뭐가", "무엇", "뭐야", "핵심"]):
        intro = "핵심만 말씀드리면요. "
    else:
        intro = "질문하신 걸 기준으로 뉴스에서 찾아본 내용이에요. "

    lines = [intro]
    for i, item in enumerate(top, 1):
        title = item.get("title", "")
        content = item.get("content") or item.get("snippet") or ""
        lines.append(f"• {title}")
        if content:
            lines.append(f"  {content[:240].strip()}{'...' if len(content) > 240 else ''}")
    return "\n".join(lines)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/search', methods=['POST'])
def search():
    global last_search
    try:
        data = request.json or {}
        keyword = data.get('keyword', '').strip()
        
        if not keyword:
            return jsonify({'error': '키워드를 입력해주세요.'}), 400
        
        # 뉴스 검색
        news_items = search_google_news(keyword, num_results=10)
        
        if not news_items:
            return jsonify({
                'error': '뉴스를 찾을 수 없습니다. 다른 키워드로 시도해보세요.',
                'news': [],
                'summary': ''
            }), 404
        
        # 뉴스 요약
        summary = summarize_news(news_items, keyword)

        # 최근 검색 결과 갱신 (대화 기능용)
        last_search = {
            "keyword": keyword,
            "news": news_items,
            "summary": summary
        }

        # 검색 히스토리 저장
        save_history(keyword, news_items, summary)
        
        return jsonify({
            'success': True,
            'keyword': keyword,
            'news': news_items,
            'summary': summary,
            'count': len(news_items)
        })
    
    except Exception as e:
        return jsonify({'error': f'오류가 발생했습니다: {str(e)}'}), 500


@app.route('/chat', methods=['POST'])
def chat_with_news():
    """수집한 뉴스들을 가지고 대화하는 엔드포인트 - Gemini API 사용"""
    try:
        data = request.json or {}
        question = data.get('question', '').strip()

        if not question:
            return jsonify({'error': '질문을 입력해주세요.'}), 400

        if not last_search.get("news"):
            return jsonify({'error': '먼저 키워드를 검색해서 뉴스를 불러와 주세요.'}), 400

        keyword = last_search.get("keyword") or ""
        news_items = last_search.get("news") or []

        # Gemini API 사용 (환경변수 GEMINI_API_KEY가 있을 때만)
        if not GEMINI_API_KEY:
            answer = simple_chat_answer(question, news_items, keyword)
        else:
            try:
                context = build_news_context(news_items)
                model = genai.GenerativeModel('gemini-pro')
                prompt = f"""당신은 뉴스에 대해 대화하는 친근한 전문가입니다.

【중요】
- 사용자의 질문에 **정확히 맞는** 답만 하세요. 질문이 바뀌면 답도 완전히 달라져야 합니다.
- "요약해줘", "핵심만", "어떤 게 중요해?" 등 질문 유형에 맞게 **그 질문에만 해당하는** 답을 하세요.
- 뉴스 내용을 근거로 하되, 말투는 자연스럽고 자유롭게. 짧은 질문에는 짧게, 구체적인 질문에는 구체적으로 답하세요.
- 뉴스에 없는 내용은 추측하지 말고 "뉴스에서는 이 부분이 안 나와 있어요"처럼 말하세요.

키워드: {keyword}

뉴스 목록:
{context}

사용자 질문: {question}

위 뉴스만 참고해서, **이 질문에만 해당하는** 답변을 자유롭게 해주세요."""
                response = model.generate_content(
                    prompt,
                    generation_config={
                        'max_output_tokens': 1024,
                        'temperature': 0.8,
                    }
                )
                answer = response.text
            except Exception as e:
                print(f"뉴스 대화 Gemini API 오류: {e}")
                import traceback
                traceback.print_exc()
                answer = simple_chat_answer(question, news_items, keyword)

        return jsonify({
            "success": True,
            "answer": answer
        })

    except Exception as e:
        return jsonify({'error': f'대화 처리 중 오류가 발생했습니다: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
