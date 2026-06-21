import { useEffect, useRef, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from "recharts";
import { useApp } from "../context/AppContext";
import { getTrends } from "../lib/api";
import { getEmotionGroup } from "../lib/emotions";

const GROUP_COLORS = ["#1B365D", "#4d7ab5", "#e07b39", "#5a9e6f"];

const SENT_COLOR = {
  positive: "#C0392B",
  neutral:  "#87867f",
  negative: "#2C5F8A",
};

export default function TimeseriesModal() {
  const { chartSelection, setChartSelection, compareGroups, dt } = useApp();

  const [modalDt, setModalDt] = useState(dt);
  const [trendsData, setTrendsData] = useState(null);
  const [loading, setLoading] = useState(true);

  const { selectedEmotions, timeseriesOpen } = chartSelection;

  // 모달이 열릴 때마다 메인 ControlBar의 dt를 초기값으로 사용
  const prevOpen = useRef(false);
  useEffect(() => {
    if (timeseriesOpen && !prevOpen.current) setModalDt(dt);
    prevOpen.current = timeseriesOpen;
  }, [timeseriesOpen, dt]);

  useEffect(() => {
    if (!timeseriesOpen || selectedEmotions.length === 0) return;
    setLoading(true);
    getTrends({ dt: modalDt, selectedEmotions, compareGroups }).then((res) => {
      setTrendsData(res);
      setLoading(false);
    });
  }, [timeseriesOpen, modalDt, selectedEmotions, compareGroups]);

  function handleClose() {
    setChartSelection((s) => ({ ...s, timeseriesOpen: false }));
  }

  function removeEmotion(emotion) {
    setChartSelection((s) => ({
      ...s,
      selectedEmotions: s.selectedEmotions.filter((e) => e !== emotion),
      timeseriesOpen: s.selectedEmotions.length > 1,
    }));
  }

  if (!timeseriesOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-5xl max-h-[90vh] overflow-y-auto">
        {/* header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 rounded-t-2xl z-10">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-semibold text-gray-800">시계열 분석</h2>
            <button
              onClick={handleClose}
              className="text-gray-400 hover:text-gray-700 text-xl transition-colors"
            >
              ✕
            </button>
          </div>
          <div className="flex items-center gap-4 flex-wrap">
            {/* modal dt toggle */}
            <div className="flex bg-gray-100 rounded-lg overflow-hidden">
              {["6h", "1d", "1w", "1m", "1y"].map((opt) => (
                <button
                  key={opt}
                  onClick={() => setModalDt(opt)}
                  className={`px-3 py-1 text-sm font-medium transition-colors ${
                    modalDt === opt ? "bg-[#1B365D] text-white" : "text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  {opt}
                </button>
              ))}
            </div>
            {/* selected emotions */}
            <div className="flex gap-2 flex-wrap">
              {selectedEmotions.map((e) => (
                <button
                  key={e}
                  onClick={() => removeEmotion(e)}
                  className="flex items-center gap-1 text-xs px-2.5 py-1 bg-[#1B365D]/10 text-[#1B365D] rounded-full hover:bg-red-50 hover:text-red-600 transition-colors"
                >
                  {e} <span>✕</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* charts */}
        <div className="p-6">
          {loading ? (
            <div className="h-64 flex items-center justify-center text-gray-400 text-sm">
              데이터 로딩 중...
            </div>
          ) : (
            <div className="space-y-6">
              {selectedEmotions.map((emotion) => {
                const seriesMap = trendsData?.trends[emotion] ?? {};
                const bucketLabels = trendsData?.bucketLabels ?? [];

                const chartData = bucketLabels.map((label, i) => {
                  const point = { time: label };
                  for (const g of compareGroups) {
                    point[g.key] = seriesMap[g.key]?.[i]?.count ?? 0;
                  }
                  return point;
                });

                const subplotHeight = selectedEmotions.length === 1 ? 300 : 200;

                return (
                  <div key={emotion}>
                    <p className="text-sm font-semibold text-gray-700 mb-2">{emotion}</p>
                    <ResponsiveContainer width="100%" height={subplotHeight}>
                      <LineChart data={chartData} margin={{ top: 4, right: 20, left: 0, bottom: 4 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
                        <XAxis dataKey="time" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
                        <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                        <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                        {compareGroups.map((g, i) => {
                          const isSingleTotal = compareGroups.length === 1 && g.key === "전체";
                          const stroke = isSingleTotal
                            ? (SENT_COLOR[getEmotionGroup(emotion)] || "#1B365D")
                            : GROUP_COLORS[i % GROUP_COLORS.length];
                          return (
                            <Line
                              key={g.key}
                              type="monotone"
                              dataKey={g.key}
                              name={g.label}
                              stroke={stroke}
                              strokeWidth={2}
                              dot={false}
                              activeDot={{ r: 4 }}
                            />
                          );
                        })}
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                );
              })}
            </div>
          )}

          {/* common legend — only shown for multi-group */}
          {(compareGroups.length > 1 || compareGroups[0]?.key !== "전체") && (
            <div className="flex items-center gap-4 mt-4 flex-wrap pt-4 border-t border-gray-100">
              {compareGroups.map((g, i) => (
                <div key={g.key} className="flex items-center gap-1.5 text-xs text-gray-600">
                  <span
                    className="w-6 h-0.5 inline-block"
                    style={{ backgroundColor: GROUP_COLORS[i % GROUP_COLORS.length] }}
                  />
                  {g.label}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
