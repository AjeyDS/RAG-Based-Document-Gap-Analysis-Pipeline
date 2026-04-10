import type {
  ComparisonResult,
  GenerateGapSource,
  KnowledgeBaseFile,
  KnowledgeBaseMatch,
  UploadedDocument,
} from "./types";

// Default to real backend (via Vite `/api` proxy). Enable mock explicitly.
const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

const API_BASE = import.meta.env.VITE_API_URL ?? "";

async function mockDelay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function extractTextFromPdf(_file: File): Promise<string> {
  await mockDelay(300);
  return `# Sample BRD / User Story Document

## Executive Summary
This is a mock extracted document from the uploaded PDF. In production, this would be the actual text extracted from the PDF using a library like pdf.js or a backend service.

## Requirements
- **REQ-1**: User authentication must support SSO
- **REQ-2**: Dashboard shall display real-time metrics
- **REQ-3**: Export functionality for reports in PDF and CSV formats

## User Stories
1. As a product owner, I want to view sprint burndown so that I can track progress.
2. As a developer, I want to receive notifications when PRs are ready for review.
3. As an admin, I want to manage user roles so that access is properly controlled.

## Gap Section (Not in Knowledge Base)
This section describes new requirements that do not exist in the current knowledge base. The system should identify these as gaps and allow the user to generate content from LLM or online sources.`;
}

function createMockMatches(_filename: string): KnowledgeBaseMatch[] {
  return [
    {
      id: "match-1",
      documentId: "doc-kb-1",
      documentTitle: "Product BRD v2.1",
      content: `# Product BRD v2.1

## Executive Summary
Existing product requirements document in the knowledge base.

## Requirements
- **REQ-1**: User authentication must support SSO
- **REQ-2**: Dashboard shall display real-time metrics
- **REQ-3**: Export functionality for reports in PDF format only

## User Stories
1. As a product owner, I want to view sprint burndown so that I can track progress.
2. As a developer, I want to receive notifications when PRs are ready for review.`,
      similarityScore: 0.92,
    },
    {
      id: "match-2",
      documentId: "doc-kb-2",
      documentTitle: "Platform User Stories Q3",
      content: `# Platform User Stories Q3

## Requirements
- **REQ-1**: User authentication must support SSO
- **REQ-2**: Dashboard shall display real-time metrics

## User Stories
1. As a product owner, I want to view sprint burndown so that I can track progress.
2. As a developer, I want to receive notifications when PRs are ready for review.
3. As an admin, I want to manage user roles so that access is properly controlled.`,
      similarityScore: 0.85,
    },
  ];
}

function createMockComparisonResult(
  _uploadedText: string,
  _matches: KnowledgeBaseMatch[]
): ComparisonResult {
  return {
    overallSimilarity: 0.78,
    sections: [
      {
        id: "sec-1",
        label: "Executive Summary",
        knowledgeBaseContent: `Existing product requirements document in the knowledge base.`,
        uploadedContent: `This is a mock extracted document from the uploaded PDF.`,
        matchType: "different",
      },
      {
        id: "sec-2",
        label: "Requirements",
        knowledgeBaseContent: `- **REQ-1**: User authentication must support SSO
- **REQ-2**: Dashboard shall display real-time metrics
- **REQ-3**: Export functionality for reports in PDF format only`,
        uploadedContent: `- **REQ-1**: User authentication must support SSO
- **REQ-2**: Dashboard shall display real-time metrics
- **REQ-3**: Export functionality for reports in PDF and CSV formats`,
        matchType: "different",
      },
      {
        id: "sec-3",
        label: "User Stories",
        knowledgeBaseContent: `1. As a product owner, I want to view sprint burndown so that I can track progress.
2. As a developer, I want to receive notifications when PRs are ready for review.
3. As an admin, I want to manage user roles so that access is properly controlled.`,
        uploadedContent: `1. As a product owner, I want to view sprint burndown so that I can track progress.
2. As a developer, I want to receive notifications when PRs are ready for review.
3. As an admin, I want to manage user roles so that access is properly controlled.`,
        matchType: "matched",
      },
      {
        id: "sec-4",
        label: "Gap Section",
        knowledgeBaseContent: "",
        uploadedContent: `This section describes new requirements that do not exist in the current knowledge base. The system should identify these as gaps and allow the user to generate content from LLM or online sources.`,
        matchType: "uploaded_only",
      },
    ],
    gaps: [
      {
        id: "gap-1",
        description: "CSV export format not in knowledge base",
        uploadedExcerpt:
          "Export functionality for reports in PDF and CSV formats",
        suggestedContext: "Report export formats",
      },
      {
        id: "gap-2",
        description: "New gap section with requirements not in knowledge base",
        uploadedExcerpt:
          "This section describes new requirements that do not exist in the current knowledge base.",
        suggestedContext: "Document comparison gaps",
      },
    ],
    gapAnalysisJson: {
      new_document_title: "New BRD – Vendor Management v2",
      existing_document_title: "RISE BRD 2 – Vendor Qualification",
      comparisons: [
        {
          new_ac_id: "AC-1.1",
          new_ac_title: "SAP sync execution",
          new_ac_criteria: "Given the SAP RFC interface is active, when the hourly job runs, then vendor data shall be fetched and updated.",
          matched_ac_id: "AC-1.1",
          matched_ac_title: "SAP sync execution",
          verdict: "covered",
          confidence: "high",
          description: "Both systems require hourly SAP RFC synchronization with duplicate prevention. Fully covered."
        },
        {
          new_ac_id: "AC-1.2",
          new_ac_title: "Mandatory field validation",
          new_ac_criteria: "Given vendor data is received, when mandatory fields are missing, then the record shall be rejected.",
          matched_ac_id: "AC-1.2",
          matched_ac_title: "Mandatory field validation",
          verdict: "covered",
          confidence: "high",
          description: "Existing document requires rejection and error logging when mandatory fields missing. Equivalent."
        },
        {
          new_ac_id: "AC-1.3",
          new_ac_title: "Real-time sync fallback",
          new_ac_criteria: "When batch sync fails, a real-time webhook fallback should trigger within 5 minutes.",
          matched_ac_id: null,
          matched_ac_title: null,
          verdict: "gap",
          confidence: "high",
          description: "The existing KB only defines scheduled batch sync with no failure recovery. Critical resilience gap."
        },
        {
          new_ac_id: "AC-2.1",
          new_ac_title: "Initiation date calculation",
          new_ac_criteria: "Initiation Date = Due Date minus 60 days. Auto-calculated and non-editable.",
          matched_ac_id: "AC-2.1",
          matched_ac_title: "Initiation date calculation",
          verdict: "partial",
          confidence: "medium",
          description: "Both auto-calculate but threshold differs: new requires 60 days, existing uses 90 days."
        },
        {
          new_ac_id: "AC-2.2",
          new_ac_title: "Reminder alerts",
          new_ac_criteria: "Alerts at 60, 30, 15 days prior. Only triggered if form not submitted. Notifications logged.",
          matched_ac_id: "AC-2.2",
          matched_ac_title: "Reminder alerts",
          verdict: "covered",
          confidence: "high",
          description: "Multi-stage reminders with conditional triggering fully defined in existing KB."
        },
        {
          new_ac_id: "AC-2.3",
          new_ac_title: "Slack notification channel",
          new_ac_criteria: "Requalification alerts should also be sent to a configured Slack channel.",
          matched_ac_id: null,
          matched_ac_title: null,
          verdict: "good_to_have",
          confidence: "medium",
          description: "Existing KB only supports email. Slack would improve visibility but is not critical."
        }
      ],
      overall_summary: {
        total_new_criteria: 6,
        covered_count: 3,
        partial_count: 1,
        gap_count: 1,
        good_to_have_count: 1,
        conflict_count: 0,
        coverage_percentage: 66.7,
        key_gaps: [
          "No real-time sync fallback when batch SAP synchronization fails."
        ],
        key_additions: [
          "Slack notification channel for requalification alerts would improve team response time."
        ],
        recommendation: "The existing system covers core vendor management workflows but lacks resilience mechanisms for sync failures. The most critical action item is implementing a real-time fallback for SAP synchronization. The Slack integration is a low-effort enhancement worth considering."
      }
    }
  };
}

let mockKnowledgeBase: KnowledgeBaseFile[] = [
  {
    id: "kb-1",
    filename: "Product BRD v2.1.pdf",
    uploadedAt: new Date(Date.now() - 86400000 * 3).toISOString(),
    sizeBytes: 245_000,
    status: "ready",
  },
  {
    id: "kb-2",
    filename: "Platform User Stories Q3.pdf",
    uploadedAt: new Date(Date.now() - 86400000).toISOString(),
    sizeBytes: 128_000,
    status: "ready",
  },
];

export async function getKnowledgeBaseFiles(): Promise<KnowledgeBaseFile[]> {
  if (USE_MOCK) {
    await mockDelay(200);
    return [...mockKnowledgeBase];
  }

  const response = await fetch(`${API_BASE}/api/knowledge-base?t=${Date.now()}`, {
    cache: "no-store",
    headers: {
      "Pragma": "no-cache",
      "Cache-Control": "no-cache"
    }
  });
  if (!response.ok) throw new Error("Failed to load knowledge base");
  return response.json();
}

export async function uploadKnowledgeBaseFiles(
  files: File[]
): Promise<KnowledgeBaseFile[]> {
  if (USE_MOCK) {
    await mockDelay(1200);
    const newFiles: KnowledgeBaseFile[] = files.map((file, index) => ({
      id: `kb-${Date.now()}-${index}`,
      filename: file.name,
      uploadedAt: new Date().toISOString(),
      sizeBytes: file.size,
      status: "ready" as const,
    }));
    mockKnowledgeBase = [...mockKnowledgeBase, ...newFiles];
    return newFiles;
  }

  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  const response = await fetch(`${API_BASE}/api/knowledge-base/upload`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) throw new Error("Knowledge base upload failed");
  return response.json();
}

export async function removeKnowledgeBaseFile(
  fileId: string
): Promise<void> {
  if (USE_MOCK) {
    await mockDelay(300);
    mockKnowledgeBase = mockKnowledgeBase.filter((f) => f.id !== fileId);
    return;
  }

  const response = await fetch(`${API_BASE}/api/knowledge-base/${fileId}`, {
    method: "DELETE",
  });
  if (!response.ok) throw new Error("Failed to remove file");
}

export async function uploadAndSearch(
  file: File
): Promise<{ document: UploadedDocument; matches: KnowledgeBaseMatch[] }> {
  if (USE_MOCK) {
    await mockDelay(800);
    const extractedText = await extractTextFromPdf(file);
    const matches = createMockMatches(file.name);
    return {
      document: { filename: file.name, extractedText },
      matches,
    };
  }

  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE}/api/documents/upload`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) throw new Error("Upload failed");
  return response.json();
}

export async function compareDocuments(
  uploadedText: string,
  matches: KnowledgeBaseMatch[],
  extractedJson?: any
): Promise<ComparisonResult> {
  if (USE_MOCK) {
    await mockDelay(400);
    return createMockComparisonResult(uploadedText, matches);
  }

  const response = await fetch(`${API_BASE}/api/documents/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ uploadedText, matches, extractedJson }),
  });
  if (!response.ok) throw new Error("Compare failed");
  return response.json();
}

export async function generateGapContent(
  gapId: string,
  source: GenerateGapSource
): Promise<string> {
  if (USE_MOCK) {
    await mockDelay(600);
    return `[Mock generated content for gap ${gapId} from ${source}]\n\nThis is placeholder text that would be generated by the LLM or fetched from online sources. In production, the backend would call the appropriate service and return the actual generated content.`;
  }

  const response = await fetch(`${API_BASE}/api/gaps/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ gapId, source }),
  });
  if (!response.ok) throw new Error("Generate failed");
  const data = await response.json();
  return data.content as string;
}
