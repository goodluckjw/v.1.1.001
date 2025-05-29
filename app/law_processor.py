# 검색기능은 단일 검색어 기준. 공백포함 문자열 검색 가능. 가운뎃점 중간점 정규화 기능
# 개정문생성은 큰따옴표로 감싸서 문자열로 지원함. 
# 개정문생성 결과에서 원하는 특정 법률을 배제할 수 있도록 함.
# 가운뎃점(U+318D) 대신 샵(#)을 쓸 수 있도록 함. 찾을 문자열, 바꿀 문자열 모두.
# 개정문 결과에서 특정 법률을 배제할 수 있는 기능 추가
# 낫표를 중괄호로 입력할 수 있음.

import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote
import re
import os
import unicodedata
from collections import defaultdict

OC = os.getenv("OC", "chetera")
BASE = "http://www.law.go.kr"

def highlight(text, query):
    """검색어를 HTML로 하이라이트 처리해주는 함수"""
    if not query or not text:
        return text
    # 중간점을 가운뎃점으로 정규화 (하이라이트에서도 일관성 유지)
    normalized_query = normalize_special_chars(query)  # 변경
    
    # 정규식 특수문자 이스케이프
    escaped_query = re.escape(normalized_query)
    # 대소문자 구분없이 검색
    pattern = re.compile(f'({escaped_query})', re.IGNORECASE)
    return pattern.sub(r'<mark>\1</mark>', text)

def get_law_list_from_api(query):
    # 이미 큰따옴표로 감싸져 있는지 확인
    if query.startswith('"') and query.endswith('"'):
        exact_query = query  # 이미 큰따옴표가 있으면 그대로 사용
    else:
        exact_query = f'"{query}"'  # 없으면 추가
    
    encoded_query = quote(exact_query)
    page = 1
    laws = []
    
    # 디버깅을 위해 실제 검색 쿼리 출력
    print(f"API 검색 쿼리: {exact_query}")
    
    while True:
        url = f"{BASE}/DRF/lawSearch.do?OC={OC}&target=law&type=XML&display=100&page={page}&search=2&knd=A0002&query={encoded_query}"
        try:
            res = requests.get(url, timeout=10)
            res.encoding = 'utf-8'
            if res.status_code != 200:
                break
            root = ET.fromstring(res.content)
            for law in root.findall("law"):
                laws.append({
                    "법령명": law.findtext("법령명한글", "").strip(),
                    "MST": law.findtext("법령일련번호", "")
                })
            if len(root.findall("law")) < 100:
                break
            page += 1
        except Exception as e:
            print(f"법률 검색 중 오류 발생: {e}")
            break
    
    # 디버깅을 위해 검색된 법률 목록 출력
    print(f"검색된 법률 수: {len(laws)}")
    for idx, law in enumerate(laws[:5]):  # 처음 5개만 출력
        print(f"{idx+1}. {law['법령명']}")
    
    return laws

def get_law_text_by_mst(mst):
    url = f"{BASE}/DRF/lawService.do?OC={OC}&target=law&MST={mst}&type=XML"
    try:
        res = requests.get(url, timeout=10)
        res.encoding = 'utf-8'
        if res.status_code == 200:
            return res.content
        else:
            print(f"법령 XML 가져오기 실패: 상태 코드 {res.status_code}")
            return None
    except Exception as e:
        print(f"법령 XML 가져오기 중 오류 발생: {e}")
        return None

def clean(text):
    return re.sub(r"\s+", "", text or "")

def normalize_special_chars(text):
    """특수문자를 정규화하는 함수: 중간점, 마침표, 중괄호를 적절한 문자로 변환"""
    if text:
        # 중간점(U+00B7)을 가운뎃점(U+318D)으로 변환
        text = text.replace('·', 'ㆍ')  
        # 마침표(.)를 가운뎃점(U+318D)으로 변환
        text = text.replace('.', 'ㆍ')
        # 중괄호를 법률 인용 기호로 변환
        text = text.replace('{', '「')  # 왼쪽 중괄호를 왼쪽 인용 기호로
        text = text.replace('}', '」')  # 오른쪽 중괄호를 오른쪽 인용 기호로
    return text

def normalize_number(text):
    try:
        return str(int(unicodedata.numeric(text)))
    except:
        return text

def make_article_number(조문번호, 조문가지번호):
    return f"제{조문번호}조의{조문가지번호}" if 조문가지번호 and 조문가지번호 != "0" else f"제{조문번호}조"

def has_batchim(word):
    """단어의 마지막 글자에 받침이 있는지 확인"""
    if not word:
        return False
    
    # 한글의 유니코드 범위: AC00-D7A3
    last_char = word[-1]
    if '가' <= last_char <= '힣':
        # 한글 유니코드 계산식: [(초성 * 21) + 중성] * 28 + 종성 + 0xAC00
        char_code = ord(last_char)
        # 종성 값 추출 (0은 받침 없음, 1-27은 받침 있음)
        jongseong = (char_code - 0xAC00) % 28
        return jongseong != 0
    return False

def has_rieul_batchim(word):
    """단어의 마지막 글자에 'ㄹ' 받침이 있는지 확인"""
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
    """조번호를 추출하여 정수로 변환하는 함수"""
    article_match = re.search(r'제(\d+)조(?:의(\d+))?', loc)
    if not article_match:
        return (0, 0)
    
    # 조번호를 정수로 변환 (37 < 357 정렬을 위해)
    article_num = int(article_match.group(1))
    article_sub = int(article_match.group(2)) if article_match.group(2) else 0
    
    return (article_num, article_sub)



def extract_chunk_and_josa(token, searchword):
    """검색어를 포함하는 덩어리와 조사를 추출"""
    # 검색어의 앞뒤 공백 제거 (trim)
    searchword = searchword.strip()
    
    # 제외할 접미사 리스트 (덩어리에 포함시키지 않을 것들)
    suffix_exclude = ["의", "에", "에서", "에게", 
                     "등", "등의", "등인", "등만", "등에", "만", "만을", "만이", "만은", "만에", "만으로"]
    
    # 처리할 조사 리스트 (규칙에 따른 18가지 조사)
    josa_list = ["을", "를", "과", "와", "이", "가", "이나", "나", "으로", "로", "은", "는", 
                "란", "이란", "라", "이라", "로서", "으로서", "로써", "으로써",
                "\"란", "\"이란", "\"라", "\"이라"]  # 따옴표가 있는 경우 추가
    
    # 원본 토큰 저장
    original_token = token
    suffix = None
    
    # 검색어 자체가 토큰인 경우 바로 반환
    if token == searchword:
        return token, None, None
    
    # 토큰에 검색어가 포함되어 있지 않으면 바로 반환
    if searchword not in token:
        return token, None, None
    
    # 토큰이 검색어로 시작하는지 확인
    if not token.startswith(searchword):
        # 검색어가 토큰 중간에 있는 경우 (다른 단어의 일부)
        return token, None, None
    
    # 1. 접미사 제거 시도 (덩어리에 포함시키지 않음)
    for s in sorted(suffix_exclude, key=len, reverse=True):
        if token == searchword + s:
            # 정확히 "검색어+접미사"인 경우 (예: "지방법원에")
            print(f"접미사 처리: '{token}' = '{searchword}' + '{s}'")  # 디버깅
            return searchword, None, s
    
    # 2. 조사 확인 (조사는 규칙에 따라 처리)
    for j in sorted(josa_list, key=len, reverse=True):
        if token == searchword + j:
            # 정확히 "검색어+조사"인 경우 (예: "지방법원을")
            print(f"조사 처리: '{token}' = '{searchword}' + '{j}'")  # 디버깅
            
            # 특수 케이스: 따옴표가 있는 조사 처리
            if j.startswith("\""):
                # 따옴표를 제거한 기본 조사
                base_josa = j[1:]
                return searchword, base_josa, None
            
            return searchword, j, None
    
    # 3. 덩어리 처리 (검색어 뒤에 다른 문자가 있는 경우)
    if token.startswith(searchword) and len(token) > len(searchword):
        # 예: "지방법원판사", "지방법원장" 등 (검색어 뒤에 다른 단어가 붙음)
        print(f"덩어리 전체 처리: '{token}' (검색어: '{searchword}')")  # 디버깅
        return token, None, None
    
    # 기본 반환 - 토큰 전체
    return token, None, None

def preprocess_search_term(search_term):
    """검색어를 전처리하는 함수"""
    # 큰따옴표로 묶인 문자열인지 확인
    if search_term.startswith('"') and search_term.endswith('"'):
        # 따옴표 제거하고 구문으로 처리
        return search_term[1:-1], True
    else:
        # 일반 단어로 처리
        return search_term, False

def find_phrase_with_josa(text, phrase):
    """공백 포함 문자열과 그 뒤의 조사를 찾는 함수"""
        # 검색 구문에서 앞뒤 공백 제거 (trim)
    phrase = phrase.strip()
    
    matches = []
    start_pos = 0
    
    while True:
        # 구문 위치 찾기
        pos = text.find(phrase, start_pos)
        if pos == -1:
            break
        
        # 구문 끝 위치
        end_pos = pos + len(phrase)
        
        # 조사가 있는지 확인 (구문 뒤 1-4글자)
        max_josa_len = min(4, len(text) - end_pos)
        potential_josa = text[end_pos:end_pos + max_josa_len]
        
        # 조사 후보 리스트
        josa_candidates = ["을", "를", "과", "와", "이", "가", "은", "는", 
                          "이나", "나", "으로", "로", "로서", "으로서", "로써", "으로써"]
        
        found_josa = None
        
        # 가장 긴 조사부터 확인
        for josa in sorted(josa_candidates, key=len, reverse=True):
            if potential_josa.startswith(josa):
                found_josa = josa
                break
        
        # 구문과 조사 정보 추가
        matches.append((pos, phrase, found_josa))
        
        # 다음 검색 시작 위치
        start_pos = pos + 1
    
    return matches

def apply_josa_rule(orig, replaced, josa):
    """개정문 조사 규칙에 따라 적절한 형식 반환"""
    # 동일한 단어면 변경할 필요 없음
    if orig == replaced:
        return f'"{orig}"를 "{replaced}"로 한다.'
        
    # 받침 여부 확인
    orig_has_batchim = has_batchim(orig)
    replaced_has_batchim = has_batchim(replaced)
    replaced_has_rieul = has_rieul_batchim(replaced)
    
    # 조사가 없는 경우 (규칙 0)
    if josa is None:
        if not orig_has_batchim:  # 규칙 0-1: A가 받침 없는 경우
            if not replaced_has_batchim or replaced_has_rieul:  # 규칙 0-1-1, 0-1-2-1
                return f'"{orig}"를 "{replaced}"로 한다.'
            else:  # 규칙 0-1-2-2: B의 받침이 ㄹ이 아닌 경우
                return f'"{orig}"를 "{replaced}"으로 한다.'
        else:  # 규칙 0-2: A가 받침 있는 경우
            if not replaced_has_batchim or replaced_has_rieul:  # 규칙 0-2-1, 0-2-2-1
                return f'"{orig}"을 "{replaced}"로 한다.'
            else:  # 규칙 0-2-2-2: B의 받침이 ㄹ이 아닌 경우
                return f'"{orig}"을 "{replaced}"으로 한다.'
    
    # 따옴표가 있는 경우 조사에서 따옴표 제거
    clean_josa = josa
    if josa and josa.startswith('"'):
        clean_josa = josa[1:]
    
    # 조사별 규칙 처리
    if clean_josa == "을":  # 규칙 1
        if replaced_has_batchim:
            if replaced_has_rieul:  # 규칙 1-1-1
                return f'"{orig}"을 "{replaced}"로 한다.'
            else:  # 규칙 1-1-2
                return f'"{orig}"을 "{replaced}"으로 한다.'
        else:  # 규칙 1-2
            return f'"{orig}을"을 "{replaced}를"로 한다.'
    
    elif clean_josa == "를":  # 규칙 2
        if replaced_has_batchim:  # 규칙 2-1
            return f'"{orig}를"을 "{replaced}을"로 한다.'
        else:  # 규칙 2-2
            return f'"{orig}"를 "{replaced}"로 한다.'
    
    elif clean_josa == "과":  # 규칙 3
        if replaced_has_batchim:
            if replaced_has_rieul:  # 규칙 3-1-1
                return f'"{orig}"을 "{replaced}"로 한다.'
            else:  # 규칙 3-1-2
                return f'"{orig}"을 "{replaced}"으로 한다.'
        else:  # 규칙 3-2
            return f'"{orig}과"를 "{replaced}와"로 한다.'
    
    elif clean_josa == "와":  # 규칙 4
        if replaced_has_batchim:  # 규칙 4-1
            return f'"{orig}와"를 "{replaced}과"로 한다.'
        else:  # 규칙 4-2
            return f'"{orig}"를 "{replaced}"로 한다.'
    
    elif clean_josa == "이":  # 규칙 5
        if replaced_has_batchim:
            if replaced_has_rieul:  # 규칙 5-1-1
                return f'"{orig}"을 "{replaced}"로 한다.'
            else:  # 규칙 5-1-2
                return f'"{orig}"을 "{replaced}"으로 한다.'
        else:  # 규칙 5-2
            return f'"{orig}이"를 "{replaced}가"로 한다.'
    
    elif clean_josa == "가":  # 규칙 6
        if replaced_has_batchim:  # 규칙 6-1
            return f'"{orig}가"를 "{replaced}이"로 한다.'
        else:  # 규칙 6-2
            return f'"{orig}"를 "{replaced}"로 한다.'
    
    elif clean_josa == "이나":  # 규칙 7
        if replaced_has_batchim:
            if replaced_has_rieul:  # 규칙 7-1-1
                return f'"{orig}"을 "{replaced}"로 한다.'
            else:  # 규칙 7-1-2
                return f'"{orig}"을 "{replaced}"으로 한다.'
        else:  # 규칙 7-2
            return f'"{orig}이나"를 "{replaced}나"로 한다.'
    
    elif clean_josa == "나":  # 규칙 8
        if replaced_has_batchim:  # 규칙 8-1
            return f'"{orig}나"를 "{replaced}이나"로 한다.'
        else:  # 규칙 8-2
            return f'"{orig}"를 "{replaced}"로 한다.'
    
    elif clean_josa == "으로":  # 규칙 9
        if replaced_has_batchim:
            if replaced_has_rieul:  # 규칙 9-1-1
                return f'"{orig}으로"를 "{replaced}로"로 한다.'
            else:  # 규칙 9-1-2
                return f'"{orig}"을 "{replaced}"으로 한다.'
        else:  # 규칙 9-2
            return f'"{orig}으로"를 "{replaced}로"로 한다.'
    
    elif clean_josa == "로":  # 규칙 10
        if orig_has_batchim:  # 규칙 10-1: A에 받침이 있는 경우
            if replaced_has_batchim:
                if replaced_has_rieul:  # 규칙 10-1-1-1
                    return f'"{orig}"을 "{replaced}"로 한다.'
                else:  # 규칙 10-1-1-2
                    return f'"{orig}로"를 "{replaced}으로"로 한다.'
            else:  # 규칙 10-1-2
                return f'"{orig}"을 "{replaced}"로 한다.'
        else:  # 규칙 10-2: A에 받침이 없는 경우
            if replaced_has_batchim:
                if replaced_has_rieul:  # 규칙 10-2-1-1
                    return f'"{orig}"를 "{replaced}"로 한다.'
                else:  # 규칙 10-2-1-2
                    return f'"{orig}로"를 "{replaced}으로"로 한다.'
            else:  # 규칙 10-2-2
                return f'"{orig}"를 "{replaced}"로 한다.'
    
    elif clean_josa == "는":  # 규칙 11
        if replaced_has_batchim:  # 규칙 11-1
            return f'"{orig}는"을 "{replaced}은"으로 한다.'
        else:  # 규칙 11-2
            return f'"{orig}"를 "{replaced}"로 한다.'
    
    elif clean_josa == "은":  # 규칙 12
        if replaced_has_batchim:
            if replaced_has_rieul:  # 규칙 12-1-1
                return f'"{orig}"을 "{replaced}"로 한다.'
            else:  # 규칙 12-1-2
                return f'"{orig}"을 "{replaced}"으로 한다.'
        else:  # 규칙 12-2
            return f'"{orig}은"을 "{replaced}는"으로 한다.'
    
    elif clean_josa == "란":  # 규칙 13
        if replaced_has_batchim:  # 규칙 13-1
            quote_prefix = '"' if josa.startswith('"') else ""
            return f'"{orig}{josa}"을 "{replaced}이{quote_prefix}란"으로 한다.'
        else:  # 규칙 13-2
            return f'"{orig}"를 "{replaced}"로 한다.'
    
    elif clean_josa == "이란":  # 규칙 14
        if replaced_has_batchim:
            if replaced_has_rieul:  # 규칙 14-1-1
                return f'"{orig}"을 "{replaced}"로 한다.'
            else:  # 규칙 14-1-2
                return f'"{orig}"을 "{replaced}"으로 한다.'
        else:  # 규칙 14-2
            quote_prefix = '"' if josa.startswith('"') else ""
            return f'"{orig}{josa}"을 "{replaced}{quote_prefix}란"으로 한다.'
    
    elif clean_josa == "로서" or clean_josa == "로써":  # 규칙 15
        if orig_has_batchim:  # 규칙 15-1: A에 받침이 있는 경우
            if replaced_has_batchim:
                if replaced_has_rieul:  # 규칙 15-1-1-1
                    return f'"{orig}"을 "{replaced}"로 한다.'
                else:  # 규칙 15-1-1-2
                    return f'"{orig}{josa}"를 "{replaced}으{clean_josa}"로 한다.'
            else:  # 규칙 15-1-2
                return f'"{orig}"을 "{replaced}"로 한다.'
        else:  # 규칙 15-2: A에 받침이 없는 경우
            if replaced_has_batchim:
                if replaced_has_rieul:  # 규칙 15-2-1-1
                    return f'"{orig}"를 "{replaced}"로 한다.'
                else:  # 규칙 15-2-1-2
                    return f'"{orig}{josa}"를 "{replaced}으{clean_josa}"로 한다.'
            else:  # 규칙 15-2-2
                return f'"{orig}"를 "{replaced}"로 한다.'
    
    elif clean_josa == "으로서" or clean_josa == "으로써":  # 규칙 16
        if replaced_has_batchim:
            if replaced_has_rieul:  # 규칙 16-1-1
                return f'"{orig}{josa}"를 "{replaced}로{clean_josa[2:]}"로 한다.'
            else:  # 규칙 16-1-2
                return f'"{orig}"을 "{replaced}"으로 한다.'
        else:  # 규칙 16-2
            return f'"{orig}{josa}"를 "{replaced}로{clean_josa[2:]}"로 한다.'
    
    elif clean_josa == "라":  # 규칙 17
        if replaced_has_batchim:  # 규칙 17-1
            quote_prefix = '"' if josa.startswith('"') else ""
            return f'"{orig}{josa}"를 "{replaced}이{quote_prefix}라"로 한다.'
        else:  # 규칙 17-2
            return f'"{orig}"를 "{replaced}"로 한다.'
    
    elif clean_josa == "이라":  # 규칙 18
        if replaced_has_batchim:
            if replaced_has_rieul:  # 규칙 18-1-1
                return f'"{orig}"을 "{replaced}"로 한다.'
            else:  # 규칙 18-1-2
                return f'"{orig}"을 "{replaced}"으로 한다.'
        else:  # 규칙 18-2
            quote_prefix = '"' if josa.startswith('"') else ""
            return f'"{orig}{josa}"를 "{replaced}{quote_prefix}라"로 한다.'
    
    # 기본 출력 형식
    if orig_has_batchim:
        return f'"{orig}"을 "{replaced}"로 한다.'
    else:
        return f'"{orig}"를 "{replaced}"로 한다.'

def format_location(loc):
    """위치 정보 형식 수정: 항번호가 비어있는 경우와 호번호, 목번호의 period 제거"""
    # 항번호가 비어있는 경우 "제항" 제거
    loc = re.sub(r'제(?=항)', '', loc)
    
    # 호번호와 목번호 뒤의 period(.) 제거
    loc = re.sub(r'(\d+)\.호', r'\1호', loc)
    loc = re.sub(r'([가-힣])\.목', r'\1목', loc)
    
    return loc

def group_locations(loc_list):
    """위치 정보 그룹화 (조 > 항 > 호 > 목 순서로 사전식 정렬)
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
        
        # 목번호 (가나다 순서)
        subitem_match = re.search(r'([가-힣])목', loc)
        subitem_num = ord(subitem_match.group(1)) - ord('가') + 1 if subitem_match else 0
        
        # 제목 여부
        title_match = re.search(r'제목', loc)
        is_title = 1 if title_match else 0
        
        # "각 목 외의 부분" 확인
        outside_parts = 0
        if "외의 부분" in loc:
            outside_parts = 1
            
        return (article_num, article_sub, clause_num, item_num, item_sub, outside_parts, subitem_num, is_title)
    
    # 위치 정보 정렬 (사전식)
    sorted_locs = sorted(formatted_locs, key=parse_location)
    
    # 조항별 그룹화 준비
    article_groups = {}  # 조별 그룹화
    
    # 1. 먼저 조별로 항목 분류
    for loc in sorted_locs:
        # 조번호 추출
        article_match = re.match(r'(제\d+조(?:의\d+)?)', loc)
        if not article_match:
            continue
            
        article_num = article_match.group(1)
        rest_part = loc[len(article_num):]
        
        # 가지번호 확인 (예: 제14호의3)
        appendix_match = re.search(r'(제\d+호)의(\d+)', rest_part)
        if appendix_match:
            # 정확한 호의 가지번호 표시 (예: 제14호의3)
            rest_part = rest_part.replace(appendix_match.group(0), f"{appendix_match.group(1)}의{appendix_match.group(2)}")
        
        # 항번호 확인
        clause_part = ""
        clause_match = re.search(r'(제\d+항)', rest_part)
        if clause_match:
            clause_part = clause_match.group(1)
            rest_part = rest_part[rest_part.find(clause_part) + len(clause_part):]
        
        # 제목 확인
        title_part = ""
        if " 제목" in loc:
            if " 제목 및 본문" in loc:
                title_part = " 제목 및 본문"
            else:
                title_part = " 제목"
            
            # 제목 부분 제거
            rest_part = rest_part.replace(title_part, "")
            
        # "각 목 외의 부분" 확인
        outside_part = ""
        if " 각 목 외의 부분" in loc or " 외의 부분" in loc:
            outside_part = " 각 목 외의 부분"
            rest_part = rest_part.replace(" 각 목 외의 부분", "").replace(" 외의 부분", "")
        
        # 호목 정보 추출 부분
        item_goal_part = ""
        if "제" in rest_part and ("호" in rest_part or "목" in rest_part):
            # 호 또는 목 정보가 있는 경우
            # 가지번호가 있는 경우를 정확히 처리
            appendix_match = re.search(r'(제\d+호)의(\d+)', rest_part)
            if appendix_match:
                item_goal_part = appendix_match.group(0)  # 전체 패턴 사용
            else:
                item_match = re.match(r'제\d+호|[가-힣]목', rest_part.strip())
                if item_match:
                    item_goal_part = rest_part.strip()
        
        # 조번호 기준으로 그룹화
        if article_num not in article_groups:
            article_groups[article_num] = []
            
        # 항과 호목 정보 저장
        article_groups[article_num].append((clause_part, title_part, outside_part, item_goal_part))
    
    # 결과 구성
    result_parts = []
    
    # 조별로 처리
    for article_num, items in sorted(article_groups.items(), key=lambda x: extract_article_num(x[0])):
        # 항별로 그룹화 시도
        clause_groups = {}
        
        for clause, title, outside, item_goal in items:
            key = (clause, title, outside)
            if key not in clause_groups:
                clause_groups[key] = []
                
            if item_goal:
                clause_groups[key].append(item_goal)
        
        # 같은 항끼리 처리
        article_clause_parts = []
        
        # 항번호 순으로 정렬
        for (clause, title, outside), item_goals in sorted(clause_groups.items(), 
                                                        key=lambda x: int(re.search(r'제(\d+)항', x[0][0]).group(1)) if re.search(r'제(\d+)항', x[0][0]) else 0):
            loc_str = article_num
            
            if title:
                loc_str += title
                
            if clause:
                loc_str += clause
                
            if outside:
                loc_str += outside
                
            # 호목 처리
            if item_goals:
                # 호목 정렬 후 가운뎃점으로 연결
                sorted_items = sorted(item_goals, key=lambda x: parse_location(f"{article_num}{clause}{x}"))
                # 먼저 중복 제거
                unique_items = []
                for item in sorted_items:
                    if item not in unique_items:
                        unique_items.append(item)
                
                if unique_items:
                    # 가지번호가 있는 경우 주의해서 처리
                    items_str = "ㆍ".join([
                        item if item.startswith("제") else f"제{item}" 
                        for item in unique_items
                    ])
                    loc_str += f"{items_str}"
            
            article_clause_parts.append(loc_str)
        
        # 결과에 조별 정보 추가 - 각 조는 쉼표로 연결
        if article_clause_parts:
            result_parts.extend(article_clause_parts)
    
    # 최종 결과 반환 - 모든 위치 정보를 평면적인 목록으로 다루고, 마지막 항목 앞에만 '및' 사용
    if result_parts:
        if len(result_parts) == 1:
            return result_parts[0]
        else:
            # 마지막 항목 앞에만 '및' 사용, 나머지는 쉼표로 연결
            return ", ".join(result_parts[:-1]) + f" 및 {result_parts[-1]}"
    else:
        return ""
        
def run_amendment_logic(find_word, replace_word, exclude_laws=None):
    """개정문 생성 로직"""
    amendment_results = []
    skipped_laws = []  # 디버깅을 위해 누락된 법률 추적

      # 배제할 법률 목록이 None이면 빈 리스트로 초기화
    if exclude_laws is None:
        exclude_laws = []

        # 배제할 법률 목록 전처리 - 공백 정규화
    normalized_exclude_laws = []
    for law in exclude_laws:
        if law.strip():  # 빈 문자열이 아닌 경우에만 처리
            # 모든 연속된 공백을 단일 공백으로 변환하고 양쪽 공백 제거
            normalized_law = ' '.join(law.split())
            normalized_exclude_laws.append(normalized_law)

      # 중간점을 가운뎃점으로 정규화
    normalized_find_word = normalize_special_chars(find_word)  # 변경
    normalized_replace_word = normalize_special_chars(replace_word)  # 변경
    
    # 새로 추가: 검색어 전처리
    processed_find_word, is_phrase = preprocess_search_term(normalized_find_word)
    processed_replace_word, _ = preprocess_search_term(normalized_replace_word)

    # 추가: 명시적으로 공백 제거 확인
    processed_find_word = processed_find_word.strip()
    processed_replace_word = processed_replace_word.strip()
    
    # 부칙 정보 확인을 위한 변수
    부칙_검색됨 = False  # 부칙에서 검색어가 발견되었는지 여부
    
    laws = get_law_list_from_api(processed_find_word)
    print(f"총 {len(laws)}개 법률이 검색되었습니다.")
    
    # 실제로 출력된 법률을 추적하기 위한 변수
    출력된_법률수 = 0
    
    for idx, law in enumerate(laws):
        law_name = law["법령명"]
        
        # 공백을 정규화한 법률명 생성
        normalized_law_name = ' '.join(law_name.split())
        
        # 배제할 법률 목록에 있는지 확인 - 공백 무시 비교
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
            continue
            
        mst = law["MST"]
        print(f"처리 중: {idx+1}/{len(laws)} - {law_name} (MST: {mst})")
        
        xml_data = get_law_text_by_mst(mst)
        if not xml_data:
            skipped_laws.append(f"{law_name}: XML 데이터 없음")
            continue
            
        try:
            tree = ET.fromstring(xml_data)
        except ET.ParseError as e:
            skipped_laws.append(f"{law_name}: XML 파싱 오류 - {str(e)}")
            continue
            
        articles = tree.findall(".//조문단위")
        if not articles:
            skipped_laws.append(f"{law_name}: 조문단위 없음")
            continue
            
        print(f"조문 개수: {len(articles)}")
        
        chunk_map = defaultdict(list)
        
        # 법률에서 검색어의 모든 출현을 찾기 위한 디버깅 변수
        found_matches = 0
        found_in_부칙 = False  # 부칙에서 검색어 발견됨
        
        # 법률의 모든 텍스트 내용을 검색
        for article in articles:
            # 조문
            조번호 = article.findtext("조문번호", "").strip()
            조가지번호 = article.findtext("조문가지번호", "").strip()
            조문식별자 = make_article_number(조번호, 조가지번호)
            
            # 조문의 부칙 여부 확인
            조문명 = article.findtext("조문명", "").strip()
            is_부칙 = "부칙" in 조문명
            
            # 조문 제목 검색 (추가)
            조문제목 = article.findtext("조문제목", "") or ""
            
            # 수정: 구문/단어에 따라 다른 검색 방식 적용
            if is_phrase:
                제목에_검색어_있음 = processed_find_word in 조문제목
            else:
                제목에_검색어_있음 = processed_find_word in 조문제목
            
            # 조문내용에서 검색
            조문내용 = article.findtext("조문내용", "") or ""
            
            # 수정: 구문/단어에 따라 다른 검색 방식 적용
            if is_phrase:
                본문에_검색어_있음 = processed_find_word in 조문내용
            else:
                본문에_검색어_있음 = processed_find_word in 조문내용
            
            if 제목에_검색어_있음 or 본문에_검색어_있음:
                found_matches += 1
                if is_부칙:
                    found_in_부칙 = True
                    continue  # 부칙은 검색에서 제외
                
                # 위치 정보에 제목 표시 추가
                location_suffix = ""
                if 제목에_검색어_있음 and 본문에_검색어_있음:
                    location_suffix = " 제목 및 본문"
                elif 제목에_검색어_있음:
                    location_suffix = " 제목"
                
                # 수정: 제목에서 구문/단어 검색 방식 분기
                if 제목에_검색어_있음:
                    if is_phrase:
                        # 공백 포함 구문 처리
                        phrase_matches = find_phrase_with_josa(조문제목, processed_find_word)
                        for _, phrase, josa in phrase_matches:
                            location = f"{조문식별자} 제목"
                            chunk_map[(processed_find_word, processed_replace_word, josa, None)].append(location)
                    else:
                        # 단어 단위 처리 (기존 방식)
                        tokens = re.findall(r'[가-힣A-Za-z0-9]+', 조문제목)
                        for token in tokens:
                            if processed_find_word in token:
                                chunk, josa, suffix = extract_chunk_and_josa(token, processed_find_word)
                                replaced = chunk.replace(processed_find_word, processed_replace_word)
                                location = f"{조문식별자} 제목"
                                chunk_map[(chunk, replaced, josa, suffix)].append(location)
                
                # 수정: 본문에서 구문/단어 검색 방식 분기
                elif 본문에_검색어_있음:  # elif로 변경하여 중복 검색 방지
                    print(f"매치 발견: {조문식별자}")
                    
                    if is_phrase:
                        # 공백 포함 구문 처리
                        phrase_matches = find_phrase_with_josa(조문내용, processed_find_word)
                        for _, phrase, josa in phrase_matches:
                            location = f"{조문식별자}"
                            chunk_map[(processed_find_word, processed_replace_word, josa, None)].append(location)
                    else:
                        # 단어 단위 처리 (기존 방식)
                        tokens = re.findall(r'[가-힣A-Za-z0-9]+', 조문내용)
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
                        break
                
                항내용 = 항.findtext("항내용", "") or ""
                
                # 수정: 구문/단어에 따라 다른 검색 방식 적용
                if is_phrase:
                    항_검색어_있음 = processed_find_word in 항내용
                else:
                    항_검색어_있음 = processed_find_word in 항내용
                
                if 항_검색어_있음:
                    found_matches += 1
                    if is_부칙:
                        found_in_부칙 = True
                        continue  # 부칙은 검색에서 제외
                    
                    additional_info = ""
                    if 각목외의부분:
                        additional_info = " 각 목 외의 부분"
                        
                    print(f"매치 발견: {조문식별자}{항번호_부분}{additional_info}")
                    
                    if is_phrase:
                        # 공백 포함 구문 처리
                        phrase_matches = find_phrase_with_josa(항내용, processed_find_word)
                        for _, phrase, josa in phrase_matches:
                            location = f"{조문식별자}{항번호_부분}{additional_info}"
                            chunk_map[(processed_find_word, processed_replace_word, josa, None)].append(location)
                    else:
                        # 단어 단위 처리 (기존 방식)
                        tokens = re.findall(r'[가-힣A-Za-z0-9]+', 항내용)
                        for token in tokens:
                            if processed_find_word in token:
                                chunk, josa, suffix = extract_chunk_and_josa(token, processed_find_word)
                                replaced = chunk.replace(processed_find_word, processed_replace_word)
                                location = f"{조문식별자}{항번호_부분}{additional_info}"
                                chunk_map[(chunk, replaced, josa, suffix)].append(location)
                
                # 호 내용 검색
                for 호 in 항.findall("호"):
                    호번호 = 호.findtext("호번호")
                    
                    # 가지번호 확인 (예: 제14호의3)
                    호가지번호 = None
                    # 호가지번호는 XML 태그로 존재
                    if 호.find("호가지번호") is not None:
                        호가지번호 = 호.findtext("호가지번호", "").strip()
                    
                    호내용 = 호.findtext("호내용", "") or ""
                    
                    # 수정: 구문/단어에 따라 다른 검색 방식 적용
                    if is_phrase:
                        호_검색어_있음 = processed_find_word in 호내용
                    else:
                        호_검색어_있음 = processed_find_word in 호내용
                    
                    if 호_검색어_있음:
                        found_matches += 1
                        if is_부칙:
                            found_in_부칙 = True
                            continue  # 부칙은 검색에서 제외
                        
                        # 호번호 표시 (가지번호가 있으면 추가)
                        호번호_표시 = f"제{호번호}호"
                        if 호가지번호:
                            호번호_표시 = f"제{호번호}호의{호가지번호}"
                            
                        print(f"매치 발견: {조문식별자}{항번호_부분}{호번호_표시}")
                        
                        if is_phrase:
                            # 공백 포함 구문 처리
                            phrase_matches = find_phrase_with_josa(호내용, processed_find_word)
                            for _, phrase, josa in phrase_matches:
                                location = f"{조문식별자}{항번호_부분}{호번호_표시}"
                                chunk_map[(processed_find_word, processed_replace_word, josa, None)].append(location)
                        else:
                            # 단어 단위 처리 (기존 방식)
                            tokens = re.findall(r'[가-힣A-Za-z0-9]+', 호내용)
                            for token in tokens:
                                if processed_find_word in token:
                                    chunk, josa, suffix = extract_chunk_and_josa(token, processed_find_word)
                                    replaced = chunk.replace(processed_find_word, processed_replace_word)
                                    location = f"{조문식별자}{항번호_부분}{호번호_표시}"
                                    chunk_map[(chunk, replaced, josa, suffix)].append(location)

                    # 목 내용 검색
                    for 목 in 호.findall("목"):
                        목번호 = 목.findtext("목번호")
                        for m in 목.findall("목내용"):
                            if not m.text:
                                continue
                            
                            # 수정: 구문/단어에 따라 다른 검색 방식 적용
                            if is_phrase:
                                목_검색어_있음 = processed_find_word in m.text
                            else:
                                목_검색어_있음 = processed_find_word in m.text
                                
                            if 목_검색어_있음:
                                found_matches += 1
                                if is_부칙:
                                    found_in_부칙 = True
                                    continue  # 부칙은 검색에서 제외
                                
                                # 호번호 표시 (가지번호가 있으면 추가)
                                호번호_표시 = f"제{호번호}호"
                                if 호가지번호:
                                    호번호_표시 = f"제{호번호}호의{호가지번호}"
                                    
                                print(f"매치 발견: {조문식별자}{항번호_부분}{호번호_표시}{목번호}목")
                                
                                if is_phrase:
                                    # 공백 포함 구문 처리
                                    for line in m.text.splitlines():
                                        if processed_find_word in line:
                                            phrase_matches = find_phrase_with_josa(line, processed_find_word)
                                            for _, phrase, josa in phrase_matches:
                                                location = f"{조문식별자}{항번호_부분}{호번호_표시}{목번호}목"
                                                chunk_map[(processed_find_word, processed_replace_word, josa, None)].append(location)
                                else:
                                    # 단어 단위 처리 (기존 방식)
                                    줄들 = [line.strip() for line in m.text.splitlines() if line.strip()]
                                    for 줄 in 줄들:
                                        if processed_find_word in 줄:
                                            tokens = re.findall(r'[가-힣A-Za-z0-9]+', 줄)
                                            for token in tokens:
                                                if processed_find_word in token:
                                                    chunk, josa, suffix = extract_chunk_and_josa(token, processed_find_word)
                                                    replaced = chunk.replace(processed_find_word, processed_replace_word)
                                                    location = f"{조문식별자}{항번호_부분}{호번호_표시}{목번호}목"
                                                    chunk_map[(chunk, replaced, josa, suffix)].append(location)

        # 검색 결과가 없으면 다음 법률로
        if not chunk_map:
            continue
        
        # 디버깅을 위해 추출된 청크 정보 출력
        print(f"추출된 청크 수: {len(chunk_map)}")
        for (chunk, replaced, josa, suffix), locations in chunk_map.items():
            print(f"청크: '{chunk}', 대체: '{replaced}', 조사: '{josa}', 접미사: '{suffix}', 위치 수: {len(locations)}")
        
        # 같은 출력 형식을 가진 항목들을 그룹화
        rule_map = defaultdict(list)
        
        for (chunk, replaced, josa, suffix), locations in chunk_map.items():
            # "로서/로써", "으로서/으로써" 특수 접미사 처리
            if josa in ["로서", "로써", "으로서", "으로써"]:  # 조사로 처리
                # 조사 규칙 적용
                rule = apply_josa_rule(chunk, replaced, josa)
            # "등", "등인", "등만", "에" 등의 접미사는 덩어리에서 제외하고 일반 처리
            elif suffix in ["등", "등의", "등인", "등만", "등에", "에", "에게", "만", "만을", "만이", "만은", "만에", "만으로"]:
                # 규칙 0 적용 (조사가 없는 경우)
                rule = apply_josa_rule(chunk, replaced, josa)
            elif suffix and suffix != "의":  # "의"는 개별 처리하지 않음
                # 접미사가 있는 경우 접미사를 포함한 단어로 처리
                orig_with_suffix = chunk + suffix
                replaced_with_suffix = replaced + suffix
                rule = apply_josa_rule(orig_with_suffix, replaced_with_suffix, josa)
            else:
                # 일반 규칙 적용
                rule = apply_josa_rule(chunk, replaced, josa)
                
            rule_map[rule].extend(locations)
        
        # 그룹화된 항목들을 정렬하여 출력
        consolidated_rules = []
        for rule, locations in rule_map.items():
            # 중복 위치 제거 및 정렬
            unique_locations = sorted(set(locations))
            
            # 2개 이상의 위치가 있으면 '각각'을 추가
            if len(unique_locations) > 1 and "각각" not in rule:
                # "A"를 "B"로 한다 -> "A"를 각각 "B"로 한다 형식으로 변경
                parts = re.match(r'(".*?")(을|를) (".*?")(으로|로) 한다\.?', rule)
                if parts:
                    orig = parts.group(1)
                    article = parts.group(2)
                    replace = parts.group(3)
                    suffix = parts.group(4)
                    modified_rule = f'{orig}{article} 각각 {replace}{suffix} 한다.'
                    result_line = f"{group_locations(unique_locations)} 중 {modified_rule}"
                else:
                    # 정규식 매치 실패 시 원래 문자열 사용
                    result_line = f"{group_locations(unique_locations)} 중 {rule}"
            else:
                result_line = f"{group_locations(unique_locations)} 중 {rule}"
            
            consolidated_rules.append(result_line)
        
        # 출력 준비
        if consolidated_rules:
            출력된_법률수 += 1
            prefix = chr(9312 + 출력된_법률수 - 1) if 출력된_법률수 <= 20 else f'({출력된_법률수})'
            
            # HTML 형식으로 출력 (br 태그 사용)
            amendment = f"{prefix} {law_name} 일부를 다음과 같이 개정한다.<br>"
          
            # 각 규칙마다 br 태그로 줄바꿈 추가
            for i, rule in enumerate(consolidated_rules):
                amendment += rule
                if i < len(consolidated_rules) - 1:  # 마지막 규칙이 아니면 줄바꿈 두 번
                    amendment += "<br>"
                else:
                    amendment += "<br>"  # 마지막 규칙은 줄바꿈 한 번
            
            amendment_results.append(amendment)
        else:
            skipped_laws.append(f"{law_name}: 결과줄이 생성되지 않음")

    # 디버깅 정보 출력
    if skipped_laws:
        print("---누락된 법률 목록---")
        for law in skipped_laws:
            print(law)
        
    # 함수의 리턴문
    return amendment_results if amendment_results else ["⚠️ 개정 대상 조문이 없습니다."]
  
def run_search_logic(query, unit="법률"):
    """검색 로직 실행 함수"""
      # 중간점을 가운뎃점으로 정규화
    normalized_query = normalize_special_chars(query)  # 변경
  
    result_dict = {}
    keyword_clean = clean(normalized_query)
    for law in get_law_list_from_api(query):
        mst = law["MST"]
        xml_data = get_law_text_by_mst(mst)
        if not xml_data:
            continue
        tree = ET.fromstring(xml_data)
        articles = tree.findall(".//조문단위")
        law_results = []
        for article in articles:
            조번호 = article.findtext("조문번호", "").strip()
            조가지번호 = article.findtext("조문가지번호", "").strip()
            조문식별자 = make_article_number(조번호, 조가지번호)
            조문내용 = article.findtext("조문내용", "") or ""
            항들 = article.findall("항")
            출력덩어리 = []
            조출력 = keyword_clean in clean(조문내용)
            첫_항출력됨 = False
            if 조출력:
                출력덩어리.append(highlight(조문내용, query))
            for 항 in 항들:
                항번호 = normalize_number(항.findtext("항번호", "").strip())
                항내용 = 항.findtext("항내용", "") or ""
                항출력 = keyword_clean in clean(항내용)
                항덩어리 = []
                하위검색됨 = False
                for 호 in 항.findall("호"):
                    호내용 = 호.findtext("호내용", "") or ""
                    호출력 = keyword_clean in clean(호내용)
                    if 호출력:
                        하위검색됨 = True
                        항덩어리.append("&nbsp;&nbsp;" + highlight(호내용, query))
                    for 목 in 호.findall("목"):
                        for m in 목.findall("목내용"):
                            if m.text and keyword_clean in clean(m.text):
                                줄들 = [line.strip() for line in m.text.splitlines() if line.strip()]
                                줄들 = [highlight(line, query) for line in 줄들]
                                if 줄들:
                                    하위검색됨 = True
                                    항덩어리.append(
                                        "<div style='margin:0;padding:0'>" +
                                        "<br>".join("&nbsp;&nbsp;&nbsp;&nbsp;" + line for line in 줄들) +
                                        "</div>"
                                    )
                if 항출력 or 하위검색됨:
                    if not 조출력 and not 첫_항출력됨:
                        출력덩어리.append(f"{highlight(조문내용, query)} {highlight(항내용, query)}")
                        첫_항출력됨 = True
                    elif not 첫_항출력됨:
                        출력덩어리.append(highlight(항내용, query))
                        첫_항출력됨 = True
                    else:
                        출력덩어리.append(highlight(항내용, query))
                    출력덩어리.extend(항덩어리)
            if 출력덩어리:
                law_results.append("<br>".join(출력덩어리))
        if law_results:
            result_dict[law["법령명"]] = law_results
    return result_dict

# 전체 파일 실행 시 필요한 코드
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("사용법: python law_processor.py <명령> <검색어> [바꿀단어]")
        print("  명령: search, amend")
        print("  예시1: python law_processor.py search 지방법원")
        print("  예시2: python law_processor.py amend 지방법원 지역법원")
        sys.exit(1)
    
    command = sys.argv[1]
    search_word = sys.argv[2]
    
    if command == "search":
        results = run_search_logic(search_word)
        for law_name, snippets in results.items():
            print(f"## {law_name}")
            for snippet in snippets:
                print(snippet)
                print("---")
    
    elif command == "amend":
        if len(sys.argv) < 4:
            print("바꿀단어를 입력하세요.")
            sys.exit(1)
        
        replace_word = sys.argv[3]
        results = run_amendment_logic(search_word, replace_word)
        
        for result in results:
            print(result)
            print("\n")
    
    else:
        print(f"알 수 없는 명령: {command}")
        sys.exit(1)
