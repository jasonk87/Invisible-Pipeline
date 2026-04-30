import React, { useState, useRef, useEffect } from 'react';
import { runPipeline, PipelineState, PipelineRound, ToolCacheEntry } from './lib/pipeline';
import { Terminal, Send, Zap, CheckCircle2, AlertCircle, Loader2, ChevronRight, History, Layers, Code, Play, Settings } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const AVAILABLE_MODELS = [
  { id: 'gemini-3-flash-preview', name: 'Gemini 3 Flash', description: 'Fast and efficient (Latest)' },
  { id: 'gemini-3.1-pro-preview', name: 'Gemini 3.1 Pro', description: 'Most capable (Latest)' },
  { id: 'gemini-3.1-flash-lite-preview', name: 'Gemini 3.1 Flash Lite', description: 'Ultra-fast, low latency' },
  { id: 'gemini-2.0-flash-001', name: 'Gemini 2.0 Flash', description: 'Next-gen performance' },
  { id: 'gemini-1.5-flash-latest', name: 'Gemini 1.5 Flash', description: 'Stable legacy model' },
  { id: 'gemini-1.5-pro-latest', name: 'Gemini 1.5 Pro', description: 'Capable legacy model' },
  { id: 'gemini-1.0-pro', name: 'Gemini 1.0 Pro', description: 'Classic stable model' },
];

export default function App() {
  const [prompt, setPrompt] = useState('');
  const [isAgentMode, setIsAgentMode] = useState(false);
  const [state, setState] = useState<PipelineState | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [selectedRoundId, setSelectedRoundId] = useState<number | null>(null);
  const [showRaw, setShowRaw] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [selectedModel, setSelectedModel] = useState(AVAILABLE_MODELS[0].id);
  const [copied, setCopied] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const handleCopy = () => {
    if (state?.finalAnswer) {
      navigator.clipboard.writeText(state.finalAnswer);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleRun = async () => {
    if (!prompt.trim() || isProcessing) return;
    
    const currentPrompt = prompt;
    // Clear prompt immediately and use a small timeout to ensure React processes it
    setPrompt('');
    
    setIsProcessing(true);
    setState(null);
    setSelectedRoundId(null);
    
    const maxRounds = isAgentMode ? 15 : 4;
    
    try {
      await runPipeline(currentPrompt, maxRounds, selectedModel, (newState) => {
        setState({ ...newState });
      });
    } finally {
      setIsProcessing(false);
    }
  };

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [state?.rounds]);

  return (
    <div className="min-h-screen flex flex-col data-grid overflow-hidden">
      {/* Header */}
      <header className="border-b border-line bg-bg/80 backdrop-blur-md p-4 flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-accent/20 border border-accent flex items-center justify-center rounded">
            <Zap className="w-5 h-5 text-accent" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight uppercase terminal-text">Invisible Pipeline</h1>
            <p className="text-[10px] text-gray-500 uppercase tracking-widest">Unidirectional Amnesia Architecture v2.2</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="hidden lg:flex items-center gap-4 mr-4 border-r border-line pr-4">
            <div className="text-right">
              <div className="text-[9px] font-bold text-gray-500 uppercase">Architecture</div>
              <div className="text-[10px] text-accent font-mono">LOCKED OUTPUT + NO REGRESSION</div>
            </div>
            <div className="text-right">
              <div className="text-[9px] font-bold text-gray-500 uppercase">Engine</div>
              <div className="text-[10px] text-blue-400 font-mono">
                {AVAILABLE_MODELS.find(m => m.id === selectedModel)?.name.toUpperCase()}
              </div>
            </div>
          </div>
          <div className="relative">
            <button 
              onClick={() => setShowSettings(!showSettings)}
              className={cn(
                "p-2 rounded-full border border-line transition-all",
                showSettings ? "bg-accent/20 border-accent text-accent" : "hover:bg-line/20 text-gray-400"
              )}
            >
              <Settings className="w-4 h-4" />
            </button>
            
            {showSettings && (
              <div className="absolute right-0 mt-2 w-64 bg-bg border border-line rounded-xl shadow-2xl z-50 p-4 animate-in fade-in slide-in-from-top-2">
                <div className="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-4">Pipeline Settings</div>
                
                <div className="space-y-4">
                  <div>
                    <label className="text-[9px] uppercase font-bold text-gray-400 mb-2 block">Model Selection</label>
                    <div className="space-y-2">
                      {AVAILABLE_MODELS.map((model) => (
                        <button
                          key={model.id}
                          onClick={() => {
                            setSelectedModel(model.id);
                            setShowSettings(false);
                          }}
                          className={cn(
                            "w-full text-left p-2 rounded border transition-all",
                            selectedModel === model.id 
                              ? "border-accent bg-accent/10 text-accent" 
                              : "border-line hover:bg-line/20 text-gray-400"
                          )}
                        >
                          <div className="text-[10px] font-bold">{model.name}</div>
                          <div className="text-[8px] opacity-60">{model.description}</div>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2 bg-line/30 px-3 py-1.5 rounded-full border border-line">
            <span className="text-[10px] uppercase font-bold text-gray-400">Agent Mode</span>
            <button 
              onClick={() => setIsAgentMode(!isAgentMode)}
              className={cn(
                "w-10 h-5 rounded-full relative transition-colors duration-200",
                isAgentMode ? "bg-accent" : "bg-gray-700"
              )}
            >
              <div className={cn(
                "absolute top-1 left-1 w-3 h-3 bg-white rounded-full transition-transform duration-200",
                isAgentMode && "translate-x-5"
              )} />
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 flex flex-col md:flex-row overflow-hidden">
        {/* Left Sidebar: Pipeline Visualization */}
        <aside className="w-full md:w-80 border-r border-line bg-bg/50 flex flex-col overflow-hidden">
          <div className="p-4 border-b border-line flex items-center justify-between bg-line/10">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-gray-400" />
              <span className="text-xs font-bold uppercase tracking-wider text-gray-400">Execution Stack</span>
            </div>
            {state && (
              <span className="text-[10px] font-mono text-accent">
                {state.rounds.length} ROUNDS
              </span>
            )}
          </div>
          
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
            {!state && !isProcessing && (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-4 opacity-30">
                <History className="w-12 h-12" />
                <p className="text-xs uppercase tracking-widest">Awaiting initialization...</p>
              </div>
            )}

            {state?.rounds.map((round, idx) => (
              <button 
                key={round.id}
                onClick={() => setSelectedRoundId(round.id === selectedRoundId ? null : round.id)}
                className={cn(
                  "w-full text-left border p-3 rounded-lg transition-all duration-300",
                  round.status === 'running' ? "border-accent bg-accent/5 animate-pulse" : "border-line bg-line/20 hover:bg-line/40",
                  selectedRoundId === round.id && "ring-1 ring-accent border-accent"
                )}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-mono text-gray-500">ROUND {round.id.toString().padStart(2, '0')}</span>
                  {round.status === 'running' && <Loader2 className="w-3 h-3 animate-spin text-accent" />}
                  {round.status === 'completed' && <CheckCircle2 className="w-3 h-3 text-accent" />}
                  {round.status === 'rewritten' && <History className="w-3 h-3 text-yellow-500" />}
                  {round.status === 'patched' && <Code className="w-3 h-3 text-blue-400" />}
                  {round.status === 'error' && <AlertCircle className="w-3 h-3 text-red-500" />}
                </div>
                <div className="text-[11px] font-bold uppercase tracking-tight mb-1">
                  {!round.isAudit ? "Foundation Generation" : 
                   round.status === 'completed' ? "Audit Approved" : 
                   round.status === 'patched' ? "Surgical Patch Audit" : 
                   round.status === 'error' ? "Execution Failed" : "Full Rewrite Audit"}
                </div>
                <div className="text-[9px] text-gray-500 font-mono truncate">
                  MODEL: {round.model}
                </div>
                
                {round.error && (
                  <div className="mt-2 text-[8px] text-red-500 font-mono bg-red-500/10 p-1.5 rounded border border-red-500/20">
                    ERROR: {round.error}
                  </div>
                )}
                
                {round.executionResults && round.executionResults.length > 0 && (
                  <div className="mt-2 flex items-center gap-1.5">
                    <Play className="w-2.5 h-2.5 text-accent" />
                    <span className="text-[8px] font-mono text-accent uppercase">Reality Check Run</span>
                  </div>
                )}

                {selectedRoundId === round.id && (
                  <div className="mt-3 pt-3 border-t border-line/50 space-y-3">
                    {round.auditFeedback && (
                      <div>
                        <div className="text-[8px] uppercase font-bold text-gray-500 mb-1">Auditor Feedback:</div>
                        <div className="text-[9px] text-accent font-mono line-clamp-4 bg-accent/5 p-1.5 rounded border border-accent/20">
                          {round.auditFeedback}
                        </div>
                      </div>
                    )}

                    {round.proposedAnswer && (
                      <div>
                        <div className="text-[8px] uppercase font-bold text-gray-500 mb-1">Draft Snapshot:</div>
                        <div className="text-[9px] text-gray-400 font-mono line-clamp-4 overflow-hidden">
                          {round.proposedAnswer}
                        </div>
                      </div>
                    )}
                    
                    {round.executionResults && round.executionResults.map((res, i) => (
                      <div key={i} className="bg-black/40 p-2 rounded border border-line/30">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-[7px] uppercase font-bold text-gray-500">Execution Result</span>
                          <span className={cn(
                            "text-[7px] font-mono",
                            res.status === 'success' ? "text-accent" : 
                            res.status === 'skipped' ? "text-gray-500" : "text-red-400"
                          )}>{res.status.toUpperCase()}</span>
                        </div>
                        <div className="text-[8px] font-mono text-gray-300 break-all line-clamp-3">
                          {res.output}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </button>
            ))}
            
            {state?.isComplete && !state?.error && (
              <div className="border border-accent/50 bg-accent/10 p-3 rounded-lg flex items-center gap-3">
                <CheckCircle2 className="w-5 h-5 text-accent" />
                <div>
                  <div className="text-[10px] font-bold uppercase text-accent">Pipeline Halted</div>
                  <div className="text-[9px] text-accent/70 font-mono">[COMPLETE] TAG DETECTED</div>
                </div>
              </div>
            )}

            {state?.error && (
              <div className="border border-red-500/50 bg-red-500/10 p-3 rounded-lg flex items-center gap-3">
                <AlertCircle className="w-5 h-5 text-red-500" />
                <div>
                  <div className="text-[10px] font-bold uppercase text-red-500">System Error</div>
                  <div className="text-[9px] text-red-500/70 font-mono">{state.error}</div>
                </div>
              </div>
            )}
          </div>
        </aside>

        {/* Main Content: Output Area */}
        <section className="flex-1 flex flex-col bg-bg overflow-hidden">
          <div className="flex-1 overflow-y-auto p-4 md:p-12 space-y-8">
            {state?.finalAnswer ? (
              <div className="max-w-4xl mx-auto">
                <div className="flex items-center justify-between mb-6 opacity-50">
                  <div className="flex items-center gap-2">
                    <Terminal className="w-4 h-4" />
                    <span className="text-[10px] uppercase tracking-[0.2em] font-bold">
                      {showRaw ? 'LITERAL ARTIFACT BUFFER' : 'RENDERED MARKDOWN VIEW'}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button 
                      onClick={handleCopy}
                      className={cn(
                        "text-[10px] uppercase font-bold border border-line px-3 py-1 rounded transition-all",
                        copied ? "bg-accent text-bg border-accent" : "hover:bg-line/20"
                      )}
                    >
                      {copied ? 'Copied!' : 'Copy Artifact'}
                    </button>
                    <button 
                      onClick={() => setShowRaw(!showRaw)}
                      className="text-[10px] uppercase font-bold border border-line px-3 py-1 rounded hover:bg-line/20 transition-colors"
                    >
                      {showRaw ? 'Show Rendered' : 'Show Literal'}
                    </button>
                  </div>
                </div>
                {showRaw ? (
                  <div className="relative group">
                    <pre className="text-xs font-mono bg-black/40 p-4 md:p-8 rounded-xl border border-line overflow-x-auto whitespace-pre-wrap break-words leading-relaxed shadow-inner">
                      {state.finalAnswer}
                    </pre>
                  </div>
                ) : (
                  <div className="markdown-body p-4 md:p-8 bg-bg/50 rounded-xl border border-line">
                    <ReactMarkdown>{state.finalAnswer}</ReactMarkdown>
                  </div>
                )}
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-center space-y-6">
                <div className="w-24 h-24 border border-line rounded-full flex items-center justify-center relative">
                  <div className="absolute inset-0 border border-accent/20 rounded-full animate-ping" />
                  <Zap className="w-10 h-10 text-gray-700" />
                </div>
                <div className="space-y-2">
                  <h2 className="text-xl font-bold tracking-tight text-gray-400">System Idle</h2>
                  <p className="text-sm text-gray-600 max-w-xs mx-auto">Input a prompt below to trigger the unidirectional amnesia pipeline.</p>
                </div>
              </div>
            )}
          </div>

          {/* Input Area */}
          <div className="p-4 border-t border-line bg-line/5">
            <div className="max-w-4xl mx-auto relative">
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleRun();
                  }
                }}
                placeholder="Enter a complex prompt (e.g., 'Generate the full economic ruleset for an NPC village')..."
                className="w-full bg-bg border border-line rounded-xl p-4 pr-16 text-sm focus:outline-none focus:border-accent transition-colors min-h-[100px] resize-none terminal-text"
                disabled={isProcessing}
              />
              <button
                onClick={handleRun}
                disabled={isProcessing || !prompt.trim()}
                className={cn(
                  "absolute bottom-4 right-4 p-2 rounded-lg transition-all duration-200",
                  isProcessing || !prompt.trim() 
                    ? "bg-gray-800 text-gray-600 cursor-not-allowed" 
                    : "bg-accent text-bg hover:scale-105 active:scale-95 shadow-[0_0_15px_rgba(0,255,65,0.3)]"
                )}
              >
                {isProcessing ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
              </button>
            </div>
            <div className="max-w-4xl mx-auto mt-2 flex items-center justify-between px-2">
              <div className="flex items-center gap-4">
                <div className={cn(
                  "flex items-center gap-1.5 transition-opacity duration-300",
                  isProcessing ? "opacity-100" : "opacity-50"
                )}>
                  <div className={cn(
                    "w-1.5 h-1.5 rounded-full",
                    isProcessing ? "bg-yellow-500 animate-pulse" : "bg-accent"
                  )} />
                  <span className="text-[9px] uppercase font-bold tracking-wider">
                    {isProcessing ? "System Processing" : "System Ready"}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 opacity-50">
                  <div className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                  <span className="text-[9px] uppercase font-bold tracking-wider">
                    {AVAILABLE_MODELS.find(m => m.id === selectedModel)?.name}
                  </span>
                </div>
              </div>
              <div className="text-[9px] text-gray-600 font-mono">
                {isProcessing ? "EXECUTING PIPELINE..." : "PRESS ENTER TO EXECUTE"}
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
