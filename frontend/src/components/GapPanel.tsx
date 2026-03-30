import {
  Sparkles,
  Globe,
  Copy,
  Check,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
} from "lucide-react";
import { useCallback, useState } from "react";
import type { Gap, GenerateGapSource } from "../api/types";
import { generateGapContent } from "../api/client";

interface GapPanelProps {
  gaps: Gap[];
  onGapUpdate?: (gapId: string, generatedContent: string) => void;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [text]);

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded transition-colors focus:outline-none focus:ring-2 focus:ring-gray-400"
      aria-label="Copy to clipboard"
    >
      {copied ? (
        <>
          <Check className="w-3.5 h-3.5 text-green-600" />
          <span className="text-green-600">Copied</span>
        </>
      ) : (
        <>
          <Copy className="w-3.5 h-3.5" />
          Copy
        </>
      )}
    </button>
  );
}

function GapCard({
  gap,
  generatedContent,
  isGenerating,
  generatingSource,
  onGenerate,
}: {
  gap: Gap;
  generatedContent: string | undefined;
  isGenerating: boolean;
  generatingSource: string | null;
  onGenerate: (gapId: string, source: GenerateGapSource) => void;
}) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="border border-gray-200 rounded-xl bg-white shadow-sm overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="w-full flex items-center gap-3 px-5 py-4 text-left hover:bg-gray-50 transition-colors focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500"
        aria-expanded={expanded}
      >
        {expanded ? (
          <ChevronDown className="w-4 h-4 text-gray-400 shrink-0" />
        ) : (
          <ChevronRight className="w-4 h-4 text-gray-400 shrink-0" />
        )}
        <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0" />
        <span className="flex-1 font-medium text-gray-800 text-sm">
          {gap.description}
        </span>
        {generatedContent && (
          <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-green-100 text-green-700 shrink-0">
            Generated
          </span>
        )}
      </button>

      {expanded && (
        <div className="px-5 pb-5 space-y-4">
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
            <p className="text-xs font-medium text-amber-700 mb-1">
              From uploaded document:
            </p>
            <p className="text-sm text-amber-900 italic leading-relaxed">
              &ldquo;{gap.uploadedExcerpt}&rdquo;
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => onGenerate(gap.id, "llm")}
              disabled={isGenerating}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 rounded-lg shadow-sm disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-all"
              aria-label={`Generate from LLM for: ${gap.description}`}
            >
              <Sparkles className="w-4 h-4" />
              {generatingSource === `${gap.id}-llm` ? "Generating..." : "Generate with LLM"}
            </button>
            <button
              type="button"
              onClick={() => onGenerate(gap.id, "online")}
              disabled={isGenerating}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 rounded-lg shadow-sm disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-all"
              aria-label={`Search online for: ${gap.description}`}
            >
              <Globe className="w-4 h-4" />
              {generatingSource === `${gap.id}-online` ? "Searching..." : "Search online"}
            </button>
          </div>

          {generatedContent && (
            <div className="bg-gray-50 border border-gray-200 rounded-lg overflow-hidden">
              <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 bg-white">
                <span className="text-xs font-semibold text-gray-600 uppercase tracking-wider">
                  Generated content
                </span>
                <CopyButton text={generatedContent} />
              </div>
              <pre className="whitespace-pre-wrap font-sans text-sm text-gray-800 p-4 leading-relaxed">
                {generatedContent}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function GapPanel({ gaps, onGapUpdate }: GapPanelProps) {
  const [generatingId, setGeneratingId] = useState<string | null>(null);
  const [generatedContent, setGeneratedContent] = useState<
    Record<string, string>
  >({});

  const handleGenerate = useCallback(
    async (gapId: string, source: GenerateGapSource): Promise<void> => {
      setGeneratingId(`${gapId}-${source}`);
      try {
        const content = await generateGapContent(gapId, source);
        setGeneratedContent((prev) => ({ ...prev, [gapId]: content }));
        onGapUpdate?.(gapId, content);
      } finally {
        setGeneratingId(null);
      }
    },
    [onGapUpdate]
  );

  if (gaps.length === 0) {
    return null;
  }

  return (
    <div className="w-full space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-800">
            Identified Gaps
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">
            {gaps.length} {gaps.length === 1 ? "gap" : "gaps"} found in your
            document that {gaps.length === 1 ? "is" : "are"} not in the
            knowledge base.
          </p>
        </div>
      </div>
      <div className="space-y-3">
        {gaps.map((gap) => (
          <GapCard
            key={gap.id}
            gap={gap}
            generatedContent={generatedContent[gap.id]}
            isGenerating={generatingId !== null}
            generatingSource={generatingId}
            onGenerate={handleGenerate}
          />
        ))}
      </div>
    </div>
  );
}
