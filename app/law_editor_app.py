import streamlit as st
import os
import importlib.util

# Streamlit 페이지 설정
st.set_page_config(
    layout="wide", # 넓은 화면 레이아웃 사용
    menu_items={},  # 햄버거 메뉴 항목 제거 (깔끔한 UI)
    page_icon="📘",  # 페이지 아이콘 설정
)

# 애플리케이션 제목 표시
st.markdown("<h1 style='font-size:20px;'>📘 부칙개정 도우미 (v.1.1.001)</h1>", unsafe_allow_html=True)

# law_processor.py 모듈을 동적으로 로드
# 현재 스크립트의 디렉토리를 기준으로 law_processor.py 파일의 경로를 계산합니다.
# 일반적으로 'app' 디렉토리에 law_editor_app.py와 law_processor.py가 함께 있다고 가정합니다.
# 따라서 law_processor.py는 현재 파일과 동일한 디렉토리에 있다고 가정합니다.
processor_path = os.path.join(os.path.dirname(__file__), "law_processor.py") # 수정된 경로

# importlib.util을 사용하여 모듈을 동적으로 로드
spec = importlib.util.spec_from_file_location("law_processor", processor_path)
law_processor = importlib.util.module_from_spec(spec)
# 로드된 모듈을 실행 (이 부분이 IndentationError의 원인이 될 수 있으므로, law_processor.py의 들여쓰기가 중요합니다.)
spec.loader.exec_module(law_processor)

# law_processor 모듈의 함수를 현재 스크립트에서 직접 사용할 수 있도록 참조 설정
run_amendment_logic = law_processor.run_amendment_logic
run_search_logic = law_processor.run_search_logic

# 사용법 안내 섹션 (확장 가능)
with st.expander("ℹ️ 사용법 안내"):
    st.markdown(      
             "- 이 앱은 다음 두 가지 기능을 제공합니다:\n"
        "  1. **검색 기능**: 검색어가 포함된 법률 조항을 반환합니다.\n"
        "     - 공백을 포함한 문자열을 검색할 수 있습니다. 큰따옴표로 묶지 않아도 됩니다. \n"
        "     - 다중검색어 및 논리연산자(AND, OR, NOT 등)는 지원하지 않습니다. (언젠가 개선예정🥺) \n\n" 
        "  2. **개정문 생성**: 특정 문자열을 다른 문자열로 교체하는 부칙 개정문을 자동 생성합니다.\n"
        "     - 21번째 결과물부터는 원문자가 아닌 괄호숫자로 항목 번호가 표기됩니다. 오류가 아닙니다.\n" 
        "     - 공백이 포함된 문자열을 개정하려는 경우에는 <찾을 문자열> 박스에 문자열 전체를 큰따옴표로 감싸서 입력주세요. (예. \"특정범죄 가중처벌 등에 관한 법률\")  \n" 
        "     - 공백있는 문자열을 큰따옴표로 묶는 것은 오직 개정문 생성기능의 <찾을 문자열>박스에서만 필요합니다. \n" 
        "     - <배제할 법률>에 입력된 법률은 개정문 생성 대상 법률에서 배제합니다. 빈칸으로 두면 찾을 문자열이 포함된 모든 법률에 대해 개정문을 작성합니다. \n" 
        "     - <배제할 법률> 박스에서는 문자열의 공백을 무시합니다. (예. \"특정범죄 가중처벌 등에 관한 법률\"을 \"특정범죄가중처벌등에관한법률\"로 입력가능)  \n" 
        "     - 공백배제 기능은 <배제할 법률> 입력에만 적용됩니다. \n\n" 
        "- 이 앱은 현행 법률의 본문만을 검색 대상으로 합니다. 헌법, 폐지법률, 시행령, 시행규칙, 행정규칙, 제목, 부칙 등은 검색하지 않습니다. \n"
        "- 이 앱은 업무망에서는 작동하지 않습니다. 인터넷망에서 사용해주세요. \n"
        "- 가운뎃점을 입력해야 하는 경우 샵(#)으로 대체할 수 있습니다. (예. \"법률상#사실상의 주장\"을 입력하면 \"법률상ㆍ사실상의 주장\"으로 인식) \n"
        "- 법률 인용 기호, 즉 낫표(「」)는 중괄호( { } )로 입력할 수 있습니다. (예. \"{출입국관리법}에 관한 특례\"를 입력하면 → \"「출입국관리법」에 관한 특례\"를 검색함) \n"  # 추가
        "- 속도가 느립니다(테스트 결과 일반적인 경우 2&#126;3분, 개정문 출력항목 100개 기준 4&#126;5분 소요). 네트워크 속도나 시스템 성능 탓이 아니니 손으로 하는 것보다는 빠르겠지 싶은 경우에 사용해주세요.🥺 \n"
        "- 오류가 있을 수 있습니다. 오류를 발견하시는 분은 사법법제과 김재우(jwkim@assembly.go.kr)에게 알려주시면 감사하겠습니다. (캡쳐파일도 같이 주시면 좋아요)"
    )
# 검색 기능 섹션
st.header("🔍 검색 기능")
search_query = st.text_input("검색어 입력", key="search_query")
do_search = st.button("검색 시작")

if do_search and search_query:
    with st.spinner("🔍 검색 중..."):
        # law_processor 모듈의 run_search_logic 함수 호출
        result = law_processor.run_search_logic(search_query, unit="법률")
        st.success(f"{len(result)}개의 법률을 찾았습니다")
        if result:
            for law_name, sections in result.items():
                with st.expander(f"📄 {law_name}"):
                    for html in sections:
                        st.markdown(html, unsafe_allow_html=True)
        else:
            st.info("검색 결과가 없습니다.")

# 타법개정문 생성 섹션
st.header("✏️ 타법개정문 생성")
find_word = st.text_input("찾을 문자열")
replace_word = st.text_input("바꿀 문자열")
exclude_laws = st.text_input("배제할 법률 (쉼표로 구분)", 
                               help="결과에서 제외할 법률 이름을 쉼표(,)로 구분하여 입력하세요.")
do_amend = st.button("개정문 생성")

if do_amend and find_word and replace_word:
    with st.spinner("🛠 개정문 생성 중..."):
        # 입력된 배제 법률을 리스트로 변환
        exclude_law_list = [law.strip() for law in exclude_laws.split(',')] if exclude_laws else []
        # law_processor 모듈의 run_amendment_logic 함수 호출
        result = run_amendment_logic(find_word, replace_word, exclude_law_list)
        st.success("개정문 생성 완료")
        if result:
            for amend in result:
                st.markdown(amend, unsafe_allow_html=True)
        else:
            st.info("개정 대상 조문이 없습니다.")













