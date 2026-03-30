import { FileUp, FileCheck } from "lucide-react";
import { useCallback, useState } from "react";

interface PdfUploadProps {
  onUpload: (file: File) => void;
  isLoading?: boolean;
  status?: string;
}

export function PdfUpload({ onUpload, isLoading, status }: PdfUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedName, setSelectedName] = useState<string | null>(null);

  const handleFile = useCallback(
    (file: File | null) => {
      if (!file) return;

      const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
      const isDocx = file.type === "application/vnd.openxmlformats-officedocument.wordprocessingml.document" || file.name.toLowerCase().endsWith(".docx");

      if (!isPdf && !isDocx) {
        alert("Please upload a PDF or DOCX file.");
        return;
      }
      setSelectedName(file.name);
      onUpload(file);
    },
    [onUpload]
  );

  const handleDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      setIsDragging(false);
      handleFile(event.dataTransfer.files[0] ?? null);
    },
    [handleFile]
  );

  const handleDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      handleFile(event.target.files?.[0] ?? null);
      event.target.value = "";
    },
    [handleFile]
  );

  return (
    <label
      className={`
        group flex flex-col items-center justify-center gap-4 w-full max-w-xl min-h-[220px] rounded-2xl border-2 border-dashed cursor-pointer transition-all duration-200
        ${isDragging ? "border-blue-500 bg-blue-50 scale-[1.01]" : "border-gray-300 hover:border-blue-400 hover:bg-blue-50/30"}
        ${isLoading ? "pointer-events-none" : ""}
      `}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
    >
      <input
        type="file"
        accept=".pdf,application/pdf,.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        onChange={handleChange}
        disabled={isLoading}
        className="sr-only"
        aria-label="Upload PDF or DOCX file for comparison"
      />
      {isLoading ? (
        <div className="flex flex-col items-center gap-3 px-6">
          <div className="relative">
            <div className="animate-spin rounded-full h-12 w-12 border-[3px] border-gray-200 border-t-blue-600" />
            <FileCheck className="absolute inset-0 m-auto w-5 h-5 text-blue-600" />
          </div>
          {selectedName && (
            <span className="text-sm font-medium text-gray-700">
              {selectedName}
            </span>
          )}
          <span className="text-sm text-gray-500">
            {status ?? "Processing..."}
          </span>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-3 px-6">
          <div className="w-14 h-14 rounded-full bg-blue-50 group-hover:bg-blue-100 flex items-center justify-center transition-colors">
            <FileUp className="w-7 h-7 text-blue-600" aria-hidden />
          </div>
          <div className="text-center">
            <span className="text-base font-semibold text-gray-700 block">
              Drop your document here
            </span>
            <span className="text-sm text-gray-500 mt-1 block">
              or click to browse &middot; BRD, user stories, or any document
            </span>
          </div>
          <span className="text-xs text-gray-400 bg-gray-100 px-3 py-1 rounded-full">
            PDF or DOCX
          </span>
        </div>
      )}
    </label>
  );
}
