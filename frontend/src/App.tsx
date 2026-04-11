import { useCallback, useState } from "react";
import { compareDocuments, uploadAndSearch } from "./api/client";
import type {
  ComparisonResult,
  KnowledgeBaseMatch,
  UploadedDocument,
} from "./api/types";
import GapAnalysisDashboard from "./components/GapAnalysisDashboard";
import { KnowledgeBaseManager } from "./components/KnowledgeBaseManager";
import { PdfUpload } from "./components/PdfUpload";
import { ChatPanel } from "./components/ChatPanel";
import {
  FileText,
  RotateCcw,
  PanelLeftClose,
  PanelLeftOpen,
  LogOut,
  MessageSquare,
} from "lucide-react";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { Login } from "./components/Login";

type Phase = "upload" | "comparing" | "results";

function AppInner() {
  const [phase, setPhase] = useState<Phase>("upload");
  const [uploadedDocument, setUploadedDocument] =
    useState<UploadedDocument | null>(null);
  const [matches, setMatches] = useState<KnowledgeBaseMatch[]>([]);
  const [comparisonResult, setComparisonResult] =
    useState<ComparisonResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [chatOpen, setChatOpen] = useState(false);
  const [compareStatus, setCompareStatus] = useState("Docling (Parsing PDF)");

  const { isAuthenticated, isLoading, user, logout } = useAuth();

  const handleUpload = useCallback(async (file: File) => {
    setError(null);
    setPhase("comparing");
    setCompareStatus("Docling (Parsing PDF)");

    const steps = [
      "Docling (Parsing PDF)",
      "LLM (Extracting entities)",
      "Searching knowledge base",
    ];
    let stepIndex = 0;
    const interval = setInterval(() => {
      stepIndex = Math.min(stepIndex + 1, steps.length - 1);
      setCompareStatus(steps[stepIndex]);
    }, 2500);

    try {
      const { document, matches: searchMatches } = await uploadAndSearch(file);
      setUploadedDocument(document);
      setMatches(searchMatches);
      
      setCompareStatus("LLM (Generating Gap Analysis)");
      
      const result = await compareDocuments(
        document.extractedText,
        searchMatches,
        document.extractedJson
      );
      setComparisonResult(result);
      setPhase("results");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setPhase("upload");
    } finally {
      clearInterval(interval);
    }
  }, []);

  const handleReset = useCallback(() => {
    setPhase("upload");
    setUploadedDocument(null);
    setMatches([]);
    setComparisonResult(null);
    setError(null);
  }, []);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-500 font-medium">Loading session...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Login />;
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-30">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setSidebarOpen((prev) => !prev)}
              className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-gray-400"
              aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"}
            >
              {sidebarOpen ? (
                <PanelLeftClose className="w-5 h-5" />
              ) : (
                <PanelLeftOpen className="w-5 h-5" />
              )}
            </button>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-lg flex items-center justify-center">
                <FileText className="w-5 h-5 text-white" aria-hidden />
              </div>
              <div>
                <h1 className="text-lg font-bold text-gray-900 leading-tight">
                  DocCompare
                </h1>
                <p className="text-[10px] text-gray-500 uppercase tracking-wider font-medium leading-tight">
                  Knowledge Base Comparison Tool
                </p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="hidden sm:flex flex-col items-end mr-2">
              <span className="text-sm font-medium text-gray-900 leading-none">
                Logged in as: {user?.username}
              </span>
              <span className="text-xs text-gray-500 uppercase tracking-wider font-semibold mt-1">
                ({user?.role})
              </span>
            </div>
            
            {phase === "results" && (
              <button
                type="button"
                onClick={handleReset}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-colors"
                aria-label="Compare another document"
              >
                <RotateCcw className="w-4 h-4" />
                New comparison
              </button>
            )}

            <button
              type="button"
              onClick={() => setChatOpen(!chatOpen)}
              className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-blue-700 bg-blue-50 border border-blue-200 hover:bg-blue-100 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
              aria-label="Chat with KB"
            >
              <MessageSquare className="w-4 h-4" />
              <span className="hidden sm:inline">Ask KB</span>
            </button>

            <button
              type="button"
              onClick={() => { handleReset(); logout(); }}
              className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-red-600 bg-white border border-red-200 hover:bg-red-50 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition-colors"
              aria-label="Logout"
            >
              <LogOut className="w-4 h-4" />
              <span className="hidden sm:inline">Logout</span>
            </button>
          </div>
        </div>
      </header>

      <div className="flex-1 flex max-w-[1400px] mx-auto w-full">
        <aside
          className={`
            shrink-0 border-r border-gray-200 bg-white overflow-y-auto transition-all duration-200
            ${sidebarOpen ? "w-[420px]" : "w-0 overflow-hidden border-r-0"}
          `}
        >
          <div className="p-4 w-[420px]">
            <KnowledgeBaseManager />
          </div>
        </aside>

        <main className="flex-1 min-w-0 p-6 sm:p-8 overflow-y-auto">
          {error && (
            <div
              className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl text-red-800 text-sm flex items-start gap-2"
              role="alert"
            >
              <span className="font-medium">Error:</span> {error}
            </div>
          )}

          {phase === "upload" && (
            <div className="flex flex-col items-center justify-center min-h-[60vh] gap-8">
              <div className="text-center space-y-2">
                <h2 className="text-2xl font-bold text-gray-900">
                  Compare a document
                </h2>
                <p className="text-gray-500 max-w-md">
                  Upload a BRD or user story PDF to find similar documents in the
                  knowledge base and view a side-by-side comparison.
                </p>
              </div>
              <PdfUpload onUpload={handleUpload} />
            </div>
          )}

          {phase === "comparing" && (
            <div className="flex flex-col items-center justify-center min-h-[60vh] gap-8">
              <PdfUpload
                onUpload={handleUpload}
                isLoading
                status={compareStatus}
              />
            </div>
          )}

          {phase === "results" && comparisonResult && uploadedDocument && (
            <div className="space-y-8">
              <div className="flex flex-col sm:flex-row sm:items-center gap-3 pb-4 border-b border-gray-200">
                <div className="flex items-center gap-2">
                  <FileText className="w-5 h-5 text-blue-600" />
                  <span className="text-sm font-medium text-gray-800">
                    {uploadedDocument.filename}
                  </span>
                </div>
                {matches.length > 0 && (
                  <span className="text-xs text-gray-500 bg-gray-100 px-2.5 py-1 rounded-full">
                    {matches.length} matching{" "}
                    {matches.length === 1 ? "document" : "documents"} found
                  </span>
                )}
              </div>
              
              {comparisonResult.gapAnalysisJson ? (
                <GapAnalysisDashboard data={comparisonResult.gapAnalysisJson} />
              ) : (
                <div className="p-12 text-center text-gray-500 bg-white rounded-xl border border-gray-200 shadow-sm">
                  Loading gap analysis or no matching documents found...
                </div>
              )}
            </div>
          )}
        </main>
        
        {chatOpen && (
          <aside className="w-[380px] shrink-0 border-l border-gray-200 bg-white overflow-hidden p-4">
            <ChatPanel onClose={() => setChatOpen(false)} />
          </aside>
        )}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppInner />
    </AuthProvider>
  );
}
