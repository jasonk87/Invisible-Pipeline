import { useEffect, useMemo, useState } from 'react';

type RunResponse = { text: string; completed: boolean; stop_reason: string | null; metadata: Record<string, any> };
const API_BASE = 'http://localhost:8000';

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-4"><h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-400">{title}</h3>{children}</section>;
}

export default function App() {
  const [task, setTask] = useState('Summarize the architecture and key local modules in this workspace.');
  const [model, setModel] = useState('ollama:gemma:e2b');
  const [responseMode, setResponseMode] = useState('pipeline');
  const [executionMode, setExecutionMode] = useState('direct');
  const [maxRounds, setMaxRounds] = useState(4); const [maxActions, setMaxActions] = useState(10); const [timeout, setTimeoutValue] = useState(600);
  const [role, setRole] = useState(''); const [persona, setPersona] = useState(''); const [enableTracing, setEnableTracing] = useState(true);
  const [models, setModels] = useState<string[]>(['ollama:gemma:e2b']); const [warning, setWarning] = useState('');
  const [status, setStatus] = useState<'checking'|'connected'|'offline'>('checking');
  const [result, setResult] = useState<RunResponse | null>(null); const [debugReport, setDebugReport] = useState(''); const [error, setError] = useState(''); const [loading, setLoading] = useState(false);

  const checkBackend = async () => {
    setStatus('checking'); setWarning('');
    try {
      const res = await fetch(`${API_BASE}/api/models`); const data = await res.json();
      const list = Array.isArray(data.models) && data.models.length ? data.models : ['ollama:gemma:e2b'];
      setModels(list); if (!list.includes(model)) setModel(list[0]); if (data.warning) setWarning(data.warning); setStatus('connected');
    } catch {
      setStatus('offline');
    }
  };
  useEffect(() => { checkBackend(); }, []);

  const runAgent = async () => {
    setLoading(true); setError(''); setDebugReport('');
    try {
      const res = await fetch(`${API_BASE}/api/agent/run`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ task, model, response_mode: responseMode, execution_mode: executionMode, max_rounds: maxRounds, max_actions: maxActions, timeout, role: role||null, persona: persona||null, enable_tracing: enableTracing }) });
      if (!res.ok) throw new Error(`Backend error: ${res.status}`);
      setResult(await res.json());
    } catch (e:any) { setError(e?.message || 'Backend unavailable. Is module_lab_server running?'); }
    finally { setLoading(false); }
  };

  const loadDebug = async () => {
    if (!result) return;
    const res = await fetch(`${API_BASE}/api/debug/report`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ metadata: result.metadata })});
    const data = await res.json(); setDebugReport(data.report || '');
  };

  const events = useMemo(() => (result?.metadata?.events ?? []) as any[], [result]);
  const llmTraces = useMemo(() => (result?.metadata?.llm_traces ?? []) as any[], [result]);
  const toolTraces = useMemo(() => (result?.metadata?.tool_traces ?? []) as any[], [result]);

  return <div className="min-h-screen bg-zinc-950 text-zinc-100">
    <header className="border-b border-zinc-800 bg-zinc-950/90 p-4"><div className="mx-auto max-w-[1500px]"><h1 className="text-xl font-bold">Module Lab Cockpit</h1><p className="text-sm text-zinc-400">AI modules control center · local backend wiring validation</p></div></header>
    <main className="mx-auto grid max-w-[1500px] grid-cols-12 gap-4 p-4">
      <aside className="col-span-12 lg:col-span-2 space-y-4">
        <Section title="Navigation"><div className="text-sm text-zinc-300">Single Agent Lab</div><div className="text-xs text-zinc-500 mt-2">Team Lab (coming later)</div></Section>
        <Section title="Backend Status">
          <div className="text-xs text-zinc-400">URL: {API_BASE}</div>
          <div className={`mt-2 font-semibold ${status==='connected'?'text-emerald-400':status==='offline'?'text-red-400':'text-yellow-300'}`}>{status==='connected'?'Connected':status==='offline'?'Offline':'Checking...'}</div>
          <button className="mt-2 rounded border border-zinc-700 px-2 py-1 text-xs" onClick={checkBackend}>Refresh</button>
          <div className="mt-3 text-xs text-zinc-300">Models: {models.join(', ')}</div>
          {warning && <div className="mt-2 rounded border border-amber-600/50 bg-amber-950/50 p-2 text-xs text-amber-300">{warning}</div>}
        </Section>
      </aside>

      <section className="col-span-12 lg:col-span-7 space-y-4">
        <Section title="Single Agent Lab">
          <label className="text-xs text-zinc-400">Task</label>
          <textarea className="mt-1 w-full rounded border border-zinc-700 bg-zinc-950 p-3 text-sm" rows={7} value={task} onChange={(e)=>setTask(e.target.value)} />
          <div className="mt-3 grid grid-cols-2 gap-2 lg:grid-cols-3">
            <input className="rounded border border-zinc-700 bg-zinc-950 p-2 text-sm" value={model} onChange={(e)=>setModel(e.target.value)} list="models" placeholder="model" />
            <datalist id="models">{models.map((m)=><option key={m} value={m}/> )}</datalist>
            <select className="rounded border border-zinc-700 bg-zinc-950 p-2 text-sm" value={responseMode} onChange={(e)=>setResponseMode(e.target.value)}><option>raw</option><option>think</option><option>pipeline</option></select>
            <select className="rounded border border-zinc-700 bg-zinc-950 p-2 text-sm" value={executionMode} onChange={(e)=>setExecutionMode(e.target.value)}><option>direct</option><option>react</option></select>
            <input className="rounded border border-zinc-700 bg-zinc-950 p-2 text-sm" type="number" value={maxRounds} onChange={(e)=>setMaxRounds(Number(e.target.value))} placeholder="max_rounds"/>
            <input className="rounded border border-zinc-700 bg-zinc-950 p-2 text-sm" type="number" value={maxActions} onChange={(e)=>setMaxActions(Number(e.target.value))} placeholder="max_actions"/>
            <input className="rounded border border-zinc-700 bg-zinc-950 p-2 text-sm" type="number" value={timeout} onChange={(e)=>setTimeoutValue(Number(e.target.value))} placeholder="timeout"/>
            <input className="rounded border border-zinc-700 bg-zinc-950 p-2 text-sm" value={role} onChange={(e)=>setRole(e.target.value)} placeholder="role"/>
            <input className="rounded border border-zinc-700 bg-zinc-950 p-2 text-sm" value={persona} onChange={(e)=>setPersona(e.target.value)} placeholder="persona"/>
            <label className="flex items-center gap-2 rounded border border-zinc-700 bg-zinc-950 p-2 text-sm"><input type="checkbox" checked={enableTracing} onChange={(e)=>setEnableTracing(e.target.checked)}/>enable_tracing</label>
          </div>
          <div className="mt-4 flex gap-2"><button onClick={runAgent} disabled={loading} className="rounded bg-emerald-500 px-4 py-2 text-black font-semibold">{loading?'Running...':'Run Agent'}</button><button onClick={loadDebug} disabled={!result} className="rounded border border-zinc-700 px-4 py-2">Debug Report</button></div>
          {error && <div className="mt-3 rounded border border-red-700 bg-red-950/40 p-3 text-sm text-red-300">{error}</div>}
        </Section>

        <Section title="Final Answer">
          <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded bg-zinc-950 p-3 text-sm text-zinc-200">{result?.text || 'Run an agent task to see output.'}</pre>
        </Section>

        <Section title="Execution Timeline">
          <div className="space-y-2">
            {events.map((e, i)=><details key={`e${i}`} className="rounded border border-zinc-800 bg-zinc-950 p-2"><summary className="cursor-pointer text-sm"><span className="text-emerald-400">[{e.type}]</span> {e.title || 'event'}</summary><pre className="mt-2 overflow-auto whitespace-pre-wrap text-xs text-zinc-300">{JSON.stringify(e.details ?? e, null, 2)}</pre></details>)}
            {llmTraces.map((t, i)=><details key={`l${i}`} className="rounded border border-sky-900 bg-zinc-950 p-2"><summary className="cursor-pointer text-sm text-sky-300">LLM Trace {i+1}</summary><pre className="mt-2 overflow-auto whitespace-pre-wrap text-xs">Prompt:\n{t.prompt}\n\nResponse:\n{t.response}</pre></details>)}
            {toolTraces.map((t, i)=><details key={`t${i}`} className="rounded border border-violet-900 bg-zinc-950 p-2"><summary className="cursor-pointer text-sm text-violet-300">Tool Trace {i+1}: {t.tool_name}</summary><pre className="mt-2 overflow-auto whitespace-pre-wrap text-xs">Args: {JSON.stringify(t.args, null, 2)}\n\nOutput: {t.output || ''}</pre></details>)}
            {!events.length && !llmTraces.length && !toolTraces.length && <div className="text-sm text-zinc-500">No timeline yet.</div>}
          </div>
        </Section>
      </section>

      <aside className="col-span-12 lg:col-span-3 space-y-4">
        <Section title="Run Inspector">
          <div className="space-y-2 text-sm">
            <div>completed: <span className="text-emerald-400">{String(result?.completed ?? false)}</span></div>
            <div>stop_reason: <span className="text-zinc-300">{String(result?.stop_reason ?? 'n/a')}</span></div>
            <div>LLM traces: {result?.metadata?.llm_traces_count ?? llmTraces.length}</div>
            <div>Tool traces: {result?.metadata?.tool_traces_count ?? toolTraces.length}</div>
            <div>Events: {events.length}</div>
          </div>
          <details className="mt-3"><summary className="cursor-pointer text-xs text-zinc-400">Raw metadata</summary><pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap rounded bg-zinc-950 p-2 text-xs">{JSON.stringify(result?.metadata ?? {}, null, 2)}</pre></details>
        </Section>
        <Section title="Debug Report"><pre className="max-h-[480px] overflow-auto whitespace-pre-wrap rounded bg-zinc-950 p-2 font-mono text-xs">{debugReport || 'Click Debug Report after a run.'}</pre></Section>
      </aside>
    </main>
  </div>;
}
