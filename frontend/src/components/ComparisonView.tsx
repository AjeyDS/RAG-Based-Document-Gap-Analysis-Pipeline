import { CheckCircle2, AlertTriangle, FileQuestion, BookOpen } from "lucide-react";
import { diffWordsWithSpace } from "diff";
import type { ComparisonSection } from "../api/types";

interface ComparisonViewProps {
  sections: ComparisonSection[];
  uploadedDocumentTitle: string;
  knowledgeBaseTitle?: string;
  overallSimilarity?: number;
}

const MATCH_CONFIG: Record<
  ComparisonSection["matchType"],
  { bg: string; border: string; badge: string; badgeText: string; icon: typeof CheckCircle2; label: string }
> = {
  matched: {
    bg: "bg-green-50/60",
    border: "border-l-green-500",
    badge: "bg-green-100 text-green-800",
    badgeText: "text-green-600",
    icon: CheckCircle2,
    label: "Matched",
  },
  different: {
    bg: "bg-amber-50/60",
    border: "border-l-amber-500",
    badge: "bg-amber-100 text-amber-800",
    badgeText: "text-amber-600",
    icon: AlertTriangle,
    label: "Different",
  },
  uploaded_only: {
    bg: "bg-blue-50/60",
    border: "border-l-blue-500",
    badge: "bg-blue-100 text-blue-800",
    badgeText: "text-blue-600",
    icon: FileQuestion,
    label: "Uploaded only",
  },
  knowledge_base_only: {
    bg: "bg-gray-50/60",
    border: "border-l-gray-400",
    badge: "bg-gray-100 text-gray-700",
    badgeText: "text-gray-500",
    icon: BookOpen,
    label: "KB only",
  },
};

function SimilarityBadge({ value }: { value: number }) {
  const percentage = Math.round(value * 100);
  const color =
    percentage >= 80
      ? "text-green-700 bg-green-100"
      : percentage >= 50
        ? "text-amber-700 bg-amber-100"
        : "text-red-700 bg-red-100";
  return (
    <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${color}`}>
      {percentage}% similar
    </span>
  );
}

function DiffContent({
  oldText,
  newText,
  type
}: {
  oldText: string;
  newText: string;
  type: "kb" | "uploaded"
}) {
  if (!oldText && type === "kb") return <span className="text-sm text-gray-400 italic">No matching content in knowledge base</span>;
  if (!newText && type === "uploaded") return <span className="text-sm text-gray-400 italic">No matching content in uploaded document</span>;

  const cleanText = (str: string) => str.replace(/[#*_~`]/g, '');
  const differences = diffWordsWithSpace(cleanText(oldText || ""), cleanText(newText || ""));

  return (
    <pre className="whitespace-pre-wrap font-sans text-sm text-gray-800 leading-relaxed">
      {differences.map((part, index) => {
        if (type === "kb") {
          if (part.added) return null;
          if (part.removed) {
            return (
              <span key={index} className="bg-red-100 text-red-900 line-through rounded-sm decoration-red-400">
                {part.value}
              </span>
            );
          }
          return <span key={index}>{part.value}</span>;
        } else {
          if (part.removed) return null;
          if (part.added) {
            return (
              <span key={index} className="bg-green-100 text-green-900 font-medium rounded-sm">
                {part.value}
              </span>
            );
          }
          return <span key={index}>{part.value}</span>;
        }
      })}
    </pre>
  );
}

export function ComparisonView({
  sections,
  uploadedDocumentTitle,
  knowledgeBaseTitle = "Knowledge Base",
  overallSimilarity,
}: ComparisonViewProps) {
  return (
    <div className="w-full space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-gray-800">
          Side-by-Side Comparison
        </h2>
        <div className="flex items-center gap-3 flex-wrap">
          {overallSimilarity !== undefined && (
            <SimilarityBadge value={overallSimilarity} />
          )}
          {Object.entries(MATCH_CONFIG).map(([key, config]) => {
            const Icon = config.icon;
            return (
              <span key={key} className="inline-flex items-center gap-1 text-xs text-gray-600">
                <Icon className={`w-3.5 h-3.5 ${config.badgeText}`} />
                {config.label}
              </span>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-0">
        <div className="bg-indigo-50 rounded-tl-lg px-4 py-2.5 border-b border-indigo-100">
          <h3 className="text-sm font-semibold text-indigo-800 flex items-center gap-2">
            <BookOpen className="w-4 h-4" />
            {knowledgeBaseTitle}
          </h3>
        </div>
        <div className="bg-blue-50 rounded-tr-lg px-4 py-2.5 border-b border-blue-100">
          <h3 className="text-sm font-semibold text-blue-800 flex items-center gap-2">
            <FileQuestion className="w-4 h-4" />
            {uploadedDocumentTitle}
          </h3>
        </div>
      </div>

      <div className="border border-gray-200 rounded-xl overflow-hidden divide-y divide-gray-100">
        {sections.map((section) => {
          const config = MATCH_CONFIG[section.matchType];
          const Icon = config.icon;
          return (
            <div key={section.id} className={`${config.bg}`}>
              <div className="px-4 py-2 flex items-center gap-2 border-b border-gray-100/80">
                <Icon className={`w-4 h-4 ${config.badgeText}`} />
                <span className="text-xs font-semibold text-gray-700">
                  {section.label}
                </span>
                <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${config.badge}`}>
                  {config.label}
                </span>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-gray-200/60">
                <div className={`p-4 border-l-4 ${config.border} min-h-[80px]`}>
                  <DiffContent
                    oldText={section.knowledgeBaseContent}
                    newText={section.uploadedContent}
                    type="kb"
                  />
                </div>
                <div className={`p-4 border-l-4 ${config.border} min-h-[80px]`}>
                  <DiffContent
                    oldText={section.knowledgeBaseContent}
                    newText={section.uploadedContent}
                    type="uploaded"
                  />
                </div>
              </div>
            </div>
          );
        })}

      </div>
    </div>
  );
}
