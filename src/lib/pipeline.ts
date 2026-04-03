import { GoogleGenAI, GenerateContentResponse } from "@google/genai";

export interface ToolCacheEntry {
  type: 'code_execution';
  query: string;
  output: string;
  status: 'success' | 'error' | 'skipped';
}

export interface PipelineRound {
  id: number;
  status: 'pending' | 'running' | 'completed' | 'rewritten' | 'patched' | 'error';
  proposedAnswer: string;
  isAudit: boolean;
  model: string;
  error?: string;
  auditFeedback?: string;
  executionResults?: ToolCacheEntry[];
}

export interface PipelineState {
  rounds: PipelineRound[];
  toolCache: ToolCacheEntry[];
  finalAnswer: string;
  isComplete: boolean;
  error?: string;
}

const SYSTEM_WRAPPER = `SYSTEM RULES: YOU ARE THE GATEKEEPER
You are reviewing a proposed answer.

If it fully satisfies the task, output exactly:
[COMPLETE]

If it does not, output a corrected full replacement or surgical patches (<<<< SEARCH / ==== / >>>>).

RULES:
- Preserve exact required strings (headers, versions, signatures).
- Do not remove or alter previously correct content from [PREVIOUS VERSION].
- For code tasks, output valid code only. No markdown separators (---) inside code blocks.
- Entrypoints/guards must be exact (e.g., if __name__ == "__main__":).
- Fix only what is necessary to satisfy the task.
- Do not add commentary or meta-talk.

INPUT DATA:
* [USER PROMPT]: The original task.
* [EXECUTED TOOLS / CACHE]: Results from code execution.
* [PREVIOUS VERSION]: The draft from the previous round.
* [PROPOSED ANSWER]: The current draft to be audited.

YOUR DIRECTIVE:
Verify [PROPOSED ANSWER]. If it satisfies the task and rules: Output [COMPLETE]. Otherwise, output the fix.`;

// Create a Web Worker Blob for safe code execution
const workerCode = `
  self.onmessage = async (e) => {
    const { code } = e.data;
    let output = "";
    let status = 'success';
    
    const customConsole = {
      log: (...args) => { output += args.join(" ") + "\\n"; },
      error: (...args) => { output += "ERROR: " + args.join(" ") + "\\n"; status = 'error'; },
      warn: (...args) => { output += "WARN: " + args.join(" ") + "\\n"; },
      info: (...args) => { output += "INFO: " + args.join(" ") + "\\n"; }
    };

    try {
      const fn = new Function('console', \`return (async () => { \${code} })()\`);
      await fn(customConsole);
      if (output === "") output = "Code executed successfully (no output).";
    } catch (e) {
      output += "RUNTIME ERROR: " + e.message;
      status = 'error';
    }
    
    self.postMessage({ output, status });
  };
`;

const workerBlob = new Blob([workerCode], { type: 'application/javascript' });
const workerUrl = URL.createObjectURL(workerBlob);

function runInWorker(code: string, timeoutMs: number): Promise<{ output: string, status: 'success' | 'error' }> {
  return new Promise((resolve) => {
    const worker = new Worker(workerUrl);
    const timeout = setTimeout(() => {
      worker.terminate();
      resolve({ output: "RUNTIME ERROR: Execution timed out (" + timeoutMs + "ms)", status: 'error' });
    }, timeoutMs);

    worker.onmessage = (e) => {
      clearTimeout(timeout);
      worker.terminate();
      resolve(e.data);
    };

    worker.onerror = (e) => {
      clearTimeout(timeout);
      worker.terminate();
      resolve({ output: "RUNTIME ERROR: " + e.message, status: 'error' });
    };

    worker.postMessage({ code });
  });
}

function applyPatches(text: string, patches: { search: string; replace: string }[]): string {
  let result = text;
  for (const patch of patches) {
    if (result.includes(patch.search)) {
      // Use split/join to replace ALL occurrences and avoid $ replacement pattern issues
      result = result.split(patch.search).join(patch.replace);
    } else {
      // Try a more flexible match: ignore trailing whitespace and allow flexible indentation
      const lines = patch.search.split('\n');
      const escapedLines = lines.map(line => 
        line.trim() === '' ? '\\s*' : line.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').trimEnd()
      );
      
      // Construct a regex that allows flexible whitespace at line starts/ends
      const flexibleRegex = new RegExp(escapedLines.join('\\s*\\n\\s*'), 'g');
      
      if (flexibleRegex.test(result)) {
        console.log("Patch: Found flexible match for search block");
        // Replace all occurrences using the regex
        result = result.replace(flexibleRegex, () => patch.replace);
      } else {
        console.warn("Patch search block not found:", patch.search);
      }
    }
  }
  return result;
}

function parsePatches(text: string): { search: string; replace: string }[] | null {
  const patches: { search: string; replace: string }[] = [];
  // Even more robust regex for patches
  const regex = /<<<<\s*SEARCH\s*[\n\r]+([\s\S]*?)[\n\r]+\s*====\s*[\n\r]+([\s\S]*?)[\n\r]+\s*>>>>/g;
  let match;
  while ((match = regex.exec(text)) !== null) {
    patches.push({ search: match[1], replace: match[2] });
  }
  return patches.length > 0 ? patches : null;
}

async function executeCodeBlocks(text: string): Promise<ToolCacheEntry[]> {
  // More robust regex for code blocks
  const codeBlockRegex = /```(\w+)?\s*[\n\r]+([\s\S]*?)[\n\r]+\s*```/g;
  const results: ToolCacheEntry[] = [];
  let match;

  while ((match = codeBlockRegex.exec(text)) !== null) {
    const lang = match[1]?.toLowerCase();
    const code = match[2];
    
    // Only execute if it's explicitly a JS/TS block
    const supportedLangs = ['js', 'ts', 'javascript', 'typescript'];
    if (lang && !supportedLangs.includes(lang)) {
      results.push({
        type: 'code_execution',
        query: code,
        output: `Reality Check: Skipping unsupported language "${lang}"`,
        status: 'skipped'
      });
      continue;
    }

    // If no language is specified, we check if it looks like it might be JS
    if (!lang) {
      const isLikelyJS = /console\.log|const\s+|let\s+|var\s+|function\s*\(|=>/.test(code);
      const isLikelyPython = /import\s+|def\s+|print\(/.test(code);
      
      if (!isLikelyJS || isLikelyPython) {
        // If it looks like Python, we can do a basic syntax check even if we can't run it
        if (isLikelyPython) {
          let pythonOutput = "";
          let pythonStatus: 'success' | 'error' = 'success';
          
          // Check for common Python mistakes mentioned in feedback
          if (code.includes('if name == "main":') || code.includes("if name == 'main':")) {
            pythonOutput += "REALITY CHECK ERROR: Invalid Python main guard. Use 'if __name__ == \"__main__\":'\n";
            pythonStatus = 'error';
          }
          
          if (code.includes('---')) {
            pythonOutput += "REALITY CHECK ERROR: Markdown separators (---) found inside code block. This is invalid Python.\n";
            pythonStatus = 'error';
          }

          results.push({
            type: 'code_execution',
            query: code,
            output: pythonStatus === 'error' ? pythonOutput.trim() : "Reality Check: Python block detected. (Basic syntax check passed, execution skipped in browser)",
            status: pythonStatus === 'error' ? 'error' : 'skipped'
          });
        } else {
          results.push({
            type: 'code_execution',
            query: code,
            output: "Reality Check: Skipping untagged or non-JS looking block",
            status: 'skipped'
          });
        }
        continue;
      }
    }

    // Explicit Python block check
    if (lang === 'python' || lang === 'py') {
      let pythonOutput = "";
      let pythonStatus: 'success' | 'error' = 'success';
      
      if (code.includes('if name == "main":') || code.includes("if name == 'main':")) {
        pythonOutput += "REALITY CHECK ERROR: Invalid Python main guard. Use 'if __name__ == \"__main__\":'\n";
        pythonStatus = 'error';
      }
      
      if (code.includes('---')) {
        pythonOutput += "REALITY CHECK ERROR: Markdown separators (---) found inside code block. This is invalid Python.\n";
        pythonStatus = 'error';
      }

      results.push({
        type: 'code_execution',
        query: code,
        output: pythonStatus === 'error' ? pythonOutput.trim() : "Reality Check: Python block detected. (Basic syntax check passed, execution skipped in browser)",
        status: pythonStatus === 'error' ? 'error' : 'skipped'
      });
      continue;
    }

    console.log("Reality Check: Executing code block...");
    
    const { output, status } = await runInWorker(code, 5000);

    results.push({
      type: 'code_execution',
      query: code,
      output: output.trim(),
      status
    });
  }

  return results;
}

export async function runPipeline(
  prompt: string,
  maxRounds: number = 3,
  modelName: string = "gemini-3-flash-preview",
  onUpdate: (state: PipelineState) => void
) {
  console.log(`Starting Advanced Pipeline v2.1 (Strict Separation of Powers) with model: ${modelName}...`);
  
  // Fallback check for API key to prevent silent hangs
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    console.error("GEMINI_API_KEY is missing from environment variables.");
    onUpdate({ 
      rounds: [], 
      toolCache: [], 
      finalAnswer: '', 
      isComplete: false, 
      error: "API Key Missing: Please ensure GEMINI_API_KEY is set in your environment." 
    });
    return;
  }

  const ai = new GoogleGenAI({ apiKey });
  
  let currentState: PipelineState = {
    rounds: [],
    toolCache: [],
    finalAnswer: '',
    isComplete: false
  };

  const update = (newState: Partial<PipelineState>) => {
    currentState = { ...currentState, ...newState };
    onUpdate({ ...currentState });
  };

  try {
    let currentDraft = "";
    let previousDraft = "";

    for (let roundIdx = 1; roundIdx <= maxRounds; roundIdx++) {
      console.log(`--- Round ${roundIdx} ---`);
      const isFirstRound = roundIdx === 1;
      
      const newRound: PipelineRound = {
        id: roundIdx,
        status: 'running',
        proposedAnswer: currentDraft,
        isAudit: !isFirstRound,
        model: modelName
      };

      update({ rounds: [...currentState.rounds, newRound] });

      let response: GenerateContentResponse;

      try {
        const apiTimeout = 120000; // 120s timeout for API calls
        const timeoutPromise = new Promise<never>((_, reject) => 
          setTimeout(() => reject(new Error(`Model response timed out after ${apiTimeout/1000}s`)), apiTimeout)
        );

        if (isFirstRound) {
          const callPromise = ai.models.generateContent({
            model: modelName,
            contents: prompt,
            config: {
              systemInstruction: "You are a high-precision execution engine. Provide the absolute best final answer to the user's prompt. Follow all instructions exactly. Do not output [COMPLETE]."
            }
          });
          response = await Promise.race([callPromise, timeoutPromise]);
        } else {
          const auditPrompt = `
[USER PROMPT]: ${prompt}
[EXECUTED TOOLS / CACHE]: ${JSON.stringify(currentState.toolCache)}
[PREVIOUS VERSION]: ${previousDraft || "None (First Audit)"}
[PROPOSED ANSWER]: ${currentDraft}
          `.trim();

          const callPromise = ai.models.generateContent({
            model: modelName,
            contents: auditPrompt,
            config: {
              systemInstruction: SYSTEM_WRAPPER
            }
          });
          response = await Promise.race([callPromise, timeoutPromise]);
        }

        if (!response || !response.candidates || response.candidates.length === 0) {
          throw new Error("The model returned an empty response or was blocked by safety filters.");
        }
      } catch (apiError: any) {
        console.error(`Round ${roundIdx} Error:`, apiError);
        const updatedRounds = [...currentState.rounds];
        updatedRounds[roundIdx - 1].status = 'error';
        updatedRounds[roundIdx - 1].error = apiError.message || "Operation failed";
        update({ 
          rounds: updatedRounds, 
          error: `Round ${roundIdx} failed: ${apiError.message}`,
          isComplete: true 
        });
        return; // Stop the pipeline on error
      }

      const rawResponse = (response.text || '').trim();
      const updatedRounds = [...currentState.rounds];
      const currentRound = updatedRounds[roundIdx - 1];

      // 1. Check for [COMPLETE] - STRICT: Must be the ONLY text in the response
      if (rawResponse.toUpperCase() === '[COMPLETE]' && !isFirstRound) {
        console.log(`Round ${roundIdx}: [COMPLETE] detected. No edits made. Halting.`);
        currentRound.status = 'completed';
        update({ rounds: updatedRounds, isComplete: true, finalAnswer: currentDraft });
        break;
      }

      // 2. Process Edits (Patches or Rewrite)
      // If the agent tried to include [COMPLETE] with other text, we ignore the tag and treat it as an edit
      const cleanedResponse = rawResponse.replace(/\[COMPLETE\]/gi, '').trim();
      
      previousDraft = currentDraft; // Save the draft before updating it
      
      const patches = parsePatches(cleanedResponse);
      if (patches) {
        console.log(`Round ${roundIdx}: Applying ${patches.length} patches.`);
        
        // Extract feedback (text outside the patches)
        const feedback = cleanedResponse.replace(/<<<<\s*SEARCH\s*[\n\r]+([\s\S]*?)[\n\r]+\s*====\s*[\n\r]+([\s\S]*?)[\n\r]+\s*>>>>/g, '').trim();
        currentRound.auditFeedback = feedback;
        
        currentDraft = applyPatches(currentDraft, patches);
        currentRound.status = 'patched';
      } else {
        // If no patches, check if it's a rewrite or just filler
        const isSubstantial = cleanedResponse.length > currentDraft.length * 0.5 || cleanedResponse.includes('```');
        
        if (!isFirstRound && !isSubstantial && cleanedResponse.length < 200) {
          console.log(`Round ${roundIdx}: Detected filler response. Ignoring to prevent draft wipe.`);
          currentRound.status = 'completed';
          currentRound.auditFeedback = cleanedResponse;
          // Don't update currentDraft
        } else {
          console.log(`Round ${roundIdx}: Full rewrite/foundation.`);
          currentDraft = cleanedResponse;
          currentRound.status = isFirstRound ? 'completed' : 'rewritten';
        }
      }

      currentRound.proposedAnswer = currentDraft;

      // 3. Reality Check: Execute Code Blocks
      console.log(`Round ${roundIdx}: Running Reality Check...`);
      const executionResults = await executeCodeBlocks(currentDraft);
      currentRound.executionResults = executionResults;
      
      // Update global cache
      update({ 
        rounds: updatedRounds, 
        toolCache: [...currentState.toolCache, ...executionResults],
        finalAnswer: currentDraft
      });

      if (roundIdx === maxRounds) {
        console.log(`Round ${roundIdx}: Max rounds reached. Finalizing.`);
        update({ isComplete: true });
      }
    }
  } catch (error: any) {
    console.error("Pipeline Error:", error);
    update({ error: error.message || "An unknown error occurred" });
  }
}
