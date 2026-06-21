import { useState } from "react";
import { useApp } from "../context/AppContext";
import FilterPanel from "./FilterPanel";

const DT_OPTIONS = ["6h", "1d", "1w", "1m", "1y"];
const SENTIMENT_OPTIONS = [
  { value: "all", label: "전체" },
  { value: "positive", label: "긍정" },
  { value: "neutral", label: "중립" },
  { value: "negative", label: "부정" },
];

export default function ControlBar() {
  const { dt, setDt, sentimentGroup, setSentimentGroup, activeFilter, compareGroups, setChartSelection } = useApp();
  const [filterOpen, setFilterOpen] = useState(false);

  const activeCount = activeFilter.publishers.length + activeFilter.categories.length;

  function handleDtChange(val) {
    setDt(val);
    setChartSelection((s) => ({ ...s, selectedEmotions: [] }));
  }

  function handleSentimentChange(val) {
    setSentimentGroup(val);
    setChartSelection((s) => ({ ...s, selectedEmotions: [] }));
  }

  return (
    <div className="sticky top-14 z-30 bg-[#f5f4ed] border-b border-gray-200">
      <div className="max-w-[1280px] mx-auto px-6 py-3 flex items-center gap-4 flex-wrap">
        {/* dt toggle */}
        <div className="flex bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm">
          {DT_OPTIONS.map((opt) => (
            <button
              key={opt}
              onClick={() => handleDtChange(opt)}
              className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                dt === opt
                  ? "bg-[#1B365D] text-white"
                  : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              {opt}
            </button>
          ))}
        </div>

        <div className="w-px h-6 bg-gray-300" />

        {/* sentiment group filter */}
        <div className="flex bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm">
          {SENTIMENT_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => handleSentimentChange(opt.value)}
              className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                sentimentGroup === opt.value
                  ? "bg-[#1B365D] text-white"
                  : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>

        <div className="w-px h-6 bg-gray-300" />

        {/* filter toggle */}
        <div className="relative">
          <button
            onClick={() => setFilterOpen((v) => !v)}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border shadow-sm transition-colors ${
              activeCount > 0
                ? "bg-[#1B365D] text-white border-[#1B365D]"
                : "bg-white text-gray-700 border-gray-200 hover:bg-gray-50"
            }`}
          >
            필터
            {activeCount > 0 && (
              <span className="bg-white text-[#1B365D] rounded-full text-xs px-1.5 py-0.5 font-semibold leading-none">
                {activeCount}
              </span>
            )}
            <span className="text-xs">{filterOpen ? "▲" : "▼"}</span>
          </button>

          {filterOpen && (
            <FilterPanel onClose={() => setFilterOpen(false)} />
          )}
        </div>

        {/* active compare groups preview */}
        {compareGroups.length > 0 && compareGroups[0].key !== "전체" && (
          <div className="flex items-center gap-1.5 ml-2 flex-wrap">
            <span className="text-xs text-gray-500">비교:</span>
            {compareGroups.map((g, i) => (
              <span
                key={g.key}
                className="text-xs px-2 py-0.5 rounded-full text-white font-medium"
                style={{ backgroundColor: GROUP_COLORS[i % GROUP_COLORS.length] }}
              >
                {g.label}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export const GROUP_COLORS = ["#1B365D", "#4d7ab5", "#e07b39", "#5a9e6f"];
