import { useState, useEffect, useCallback, type Dispatch, type SetStateAction } from "react";
import { X, Save, Loader2, Activity } from "lucide-react";
import {
  getSettings,
  updateSettings,
  pingLlmSettings,
  type LlmUseCaseTarget,
} from "../api/client";

interface SettingsModalProps {
  onClose: () => void;
}

const OFFICIAL_OPENAI_BASE = "https://api.openai.com/v1";
const DEFAULT_OLLAMA_BASE = "http://localhost:11434/v1";

const GPT_MODEL_OPTIONS = ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "o4-mini", "__custom__"];
const OLLAMA_MODEL_OPTIONS = [
  "llama3.1:latest",
  "llama3.2:latest",
  "mistral:latest",
  "phi3:latest",
  "__custom__",
];

type FeatureBlock = {
  model: string;
  baseUrl: string;
};

function norm(s: string | null | undefined): string {
  return (s ?? "").trim();
}

function coalesceDisplay(override: string | null | undefined, fallback: string): string {
  const o = norm(override);
  return o || fallback;
}

function isOllamaUrl(url: string): boolean {
  return norm(url).includes("11434");
}

export function SettingsModal({ onClose }: SettingsModalProps) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [globalModel, setGlobalModel] = useState("gpt-4o");
  const [globalBaseUrl, setGlobalBaseUrl] = useState("");

  const [ingestion, setIngestion] = useState<FeatureBlock>({ model: "gpt-4o", baseUrl: "" });
  const [comparison, setComparison] = useState<FeatureBlock>({ model: "gpt-4o", baseUrl: "" });
  const [chat, setChat] = useState<FeatureBlock>({ model: "gpt-4o", baseUrl: "" });

  const [ingModelSelect, setIngModelSelect] = useState<string>("gpt-4o");
  const [cmpModelSelect, setCmpModelSelect] = useState<string>("gpt-4o");
  const [chatModelSelect, setChatModelSelect] = useState<string>("gpt-4o");

  const [pingStatus, setPingStatus] = useState<
    Record<LlmUseCaseTarget, { loading: boolean; message: string; ok?: boolean } | null>
  >({
    ingestion: null,
    comparison: null,
    chat: null,
  });

  const syncSelectFromModel = useCallback((model: string, gptOpts: string[], ollamaOpts: string[]) => {
    if (gptOpts.includes(model)) return model;
    if (ollamaOpts.includes(model)) return model;
    return "__custom__";
  }, []);

  useEffect(() => {
    getSettings()
      .then((data) => {
        const gm = data.llm_model || "gpt-4o";
        const gb = data.llm_base_url ?? "";
        setGlobalModel(gm);
        setGlobalBaseUrl(gb);

        const ingM = coalesceDisplay(data.llm_ingestion_model, gm);
        const ingB = coalesceDisplay(data.llm_ingestion_base_url, gb);
        setIngestion({ model: ingM, baseUrl: ingB });
        setIngModelSelect(syncSelectFromModel(ingM, GPT_MODEL_OPTIONS, OLLAMA_MODEL_OPTIONS));

        const cmpM = coalesceDisplay(data.llm_comparison_model, gm);
        const cmpB = coalesceDisplay(data.llm_comparison_base_url, gb);
        setComparison({ model: cmpM, baseUrl: cmpB });
        setCmpModelSelect(syncSelectFromModel(cmpM, GPT_MODEL_OPTIONS, OLLAMA_MODEL_OPTIONS));

        const chM = coalesceDisplay(data.llm_chat_model, gm);
        const chB = coalesceDisplay(data.llm_chat_base_url, gb);
        setChat({ model: chM, baseUrl: chB });
        setChatModelSelect(syncSelectFromModel(chM, GPT_MODEL_OPTIONS, OLLAMA_MODEL_OPTIONS));

        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [syncSelectFromModel]);

  const buildOverrides = () => {
    const gM = norm(globalModel);
    const gB = norm(globalBaseUrl);
    return {
      llm_ingestion_model: norm(ingestion.model) === gM ? null : ingestion.model.trim(),
      llm_ingestion_base_url: norm(ingestion.baseUrl) === gB ? null : ingestion.baseUrl.trim() || null,
      llm_comparison_model: norm(comparison.model) === gM ? null : comparison.model.trim(),
      llm_comparison_base_url: norm(comparison.baseUrl) === gB ? null : comparison.baseUrl.trim() || null,
      llm_chat_model: norm(chat.model) === gM ? null : chat.model.trim(),
      llm_chat_base_url: norm(chat.baseUrl) === gB ? null : chat.baseUrl.trim() || null,
    };
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const o = buildOverrides();
      await updateSettings({
        llm_provider: "openai",
        llm_model: globalModel.trim() || "gpt-4o",
        llm_base_url: globalBaseUrl.trim() || null,
        ...o,
      });
      onClose();
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const runPing = async (target: LlmUseCaseTarget) => {
    setPingStatus((s) => ({ ...s, [target]: { loading: true, message: "Testing…" } }));
    try {
      const res = await pingLlmSettings(target);
      setPingStatus((s) => ({
        ...s,
        [target]: {
          loading: false,
          ok: res.ok,
          message: res.ok
            ? `${res.detail ?? "OK"} (${res.latency_ms ?? "?"} ms)`
            : (res.error ?? "Unreachable"),
        },
      }));
    } catch (e) {
      setPingStatus((s) => ({
        ...s,
        [target]: {
          loading: false,
          ok: false as boolean,
          message: e instanceof Error ? e.message : "Ping failed",
        },
      }));
    }
  };

  const setPresetGpt = (setter: Dispatch<SetStateAction<FeatureBlock>>, setSel: (v: string) => void) => {
    setSel("gpt-4o");
    setter({ model: "gpt-4o", baseUrl: OFFICIAL_OPENAI_BASE });
  };

  const setPresetOllama = (setter: Dispatch<SetStateAction<FeatureBlock>>, setSel: (v: string) => void) => {
    setSel("llama3.1:latest");
    setter({ model: "llama3.1:latest", baseUrl: DEFAULT_OLLAMA_BASE });
  };

  const renderFeatureSection = (
    title: string,
    description: string,
    target: LlmUseCaseTarget,
    block: FeatureBlock,
    setBlock: Dispatch<SetStateAction<FeatureBlock>>,
    modelSelect: string,
    setModelSelect: (v: string) => void,
  ) => {
    const ping = pingStatus[target];
    const ollamaActive = isOllamaUrl(block.baseUrl);
    const gptActive = !ollamaActive;

    return (
      <div className="rounded-xl border border-gray-200 bg-white p-4 space-y-3 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
            <p className="text-xs text-gray-500 mt-0.5">{description}</p>
          </div>
          <button
            type="button"
            onClick={() => runPing(target)}
            disabled={ping?.loading}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            {ping?.loading ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Activity className="w-3.5 h-3.5" />
            )}
            Test connection
          </button>
        </div>
        {ping && !ping.loading && ping.ok !== undefined && (
          <p
            className={`text-xs rounded-md px-2 py-1.5 ${
              ping.ok ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-red-800"
            }`}
          >
            {ping.message}
          </p>
        )}
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setPresetGpt(setBlock, setModelSelect)}
            className={`flex-1 py-1.5 px-2 rounded-lg text-xs font-medium border transition-colors ${
              gptActive
                ? "bg-blue-50 border-blue-200 text-blue-800 ring-1 ring-blue-400"
                : "bg-white border-gray-200 text-gray-600 hover:bg-gray-50"
            }`}
          >
            GPT (OpenAI)
          </button>
          <button
            type="button"
            onClick={() => setPresetOllama(setBlock, setModelSelect)}
            className={`flex-1 py-1.5 px-2 rounded-lg text-xs font-medium border transition-colors ${
              ollamaActive
                ? "bg-amber-50 border-amber-200 text-amber-900 ring-1 ring-amber-400"
                : "bg-white border-gray-200 text-gray-600 hover:bg-gray-50"
            }`}
          >
            Ollama (experimental)
          </button>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Model</label>
          <div className="flex gap-2 flex-col sm:flex-row">
            <select
              value={modelSelect}
              onChange={(e) => {
                const v = e.target.value;
                setModelSelect(v);
                if (v !== "__custom__") {
                  setBlock((prev) => ({ ...prev, model: v }));
                }
              }}
              className="w-full sm:w-52 px-2 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {(isOllamaUrl(block.baseUrl) ? OLLAMA_MODEL_OPTIONS : GPT_MODEL_OPTIONS).map((opt) => (
                <option key={opt} value={opt}>
                  {opt === "__custom__" ? "Other…" : opt}
                </option>
              ))}
            </select>
            {(modelSelect === "__custom__" ||
              (!GPT_MODEL_OPTIONS.includes(modelSelect) &&
                !OLLAMA_MODEL_OPTIONS.includes(modelSelect))) && (
              <input
                type="text"
                value={block.model}
                onChange={(e) => setBlock((prev) => ({ ...prev, model: e.target.value }))}
                className="flex-1 min-w-0 px-2 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Custom model id"
              />
            )}
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Base URL</label>
          <input
            type="text"
            value={block.baseUrl}
            onChange={(e) => setBlock((prev) => ({ ...prev, baseUrl: e.target.value }))}
            className="w-full px-2 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Match default below, or OpenAI / Ollama host"
          />
          <p className="mt-1 text-[11px] text-gray-500">
            Leave identical to <strong>Default base URL</strong> below to inherit the deployment default.
          </p>
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm">
        <div className="bg-white p-6 rounded-2xl shadow-xl w-full max-w-md text-center text-gray-500">
          Loading settings...
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden border border-gray-100">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-gray-50/50 shrink-0">
          <h2 className="text-lg font-bold text-gray-900">LLM settings</h2>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-6 overflow-y-auto flex-1">
          <p className="text-sm text-gray-600 bg-blue-50/80 border border-blue-100 rounded-lg px-3 py-2">
            <strong>Production default:</strong> OpenAI (official API). Per-feature values that match the defaults
            below are stored as inherited. Ollama is <strong>experimental</strong> and may return lower-quality or
            incompatible JSON for some flows.
          </p>

          <div className="rounded-xl border border-gray-200 bg-gray-50/50 p-4 space-y-3">
            <h3 className="text-sm font-semibold text-gray-900">Default (all features)</h3>
            <p className="text-xs text-gray-500">
              Used when a feature&apos;s model or base URL matches these values, and for CLI / env fallbacks.
            </p>
            <div className="grid sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Default model</label>
                <input
                  type="text"
                  value={globalModel}
                  onChange={(e) => setGlobalModel(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Default base URL</label>
                <input
                  type="text"
                  value={globalBaseUrl}
                  onChange={(e) => setGlobalBaseUrl(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Empty = OpenAI default endpoint"
                />
              </div>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  setGlobalModel("gpt-4o");
                  setGlobalBaseUrl("");
                }}
                className={`text-xs py-1.5 px-2 rounded-lg border font-medium ${
                  !isOllamaUrl(globalBaseUrl)
                    ? "bg-blue-50 border-blue-200 text-blue-800"
                    : "border-gray-200 text-gray-600 hover:bg-white"
                }`}
              >
                Preset: OpenAI
              </button>
              <button
                type="button"
                onClick={() => {
                  setGlobalModel("llama3.1:latest");
                  setGlobalBaseUrl(DEFAULT_OLLAMA_BASE);
                }}
                className={`text-xs py-1.5 px-2 rounded-lg border font-medium ${
                  isOllamaUrl(globalBaseUrl)
                    ? "bg-amber-50 border-amber-200 text-amber-900"
                    : "border-gray-200 text-gray-600 hover:bg-white"
                }`}
              >
                Preset: Ollama (experimental)
              </button>
            </div>
          </div>

          {renderFeatureSection(
            "Ingestion",
            "Structured extraction when adding knowledge base documents.",
            "ingestion",
            ingestion,
            setIngestion,
            ingModelSelect,
            setIngModelSelect,
          )}
          {renderFeatureSection(
            "Document comparison",
            "Gap analysis JSON when comparing an upload to the knowledge base.",
            "comparison",
            comparison,
            setComparison,
            cmpModelSelect,
            setCmpModelSelect,
          )}
          {renderFeatureSection(
            "Chat",
            "RAG answers over retrieved chunks.",
            "chat",
            chat,
            setChat,
            chatModelSelect,
            setChatModelSelect,
          )}

          {saveError && <p className="text-sm text-red-600">{saveError}</p>}
        </div>

        <div className="px-6 py-4 border-t border-gray-100 bg-gray-50 flex justify-end gap-3 shrink-0">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-200 shadow-sm"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 shadow-sm"
          >
            {saving ? (
              "Saving…"
            ) : (
              <>
                <Save className="w-4 h-4" />
                Save settings
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
