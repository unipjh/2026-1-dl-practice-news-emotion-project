import { useEffect, useState } from "react";
import { useApp } from "../context/AppContext";
import { getHighlightStyle, getEvidenceTokens } from "../lib/filterLogic";
import { getHeadlineDetail } from "../lib/api";

export default function HeadlineDetail() {
  const { selectedHeadline: item, setSelectedHeadline, showToast } = useApp();
  const [detail, setDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  useEffect(() => {
    if (!item) {
      setDetail(null);
      return;
    }
    if (!item.id) {
      setDetail(item);
      return;
    }
    setLoadingDetail(true);
    getHeadlineDetail(item.id)
      .then((d) => setDetail({ ...item, ...d }))
      .catch(() => {
        setDetail(item);
        showToast("상세 정보를 불러올 수 없습니다");
      })
      .finally(() => setLoadingDetail(false));
  }, [item?.id]);

  if (!item) return null;

  const display = detail || item;
  const tokens = display.tokens || [];
  const weights = display.attention_weights || [];
  const maxWeight = weights.length > 0 ? Math.max(...weights) : 1;
  const evidenceTokens = tokens.length > 0 ? getEvidenceTokens(tokens, weights) : [];
  const visibleEmotions = (display.emotions || []).filter((e) => e.prob > 0.3);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-end">
      {/* backdrop */}
      <div
        className="absolute inset-0 bg-black/30"
        onClick={() => setSelectedHeadline(null)}
      />

      {/* panel */}
      <div className="relative w-[480px] h-full bg-white shadow-2xl overflow-y-auto animate-slide-in">
        <div className="p-6">
          {/* back button */}
          <button
            onClick={() => setSelectedHeadline(null)}
            className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 mb-5 transition-colors"
          >
            ← 목록으로
          </button>

          {/* meta */}
          <div className="flex items-center gap-2 mb-3">
            <span className="text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 font-medium">
              {display.publisher}
            </span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
              {display.category}
            </span>
            {display.url && (
              <span
                className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                  display.url.includes("naver.com")
                    ? "bg-green-50 text-green-700"
                    : "bg-amber-50 text-amber-700"
                }`}
              >
                {display.url.includes("naver.com") ? "네이버" : "RSS"}
              </span>
            )}
            <span className="text-xs text-gray-400 ml-auto">
              {formatDate(display.published_at)}
            </span>
          </div>

          {/* headline with attention highlighting */}
          <div className="mb-4 p-4 bg-gray-50 rounded-xl">
            {loadingDetail ? (
              <p className="text-base font-medium text-gray-800 leading-relaxed">
                {display.headline}
              </p>
            ) : tokens.length > 0 ? (
              <p className="text-base font-medium text-gray-800 leading-relaxed">
                {tokens.map((token, i) => {
                  const style = getHighlightStyle(weights[i], maxWeight);
                  if (!style) return <span key={i}>{token}</span>;
                  return (
                    <span key={i} className={`rounded px-0.5 mx-0.5 ${style}`}>
                      {token}
                    </span>
                  );
                })}
              </p>
            ) : (
              <p className="text-base font-medium text-gray-800 leading-relaxed">
                {display.headline}
              </p>
            )}
          </div>

          {/* source URL */}
          {display.url && (
            <a
              href={display.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 underline mb-5 transition-colors"
            >
              원본 기사 보기 →
            </a>
          )}

          {/* emotion results */}
          {visibleEmotions.length > 0 && (
            <div className="mb-6">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">감정 분류 결과</h3>
              {loadingDetail ? (
                <div className="space-y-2">
                  {[1, 2, 3].map((k) => (
                    <div key={k} className="animate-pulse">
                      <div className="h-3 bg-gray-200 rounded w-24 mb-1" />
                      <div className="h-2 bg-gray-100 rounded w-full" />
                    </div>
                  ))}
                </div>
              ) : (
                <div className="space-y-2">
                  {visibleEmotions.map((e, i) => (
                    <div key={e.label}>
                      <div className="flex items-center justify-between mb-0.5">
                        <span
                          className={`text-xs font-medium ${
                            i === 0 ? "text-gray-900" : "text-gray-600"
                          }`}
                        >
                          {e.label}
                        </span>
                        <span className="text-xs text-gray-500">
                          {e.prob.toFixed(2)}
                        </span>
                      </div>
                      <div className="w-full bg-gray-100 rounded-full h-2">
                        <div
                          className="h-2 rounded-full transition-all"
                          style={{
                            width: `${e.prob * 100}%`,
                            backgroundColor: i === 0 ? "#1B365D" : "#4d7ab5",
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* evidence tokens */}
          {evidenceTokens.length > 0 && !loadingDetail && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-2">
                Evidence Tokens
              </h3>
              <div className="flex gap-2 flex-wrap">
                {evidenceTokens.map((t) => (
                  <span
                    key={t}
                    className="px-3 py-1 bg-blue-50 text-blue-700 text-sm rounded-full border border-blue-200 font-medium"
                  >
                    "{t}"
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function formatDate(iso) {
  const d = new Date(iso);
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, "0")}.${String(
    d.getDate()
  ).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(
    d.getMinutes()
  ).padStart(2, "0")}`;
}
