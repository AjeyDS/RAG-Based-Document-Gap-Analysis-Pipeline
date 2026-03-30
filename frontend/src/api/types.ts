export interface UploadedDocument {
  filename: string;
  extractedText: string;
}

export interface KnowledgeBaseFile {
  id: string;
  filename: string;
  uploadedAt: string;
  sizeBytes: number;
  status: "processing" | "docling" | "llm" | "chunking" | "embedding" | "ready" | "error" | string;
}

export interface KnowledgeBaseMatch {
  id: string;
  documentId: string;
  documentTitle: string;
  content: string;
  similarityScore: number;
}

export interface ComparisonSection {
  id: string;
  label: string;
  knowledgeBaseContent: string;
  uploadedContent: string;
  matchType: "matched" | "different" | "uploaded_only" | "knowledge_base_only";
}

export interface Gap {
  id: string;
  description: string;
  uploadedExcerpt: string;
  suggestedContext?: string;
  generatedContent?: string;
}

export interface ComparisonResult {
  sections: ComparisonSection[];
  gaps: Gap[];
  overallSimilarity: number;
  gapAnalysisJson?: any;
}

export type GenerateGapSource = "llm" | "online";
