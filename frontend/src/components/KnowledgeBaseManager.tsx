import {
  FileText,
  Trash2,
  Loader2,
  AlertCircle,
  Plus,
  HardDrive
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import type { KnowledgeBaseFile } from "../api/types";
import {
  getKnowledgeBaseFiles,
  removeKnowledgeBaseFile,
  uploadKnowledgeBaseFiles,
} from "../api/client";

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function StatusBadge({ status }: { status: KnowledgeBaseFile["status"] }) {
  if (status === "ready") {
    return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[13px] font-medium bg-[#E8F3EA] text-[#3E6F40] border border-[#D5EAD8]">Indexed</span>;
  }
  if (status === "error") {
    return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[13px] font-medium bg-red-50 text-red-700 border border-red-100"><AlertCircle className="w-3 h-3 mr-1.5" />Error</span>;
  }
  
  let label = "Processing";
  if (status === "docling") label = "Docling (Parsing PDF)";
  if (status === "llm") label = "LLM (Extracting entities)";
  if (status === "chunking") label = "Chunking text";
  if (status === "embedding") label = "Embedding vector";
  
  return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[13px] font-medium bg-blue-50 text-blue-700 border border-blue-100"><Loader2 className="w-3 h-3 mr-1.5 animate-spin" />{label}</span>;
}

const colors = [
  "bg-[#DDEBFA] text-[#5584C1]",
  "bg-[#F5EDDD] text-[#867554]",
  "bg-[#E8F3EA] text-[#558655]",
  "bg-[#F3EBF3] text-[#9A6D9A]",
];

const getFileIconColor = (filename: string) => {
  let hash = 0;
  for (let i = 0; i < filename.length; i++) hash = filename.charCodeAt(i) + ((hash << 5) - hash);
  return colors[Math.abs(hash) % colors.length];
};

export function KnowledgeBaseManager() {
  const [files, setFiles] = useState<KnowledgeBaseFile[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshFiles = useCallback(() => {
    getKnowledgeBaseFiles()
      .then(setFiles)
      .catch(() => setError("Failed to load knowledge base files"))
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    refreshFiles();
  }, [refreshFiles]);

  useEffect(() => {
    const hasProcessing = files.some(
      (f) => f.status !== "ready" && f.status !== "error"
    );
    if (hasProcessing) {
      const interval = setInterval(refreshFiles, 500);
      return () => clearInterval(interval);
    }
  }, [files, refreshFiles]);

  const handleUpload = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFiles = Array.from(event.target.files ?? []);
      if (selectedFiles.length === 0) return;
      event.target.value = "";
      setIsUploading(true);
      setError(null);
      try {
        const newFiles = await uploadKnowledgeBaseFiles(selectedFiles);
        setFiles((prev) => [...prev, ...newFiles]);
      } catch {
        setError("Failed to upload files");
      } finally {
        setIsUploading(false);
      }
    },
    []
  );

  const handleRemove = useCallback(async (fileId: string) => {
    setRemovingId(fileId);
    try {
      await removeKnowledgeBaseFile(fileId);
      setFiles((prev) => prev.filter((f) => f.id !== fileId));
    } catch {
      setError("Failed to remove file");
    } finally {
      setRemovingId(null);
    }
  }, []);

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm flex flex-col h-full relative">
      <div className="px-5 py-4 flex items-center justify-between border-b border-gray-200">
        <div className="flex items-center gap-3">
          <HardDrive className="w-5 h-5 text-gray-600" strokeWidth={1.5} />
          <h2 className="text-base font-medium text-gray-900">
            Knowledge base
          </h2>
          <span className="flex items-center justify-center bg-[#E5EEFF] text-[#346ACB] text-xs font-medium px-2.5 py-0.5 rounded-full">
            {files.length} files
          </span>
        </div>
        
        <label
          className={`
            inline-flex items-center gap-1.5 px-3.5 py-1.5 text-sm font-medium text-gray-800 bg-[#F5F4F1] border border-[#E8E6E1] rounded-lg cursor-pointer hover:bg-[#EBEAE6] transition-colors
            ${isUploading ? "opacity-70 pointer-events-none" : ""}
          `}
        >
          <input
            type="file"
            accept=".pdf,application/pdf,.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            multiple
            onChange={handleUpload}
            disabled={isUploading}
            className="sr-only"
          />
          {isUploading ? (
            <Loader2 className="w-4 h-4 animate-spin text-gray-600" />
          ) : (
            <Plus className="w-4 h-4 text-gray-600" strokeWidth={2} />
          )}
          {isUploading ? "Uploading & indexing..." : "Add files"}
        </label>
      </div>

      {error && (
        <div className="mx-5 mt-4 p-3 bg-red-50 border border-red-100 rounded-lg text-red-600 text-xs flex items-center gap-2" role="alert">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3 text-gray-400">
            <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
            <span className="text-sm font-medium">Loading collection...</span>
          </div>
        ) : files.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="w-12 h-12 bg-gray-50 rounded-2xl flex items-center justify-center mb-4">
              <FileText className="w-6 h-6 text-gray-300" strokeWidth={1.5} />
            </div>
            <p className="text-sm font-medium text-gray-900">No documents yet</p>
            <p className="text-sm text-gray-500 mt-1">Upload files to populate your knowledge base.</p>
          </div>
        ) : (
          <ul className="divide-y divide-gray-200 flex flex-col">
            {files.map((file) => (
              <li
                key={file.id}
                className="group flex items-center px-5 py-4 hover:bg-gray-50/50 transition-colors"
              >
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center shrink-0 ${getFileIconColor(file.filename)}`}>
                  <FileText className="w-6 h-6" strokeWidth={1.5} />
                </div>
                
                <div className="flex-1 min-w-0 ml-4">
                  <p className="text-[15px] font-medium text-gray-900 truncate tracking-tight">
                    {file.filename}
                  </p>
                  <p className="text-[13px] text-gray-500 mt-0.5 truncate">
                    Document &middot; {formatFileSize(file.sizeBytes)} &middot; {formatDate(file.uploadedAt)}
                  </p>
                </div>

                <div className="flex items-center gap-3 shrink-0 ml-4">
                  <button
                    type="button"
                    onClick={() => handleRemove(file.id)}
                    disabled={removingId === file.id}
                    className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-md transition-all opacity-0 group-hover:opacity-100 focus:opacity-100 focus:outline-none"
                    aria-label={`Remove ${file.filename}`}
                  >
                    {removingId === file.id ? (
                      <Loader2 className="w-4 h-4 animate-spin text-red-500" />
                    ) : (
                      <Trash2 className="w-4 h-4" />
                    )}
                  </button>
                  <StatusBadge status={file.status} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

