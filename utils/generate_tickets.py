import random
from fpdf import FPDF

# ==========================================
# 1. 도메인 맞춤형 가상 데이터 풀 (AntiGravity ITSM 스택 기반)
# ==========================================
categories = ["Frontend", "Backend", "Database", "Infra/Monitoring"]

symptoms = {
    "Frontend": [
        "VM 서버 계정 생성 폼 제출 시 CORS 에러 발생",
        "React 라우터 전환 시 간헐적 빈 화면 노출",
        "TypeScript 타입 에러로 인한 빌드 파이프라인 실패",
        "대시보드 차트 렌더링 시 브라우저 메모리 누수"
    ],
    "Backend": [
        "요청 관리 모듈 응답 지연 및 500 내부 서버 에러",
        "Spring Boot Actuator 엔드포인트 접근 불가",
        "MSA 서비스 간 FeignClient 호출 타임아웃",
        "OOM(Out Of Memory) 킬러에 의한 컨테이너 강제 재시작"
    ],
    "Database": [
        "MariaDB 데드락(Deadlock) 발생으로 인한 트랜잭션 롤백",
        "특정 조회 쿼리 실행 시 CPU 사용률 100% 스파이크",
        "DB Connection Pool 고갈 대기 상태 지속",
        "백업 스크립트 동작 중 테이블 락(Lock) 발생"
    ],
    "Infra/Monitoring": [
        "Promtail 로그 수집기 Pod CrashLoopBackOff 상태",
        "Grafana 얼럿 연동 3rd party API 웹훅 발송 실패",
        "컨테이너 디스크 볼륨 I/O 병목 현상",
        "Loki 쿼리(LogQL) 실행 시 메모리 초과 에러"
    ]
}

resolutions = {
    "Frontend": [
        "API Gateway의 CORS Allowed Origins 설정에 프론트엔드 도메인 추가",
        "React.lazy 및 Suspense를 활용한 코드 스플리팅 적용",
        "엄격한 타입 체크(strict mode) 예외 처리 및 인터페이스 재정의",
        "차트 컴포넌트 언마운트 시 메모리 해제(Cleanup) 로직 추가"
    ],
    "Backend": [
        "HikariCP max-lifetime 조정 및 트랜잭션 스코프 최소화",
        "Security Config에서 Actuator 경로 화이트리스트 추가",
        "Resilience4j를 활용한 Circuit Breaker 패턴 적용 및 Fallback 구현",
        "JVM 힙 메모리 옵션(-Xmx, -Xms) 튜닝 및 메모리 프로파일링 진행"
    ],
    "Database": [
        "트랜잭션 격리 수준(Isolation Level) 검토 및 쿼리 순서 동기화",
        "Slow Query 분석 후 결합 인덱스(Composite Index) 추가 생성",
        "max_connections 파라미터 증가 및 슬로우 쿼리 최적화",
        "논리적 백업(mysqldump) 대신 스냅샷 기반 물리 백업으로 전략 변경"
    ],
    "Infra/Monitoring": [
        "Promtail 설정(YAML) 내 읽기 제한(Rate Limit) 버퍼 크기 확장",
        "얼럿 발송 Timeout 설정 연장 및 재시도(Retry) 큐 구축",
        "Azure Disk 성능 계층(Premium SSD)으로 볼륨 마이그레이션",
        "Loki의 chunk_target_size 및 query_timeout 파라미터 최적화"
    ]
}

# ==========================================
# 2. 100개의 랜덤 티켓 생성
# ==========================================
tickets = []
for i in range(1, 101):
    cat = random.choice(categories)
    symptom = random.choice(symptoms[cat])
    resolution = random.choice(resolutions[cat])
    
    # 텍스트 조합 시 약간의 변주를 줍니다.
    title = f"[{cat}] {symptom.split()[0]} 관련 인시던트 보고"
    content = f"시스템 모니터링 및 사용자 제보를 통해 '{symptom}' 현상이 확인되었습니다. 관련 로그 확인 요망."
    solution_text = f"원인 파악 완료. {resolution} 조치를 통해 해결하였으며, Playwright E2E 테스트로 검증 마침."
    
    tickets.append({
        "id": f"INC-{2026000 + i}",
        "title": title,
        "content": content,
        "solution": solution_text
    })

# ==========================================
# 3. PDF 생성 (macOS 내장 폰트 활용)
# ==========================================
class PDF(FPDF):
    def header(self):
        self.set_font("Nanum", "B", 15)
        self.cell(0, 10, "AntiGravity ITSM 인시던트 해결 데이터 (RAG 학습용)", ln=True, align="C")
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("Nanum", "", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

pdf = PDF()
# 로컬에 다운로드 받은 나눔고딕 폰트를 로드합니다.
import os
base_dir = os.path.dirname(os.path.abspath(__file__))
pdf.add_font("Nanum", style="", fname=os.path.join(base_dir, "NanumGothic.ttf"), uni=True)
pdf.add_font("Nanum", style="B", fname=os.path.join(base_dir, "NanumGothicBold.ttf"), uni=True)

pdf.set_auto_page_break(auto=True, margin=15)
pdf.add_page()

# 티켓 내용을 PDF에 작성
for idx, ticket in enumerate(tickets):
    pdf.set_font("Nanum", "B", 12)
    pdf.cell(0, 10, f"#{idx+1}. [{ticket['id']}] {ticket['title']}", ln=True)
    
    pdf.set_font("Nanum", "", 10)
    pdf.multi_cell(0, 7, f"증상: {ticket['content']}")
    pdf.multi_cell(0, 7, f"해결방안: {ticket['solution']}")
    pdf.ln(5) # 티켓 간 간격

# 파일 저장
output_filename = "incident_tickets_for_rag.pdf"
pdf.output(output_filename)
print(f"✅ 총 100개의 가상 티켓이 '{output_filename}' 파일로 성공적으로 저장되었습니다!")