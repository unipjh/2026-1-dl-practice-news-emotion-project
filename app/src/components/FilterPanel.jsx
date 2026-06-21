import { useEffect, useRef } from "react";
import { useApp } from "../context/AppContext";
import { canSelect, buildCompareGroups } from "../lib/filterLogic";

const PUBLISHERS = ["조선일보", "한겨레", "매일경제", "연합뉴스"];
const CATEGORIES = ["정치", "경제", "사회", "문화"];

export default function FilterPanel({ onClose }) {
  const { filterDraft, setFilterDraft, applyFilter, resetFilter, showToast } = useApp();
  const panelRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(e) {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        onClose();
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [onClose]);

  function toggle(type, value) {
    const current = filterDraft[type];
    if (current.includes(value)) {
      setFilterDraft({ ...filterDraft, [type]: current.filter((v) => v !== value) });
      return;
    }
    if (!canSelect(filterDraft)) {
      showToast("최대 4개까지 선택 가능합니다");
      return;
    }
    setFilterDraft({ ...filterDraft, [type]: [...current, value] });
  }

  const previewGroups = buildCompareGroups(filterDraft);
  const totalSelected = filterDraft.publishers.length + filterDraft.categories.length;

  function handleApply() {
    applyFilter(filterDraft);
    onClose();
  }

  function handleReset() {
    resetFilter();
    onClose();
  }

  return (
    <div
      ref={panelRef}
      className="absolute top-full left-0 mt-2 w-80 bg-white rounded-xl border border-gray-200 shadow-lg p-4 z-50"
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-semibold text-gray-800">필터 선택 (최대 4개)</span>
        <span className="text-xs text-gray-400">{totalSelected}/4</span>
      </div>

      {/* publishers */}
      <div className="mb-3">
        <p className="text-xs font-medium text-gray-500 mb-1.5">언론사</p>
        <div className="flex flex-wrap gap-1.5">
          {PUBLISHERS.map((p) => {
            const active = filterDraft.publishers.includes(p);
            const disabled = !active && !canSelect(filterDraft);
            return (
              <button
                key={p}
                onClick={() => toggle("publishers", p)}
                disabled={disabled}
                className={`px-2.5 py-1 text-xs rounded-full border transition-colors ${
                  active
                    ? "bg-[#1B365D] text-white border-[#1B365D]"
                    : disabled
                    ? "border-gray-200 text-gray-300 cursor-not-allowed"
                    : "border-gray-300 text-gray-600 hover:border-gray-400"
                }`}
              >
                {p}
              </button>
            );
          })}
        </div>
      </div>

      {/* categories */}
      <div className="mb-4">
        <p className="text-xs font-medium text-gray-500 mb-1.5">카테고리</p>
        <div className="flex flex-wrap gap-1.5">
          {CATEGORIES.map((c) => {
            const active = filterDraft.categories.includes(c);
            const disabled = !active && !canSelect(filterDraft);
            return (
              <button
                key={c}
                onClick={() => toggle("categories", c)}
                disabled={disabled}
                className={`px-2.5 py-1 text-xs rounded-full border transition-colors ${
                  active
                    ? "bg-[#1B365D] text-white border-[#1B365D]"
                    : disabled
                    ? "border-gray-200 text-gray-300 cursor-not-allowed"
                    : "border-gray-300 text-gray-600 hover:border-gray-400"
                }`}
              >
                {c}
              </button>
            );
          })}
        </div>
      </div>

      {/* preview */}
      {previewGroups.length > 0 && (
        <div className="mb-4 p-2 bg-gray-50 rounded-lg">
          <p className="text-xs text-gray-500 mb-1.5">비교 단위 미리보기</p>
          <div className="flex flex-wrap gap-1">
            {previewGroups.map((g) => (
              <span key={g.key} className="text-xs bg-[#1B365D]/10 text-[#1B365D] px-2 py-0.5 rounded-full">
                📌 {g.label}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* actions */}
      <div className="flex gap-2">
        <button
          onClick={handleReset}
          className="flex-1 py-1.5 text-sm border border-gray-300 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors"
        >
          초기화
        </button>
        <button
          onClick={handleApply}
          className="flex-1 py-1.5 text-sm bg-[#1B365D] text-white rounded-lg hover:bg-[#1B365D]/90 transition-colors"
        >
          적용
        </button>
      </div>
    </div>
  );
}
