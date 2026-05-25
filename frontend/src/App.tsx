import { useState } from 'react';
import './index.css';

interface IncidentResponse {
  layer: string;
  rag_context_used: string;
  root_cause: string;
  solution: string;
  confidence: string;
  risk_level: string;
  test_scenario: string;
  qa_test_code: string;
}

function App() {
  const [incident, setIncident] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<IncidentResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showGraph, setShowGraph] = useState(false);

  const handleAnalyze = async () => {
    if (!incident.trim()) return;
    
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch('http://localhost:8000/api/v1/analyze-incident', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ incident_report: incident }),
      });

      if (!response.ok) {
        throw new Error('서버 응답에 오류가 발생했습니다.');
      }

      const data = await response.json();
      setResult(data);
    } catch (err: any) {
      setError(err.message || '인시던트 분석 중 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container">
      <header className="header">
        <h1>ITSM Agent</h1>
        <p>AI-Powered Incident Analysis & Resolution</p>
        <button className="toggle-graph-btn" onClick={() => setShowGraph(!showGraph)}>
          {showGraph ? '워크플로우 이미지 닫기' : '워크플로우 이미지 보기'}
        </button>
      </header>

      {showGraph && (
        <section className="glass-panel graph-panel">
          <h2>LangGraph Architecture</h2>
          <img src="http://localhost:8000/api/v1/graph-image" alt="LangGraph Workflow" className="graph-image" />
        </section>
      )}

      <section className="glass-panel input-section">
        <textarea
          placeholder="장애 현상을 상세히 입력해주세요. (예: 요청 등록 후 조회 시 500 에러 발생)"
          value={incident}
          onChange={(e) => setIncident(e.target.value)}
          disabled={loading}
        />
        <button 
          className="analyze-btn" 
          onClick={handleAnalyze} 
          disabled={loading || !incident.trim()}
        >
          {loading ? (
            <><span className="loader"></span> 분석 중...</>
          ) : (
            '인시던트 분석 시작'
          )}
        </button>
        {error && <div className="error-message">{error}</div>}
      </section>

      {result && (
        <section className="glass-panel result-grid">
          <div className="result-card">
            <h3>🔍 분석 요약 <span className="badge">{result.layer} LAYER</span> <span className="badge" style={{backgroundColor: 'rgba(59, 130, 246, 0.2)', color: '#60a5fa', marginLeft: '8px'}}>{result.confidence} 확신도</span> <span className="badge" style={{backgroundColor: 'rgba(239, 68, 68, 0.2)', color: '#ef4444', marginLeft: '8px'}}>{result.risk_level} RISK</span></h3>
            <p><strong>원인:</strong> {result.root_cause}</p>
          </div>

          <div className="result-card">
            <h3>💡 해결 방안</h3>
            <p>{result.solution}</p>
          </div>

          <div className="result-card">
            <h3>🤖 QA Master 검증 시나리오 및 코드</h3>
            <p style={{whiteSpace: 'pre-line', marginBottom: '16px', lineHeight: '1.6', color: '#e2e8f0'}}>{result.test_scenario}</p>
            <pre><code>{result.qa_test_code}</code></pre>
          </div>
        </section>
      )}
    </div>
  );
}

export default App;
