import { useEffect, useState } from 'react';

type RunResponse = {
  text: string;
  completed: boolean;
  stop_reason: string | null;
  metadata: Record<string, any>;
};

const API_BASE = 'http://localhost:8000';

export default function App() {
  const [task, setTask] = useState('Explain the architecture of this repository.');
  const [model, setModel] = useState('ollama:gemma:e2b');
  const [models, setModels] = useState<string[]>(['ollama:gemma:e2b']);
  const [responseMode, setResponseMode] = useState('pipeline');
  const [executionMode, setExecutionMode] = useState('direct');
  const [maxRounds, setMaxRounds] = useState(4);
  const [maxActions, setMaxActions] = useState(10);
  const [timeout, setTimeoutValue] = useState(600);
  const [role, setRole] = useState('');
  const [persona, setPersona] = useState('');
  const [enableTracing, setEnableTracing] = useState(true);
  const [result, setResult] = useState<RunResponse | null>(null);
  const [debugReport, setDebugReport] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/api/models`).then((r) => r.json()).then((d) => {
      const list = Array.isArray(d.models) && d.models.length ? d.models : ['ollama:gemma:e2b'];
      setModels(list);
      if (!list.includes(model)) setModel(list[0]);
    }).catch(() => {});
  }, []);

  const runAgent = async () => {
    setLoading(true);
    setDebugReport('');
    try {
      const res = await fetch(`${API_BASE}/api/agent/run`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task, model, response_mode: responseMode, execution_mode: executionMode, max_rounds: maxRounds, max_actions: maxActions, timeout, role: role || null, persona: persona || null, enable_tracing: enableTracing }),
      });
      setResult(await res.json());
    } finally { setLoading(false); }
  };

  const getDebugReport = async () => {
    if (!result) return;
    const res = await fetch(`${API_BASE}/api/debug/report`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ metadata: result.metadata }),
    });
    const data = await res.json();
    setDebugReport(data.report || '');
  };

  const events = (result?.metadata?.events ?? []) as Array<any>;

  return <div style={{ maxWidth: 1000, margin: '0 auto', padding: 20, fontFamily: 'sans-serif' }}>
    <h1>Module Lab UI</h1>
    <p>Frontend calls backend at {API_BASE}</p>
    <label>Task</label>
    <textarea value={task} onChange={(e) => setTask(e.target.value)} rows={5} style={{ width: '100%' }} />
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 10, marginTop: 10 }}>
      <input value={model} onChange={(e) => setModel(e.target.value)} list="models" placeholder="model" />
      <datalist id="models">{models.map((m) => <option key={m} value={m} />)}</datalist>
      <select value={responseMode} onChange={(e) => setResponseMode(e.target.value)}><option value="raw">raw</option><option value="think">think</option><option value="pipeline">pipeline</option></select>
      <select value={executionMode} onChange={(e) => setExecutionMode(e.target.value)}><option value="direct">direct</option><option value="react">react</option></select>
      <input type="number" value={maxRounds} onChange={(e) => setMaxRounds(Number(e.target.value))} placeholder="max rounds" />
      <input type="number" value={maxActions} onChange={(e) => setMaxActions(Number(e.target.value))} placeholder="max actions" />
      <input type="number" value={timeout} onChange={(e) => setTimeoutValue(Number(e.target.value))} placeholder="timeout" />
      <input value={role} onChange={(e) => setRole(e.target.value)} placeholder="role" />
      <input value={persona} onChange={(e) => setPersona(e.target.value)} placeholder="persona" />
      <label><input type="checkbox" checked={enableTracing} onChange={(e) => setEnableTracing(e.target.checked)} /> enable_tracing</label>
    </div>
    <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
      <button onClick={runAgent} disabled={loading}>{loading ? 'Running...' : 'Run'}</button>
      <button onClick={getDebugReport} disabled={!result}>Debug Report</button>
    </div>

    {result && <div style={{ marginTop: 16 }}>
      <h2>Result</h2>
      <div><b>completed:</b> {String(result.completed)}</div>
      <div><b>stop_reason:</b> {String(result.stop_reason)}</div>
      <div><b>LLM traces count:</b> {result.metadata?.llm_traces_count ?? (result.metadata?.llm_traces?.length ?? 0)}</div>
      <div><b>Tool traces count:</b> {result.metadata?.tool_traces_count ?? (result.metadata?.tool_traces?.length ?? 0)}</div>
      <h3>Final text</h3>
      <pre style={{ whiteSpace: 'pre-wrap' }}>{result.text}</pre>
      {events.length > 0 && <><h3>Events</h3><ul>{events.map((e, i) => <li key={i}>{e.type}: {e.title}</li>)}</ul></>}
    </div>}

    {debugReport && <div style={{ marginTop: 16 }}><h3>Debug Report</h3><pre style={{ whiteSpace: 'pre-wrap' }}>{debugReport}</pre></div>}
  </div>;
}
