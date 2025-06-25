# 검색기능은 단일 검색어 기준. 공백포함 문자열 검색 가능. 가운뎃점 중간점 정규화 기능
# 개정문생성은 큰따옴표로 감싸서 문자열로 지원함. 
# 개정문생성 결과에서 원하는 특정 법률을 배제할 수 있도록 함.
# 가운뎃점(U+318D) 대신 샵(#)을 쓸 수 있도록 함. 찾을 문자열, 바꿀 문자열 모두.
# 개정문 결과에서 특정 법률을 배제할 수 있는 기능 추가
# 낫표를 중괄호로 입력할 수 있음. <- 이 부분에 대한 수정이 적용되었습니다.

import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote
import re
import os
import unicodedata
from collections import defaultdict

# API 호출을 위한 환경 변수 설정. 실제 배포 시에는 보안에 유의해야 합니다.
OC = os.getenv("OC", "chetera")
BASE = "http://www.law.go.kr"

def highlight(text, query):
    """
    검색어를 HTML로 하이라이트 처리해주는 함수.
    검색어 전처리 및 정규식 특수 문자 이스케이프를 포함합니다.
    """
    if not query or not text:
        return text
    
    # 중간점을 가운뎃점으로 정규화 (하이라이트에서도 일관성 유지)
    # 이제 중괄호도 낫표로 정규화됩니다.
    normalized_query = normalize_special_chars(query)
    
    # 검색어 전처리: 큰따옴표로 감싸진 경우 제거
    processed_query, _ = preprocess_search_term(normalized_query)
    
    # 정규식 특수문자 이스케이프
    escaped_query = re.escape(processed_query)
    
    # 유니코드를 고려한 정규식 패턴 (re.UNICODE 플래그 추가)
    # 대소문자 무시 (re.IGNORECASE) 및 유니코드 문자열 처리 (re.UNICODE)
    pattern = re.compile(f'({escaped_query})', re.IGNORECASE | re.UNICODE)
    
    # 찾은 검색어를 <mark> 태그로 감싸 하이라이트
    return pattern.sub(r'<mark>\1</mark>', text)

def get_law_list_from_api(query):
    """
    법제처 API를 통해 검색어에 해당하는 법령 목록을 가져오는 함수.
    페이지네이션을 지원하여 모든 검색 결과를 가져옵니다.
    """
    # 이미 큰따옴표로 감싸져 있는지 확인
    if query.startswith('"') and query.endswith('"'):
        exact_query = query  # 이미 큰따옴표가 있으면 그대로 사용
    else:
        exact_query = f'"{query}"'  # 없으면 추가하여 정확히 일치하는 검색을 유도

    # 유니코드 문자를 올바르게 인코딩: UTF-8 바이트로 변환 후 URL 인코딩
    # API 요청 시 한글 깨짐 방지를 위해 인코딩 처리
    if isinstance(exact_query, str):
        # 문자열인 경우 UTF-8로 인코딩한 후 quote 적용
        encoded_query = quote(exact_query.encode('utf-8'), safe='')
    else:
        # 이미 바이트인 경우 그대로 quote 적용
        encoded_query = quote(exact_query, safe='')
    
    page = 1
    laws = []
    
    # 디버깅을 위해 실제 검색 쿼리 출력
    print(f"API 검색 쿼리: {exact_query}")
    
    while True:
        # 법제처 법률 검색 API URL
        url = f"{BASE}/DRF/lawSearch.do?OC={OC}&target=law&type=XML&display=100&page={page}&search=2&knd=A0002&query={encoded_query}"
        try:
            res = requests.get(url, timeout=10) # 10초 타임아웃 설정
            res.encoding = 'utf-8' # 응답 인코딩을 UTF-8로 설정하여 한글 깨짐 방지
            if res.status_code != 200:
                # HTTP 상태 코드가 200이 아니면 오류로 간주하고 반복 중단
                print(f"API 요청 실패: 상태 코드 {res.status_code}")
                break
            
            root = ET.fromstring(res.content) # XML 응답 파싱
            
            # 모든 <law> 태그를 찾아 법령 정보 추출
            for law in root.findall("law"):
                laws.append({
                    "법령명": law.findtext("법령명한글", "").strip(), # 법령명 추출
                    "MST": law.findtext("법령일련번호", "") # 법령일련번호 (Master Serial Number) 추출
                })
            
            # 현재 페이지의 결과 수가 display 값(100)보다 적으면 마지막 페이지로 간주
            if len(root.findall("law")) < 100:
                break
            
            page += 1 # 다음 페이지로 이동
        except requests.exceptions.Timeout:
            print(f"법률 검색 중 타임아웃 발생: {url}")
            break
        except requests.exceptions.RequestException as e:
            print(f"법률 검색 중 요청 오류 발생: {e}")
            break
        except ET.ParseError as e:
            print(f"법률 검색 결과 XML 파싱 오류: {e}")
            break
        except Exception as e:
            print(f"법률 검색 중 알 수 없는 오류 발생: {e}")
            break
    
    # 디버깅을 위해 검색된 법률 목록 출력
    print(f"검색된 법률 수: {len(laws)}")
    for idx, law in enumerate(laws[:3]):  # 처음 3개만 출력
        print(f"{idx+1}. {law['법령명']}")
    
    return laws

def get_law_text_by_mst(mst):
    """
    법령일련번호(MST)를 사용하여 특정 법령의 전체 XML 데이터를 가져오는 함수.
    """
    url = f"{BASE}/DRF/lawService.do?OC={OC}&target=law&MST={mst}&type=XML"
    try:
        res = requests.get(url, timeout=10) # 10초 타임아웃 설정
        res.encoding = 'utf-8' # 응답 인코딩을 UTF-8로 설정
        if res.status_code == 200:
            return res.content
        else:
            print(f"법령 XML 가져오기 실패: 상태 코드 {res.status_code} for MST {mst}")
            return None
    except requests.exceptions.Timeout:
        print(f"법령 XML 가져오기 중 타임아웃 발생: MST {mst}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"법령 XML 가져오기 중 요청 오류 발생: {e} for MST {mst}")
        return None
    except Exception as e:
        print(f"법령 XML 가져오기 중 알 수 없는 오류 발생: {e} for MST {mst}")
        return None

def clean(text):
    """텍스트에서 모든 공백을 제거하는 함수 (검색 매칭 시 사용)"""
    return re.sub(r"\s+", "", text or "")

def normalize_special_chars(text):
    """
    특수문자를 정규화하는 함수: 중간점, 마침표, 중괄호, 샵(#)을 적절한 문자로 변환.
    이 함수에서 중괄호를 낫표로 변환하는 로직을 추가합니다.
    """
    if text:
        # 샵(#)을 가운뎃점(U+318D)으로 변환 (사용자 입력 편의성)
        text = text.replace('#', 'ㆍ')
        # 중간점(U+00B7)을 가운뎃점(U+318D)으로 변환
        text = text.replace('·', 'ㆍ')  
        # 마침표(.)를 가운뎃점(U+318D)으로 변환
        text = text.replace('.', 'ㆍ')
        # 중괄호를 법률 인용 기호(낫표)로 변환 (사용자 요청 사항)
        text = text.replace('{', '「')  # 왼쪽 중괄호를 왼쪽 낫표로
        text = text.replace('}', '」')  # 오른쪽 중괄호를 오른쪽 낫표로
    return text

def normalize_number(text):
    """유니코드 숫자를 일반 숫자로 변환 시도 (실패 시 원본 반환)"""
    try:
        return str(int(unicodedata.numeric(text)))
    except:
        return text

def make_article_number(조문번호, 조문가지번호):
    """조문 번호와 가지 번호를 조합하여 표준 형식 문자열을 생성"""
    return f"제{조문번호}조의{조문가지번호}" if 조문가지번호 and 조문가지번호 != "0" else f"제{조문번호}조"

def has_batchim(word):
    """단어의 마지막 글자에 받침이 있는지 확인하는 함수 (한국어 조사 규칙 적용 위함)"""
    if not word:
        return False
    
    last_char = word[-1]
    # 한글 유니코드 범위: AC00-D7A3
    if '가' <= last_char <= '힣':
        # 한글 유니코드 계산식: [(초성 * 21) + 중성] * 28 + 종성 + 0xAC00
        char_code = ord(last_char)
        # 종성 값 추출 (0은 받침 없음, 1-27은 받침 있음)
        jongseong = (char_code - 0xAC00) % 28
        return jongseong != 0
    return False

def has_rieul_batchim(word):
    """단어의 마지막 글자에 'ㄹ' 받침이 있는지 확인하는 함수 (한국어 조사 규칙 적용 위함)"""
    if not word:
        return False
    
    last_char = word[-1]
    if '가' <= last_char <= '힣':
        char_code = ord(last_char)
        # 종성 값 추출 (8은 'ㄹ' 받침)
        jongseong = (char_code - 0xAC00) % 28
        return jongseong == 8
    return False
    
def extract_article_num(loc):
    """조번호를 추출하여 정수로 변환하는 함수 (정렬에 사용)"""
    article_match = re.search(r'제(\d+)조(?:의(\d+))?', loc)
    if not article_match:
        return (0, 0)
    
    # 조번호를 정수로 변환 (37 < 357 정렬을 위해)
    article_num = int(article_match.group(1))
    # 조 가지 번호는 보조 정렬 키로 사용 (없으면 0)
    article_sub = int(article_match.group(2)) if article_match.group(2) else 0
    
    return (article_num, article_sub)

def extract_chunk_and_josa(token, searchword):
    """
    검색어를 포함하는 덩어리(단어/구문)와 뒤에 붙는 조사 또는 접미사를 추출하는 함수.
    이 함수는 단어 단위 검색 결과에 대한 조사를 처리합니다.
    """
    # 검색어의 앞뒤 공백 제거 (trim)
    searchword = searchword.strip()
    
    # 제외할 접미사 리스트 (덩어리에 포함시키지 않을 것들, 예를 들어 '등'은 본 단어가 아님)
    suffix_exclude = ["의", "에", "에서", "에게", 
                      "등", "등의", "등인", "등만", "등에", "만", "만을", "만이", "만은", "만에", "만으로"]
    
    # 처리할 조사 리스트 (규칙에 따른 18가지 조사 및 따옴표 포함 변형)
    josa_list = ["을", "를", "과", "와", "이", "가", "이나", "나", "으로", "로", "은", "는", 
                 "란", "이란", "라", "이라", "로서", "으로서", "로써", "으로써",
                 "\"란", "\"이란", "\"라", "\"이라"] # 따옴표가 있는 경우 추가 (예: "이라는")
    
    # 원본 토큰 저장
    original_token = token
    suffix = None # 추출된 접미사를 저장할 변수
    
    # 검색어 자체가 토큰인 경우 (조사나 접미사가 없는 경우)
    if token == searchword:
        return token, None, None
    
    # 토큰에 검색어가 포함되어 있지 않으면 바로 반환
    # 이 조건은 searchword가 token의 일부인 경우를 먼저 거르기 위함
    if searchword not in token:
        return token, None, None
    
    # 토큰이 검색어로 시작하는지 확인 (접두사로 붙는 경우 제외)
    if not token.startswith(searchword):
        # 검색어가 토큰 중간에 있는 경우 (다른 단어의 일부)
        # 예: "대한민국법원"에서 "민국법원"을 찾을 때, "대한"은 "대한민국법원"의 일부이므로 전체 토큰을 반환
        return token, None, None
    
    # 1. 접미사 제거 시도 (덩어리에 포함시키지 않음)
    # 가장 긴 접미사부터 확인하여 정확한 매칭을 유도
    for s in sorted(suffix_exclude, key=len, reverse=True):
        if token == searchword + s:
            # 정확히 "검색어+접미사"인 경우 (예: "지방법원에"에서 검색어 "지방법원"에 "에"가 붙은 경우)
            print(f"접미사 처리: '{token}' = '{searchword}' + '{s}'") # 디버깅
            return searchword, None, s # 검색어와 접미사 분리하여 반환
    
    # 2. 조사 확인 (조사는 규칙에 따라 처리)
    # 가장 긴 조사부터 확인하여 정확한 매칭을 유도
    for j in sorted(josa_list, key=len, reverse=True):
        if token == searchword + j:
            # 정확히 "검색어+조사"인 경우 (예: "지방법원을"에서 검색어 "지방법원"에 "을"이 붙은 경우)
            print(f"조사 처리: '{token}' = '{searchword}' + '{j}'") # 디버깅
            
            # 특수 케이스: 따옴표가 있는 조사 처리 (예: "\"란")
            if j.startswith("\""):
                # 따옴표를 제거한 기본 조사 부분만 반환
                base_josa = j[1:]
                return searchword, base_josa, None
            
            return searchword, j, None # 검색어와 조사 분리하여 반환
    
    # 3. 덩어리 처리 (검색어 뒤에 다른 문자가 있는 경우, 조사나 접미사가 아닌 경우)
    if token.startswith(searchword) and len(token) > len(searchword):
        # 예: "지방법원판사", "지방법원장" 등 (검색어 뒤에 다른 단어가 붙어 하나의 단어를 이루는 경우)
        print(f"덩어리 전체 처리: '{token}' (검색어: '{searchword}')") # 디버깅
        return token, None, None # 토큰 전체를 덩어리로 반환
    
    # 기본 반환 - 위에 해당하지 않는 경우 토큰 전체를 덩어리로 간주
    return token, None, None

def preprocess_search_term(search_term):
    """
    검색어를 전처리하는 함수.
    입력된 검색어가 큰따옴표로 묶여 있는지 확인하고, 그에 따라 구문 검색 여부를 결정합니다.
    """
    # 큰따옴표로 묶인 문자열인지 확인 (예: "특정범죄 가중처벌 등에 관한 법률")
    if search_term.startswith('"') and search_term.endswith('"'):
        # 따옴표 제거하고 구문으로 처리하도록 True 반환
        return search_term[1:-1], True
    else:
        # 일반 단어로 처리하도록 False 반환
        return search_term, False

def find_phrase_with_josa(text, phrase):
    """
    공백 포함 문자열(구문)과 그 뒤에 올 수 있는 조사를 찾아 반환하는 함수.
    개정문 생성 시 구문 단위 처리를 위해 사용됩니다.
    """
    # 검색 구문에서 앞뒤 공백 제거 (trim)
    phrase = phrase.strip()
    
    matches = []
    start_pos = 0
    
    while True:
        # 구문 위치 찾기
        pos = text.find(phrase, start_pos)
        if pos == -1:
            break # 더 이상 찾을 수 없으면 반복 종료
        
        # 구문 끝 위치
        end_pos = pos + len(phrase)
        
        # 조사가 있는지 확인 (구문 뒤 1-4글자 내에서)
        max_josa_len = min(4, len(text) - end_pos) # 최대 4글자까지 조사로 간주
        potential_josa = text[end_pos:end_pos + max_josa_len]
        
        # 조사 후보 리스트 (자주 사용되는 조사를 길이에 따라 정렬하여 가장 긴 것부터 매칭)
        josa_candidates = ["을", "를", "과", "와", "이", "가", "은", "는", 
                           "이나", "나", "으로", "로", "로서", "으로서", "로써", "으로써"]
        
        found_josa = None
        
        # 가장 긴 조사부터 확인하여 매칭되는 조사 찾기
        for josa in sorted(josa_candidates, key=len, reverse=True):
            if potential_josa.startswith(josa):
                found_josa = josa
                break # 가장 긴 매칭을 찾으면 중단
        
        # 구문과 조사 정보 추가
        matches.append((pos, phrase, found_josa))
        
        # 다음 검색 시작 위치 (현재 찾은 구문 다음 글자부터)
        start_pos = pos + 1
    
    return matches

def apply_josa_rule(orig, replaced, josa):
    """
    개정문 생성 시 한국어 조사 규칙에 따라 적절한 출력 형식을 반환하는 함수.
    원본 단어(orig)와 대체될 단어(replaced)의 받침 유무, 조사(josa)에 따라 18가지 규칙을 적용합니다.
    """
    # 동일한 단어면 변경할 필요 없음
    if orig == replaced:
        return f'"{orig}"를 "{replaced}"로 한다.'
        
    # 받침 여부 확인
    orig_has_batchim = has_batchim(orig)
    replaced_has_batchim = has_batchim(replaced)
    replaced_has_rieul = has_rieul_batchim(replaced)
    
    # 조사가 없는 경우 (규칙 0)
    if josa is None:
        if not orig_has_batchim:  # 규칙 0-1: A(원본)가 받침 없는 경우
            if not replaced_has_batchim or replaced_has_rieul:  # 규칙 0-1-1, 0-1-2-1
                return f'"{orig}"를 "{replaced}"로 한다.'
            else:  # 규칙 0-1-2-2: B(바꿀 단어)의 받침이 ㄹ이 아닌 경우
                return f'"{orig}"를 "{replaced}"으로 한다.'
        else:  # 규칙 0-2: A(원본)가 받침 있는 경우
            if not replaced_has_batchim or replaced_has_rieul:  # 규칙 0-2-1, 0-2-2-1
                return f'"{orig}"을 "{replaced}"로 한다.'
            else:  # 규칙 0-2-2-2: B(바꿀 단어)의 받침이 ㄹ이 아닌 경우
                return f'"{orig}"을 "{replaced}"으로 한다.'
    
    # 따옴표가 있는 경우 조사에서 따옴표 제거 (예: "\"란" -> "란")
    clean_josa = josa
    if josa and josa.startswith('"'):
        clean_josa = josa[1:]
    
    # 조사별 규칙 처리
    if clean_josa == "을":  # 규칙 1: A을 -> B을/를/으로/로
        if replaced_has_batchim: # B에 받침이 있는 경우
            if replaced_has_rieul:  # 규칙 1-1-1: B의 받침이 ㄹ인 경우
                return f'"{orig}"을 "{replaced}"로 한다.'
            else:  # 규칙 1-1-2: B의 받침이 ㄹ이 아닌 경우
                return f'"{orig}"을 "{replaced}"으로 한다.'
        else:  # 규칙 1-2: B에 받침이 없는 경우
            return f'"{orig}을"을 "{replaced}를"로 한다.'
    
    elif clean_josa == "를":  # 규칙 2: A를 -> B을/를
        if replaced_has_batchim:  # 규칙 2-1: B에 받침이 있는 경우
            return f'"{orig}를"을 "{replaced}을"로 한다.'
        else:  # 규칙 2-2: B에 받침이 없는 경우
            return f'"{orig}"를 "{replaced}"로 한다.'
    
    elif clean_josa == "과":  # 규칙 3: A과 -> B과/와/으로/로
        if replaced_has_batchim: # B에 받침이 있는 경우
            if replaced_has_rieul:  # 규칙 3-1-1: B의 받침이 ㄹ인 경우
                return f'"{orig}"을 "{replaced}"로 한다.'
            else:  # 규칙 3-1-2: B의 받침이 ㄹ이 아닌 경우
                return f'"{orig}"을 "{replaced}"으로 한다.'
        else:  # 규칙 3-2: B에 받침이 없는 경우
            return f'"{orig}과"를 "{replaced}와"로 한다.'
    
    elif clean_josa == "와":  # 규칙 4: A와 -> B과/와
        if replaced_has_batchim:  # 규칙 4-1: B에 받침이 있는 경우
            return f'"{orig}와"를 "{replaced}과"로 한다.'
        else:  # 규칙 4-2: B에 받침이 없는 경우
            return f'"{orig}"를 "{replaced}"로 한다.'
    
    elif clean_josa == "이":  # 규칙 5: A이 -> B이/가/으로/로
        if replaced_has_batchim: # B에 받침이 있는 경우
            if replaced_has_rieul:  # 규칙 5-1-1: B의 받침이 ㄹ인 경우
                return f'"{orig}"을 "{replaced}"로 한다.'
            else:  # 규칙 5-1-2: B의 받침이 ㄹ이 아닌 경우
                return f'"{orig}"을 "{replaced}"으로 한다.'
        else:  # 규칙 5-2: B에 받침이 없는 경우
            return f'"{orig}이"를 "{replaced}가"로 한다.'
    
    elif clean_josa == "가":  # 규칙 6: A가 -> B이/가
        if replaced_has_batchim:  # 규칙 6-1: B에 받침이 있는 경우
            return f'"{orig}가"를 "{replaced}이"로 한다.'
        else:  # 규칙 6-2: B에 받침이 없는 경우
            return f'"{orig}"를 "{replaced}"로 한다.'
    
    elif clean_josa == "이나":  # 규칙 7: A이나 -> B이나/나/으로/로
        if replaced_has_batchim: # B에 받침이 있는 경우
            if replaced_has_rieul:  # 규칙 7-1-1: B의 받침이 ㄹ인 경우
                return f'"{orig}"을 "{replaced}"로 한다.'
            else:  # 규칙 7-1-2: B의 받침이 ㄹ이 아닌 경우
                return f'"{orig}"을 "{replaced}"으로 한다.'
        else:  # 규칙 7-2: B에 받침이 없는 경우
            return f'"{orig}이나"를 "{replaced}나"로 한다.'
    
    elif clean_josa == "나":  # 규칙 8: 아나 -> B이나/나
        if replaced_has_batchim:  # 규칙 8-1: B에 받침이 있는 경우
            return f'"{orig}나"를 "{replaced}이나"로 한다.'
        else:  # 규칙 8-2: B에 받침이 없는 경우
            return f'"{orig}"를 "{replaced}"로 한다.'
    
    elif clean_josa == "으로":  # 규칙 9: A으로 -> B으로/로
        if replaced_has_batchim: # B에 받침이 있는 경우
            if replaced_has_rieul:  # 규칙 9-1-1: B의 받침이 ㄹ인 경우
                return f'"{orig}으로"를 "{replaced}로"로 한다.'
            else:  # 규칙 9-1-2: B의 받침이 ㄹ이 아닌 경우
                return f'"{orig}"을 "{replaced}"으로 한다.'
        else:  # 규칙 9-2: B에 받침이 없는 경우
            return f'"{orig}으로"를 "{replaced}로"로 한다.'
    
    elif clean_josa == "로":  # 규칙 10: A로 -> B으로/로
        if orig_has_batchim:  # 규칙 10-1: A(원본)에 받침이 있는 경우
            if replaced_has_batchim: # B에 받침이 있는 경우
                if replaced_has_rieul:  # 규칙 10-1-1-1: B의 받침이 ㄹ인 경우
                    return f'"{orig}"을 "{replaced}"로 한다.'
                else:  # 규칙 10-1-1-2: B의 받침이 ㄹ이 아닌 경우
                    return f'"{orig}로"를 "{replaced}으로"로 한다.'
            else:  # 규칙 10-1-2: B에 받침이 없는 경우
                return f'"{orig}"을 "{replaced}"로 한다.'
        else:  # 규칙 10-2: A(원본)에 받침이 없는 경우
            if replaced_has_batchim: # B에 받침이 있는 경우
                if replaced_has_rieul:  # 규칙 10-2-1-1: B의 받침이 ㄹ인 경우
                    return f'"{orig}"를 "{replaced}"로 한다.'
                else:  # 규칙 10-2-1-2: B의 받침이 ㄹ이 아닌 경우
                    return f'"{orig}로"를 "{replaced}으로"로 한다.'
            else:  # 규칙 10-2-2: B에 받침이 없는 경우
                return f'"{orig}"를 "{replaced}"로 한다.'
    
    elif clean_josa == "는":  # 규칙 11: A는 -> B은/는
        if replaced_has_batchim:  # 규칙 11-1: B에 받침이 있는 경우
            return f'"{orig}는"을 "{replaced}은"으로 한다.'
        else:  # 규칙 11-2: B에 받침이 없는 경우
            return f'"{orig}"를 "{replaced}"로 한다.'
    
    elif clean_josa == "은":  # 규칙 12: A은 -> B은/는/으로/로
        if replaced_has_batchim: # B에 받침이 있는 경우
            if replaced_has_rieul:  # 규칙 12-1-1: B의 받침이 ㄹ인 경우
                return f'"{orig}"을 "{replaced}"로 한다.'
            else:  # 규칙 12-1-2: B의 받침이 ㄹ이 아닌 경우
                return f'"{orig}"을 "{replaced}"으로 한다.'
        else:  # 규칙 12-2: B에 받침이 없는 경우
            return f'"{orig}은"을 "{replaced}는"으로 한다.'
    
    elif clean_josa == "란":  # 규칙 13: A란 -> B이란/란
        if replaced_has_batchim:  # 규칙 13-1: B에 받침이 있는 경우
            quote_prefix = '"' if josa and josa.startswith('"') else ""
            return f'"{orig}{josa}"을 "{replaced}이{quote_prefix}란"으로 한다.'
        else:  # 규칙 13-2: B에 받침이 없는 경우
            return f'"{orig}"를 "{replaced}"로 한다.'
    
    elif clean_josa == "이란":  # 규칙 14: A이란 -> B이란/란
        if replaced_has_batchim: # B에 받침이 있는 경우
            if replaced_has_rieul:  # 규칙 14-1-1: B의 받침이 ㄹ인 경우
                return f'"{orig}"을 "{replaced}"로 한다.'
            else:  # 규칙 14-1-2: B의 받침이 ㄹ이 아닌 경우
                return f'"{orig}"을 "{replaced}"으로 한다.'
        else:  # 규칙 14-2: B에 받침이 없는 경우
            quote_prefix = '"' if josa and josa.startswith('"') else ""
            return f'"{orig}{josa}"을 "{replaced}{quote_prefix}라"로 한다.'
    
    elif clean_josa == "로서" or clean_josa == "로써":  # 규칙 15: A로서/로써 -> B으로서/으로써/로서/로써
        if orig_has_batchim:  # 규칙 15-1: A에 받침이 있는 경우
            if replaced_has_batchim: # B에 받침이 있는 경우
                if replaced_has_rieul:  # 규칙 15-1-1-1: B의 받침이 ㄹ인 경우
                    return f'"{orig}"을 "{replaced}"로 한다.'
                else:  # 규칙 15-1-1-2: B의 받침이 ㄹ이 아닌 경우
                    return f'"{orig}{josa}"를 "{replaced}으{clean_josa}"로 한다.'
            else:  # 규칙 15-1-2: B에 받침이 없는 경우
                return f'"{orig}"을 "{replaced}"로 한다.'
        else:  # 규칙 15-2: A에 받침이 없는 경우
            if replaced_has_batchim: # B에 받침이 있는 경우
                if replaced_has_rieul:  # 규칙 15-2-1-1: B의 받침이 ㄹ인 경우
                    return f'"{orig}"를 "{replaced}"로 한다.'
                else:  # 규칙 15-2-1-2: B의 받침이 ㄹ이 아닌 경우
                    return f'"{orig}{josa}"를 "{replaced}으{clean_josa}"로 한다.'
            else:  # 규칙 15-2-2: B에 받침이 없는 경우
                return f'"{orig}"를 "{replaced}"로 한다.'
    
    elif clean_josa == "으로서" or clean_josa == "으로써":  # 규칙 16: A으로서/으로써 -> B으로서/으로써/로서/로써
        if replaced_has_batchim: # B에 받침이 있는 경우
            if replaced_has_rieul:  # 규칙 16-1-1: B의 받침이 ㄹ인 경우
                return f'"{orig}{josa}"를 "{replaced}로{clean_josa[2:]}"로 한다.'
            else:  # 규칙 16-1-2: B의 받침이 ㄹ이 아닌 경우
                return f'"{orig}"을 "{replaced}"으로 한다.'
        else:  # 규칙 16-2: B에 받침이 없는 경우
            return f'"{orig}{josa}"를 "{replaced}로{clean_josa[2:]}"로 한다.'
    
    elif clean_josa == "라":  # 규칙 17: A라 -> B이라/라
        if replaced_has_batchim:  # 규칙 17-1: B에 받침이 있는 경우
            quote_prefix = '"' if josa and josa.startswith('"') else ""
            return f'"{orig}{josa}"를 "{replaced}이{quote_prefix}라"로 한다.'
        else:  # 규칙 17-2: B에 받침이 없는 경우
            return f'"{orig}"를 "{replaced}"로 한다.'
    
    elif clean_josa == "이라":  # 규칙 18: A이라 -> B이라/라
        if replaced_has_batchim: # B에 받침이 있는 경우
            if replaced_has_rieul:  # 규칙 18-1-1: B의 받침이 ㄹ인 경우
                return f'"{orig}"을 "{replaced}"로 한다.'
            else:  # 규칙 18-1-2: B의 받침이 ㄹ이 아닌 경우
                return f'"{orig}"을 "{replaced}"으로 한다.'
        else:  # 규칙 18-2: B에 받침이 없는 경우
            quote_prefix = '"' if josa and josa.startswith('"') else ""
            return f'"{orig}{josa}"을 "{replaced}{quote_prefix}라"로 한다.'
    
    # 기본 출력 형식 (위에 정의된 규칙에 해당하지 않는 경우)
    if orig_has_batchim:
        return f'"{orig}"을 "{replaced}"로 한다.'
    else:
        return f'"{orig}"를 "{replaced}"로 한다.'

def format_location(loc):
    """
    위치 정보 문자열의 형식을 수정하는 함수.
    항번호가 비어있는 경우 '제항' 제거 및 호번호, 목번호 뒤의 '.' 제거 등을 처리합니다.
    """
    # '제항'이라는 불필요한 문자열 제거 (예: '제1조제항' -> '제1조')
    loc = re.sub(r'제(?=항)', '', loc)
    
    # 호번호와 목번호 뒤의 period(.) 제거 (예: '1.호' -> '1호')
    loc = re.sub(r'(\d+)\.호', r'\1호', loc)
    # '가.목' -> '가목'
    loc = re.sub(r'([가-힣])\.목', r'\1목', loc)
    
    return loc

def group_locations(loc_list):
    """
    위치 정보 목록을 조 > 항 > 호 > 목 순서로 정렬하고 그룹화하여 가독성 있는 문자열로 반환.
    - 조 또는 항이 바뀌면 콤마(,)로 연결
    - 같은 조항 내 호목은 가운뎃점(ㆍ)으로 연결
    - 마지막은 '및'으로 연결
    """
    if not loc_list:
        return ""
    
    # 각 위치 문자열에 형식 수정 적용
    formatted_locs = [format_location(loc) for loc in loc_list]
    
    # 조항호목 파싱 함수 (모든 정렬 기준 추출)
    def parse_location(loc):
        # 조번호 (정수로 변환)
        article_match = re.search(r'제(\d+)조(?:의(\d+))?', loc)
        article_num = int(article_match.group(1)) if article_match else 0
        article_sub = int(article_match.group(2)) if article_match and article_match.group(2) else 0
        
        # 항번호 (정수로 변환)
        clause_match = re.search(r'제(\d+)항', loc)
        clause_num = int(clause_match.group(1)) if clause_match else 0
        
        # 호번호 (정수로 변환)
        item_match = re.search(r'제(\d+)호(?:의(\d+))?', loc)
        item_num = int(item_match.group(1)) if item_match else 0
        item_sub = int(item_match.group(2)) if item_match and item_match.group(2) else 0
        
        # 목번호 (가나다 순서, '가'부터 시작하여 숫자로 변환)
        subitem_match = re.search(r'([가-힣])목', loc)
        subitem_num = ord(subitem_match.group(1)) - ord('가') + 1 if subitem_match else 0
        
        # 제목 여부 (제목이 포함된 위치인지)
        title_match = re.search(r'제목', loc)
        is_title = 1 if title_match else 0
        
        # "각 목 외의 부분" 확인
        outside_parts = 0
        if "외의 부분" in loc: # "각 목 외의 부분" 또는 "외의 부분"
            outside_parts = 1
            
        return (article_num, article_sub, clause_num, item_num, item_sub, outside_parts, subitem_num, is_title)
    
    # 위치 정보 정렬 (사전식으로 조, 항, 호, 목 순서로 정렬)
    sorted_locs = sorted(formatted_locs, key=parse_location)
    
    # 조항별 그룹화 준비 (defaultdict 사용)
    article_groups = defaultdict(list) # 조문 식별자 (예: 제1조)를 키로 사용
    
    # 1. 먼저 조별로 항목 분류 및 세부 정보 파싱
    for loc in sorted_locs:
        # 조문 식별자 (예: 제1조, 제10조의2) 추출
        article_match = re.match(r'(제\d+조(?:의\d+)?)', loc)
        if not article_match:
            continue # 조문 정보가 없으면 건너뜀
            
        article_num = article_match.group(1)
        rest_part = loc[len(article_num):] # 조문 식별자를 제외한 나머지 부분
        
        # 가지번호 확인 (예: 제14호의3) - 호번호 뒤에 '의N'이 붙는 경우
        # 이 정규식은 "제N호의M" 패턴을 정확히 찾기 위함
        appendix_match = re.search(r'(제\d+호)의(\d+)', rest_part)
        if appendix_match:
            # 정확한 호의 가지번호 표시 (예: 제14호의3)
            # rest_part = rest_part.replace(appendix_match.group(0), f"{appendix_match.group(1)}의{appendix_match.group(2)}")
            # 호의 가지번호는 원본 문자열을 그대로 사용하여 일관성 유지
            pass
        
        # 항번호 확인
        clause_part = ""
        clause_match = re.search(r'(제\d+항)', rest_part)
        if clause_match:
            clause_part = clause_match.group(1)
            # 항번호를 제외한 나머지 부분 업데이트
            rest_part = rest_part[rest_part.find(clause_part) + len(clause_part):]
        
        # 제목 확인 (법령 제목 또는 조문 제목)
        title_part = ""
        if " 제목" in loc: # ' 제목' 또는 ' 제목 및 본문'
            if " 제목 및 본문" in loc:
                title_part = " 제목 및 본문"
            else:
                title_part = " 제목"
            
            # 제목 부분 제거 (나머지 파싱에 영향을 주지 않도록)
            rest_part = rest_part.replace(title_part, "")
            
        # "각 목 외의 부분" 확인
        outside_part = ""
        if " 각 목 외의 부분" in loc or " 외의 부분" in loc:
            outside_part = " 각 목 외의 부분"
            rest_part = rest_part.replace(" 각 목 외의 부분", "").replace(" 외의 부분", "")
        
        # 호목 정보 추출 부분
        item_goal_part = ""
        # '제'로 시작하고 '호' 또는 '목'이 포함된 경우 호목 정보로 간주
        if "제" in rest_part and ("호" in rest_part or "목" in rest_part):
            # 가지번호가 있는 경우를 정확히 처리 (예: 제14호의3)
            appendix_match = re.search(r'(제\d+호)의(\d+)', rest_part)
            if appendix_match:
                item_goal_part = appendix_match.group(0) # 전체 패턴 사용
            else:
                # 일반적인 호 또는 목 번호 패턴 찾기
                item_match = re.match(r'제\d+호|[가-힣]목', rest_part.strip())
                if item_match:
                    item_goal_part = rest_part.strip() # 공백 제거 후 호목 부분 저장
        
        # 조번호 기준으로 그룹화
        # defaultdict 덕분에 키가 없으면 자동으로 리스트 생성
        article_groups[article_num].append((clause_part, title_part, outside_part, item_goal_part))
    
    # 결과 구성
    result_parts = []
    
    # 조별로 처리 (조번호 순으로 정렬)
    for article_num, items in sorted(article_groups.items(), key=lambda x: extract_article_num(x[0])):
        # 항별로 그룹화 시도
        clause_groups = defaultdict(list) # (항번호, 제목여부, 각목외의부분여부)를 키로 사용
        
        for clause, title, outside, item_goal in items:
            key = (clause, title, outside) # 항, 제목, 각목외의부분 정보를 묶어 키로 사용
            if item_goal:
                clause_groups[key].append(item_goal) # 호목 정보만 추가
        
        # 같은 항(및 제목/각목외의부분)끼리 처리
        article_clause_parts = []
        
        # 항번호 순으로 정렬 (항번호가 없으면 0으로 간주하여 정렬)
        # title과 outside가 None이 될 수 있으므로, 키 생성 시 안전하게 처리
        sorted_clause_groups_keys = sorted(clause_groups.keys(),
                                           key=lambda x: int(re.search(r'제(\d+)항', x[0]).group(1)) if re.search(r'제(\d+)항', x[0]) else 0)

        for (clause, title, outside) in sorted_clause_groups_keys:
            loc_str = article_num # 조문 번호로 시작
            
            if title:
                loc_str += title # 제목 추가
                
            if clause:
                loc_str += clause # 항번호 추가
                
            if outside:
                loc_str += outside # 각목외의부분 추가
                
            # 호목 처리
            item_goals = clause_groups[(clause, title, outside)]
            if item_goals:
                # 호목 정렬 후 가운뎃점(ㆍ)으로 연결
                # 전체 위치 문자열을 구성하여 parse_location으로 정렬 키 생성
                sorted_items = sorted(item_goals, key=lambda x: parse_location(f"{article_num}{clause}{x}"))
                
                # 중복 위치 제거
                unique_items = []
                for item in sorted_items:
                    if item not in unique_items:
                        unique_items.append(item)
                
                if unique_items:
                    # 가지번호가 있는 경우 주의해서 처리 (이미 format_location에서 처리됨)
                    # "제"로 시작하지 않는 목번호(예: "가목") 앞에 "제"를 붙이는 것을 방지
                    items_str = "ㆍ".join([
                        item for item in unique_items
                    ])
                    loc_str += f"{items_str}" # 호목 문자열 추가
            
            article_clause_parts.append(loc_str)
        
        # 결과에 조별 정보 추가 - 각 조는 쉼표로 연결
        if article_clause_parts:
            # 마지막 항목 앞에만 '및'을 사용하고 나머지는 쉼표로 연결
            if len(article_clause_parts) == 1:
                result_parts.append(article_clause_parts[0])
            else:
                result_parts.append(", ".join(article_clause_parts[:-1]) + f" 및 {article_clause_parts[-1]}")
    
    # 최종 결과 반환 - 모든 위치 정보를 평면적인 목록으로 다루고, 마지막 항목 앞에만 '및' 사용
    # 이 부분은 이미 위에서 처리된 로직이므로, result_parts를 그대로 반환하거나
    # 아니면 함수 외부에서 최종 포맷팅을 하는 것이 더 명확할 수 있습니다.
    # 현재는 각 법률의 모든 위치를 한 줄로 합쳐서 반환하는 방식입니다.
    if result_parts:
        return "".join(result_parts) # 여기서는 쉼표/및 처리가 이미 완료된 각 조별 문자열을 합칩니다.
    else:
        return ""
        
def run_amendment_logic(find_word, replace_word, exclude_laws=None):
    """
    개정문 생성 로직을 실행하는 함수.
    찾을 문자열과 바꿀 문자열, 그리고 개정 대상에서 제외할 법률 목록을 받습니다.
    """
    amendment_results = []
    skipped_laws = []  # 디버깅을 위해 누락된 법률 추적

    # 배제할 법률 목록이 None이면 빈 리스트로 초기화
    if exclude_laws is None:
        exclude_laws = []

    # 배제할 법률 목록 전처리 - 공백 정규화 (연속된 공백을 하나로, 앞뒤 공백 제거)
    normalized_exclude_laws = []
    for law in exclude_laws:
        if law.strip():  # 빈 문자열이 아닌 경우에만 처리
            normalized_law = ' '.join(law.split())
            normalized_exclude_laws.append(normalized_law)
            
    # 중간점과 중괄호를 가운뎃점/낫표로 정규화
    normalized_find_word = normalize_special_chars(find_word)  # 사용자 입력에 대한 정규화
    normalized_replace_word = normalize_special_chars(replace_word)  # 사용자 입력에 대한 정규화
    
    # 새로 추가: 검색어 전처리 (큰따옴표 유무에 따른 구문/단어 구분)
    processed_find_word, is_phrase = preprocess_search_term(normalized_find_word)
    processed_replace_word, _ = preprocess_search_term(normalized_replace_word) # 바꿀 문자열은 구문 여부 필요 없음

    # 추가: 명시적으로 공백 제거 확인 (trim)
    processed_find_word = processed_find_word.strip()
    processed_replace_word = processed_replace_word.strip()
    
    # 부칙 정보 확인을 위한 변수
    부칙_검색됨 = False  # 부칙에서 검색어가 발견되었는지 여부 (현재는 사용되지 않음, 디버깅 목적)
    
    # 법제처 API를 통해 찾을 문자열을 포함하는 법률 목록 가져오기
    laws = get_law_list_from_api(processed_find_word)
    print(f"총 {len(laws)}개 법률이 검색되었습니다.")
    
    # 실제로 출력된 법률을 추적하기 위한 변수 (출력 항목 번호 매기기 위함)
    출력된_법률수 = 0
    
    for idx, law in enumerate(laws):
        law_name = law["법령명"]
        
        # 공백을 정규화한 법률명 생성 (배제 법률 비교를 위해)
        normalized_law_name = ' '.join(law_name.split())
        
        # 배제할 법률 목록에 있는지 확인 - 다양한 방식으로 비교
        exclude_match = False
        for exclude_law in normalized_exclude_laws:
            # 1. 정확히 일치하는 경우
            if exclude_law == normalized_law_name:
                exclude_match = True
                break
            # 2. 공백을 모두 제거하고 비교
            if exclude_law.replace(" ", "") == normalized_law_name.replace(" ", ""):
                exclude_match = True
                break
            # 3. 부분 문자열 비교 (기존 로직)
            if exclude_law in normalized_law_name:
                exclude_match = True
                break
        
        if exclude_match:
            print(f"배제됨: {law_name} (사용자 지정 배제 법률)")
            skipped_laws.append(f"{law_name}: 사용자 지정 배제 법률")
            continue # 해당 법률은 건너뜀
            
        mst = law["MST"]
        print(f"처리 중: {idx+1}/{len(laws)} - {law_name} (MST: {mst})")
        
        xml_data = get_law_text_by_mst(mst) # 법령 XML 데이터 가져오기
        if not xml_data:
            skipped_laws.append(f"{law_name}: XML 데이터 없음")
            continue # XML 데이터가 없으면 건너뜀
            
        try:
            tree = ET.fromstring(xml_data) # XML 파싱
        except ET.ParseError as e:
            skipped_laws.append(f"{law_name}: XML 파싱 오류 - {str(e)}")
            continue # XML 파싱 오류 발생 시 건너뜀
            
        articles = tree.findall(".//조문단위") # 모든 조문단위 요소 찾기
        if not articles:
            skipped_laws.append(f"{law_name}: 조문단위 없음")
            continue # 조문이 없으면 건너뜀
            
        print(f"조문 개수: {len(articles)}")
        
        # 찾아낸 '덩어리'(chunk)와 위치 정보를 매핑할 딕셔너리
        # 키: (원본 덩어리, 대체될 덩어리, 조사, 접미사), 값: [위치1, 위치2, ...]
        chunk_map = defaultdict(list) 
        
        # 법률에서 검색어의 모든 출현을 찾기 위한 디버깅 변수
        found_matches = 0
        found_in_부칙 = False  # 부칙에서 검색어 발견 여부
        
        # 법률의 모든 텍스트 내용을 검색하며 조, 항, 호, 목 단위로 처리
        for article in articles:
            # 조문 정보 추출
            조번호 = article.findtext("조문번호", "").strip()
            조가지번호 = article.findtext("조문가지번호", "").strip()
            조문식별자 = make_article_number(조번호, 조가지번호)
            
            # 조문의 부칙 여부 확인 (부칙은 개정문 대상에서 제외)
            조문명 = article.findtext("조문명", "").strip()
            is_부칙 = "부칙" in 조문명
            
            # 조문 제목 검색
            조문제목 = article.findtext("조문제목", "") or ""
            
            # 조문 제목에서 검색어 확인
            제목에_검색어_있음 = processed_find_word in 조문제목
            
            # 조문내용에서 검색
            조문내용 = article.findtext("조문내용", "") or ""
            
            # 조문 내용에서 검색어 확인
            본문에_검색어_있음 = processed_find_word in 조문내용
            
            if 제목에_검색어_있음 or 본문에_검색어_있음:
                found_matches += 1
                if is_부칙:
                    found_in_부칙 = True
                    continue  # 부칙은 개정문 생성에서 제외
                
                # 위치 정보에 제목 표시 추가
                # 하나의 조문에서 제목과 본문 모두에 검색어가 있을 수 있음
                if 제목에_검색어_있음 and 본문에_검색어_있음:
                    # 제목에서 발견된 경우 처리
                    if is_phrase:
                        # 공백 포함 구문 처리
                        phrase_matches = find_phrase_with_josa(조문제목, processed_find_word)
                        for _, phrase, josa in phrase_matches:
                            location = f"{조문식별자} 제목 및 본문" # 위치 문자열에 '제목 및 본문' 명시
                            chunk_map[(processed_find_word, processed_replace_word, josa, None)].append(location)
                    else:
                        # 단어 단위 처리
                        tokens = re.findall(r'[가-힣A-Za-z0-9「」]+', 조문제목) # 낫표 포함
                        for token in tokens:
                            if processed_find_word in token:
                                chunk, josa, suffix = extract_chunk_and_josa(token, processed_find_word)
                                replaced = chunk.replace(processed_find_word, processed_replace_word)
                                location = f"{조문식별자} 제목 및 본문"
                                chunk_map[(chunk, replaced, josa, suffix)].append(location)
                    
                    # 본문에서 발견된 경우 처리 (위치 문자열은 동일하게 '제목 및 본문')
                    if is_phrase:
                        phrase_matches = find_phrase_with_josa(조문내용, processed_find_word)
                        for _, phrase, josa in phrase_matches:
                            location = f"{조문식별자} 제목 및 본문"
                            chunk_map[(processed_find_word, processed_replace_word, josa, None)].append(location)
                    else:
                        tokens = re.findall(r'[가-힣A-Za-z0-9「」]+', 조문내용)
                        for token in tokens:
                            if processed_find_word in token:
                                chunk, josa, suffix = extract_chunk_and_josa(token, processed_find_word)
                                replaced = chunk.replace(processed_find_word, processed_replace_word)
                                location = f"{조문식별자} 제목 및 본문"
                                chunk_map[(chunk, replaced, josa, suffix)].append(location)

                elif 제목에_검색어_있음:
                    # 제목에서만 발견된 경우
                    if is_phrase:
                        phrase_matches = find_phrase_with_josa(조문제목, processed_find_word)
                        for _, phrase, josa in phrase_matches:
                            location = f"{조문식별자} 제목"
                            chunk_map[(processed_find_word, processed_replace_word, josa, None)].append(location)
                    else:
                        tokens = re.findall(r'[가-힣A-Za-z0-9「」]+', 조문제목)
                        for token in tokens:
                            if processed_find_word in token:
                                chunk, josa, suffix = extract_chunk_and_josa(token, processed_find_word)
                                replaced = chunk.replace(processed_find_word, processed_replace_word)
                                location = f"{조문식별자} 제목"
                                chunk_map[(chunk, replaced, josa, suffix)].append(location)
                
                elif 본문에_검색어_있음:
                    # 본문에서만 발견된 경우
                    print(f"매치 발견: {조문식별자}") # 디버깅
                    if is_phrase:
                        phrase_matches = find_phrase_with_josa(조문내용, processed_find_word)
                        for _, phrase, josa in phrase_matches:
                            location = f"{조문식별자}"
                            chunk_map[(processed_find_word, processed_replace_word, josa, None)].append(location)
                    else:
                        tokens = re.findall(r'[가-힣A-Za-z0-9「」]+', 조문내용)
                        for token in tokens:
                            if processed_find_word in token:
                                chunk, josa, suffix = extract_chunk_and_josa(token, processed_find_word)
                                replaced = chunk.replace(processed_find_word, processed_replace_word)
                                location = f"{조문식별자}"
                                chunk_map[(chunk, replaced, josa, suffix)].append(location)

            # 항 내용 검색
            for 항 in article.findall("항"):
                항번호 = normalize_number(항.findtext("항번호", "").strip())
                항번호_부분 = f"제{항번호}항" if 항번호 else ""
                
                # 각 목 외의 부분 확인 (호에서 찾을 수 있음)
                각목외의부분 = False
                for 호 in 항.findall("호"):
                    호속성 = 호.attrib
                    if 호속성.get("구분") == "각목외의부분":
                        각목외의부분 = True
                        break # 발견하면 바로 반복 중단
                
                항내용 = 항.findtext("항내용", "") or ""
                
                # 항 내용에서 검색어 확인
                항_검색어_있음 = processed_find_word in 항내용
                
                if 항_검색어_있음:
                    found_matches += 1
                    if is_부칙:
                        found_in_부칙 = True
                        continue # 부칙은 개정문 생성에서 제외
                        
                    additional_info = ""
                    if 각목외의부분:
                        additional_info = " 각 목 외의 부분"
                        
                    print(f"매치 발견: {조문식별자}{항번호_부분}{additional_info}") # 디버깅
                    
                    if is_phrase:
                        # 공백 포함 구문 처리
                        phrase_matches = find_phrase_with_josa(항내용, processed_find_word)
                        for _, phrase, josa in phrase_matches:
                            location = f"{조문식별자}{항번호_부분}{additional_info}"
                            chunk_map[(processed_find_word, processed_replace_word, josa, None)].append(location)
                    else:
                        # 단어 단위 처리
                        tokens = re.findall(r'[가-힣A-Za-z0-9「」]+', 항내용) # 낫표 포함
                        for token in tokens:
                            if processed_find_word in token:
                                chunk, josa, suffix = extract_chunk_and_josa(token, processed_find_word)
                                replaced = chunk.replace(processed_find_word, processed_replace_word)
                                location = f"{조문식별자}{항번호_부분}{additional_info}"
                                chunk_map[(chunk, replaced, josa, suffix)].append(location)
                
                # 호 내용 검색 (항의 자식으로 존재)
                for 호 in 항.findall("호"):
                    호번호 = 호.findtext("호번호")
                    
                    # 가지번호 확인 (예: 제14호의3)
                    호가지번호 = None
                    # 호가지번호는 XML 태그로 존재할 수 있음
                    if 호.find("호가지번호") is not None:
                        호가지번호 = 호.findtext("호가지번호", "").strip()
                    
                    호내용 = 호.findtext("호내용", "") or ""
                    
                    호_검색어_있음 = processed_find_word in 호내용
                    
                    if 호_검색어_있음:
                        found_matches += 1
                        if is_부칙:
                            found_in_부칙 = True
                            continue # 부칙은 개정문 생성에서 제외
                            
                        # 호번호 표시 (가지번호가 있으면 추가)
                        호번호_표시 = f"제{호번호}호"
                        if 호가지번호:
                            호번호_표시 = f"제{호번호}호의{호가지번호}"
                            
                        print(f"매치 발견: {조문식별자}{항번호_부분}{호번호_표시}") # 디버깅
                        
                        if is_phrase:
                            # 공백 포함 구문 처리
                            phrase_matches = find_phrase_with_josa(호내용, processed_find_word)
                            for _, phrase, josa in phrase_matches:
                                location = f"{조문식별자}{항번호_부분}{호번호_표시}"
                                chunk_map[(processed_find_word, processed_replace_word, josa, None)].append(location)
                        else:
                            # 단어 단위 처리
                            tokens = re.findall(r'[가-힣A-Za-z0-9「」]+', 호내용) # 낫표 포함
                            for token in tokens:
                                if processed_find_word in token:
                                    chunk, josa, suffix = extract_chunk_and_josa(token, processed_find_word)
                                    replaced = chunk.replace(processed_find_word, processed_replace_word)
                                    location = f"{조문식별자}{항번호_부분}{호번호_표시}"
                                    chunk_map[(chunk, replaced, josa, suffix)].append(location)

                    # 목 내용 검색 (호의 자식으로 존재)
                    for 목 in 호.findall("목"):
                        목번호 = 목.findtext("목번호")
                        for m in 목.findall("목내용"):
                            if not m.text:
                                continue
                                
                            목_검색어_있음 = processed_find_word in m.text
                                
                            if 목_검색어_있음:
                                found_matches += 1
                                if is_부칙:
                                    found_in_부칙 = True
                                    continue # 부칙은 개정문 생성에서 제외
                                    
                                # 호번호 표시 (가지번호가 있으면 추가)
                                호번호_표시 = f"제{호번호}호"
                                if 호가지번호:
                                    호번호_표시 = f"제{호번호}호의{호가지번호}"
                                    
                                print(f"매치 발견: {조문식별자}{항번호_부분}{호번호_표시}{목번호}목") # 디버깅
                                
                                if is_phrase:
                                    # 공백 포함 구문 처리
                                    for line in m.text.splitlines():
                                        if processed_find_word in line:
                                            phrase_matches = find_phrase_with_josa(line, processed_find_word)
                                            for _, phrase, josa in phrase_matches:
                                                location = f"{조문식별자}{항번호_부분}{호번호_표시}{목번호}목"
                                                chunk_map[(processed_find_word, processed_replace_word, josa, None)].append(location)
                                else:
                                    # 단어 단위 처리
                                    줄들 = [line.strip() for line in m.text.splitlines() if line.strip()]
                                    for 줄 in 줄들:
                                        if processed_find_word in 줄:
                                            tokens = re.findall(r'[가-힣A-Za-z0-9「」]+', 줄) # 낫표 포함
                                            for token in tokens:
                                                if processed_find_word in token:
                                                    chunk, josa, suffix = extract_chunk_and_josa(token, processed_find_word)
                                                    replaced = chunk.replace(processed_find_word, processed_replace_word)
                                                    location = f"{조문식별자}{항번호_부분}{호번호_표시}{목번호}목"
                                                    chunk_map[(chunk, replaced, josa, suffix)].append(location)

        # 현재 법률에서 검색 결과가 없으면 다음 법률로
        if not chunk_map:
            print(f"[{law_name}]에서 검색어 '{processed_find_word}'를 찾지 못했습니다.") # 디버깅
            continue
            
        # 디버깅을 위해 추출된 청크 정보 출력
        print(f"추출된 청크 수: {len(chunk_map)}")
        for (chunk, replaced, josa, suffix), locations in chunk_map.items():
            print(f"청크: '{chunk}', 대체: '{replaced}', 조사: '{josa}', 접미사: '{suffix}', 위치 수: {len(locations)}")
            
        # 같은 출력 형식을 가진 항목들을 그룹화 (개정문 규칙별로 묶음)
        rule_map = defaultdict(list)
        
        for (chunk, replaced, josa, suffix), locations in chunk_map.items():
            # "로서/로써", "으로서/으로써" 특수 접미사 처리 -> 조사로 간주
            if josa in ["으로서", "로써", "으로서", "으로써"]:
                rule = apply_josa_rule(chunk, replaced, josa)
            # "등", "등의", "등인", "등만", "에" 등의 접미사는 덩어리에서 제외하고 일반 처리 (규칙 0 적용)
            elif suffix in ["등", "등의", "등인", "등만", "등에", "에", "에게", "만", "만을", "만이", "만은", "만에", "만으로"]:
                rule = apply_josa_rule(chunk, replaced, josa)
            elif suffix and suffix != "의": # "의"는 개별 처리하지 않음 (단순 소유격 조사로 간주)
                # 접미사가 있는 경우 접미사를 포함한 단어로 처리 (예: "지방법원장"을 "고등법원장"으로)
                orig_with_suffix = chunk + suffix
                replaced_with_suffix = replaced + suffix
                rule = apply_josa_rule(orig_with_suffix, replaced_with_suffix, josa)
            else:
                # 일반 규칙 적용 (조사가 있거나 없는 경우)
                rule = apply_josa_rule(chunk, replaced, josa)
                
            rule_map[rule].extend(locations) # 규칙별로 위치 정보 추가
        
        # 그룹화된 항목들을 정렬하여 출력
        consolidated_rules = []
        for rule, locations in rule_map.items():
            # 중복 위치 제거 및 정렬
            unique_locations = sorted(set(locations))
            
            # 2개 이상의 위치가 있으면 '각각'을 추가하는 규칙 적용
            if len(unique_locations) > 1 and "각각" not in rule:
                # "A"를 "B"로 한다 -> "A"를 각각 "B"로 한다 형식으로 변경 시도
                # 이 정규식은 "XXX"을/를 "YYY"으로/로 한다. 패턴을 찾습니다.
                parts = re.match(r'(".*?")(을|를) (".*?")(으로|로)? 한다\.?', rule)
                if parts:
                    orig_quoted = parts.group(1) # 예: "대법원"
                    josa1 = parts.group(2) # 예: 을
                    replace_quoted = parts.group(3) # 예: "지방법원"
                    josa2 = parts.group(4) if parts.group(4) else "" # 예: 으로

                    # 새로운 규칙 형태: "A"을/를 각각 "B"으로/로 한다.
                    modified_rule = f'{orig_quoted}{josa1} 각각 {replace_quoted}{josa2} 한다.'
                    result_line = f"{group_locations(unique_locations)} 중 {modified_rule}"
                else:
                    # 정규식 매치 실패 시 원래 규칙 문자열 사용
                    result_line = f"{group_locations(unique_locations)} 중 {rule}"
            else:
                # 단일 위치 또는 이미 '각각'이 포함된 규칙
                result_line = f"{group_locations(unique_locations)} 중 {rule}"
            
            consolidated_rules.append(result_line)
        
        # 출력 준비
        if consolidated_rules:
            출력된_법률수 += 1
            # 21번째 결과물부터는 원문자가 아닌 괄호 숫자로 항목 번호 표기
            prefix = chr(9312 + 출력된_법률수 - 1) if 출력된_법률수 <= 20 else f'({출력된_법률수})'
            
            # HTML 형식으로 출력 (br 태그 사용)
            amendment = f"{prefix} {law_name} 일부를 다음과 같이 개정한다.<br>"
            
            # 각 규칙마다 br 태그로 줄바꿈 추가
            for i, rule in enumerate(consolidated_rules):
                amendment += rule
                # 마지막 규칙이 아니면 줄바꿈 두 번, 마지막 규칙은 줄바꿈 한 번
                if i < len(consolidated_rules) - 1:
                    amendment += "<br>" # 다음 규칙과 한 줄 띄움
                else:
                    amendment += "<br>" # 법률과 다음 법률 사이에 한 줄 띄움
            
            amendment_results.append(amendment)
        else:
            # 이 법률에서 개정문이 생성되지 않은 경우
            skipped_laws.append(f"{law_name}: 개정 대상 조문이 없음 (필터링 또는 검색 불일치)")

    # 디버깅 정보 출력: 누락된 법률 목록
    if skipped_laws:
        print("---누락된 법률 목록---")
        for law_info in skipped_laws:
            print(law_info)
            
    # 최종 결과 반환
    return amendment_results if amendment_results else ["⚠️ 개정 대상 조문이 없습니다."]
    
def run_search_logic(query, unit="법률"):
    """
    검색 로직 실행 함수.
    사용자 질의에 따라 법률 조항을 검색하고 HTML 형식으로 반환합니다.
    """
    # 중간점과 중괄호를 가운뎃점/낫표로 정규화
    normalized_query = normalize_special_chars(query)
    
    result_dict = {} # 법률명: [HTML 형식의 조문 내용] 딕셔너리
    
    # 검색어 전처리: 큰따옴표로 감싸진 경우 구문 검색으로 처리
    processed_query, is_phrase = preprocess_search_term(normalized_query)
    
    # 디버깅 출력
    print(f"원본 검색어: {query}")
    print(f"정규화된 검색어: {normalized_query}")
    print(f"처리된 검색어: {processed_query}")
    print(f"구문 검색 모드: {is_phrase}")
    
    # 법제처 API를 통해 검색어에 해당하는 법률 목록 가져오기
    for law in get_law_list_from_api(processed_query):
        mst = law["MST"]
        law_name = law["법령명"]
        
        print(f"검색된 법령명: '{law_name}'") # 디버깅
        
        xml_data = get_law_text_by_mst(mst) # 법령의 상세 XML 데이터 가져오기
        if not xml_data:
            continue # 데이터가 없으면 건너뜀
            
        try:
            tree = ET.fromstring(xml_data) # XML 파싱
        except ET.ParseError as e:
            print(f"법령 XML 파싱 오류: {e} for MST {mst}")
            continue

        articles = tree.findall(".//조문단위") # 모든 조문단위 요소 찾기
        law_results = [] # 현재 법률에서 검색된 조문들의 HTML 리스트
        
        for article in articles:
            # 조문 정보 추출
            조번호 = article.findtext("조문번호", "").strip()
            조가지번호 = article.findtext("조문가지번호", "").strip()
            조문식별자 = make_article_number(조번호, 조가지번호)
            조문내용 = article.findtext("조문내용", "") or ""
            조문제목 = article.findtext("조문제목", "") or "" # 조문 제목 추가
            항들 = article.findall("항") # 모든 항 요소 찾기
            
            출력덩어리 = [] # 현재 조문에서 출력할 내용들을 담을 리스트
            
            # 조문 제목 검색
            제목_검색됨 = processed_query in 조문제목
            # 조문 내용 검색 (공백 포함 여부에 따라 다르게 처리)
            본문_검색됨 = processed_query in 조문내용 if is_phrase else clean(processed_query) in clean(조문내용)
            
            # 해당 조문의 출력 여부 결정
            조문_출력될_것인가 = 제목_검색됨 or 본문_검색됨
            
            첫_항출력됨 = False # 조문내용이 이미 출력되었는지 여부
            
            # 조문 제목 또는 내용에 검색어가 있을 경우 처리
            if 조문_출력될_것인가:
                header_html = f"<h3>{조문식별자} {조문제목}</h3>" if 조문제목 else f"<h3>{조문식별자}</h3>"
                출력덩어리.append(header_html)
                
                # 제목 내용 하이라이트 및 추가
                if 제목_검색됨:
                    출력덩어리.append(highlight(조문제목, processed_query))
                
                # 본문 내용 하이라이트 및 추가
                if 본문_검색됨:
                    출력덩어리.append(highlight(조문내용, processed_query))
                
                첫_항출력됨 = True # 조문 내용은 이미 출력되었음을 표시

            for 항 in 항들:
                항번호 = normalize_number(항.findtext("항번호", "").strip())
                항내용 = 항.findtext("항내용", "") or ""
                
                # 항 내용 검색 (공백 포함 여부에 따라 다르게 처리)
                항_검색됨 = processed_query in 항내용 if is_phrase else clean(processed_query) in clean(항내용)
                
                하위_호목_검색됨 = False # 현재 항의 하위 호/목에서 검색어가 발견되었는지 여부
                항내용_출력_필요 = False # 현재 항 내용을 출력해야 하는지 여부
                
                호들 = 항.findall("호") # 모든 호 요소 찾기
                
                # 호 또는 목 내용에서 검색어 확인
                for 호 in 호들:
                    호내용 = 호.findtext("호내용", "") or ""
                    호_검색됨 = processed_query in 호내용 if is_phrase else clean(processed_query) in clean(호내용)
                    
                    if 호_검색됨:
                        하위_호목_검색됨 = True
                        항내용_출력_필요 = True
                        break # 호에서 발견되면 더 이상 하위 목을 검사할 필요 없음

                    for 목 in 호.findall("목"):
                        for m in 목.findall("목내용"):
                            if m.text:
                                목_검색됨 = processed_query in m.text if is_phrase else clean(processed_query) in clean(m.text)
                                if 목_검색됨:
                                    하위_호목_검색됨 = True
                                    항내용_출력_필요 = True
                                    break
                        if 하위_호목_검색됨:
                            break
                
                # 항 내용 자체에 검색어가 있거나, 하위 호/목에서 검색어가 발견되었다면 해당 항과 그 하위를 출력
                if 항_검색됨 or 하위_호목_검색됨:
                    if not 조문_출력될_것인가 and not 첫_항출력됨:
                        # 조문 내용이 출력되지 않았고, 현재 항이 처음 출력되는 항이라면
                        # 조문 헤더와 조문 내용을 먼저 출력 (하이라이트 포함)
                        header_html = f"<h3>{조문식별자} {조문제목}</h3>" if 조문제목 else f"<h3>{조문식별자}</h3>"
                        출력덩어리.append(header_html)
                        출력덩어리.append(highlight(조문내용, processed_query))
                        첫_항출력됨 = True
                        
                    # 항 내용 자체 하이라이트 (이미 조문내용에 포함된 경우 제외)
                    if 항_검색됨 and not 본문_검색됨: # 본문에서 이미 항내용이 하이라이트된 경우 중복 방지
                        출력덩어리.append(f"<p>&nbsp;&nbsp;{항번호}. {highlight(항내용, processed_query)}</p>")
                    elif not 항_검색됨 and 항내용_출력_필요: # 항 내용 자체에는 없지만 하위에서 찾은 경우
                        출력덩어리.append(f"<p>&nbsp;&nbsp;{항번호}. {항내용}</p>")
                    elif 항_검색됨 and 본문_검색됨: # 본문에서 이미 하이라이트되었지만 항번호가 필요한 경우
                        # 본문 하이라이트가 더 큰 범위이므로, 항번호만 붙여서 다시 표시하거나, 이 부분을 재고해야 함.
                        # 여기서는 일단 간단히 처리: 항번호만 표시하고 내용은 본문에서 하이라이트된 것으로 간주.
                        # 더 정교하게 하려면 본문 하이라이트 시 항번호를 포함하도록 수정해야 함.
                        # 현재 로직은 항내용 자체에 검색어가 있다면 항 번호와 내용을 다시 출력합니다.
                         출력덩어리.append(f"<p>&nbsp;&nbsp;{항번호}. {highlight(항내용, processed_query)}</p>")

                    # 호 내용 처리
                    for 호 in 호들:
                        호번호 = 호.findtext("호번호")
                        호내용 = 호.findtext("호내용", "") or ""
                        
                        호_검색됨 = processed_query in 호내용 if is_phrase else clean(processed_query) in clean(호내용)
                        
                        if 호_검색됨:
                            출력덩어리.append(f"<p>&nbsp;&nbsp;&nbsp;&nbsp;{호번호}. {highlight(호내용, processed_query)}</p>")
                        elif (not 호_검색됨) and any(processed_query in (m.text or "") if is_phrase else clean(processed_query) in clean(m.text or "") for 목 in 호.findall("목") for m in 목.findall("목내용")):
                            # 호 내용 자체에는 없지만 하위 목에서 찾은 경우
                             출력덩어리.append(f"<p>&nbsp;&nbsp;&nbsp;&nbsp;{호번호}. {호내용}</p>")

                        # 목 내용 처리
                        for 목 in 호.findall("목"):
                            for m in 목.findall("목내용"):
                                if m.text:
                                    목_검색됨 = processed_query in m.text if is_phrase else clean(processed_query) in clean(m.text)
                                    if 목_검색됨:
                                        줄들 = [line.strip() for line in m.text.splitlines() if line.strip()]
                                        줄들 = [highlight(line, processed_query) for line in 줄들]
                                        if 줄들:
                                            출력덩어리.append(
                                                "<div style='margin:0;padding:0'>" +
                                                "<br>".join(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;({목.findtext('목번호')}). {line}" for line in 줄들) +
                                                "</div>"
                                            )
                                    elif (not 목_검색됨) and any(processed_query in (m.text or "") if is_phrase else clean(processed_query) in clean(m.text or "") for m in 목.findall("목내용")):
                                        # 목 내용 자체에는 없지만 그 하위에 또 다른 내용이 있고 거기에 검색어가 있는 경우 (이런 경우는 거의 없지만 대비)
                                        # 현재 코드 구조상 목의 자식으로 '목내용'만 있으므로 이 부분은 필요 없을 수 있음.
                                        pass # 이 경우는 현재 로직에서 처리 안함
                                        
            # 현재 법률에서 검색된 조문들이 있다면 결과 딕셔너리에 추가
            if 출력덩어리:
                law_results.append("".join(출력덩어리))
        
        # 현재 법률에서 최종 결과가 있다면 딕셔너리에 추가
        if law_results:
            result_dict[law["법령명"]] = law_results
    
    return result_dict
