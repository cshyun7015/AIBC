import re
from typing import List
from langchain_core.documents import Document

class DocumentPreprocessor:
    def clean_text(self, text: str) -> str:
        """텍스트 노이즈 정제 및 정규화"""
        # 연속된 공백 및 탭을 하나의 공백으로 통일
        text = re.sub(r'[ \t]+', ' ', text)
        # 3번 이상 연속된 줄바꿈을 2번으로 축소
        text = re.sub(r'\n{3,}', '\n\n', text)
        # 특수 제어 문자(널 바이트 등) 제거
        text = text.replace('\x00', '')
        # 좌우 공백 제거
        return text.strip()

    def extract_metadata(self, text: str) -> dict:
        """정규식을 활용한 핵심 필드 파싱 (메타데이터 설계)"""
        metadata = {}
        
        # 1. Ticket ID 추출 (예: "Ticket: #1024" 또는 "Ticket ID: INC001")
        ticket_match = re.search(r'(?:Ticket(?:\sID)?|티켓번호)[\s:]*#?([A-Z0-9\-]+)', text, re.IGNORECASE)
        if ticket_match:
            metadata['ticket_id'] = ticket_match.group(1).strip()
            
        # 2. Layer 추출 (예: "Layer: DB" 또는 "계층: BACKEND")
        layer_match = re.search(r'(?:Layer|계층)[\s:]*([A-Za-z가-힣]+)', text, re.IGNORECASE)
        if layer_match:
            metadata['layer'] = layer_match.group(1).strip().upper()
            
        # 3. Severity/위험도 추출 (예: "Severity: High" 또는 "위험도: 높음")
        severity_match = re.search(r'(?:Severity|위험도)[\s:]*([A-Za-z가-힣]+)', text, re.IGNORECASE)
        if severity_match:
            metadata['severity'] = severity_match.group(1).strip()
            
        # 4. Date/발생일시 추출 (예: "Date: 2023-10-15" 또는 "발생일시: 2023/10/15")
        date_match = re.search(r'(?:Date|발생일시|일시)[\s:]*([\d]{4}[-/][\d]{1,2}[-/][\d]{1,2})', text, re.IGNORECASE)
        if date_match:
            metadata['date'] = date_match.group(1).strip()
            
        return metadata

    def clean_documents(self, docs: List[Document]) -> List[Document]:
        """문서 리스트 전체를 순회하며 정제 적용"""
        for doc in docs:
            doc.page_content = self.clean_text(doc.page_content)
        return docs

    def extract_and_inject_metadata(self, docs: List[Document]) -> List[Document]:
        """문서 리스트 전체를 순회하며 메타데이터 파싱 및 병합"""
        for doc in docs:
            extracted_meta = self.extract_metadata(doc.page_content)
            # 기존 메타데이터(source, page 등) 보존하며 파싱된 메타데이터 병합
            doc.metadata.update(extracted_meta)
        return docs
