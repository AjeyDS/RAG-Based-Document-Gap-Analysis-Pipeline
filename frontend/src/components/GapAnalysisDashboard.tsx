import React, { useState, useMemo } from "react";

/*
 * GapAnalysisDashboard
 * ====================
 * Drop-in React component that renders the gap analysis JSON output.
 */

/* ─── Color config per verdict ─── */
const VERDICT_CONFIG: Record<string, { label: string; bg: string; text: string; border: string }> = {
  covered: {
    label: "Covered",
    bg: "#EAF3DE",
    text: "#27500A",
    border: "#97C459",
  },
  partial: {
    label: "Partial",
    bg: "#E6F1FB",
    text: "#0C447C",
    border: "#85B7EB",
  },
  gap: {
    label: "Gap",
    bg: "#FCEBEB",
    text: "#791F1F",
    border: "#F09595",
  },
  good_to_have: {
    label: "Good to have",
    bg: "#FAEEDA",
    text: "#633806",
    border: "#FAC775",
  },
  conflict: {
    label: "Conflict",
    bg: "#FBEAF0",
    text: "#72243E",
    border: "#ED93B1",
  },
};

/* ─── Badge component ─── */
function Badge({ verdict, children }: { verdict: string; children?: React.ReactNode }) {
  const config = VERDICT_CONFIG[verdict] || VERDICT_CONFIG.gap;
  return (
    <span
      style={{
        display: "inline-block",
        fontSize: 11,
        fontWeight: 500,
        padding: "2px 10px",
        borderRadius: 6,
        background: config.bg,
        color: config.text,
        whiteSpace: "nowrap",
      }}
    >
      {children || config.label}
    </span>
  );
}

/* ─── Stat card ─── */
function StatCard({ value, label, color }: { value: number | string; label: string; color: string }) {
  return (
    <div
      style={{
        background: "#f5f5f0",
        borderRadius: 8,
        padding: "12px 8px",
        textAlign: "center",
        flex: 1,
        minWidth: 0,
      }}
    >
      <p style={{ fontSize: 22, fontWeight: 500, margin: 0, color }}>
        {value}
      </p>
      <p style={{ fontSize: 12, color: "#888", margin: "4px 0 0" }}>
        {label}
      </p>
    </div>
  );
}

/* ─── Single AC card ─── */
function ACCard({ comparison, existingDocTitle }: { comparison: any; existingDocTitle: string }) {
  const config = VERDICT_CONFIG[comparison.verdict] || VERDICT_CONFIG.gap;

  return (
    <div
      style={{
        borderLeft: `3px solid ${config.border}`,
        margin: "8px 0 8px 16px",
        padding: "12px 16px",
        borderRadius: 0,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 6,
        }}
      >
        <Badge verdict={comparison.verdict} />
        {comparison.confidence && (
          <span style={{ fontSize: 12, color: "#aaa" }}>
            {comparison.confidence} confidence
          </span>
        )}
      </div>

      <p style={{ fontSize: 14, fontWeight: 500, margin: "0 0 4px" }}>
        {comparison.new_ac_id} — {comparison.new_ac_title}
      </p>

      <p
        style={{
          fontSize: 13,
          color: "#666",
          margin: "0 0 4px",
          lineHeight: 1.6,
        }}
      >
        {comparison.new_ac_criteria}
      </p>

      <p
        style={{
          fontSize: 13,
          color: "#444",
          margin: "8px 0 6px",
          lineHeight: 1.6,
          fontStyle: "italic",
        }}
      >
        {comparison.description}
      </p>

      <p style={{ fontSize: 12, color: "#aaa", margin: "6px 0 0" }}>
        {comparison.matched_ac_id
          ? `Matched: ${comparison.matched_ac_id} "${comparison.matched_ac_title}" from ${existingDocTitle}`
          : "No match found in knowledge base"}
      </p>
    </div>
  );
}

/* ─── Story accordion row ─── */
function StoryRow({ storyId, storyTitle, comparisons, existingDocTitle }: { storyId: string; storyTitle: string; comparisons: any[]; existingDocTitle: string }) {
  const [open, setOpen] = useState(false);

  /* Count verdicts for this story */
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    comparisons.forEach((comp) => {
      c[comp.verdict] = (c[comp.verdict] || 0) + 1;
    });
    return c;
  }, [comparisons]);

  return (
    <div style={{ marginBottom: 6 }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          width: "100%",
          padding: "12px 16px",
          border: "0.5px solid #e0e0e0",
          borderRadius: 8,
          background: open ? "#f9f9f6" : "#fff",
          cursor: "pointer",
          fontSize: 14,
          textAlign: "left",
        }}
      >
        <span>
          <span style={{ fontWeight: 500 }}>{storyId}</span>
          <span style={{ color: "#888", marginLeft: 8 }}>{storyTitle}</span>
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {Object.entries(counts).map(([verdict, count]) => (
            <Badge key={verdict} verdict={verdict}>
              {count}
            </Badge>
          ))}
          <span
            style={{
              fontSize: 12,
              color: "#ccc",
              transition: "transform 0.2s",
              transform: open ? "rotate(90deg)" : "rotate(0deg)",
              marginLeft: 4,
            }}
          >
            &#9654;
          </span>
        </span>
      </button>

      {open && (
        <div style={{ marginTop: 4 }}>
          {comparisons.map((comp) => (
            <ACCard
              key={comp.new_ac_id}
              comparison={comp}
              existingDocTitle={existingDocTitle}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── Filter pills ─── */
function FilterBar({ activeFilter, onFilterChange, summary }: { activeFilter: string; onFilterChange: (f: string) => void; summary: any }) {
  const filters = [
    { key: "all", label: "All", count: summary.total_new_criteria },
    { key: "covered", label: "Covered", count: summary.covered_count },
    { key: "partial", label: "Partial", count: summary.partial_count },
    { key: "gap", label: "Gaps", count: summary.gap_count },
    {
      key: "good_to_have",
      label: "Good to have",
      count: summary.good_to_have_count,
    },
    { key: "conflict", label: "Conflicts", count: summary.conflict_count },
  ];

  return (
    <div
      style={{
        display: "flex",
        gap: 6,
        marginBottom: 16,
        flexWrap: "wrap",
      }}
    >
      {filters
        .filter((f) => f.key === "all" || (f.count && f.count > 0))
        .map((f) => (
          <button
            key={f.key}
            onClick={() => onFilterChange(f.key)}
            style={{
              padding: "6px 14px",
              borderRadius: 20,
              border:
                activeFilter === f.key
                  ? "1.5px solid #444"
                  : "0.5px solid #ddd",
              background: activeFilter === f.key ? "#f0f0ec" : "transparent",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: activeFilter === f.key ? 500 : 400,
            }}
          >
            {f.label} ({f.count || 0})
          </button>
        ))}
    </div>
  );
}

/* ─── Main dashboard ─── */
export default function GapAnalysisDashboard({ data }: { data: any }) {
  const [activeFilter, setActiveFilter] = useState("all");

  const summary = data.overall_summary || {};
  // Safety net: strictly filter out non-AC comparisons
  const comparisons = useMemo(() => {
    const allComps = data.comparisons || [];
    return allComps.filter((c: any) => c.new_ac_id && c.new_ac_id.includes("AC-"));
  }, [data.comparisons]);

  /* Group comparisons by story (using metadata from comparisons) */
  const stories = useMemo(() => {
    const map = new Map<string, { storyId: string; storyTitle: string; comparisons: any[] }>();

    comparisons.forEach((comp: any) => {
      /* Extract story ID from AC ID: "AC-1.2" -> "US-1", "AC-2.3" -> "US-2" */
      const acParts = comp.new_ac_id.replace(/^AC-/, "").split(".");
      const storyNum = acParts[0];
      const storyKey = `US-${storyNum}`;

      if (!map.has(storyKey)) {
        map.set(storyKey, {
          storyId: storyKey,
          storyTitle: comp.new_ac_title
            ? comp.new_ac_title.split("—")[0]?.trim()
            : storyKey,
          comparisons: [],
        });
      }
      map.get(storyKey)!.comparisons.push(comp);
    });

    return Array.from(map.values());
  }, [comparisons]);

  /* Apply filter */
  const filteredStories = useMemo(() => {
    if (activeFilter === "all") return stories;
    return stories
      .map((s) => ({
        ...s,
        comparisons: s.comparisons.filter(
          (c) => c.verdict === activeFilter
        ),
      }))
      .filter((s) => s.comparisons.length > 0);
  }, [stories, activeFilter]);

  /* Progress bar segments */
  const total = summary.total_new_criteria || 1;
  const segments = [
    { pct: ((summary.covered_count || 0) / total) * 100, color: "#97C459" },
    { pct: ((summary.partial_count || 0) / total) * 100, color: "#85B7EB" },
    { pct: ((summary.gap_count || 0) / total) * 100, color: "#F09595" },
    { pct: ((summary.good_to_have_count || 0) / total) * 100, color: "#FAC775" },
    {
      pct: ((summary.conflict_count || 0) / total) * 100,
      color: "#ED93B1",
    },
  ];

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", width: "100%" }}>
      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 500, margin: "0 0 4px" }}>
          Gap analysis results
        </h2>
        <p style={{ fontSize: 13, color: "#888", margin: 0 }}>
          {data.new_document_title || "New document"} vs{" "}
          {data.existing_document_title || "Knowledge base document"}
        </p>
      </div>

      {/* Stat cards */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <StatCard
          value={summary.total_new_criteria || 0}
          label="Total ACs"
          color="#333"
        />
        <StatCard
          value={summary.covered_count || 0}
          label="Covered"
          color="#27500A"
        />
        <StatCard
          value={summary.partial_count || 0}
          label="Partial"
          color="#0C447C"
        />
        <StatCard value={summary.gap_count || 0} label="Gaps" color="#791F1F" />
        <StatCard
          value={summary.good_to_have_count || 0}
          label="Good to have"
          color="#633806"
        />
      </div>

      {/* Progress bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: 13,
          color: "#888",
          marginBottom: 6,
        }}
      >
        <span>
          Coverage: {summary.coverage_percentage || 0}%
        </span>
        <span>
          {(summary.covered_count || 0) + (summary.partial_count || 0)} of{" "}
          {summary.total_new_criteria || 0} covered or partial
        </span>
      </div>
      <div
        style={{
          height: 6,
          borderRadius: 3,
          background: "#f0f0ec",
          overflow: "hidden",
          display: "flex",
          marginBottom: 20,
        }}
      >
        {segments.map(
          (seg, i) =>
            seg.pct > 0 && (
              <div
                key={i}
                style={{
                  width: `${seg.pct}%`,
                  height: "100%",
                  background: seg.color,
                }}
              />
            )
        )}
      </div>

      {/* Key gaps callout */}
      {summary.key_gaps && summary.key_gaps.length > 0 && (
        <div
          style={{
            background: "#FCEBEB",
            borderRadius: 8,
            padding: "12px 16px",
            marginBottom: 16,
          }}
        >
          <p
            style={{
              fontSize: 13,
              fontWeight: 500,
              margin: "0 0 6px",
              color: "#791F1F",
            }}
          >
            Key gaps
          </p>
          {summary.key_gaps.map((gap: string, i: number) => (
            <p
              key={i}
              style={{
                fontSize: 13,
                color: "#791F1F",
                margin: "2px 0",
                lineHeight: 1.5,
              }}
            >
              • {gap}
            </p>
          ))}
        </div>
      )}

      {/* Key additions callout */}
      {summary.key_additions && summary.key_additions.length > 0 && (
        <div
          style={{
            background: "#FAEEDA",
            borderRadius: 8,
            padding: "12px 16px",
            marginBottom: 16,
          }}
        >
          <p
            style={{
              fontSize: 13,
              fontWeight: 500,
              margin: "0 0 6px",
              color: "#633806",
            }}
          >
            Recommended additions
          </p>
          {summary.key_additions.map((add: string, i: number) => (
            <p
              key={i}
              style={{
                fontSize: 13,
                color: "#633806",
                margin: "2px 0",
                lineHeight: 1.5,
              }}
            >
              • {add}
            </p>
          ))}
        </div>
      )}

      {/* Recommendation */}
      {summary.recommendation && (
        <div
          style={{
            background: "#f9f9f6",
            borderRadius: 8,
            padding: "12px 16px",
            marginBottom: 20,
          }}
        >
          <p
            style={{
              fontSize: 13,
              fontWeight: 500,
              margin: "0 0 6px",
              color: "#444",
            }}
          >
            Overall recommendation
          </p>
          <p
            style={{
              fontSize: 13,
              color: "#666",
              margin: 0,
              lineHeight: 1.6,
            }}
          >
            {summary.recommendation}
          </p>
        </div>
      )}

      {/* Filter bar */}
      <FilterBar
        activeFilter={activeFilter}
        onFilterChange={setActiveFilter}
        summary={summary}
      />

      {/* Story accordions */}
      <div>
        {filteredStories.map((story) => (
          <StoryRow
            key={story.storyId}
            storyId={story.storyId}
            storyTitle={story.storyTitle}
            comparisons={story.comparisons}
            existingDocTitle={
              data.existing_document_title || "Knowledge base"
            }
          />
        ))}
      </div>
    </div>
  );
}
