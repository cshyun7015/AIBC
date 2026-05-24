1. 과제 주제
나만의 End-to-End AI Agent 서비스 개발
2. 과제 개요
이번 과제는 AI 기술들을 기반으로, 실제 사용 가능한 AI Agent 서비스를 직접 설계하고 구현하는 것을 목표로 합니다.
문제 정의부터 프롬프트 설계, Agent 구조 설계, RAG 기반 지식 결합, 사용자 경험 구현까지 하나의 흐름으로 연결된 완결형 서비스를 개발해야 합니다.
Agent의 핵심 기능은 LangChain/LangGraph 기반으로 구현하며, 서비스 수준을 높이기 위해 필요에 따라 출력 구조화, 도구·시스템 연동, Agent 간 협업 등 다양한 확장 기능을 적용할 수 있습니다.
최종 결과물은 단순 예제를 넘어 실제 업무·서비스 환경에서도 활용 가능한 수준의 실무형 AI Agent여야 합니다.
3. 과제 목표
Prompt → 설계 → 구현 → 패키징까지 Agentic 서비스를 완성하는 것을 목표로 합니다.
LangChain/LangGraph 기반 역할 기반 또는 Multi-Agent 구조 설계
RAG 기반 지식 응답, Structured Output·Function Calling 등 고도화 기법 기반 안정적 응답 구성
UI/서비스로 패키징해 실제 사용 가능한 형태로 구현, 최신 기술(MCP/A2A 등)을 적용해 확장성·완성도 강화
※ 핵심은 모든 기술을 다 쓰는 것이 아닌, 기술을 적절히 선택·조합해 높은 품질의 Agent 서비스를 설계·구현하는 것입니다.
4. 수행 가이드라인
4.1 주제 선정
실제 적용 가능성이 높고, 해결하고자 하는 문제가 명확한 주제를 선정합니다.
기존 서비스와 차별화할 요소를 고려하면 설계 및 구현 완성도 향상에 도움이 됩니다.
4.2 필수 기술 요소
대부분의 완결적 Agent 서비스에 공통적으로 요구되는 하기 내용이 포함되어야 합니다.
1) Prompt Engineering
역할 기반 프롬프트 설계, CoT, Few-shot 등 고품질 응답을 위한 구성
다양한 입력 상황에서도 일관성을 확보하는 프롬프트 구조화
2) LangChain/LangGraph 기반 Agent 구현
Multi-Agent 구조 설계 (단일 Agent 미인정)
Tool Calling, ReAct 기반 실행, Memory 활용
3) RAG (Retrieval-Augmented Generation)
데이터 전처리, 임베딩, Vector DB (FAISS/Chroma 등) 구성
검색 기반 지식 보강 기능 설계 및 구현
4) 서비스 개발 및 패키징
Streamlit 또는 원하는 프론트엔드 프레임워크로 UI 구성
FastAPI 기반 백엔드 구성, Docker 기반 배포 환경 구성(선택)
4.3 선택 요소 (Advanced Option)
A. LLM Fundamentals 기반 고도 설계
Structured Output, Function Calling, Reasoning 흐름 설계
B. MCP(Model Context Protocol) 기반 도구 연결
파일 시스템 접근, 외부 API/사내 시스템 연동 구조 설계
C. A2A(Agent-to-Agent) 협업 구조 설계
역할별 Agent 간 통신, 협업 기반 문제 해결 구조

기획 및 설계
# **[서비스명 - 이름]**
*예: AI Tech. Trend Agent – 홍길동*
## **1. 프로젝트 개요 – 기획 배경 및 핵심 내용**
### **1.1 프로젝트 기획 배경**
* *어떤 문제를 해결하고자 하는가?*
* *기존 방식의 한계는 무엇인가?*
* *Agent 서비스로 해결할 수 있는 Pain Point는 무엇인가?*
* *이 프로젝트를 시작하게 된 동기는 무엇인가?*
### **1.2 핵심 아이디어 및 가치 제안(Value Proposition)**
* *서비스가 제공하는 핵심 기능은 무엇인가?*
* *사용자에게 제공되는 가치와 기대효과는 무엇인가?*
* *기존 서비스 대비 차별성은 무엇인가?*
### **1.3 대상 사용자 및 기대 사용자 경험(UX)**
* *주요 타겟(예: 일반 사용자 / 실무자 / 개발자 등)*
* *사용자에게 어떤 흐름과 경험을 제공할 것인가?*
* *사용자가 서비스에서 얻는 구체적 Benefit은 무엇인가?*
## **2. 기술 구성 – 서비스에 적용할 기술 스택**
*아래 항목을 참고해 서비스에 적용한 기술 / 방식 등을 정리하세요
### **2.1 Prompt Engineering 전략**
* *역할 기반 프롬프트*
* *CoT/Few-shot 등 고품질 응답 전략*
* *출력 구조화 템플릿 정의*
* *사용자 유형/상황별 프롬프트 분기*
### **2.2 LangChain / LangGraph 기반 Agent 구조**
* *Multi-Agent 설계 개념*
* *각 Agent의 역할(Role) 정의*
* *Tool Calling, ReAct, Memory 활용 여부*
### **2.3 RAG 구성**
* *데이터 수집/전처리 파이프라인*
* *임베딩 모델 및 Vector DB 선택*
* *검색 로직과 응답 생성 방식*
### **2.4 서비스 개발 및 패키징 계획**
* *UI 개발 방식(Streamlit, React 등)*
* *BE(API) 및 배포 전략(FastAPI, Docker 등)*
* *설정/환경 관리 계획*
### **2.5 선택적 확장 기능**
* *LLM Fundamentals 기반 Structured Output / Function Calling*
* *MCP 기반 파일·시스템·API 연동*
* *A2A 기반 Agent 협업 구조*
## **3. 주요 기능 및 동작 시나리오**
### **3.1 사용자 시나리오(Use Case Scenario)**
* *사용자 목표와 과제 흐름*
* *서비스 이용 단계별 행동 정의*
### **3.2 시스템 구조도 / Multi-Agent 다이어그램**
*아래 두 가지 중 **하나 이상 필수 업로드**
* *시스템 전체 구조도*
* *Multi-Agent 구성도(LangGraph 등 사용 가능)*
Add image
### **3.3 서비스 플로우(Flow Chart / Sequence Diagram 등)**
* 사용자 요청 → Agent 처리 → RAG 검색 → 응답 생성 → UI 출력까지 흐름
Add image
## **4. 실행 결과**
*서비스 개발 IDE 내 소스 실행 결과
* *서비스 실행 결과 (text)*
* *데모 이미지 or 영상 등*
Add image
Add video
## **5. 추가 아이디어 (선택)**
향후 개선하고 싶은 기능이나 확장 아이디어를 자유롭게 작성하세요.
* *데이터 품질 개선, 타겟 분류 로직 고도화*

* *성능 최적화, 알림 채널 확대, UX 개선 등*
