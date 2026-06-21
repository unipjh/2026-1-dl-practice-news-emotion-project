import { useEffect, useState } from "react";
import { useApp } from "../context/AppContext";
import {
  POSITIVE_EMOTIONS,
  NEUTRAL_EMOTIONS,
  NEGATIVE_EMOTIONS,
  ALL_EMOTIONS,
  isCountableEmotion,
} from "../lib/emotions";
import { getAllHeadlines } from "../lib/api";

const SECTIONS = [
  { label: "긍정", emotions: POSITIVE_EMOTIONS, color: "bg-red-50 text-red-700 border-red-200", activeColor: "bg-red-700 text-white border-red-700" },
  { label: "중립", emotions: NEUTRAL_EMOTIONS, color: "bg-gray-100 text-gray-600 border-gray-200", activeColor: "bg-gray-600 text-white border-gray-600" },
  { label: "부정", emotions: NEGATIVE_EMOTIONS, color: "bg-blue-50 text-blue-800 border-blue-200", activeColor: "bg-[#2C5F8A] text-white border-[#2C5F8A]" },
];

const EMOTION_THRESHOLD = 0.3;
const DISPLAY_LIMIT = 200; // 미검색 시 표시 상한 (검색 시 전체 대상)

function matchesEmotion(record, emotion) {
  return record.emotions.some(
    (e) => e.label === emotion && isCountableEmotion(record.emotions, e.label, EMOTION_THRESHOLD, record.top_emotion ?? null)
  );
}

export default function HeadlineExplorer() {
  const { setSelectedHeadline, showToast } = useApp();

  const [counts, setCounts] = useState({});
  const [selectedEmotion, setSelectedEmotion] = useState(null);
  const [headlines, setHeadlines] = useState([]);
  const [loadingHeadlines, setLoadingHeadlines] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  // 전체 캐시에서 감정별 카운트 계산
  useEffect(() => {
    getAllHeadlines()
      .then((all) => {
        const newCounts = {};
        for (const emotion of ALL_EMOTIONS) {
          newCounts[emotion] = all.filter((r) => matchesEmotion(r, emotion)).length;
        }
        setCounts(newCounts);
      })
      .catch(() => showToast("감정 분포를 불러올 수 없습니다"));
  }, []);

  // 선택된 감정으로 헤드라인 필터링
  useEffect(() => {
    if (!selectedEmotion) {
      setHeadlines([]);
      return;
    }
    setLoadingHeadlines(true);
    getAllHeadlines()
      .then((all) => {
        const filtered = all.filter((r) => matchesEmotion(r, selectedEmotion));
        setHeadlines(filtered);
      })
      .catch(() => {
        setHeadlines([]);
        showToast("헤드라인을 불러올 수 없습니다");
      })
      .finally(() => setLoadingHeadlines(false));
  }, [selectedEmotion]);

  const searchResults = searchQuery
    ? headlines.filter((h) => h.headline.includes(searchQuery))
    : null;
  const filteredHeadlines = searchResults ?? headlines.slice(0, DISPLAY_LIMIT);

  function handleEmotionClick(emotion) {
    setSelectedEmotion((prev) => (prev === emotion ? null : emotion));
    setSearchQuery("");
  }

  return (
    <div className="max-w-[1280px] mx-auto px-6 py-6">
      {/* 감정 버튼 섹션 */}
      <div className="bg-[#faf9f5] rounded-xl border border-gray-200 p-6 mb-4">
        <div className="flex items-center gap-2 mb-4">
          <h2 className="text-base font-semibold text-gray-800">감정별 탐색</h2>
          <span className="text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
            전체 기간
          </span>
        </div>
        <div className="space-y-4">
          {SECTIONS.map(({ label, emotions, color, activeColor }) => (
            <div key={label}>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                {label}
              </p>
              <div className="flex flex-wrap gap-2">
                {emotions.map((emotion) => {
                  const isSelected = selectedEmotion === emotion;
                  return (
                    <button
                      key={emotion}
                      onClick={() => handleEmotionClick(emotion)}
                      className={`text-xs px-3 py-1.5 rounded-full border font-medium transition-colors ${
                        isSelected ? activeColor : color
                      }`}
                    >
                      {emotion}
                      <span className="ml-1.5 opacity-70">
                        ({counts[emotion] ?? 0})
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 검색 + 헤드라인 목록 */}
      <div className="bg-[#faf9f5] rounded-xl border border-gray-200 p-6">
        <div className="flex items-center gap-3 mb-4">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="헤드라인 검색..."
            className="flex-1 text-sm px-3 py-2 border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-1 focus:ring-[#1B365D]"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="text-xs text-gray-400 hover:text-gray-600"
            >
              초기화
            </button>
          )}
        </div>

        {!selectedEmotion ? (
          <p className="text-sm text-gray-400 py-8 text-center">
            위에서 감정을 선택하면 해당 감정의 헤드라인이 표시됩니다.
          </p>
        ) : loadingHeadlines ? (
          <div className="py-8 text-center text-sm text-gray-400">로딩 중...</div>
        ) : filteredHeadlines.length === 0 ? (
          <p className="text-sm text-gray-400 py-8 text-center">
            해당 조건의 헤드라인이 없습니다.
          </p>
        ) : (
          <>
            <p className="text-xs text-gray-400 mb-3">
              {searchQuery
                ? `${filteredHeadlines.length}건 검색됨 / 전체 ${headlines.length}건 대상`
                : headlines.length > DISPLAY_LIMIT
                  ? `총 ${headlines.length}건 중 최신 ${DISPLAY_LIMIT}건 표시 — 검색으로 전체 탐색`
                  : `총 ${headlines.length}건`}
            </p>
            <div className="divide-y divide-gray-100">
              {filteredHeadlines.map((item) => {
                const top2 = item.emotions.slice(0, 2);
                return (
                  <div
                    key={item.id}
                    className="py-3 cursor-pointer hover:bg-gray-50 -mx-2 px-2 rounded-lg transition-colors"
                    onClick={() => setSelectedHeadline(item)}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 font-medium">
                        {item.publisher}
                      </span>
                      <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
                        {item.category}
                      </span>
                      <span className="text-xs text-gray-400 ml-auto">
                        {formatDate(item.published_at)}
                      </span>
                    </div>
                    <p className="text-sm font-medium text-gray-800 mb-1 leading-snug">
                      {item.headline}
                    </p>
                    <div className="flex gap-2">
                      {top2.map((e) => (
                        <span key={e.label} className="text-xs text-gray-500">
                          {e.label}{" "}
                          <span className="text-gray-400">{e.prob.toFixed(2)}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function formatDate(iso) {
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
