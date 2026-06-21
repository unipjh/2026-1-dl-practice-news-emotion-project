import { useEffect, useState, useCallback } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Cell, Legend, LabelList,
} from "recharts";
import { useApp } from "../context/AppContext";
import { getDistribution } from "../lib/api";
import { toggleEmotionSelect } from "../lib/filterLogic";
import { getEmotionGroup } from "../lib/emotions";

const GROUP_COLORS = ["#1B365D", "#4d7ab5", "#e07b39", "#5a9e6f"];
const AVG_COLOR = "#87867f";

const SENT_COLOR = {
  positive: "#C0392B",
  neutral: "#87867f",
  negative: "#2C5F8A",
};

// Per-group shade palettes: darker for group 0, progressively lighter
const SENTIMENT_PALETTES = {
  positive: ["#C0392B", "#cf5e55", "#dc8880"],
  neutral:  ["#87867f", "#9e9d96", "#b6b5af"],
  negative: ["#2C5F8A", "#4a7aaa", "#6d99c2"],
};

export default function EmotionBarChart() {
  const {
    dt, sentimentGroup, compareGroups,
    chartSelection, setChartSelection, showToast,
  } = useApp();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const isMultiGroup = compareGroups.length > 1 || compareGroups[0]?.key !== "전체";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getDistribution({ dt, sentimentGroup, compareGroups });
      setData(res);
    } finally {
      setLoading(false);
    }
  }, [dt, sentimentGroup, compareGroups]);

  useEffect(() => { load(); }, [load]);

  function handleEmotionClick(label) {
    const next = toggleEmotionSelect(chartSelection, label);
    if (next._toastTrigger !== chartSelection._toastTrigger) {
      showToast("최대 3개까지 선택 가능합니다");
    }
    setChartSelection({ ...next, _toastTrigger: undefined });
  }

  function handleOpenTimeseries() {
    if (chartSelection.selectedEmotions.length === 0) return;
    setChartSelection((s) => ({ ...s, timeseriesOpen: true }));
  }

  if (loading) {
    return (
      <div className="bg-[#faf9f5] rounded-xl border border-gray-200 p-6 mb-4">
        <div className="h-96 flex items-center justify-center text-gray-400 text-sm">
          데이터 로딩 중...
        </div>
      </div>
    );
  }

  if (!data) return null;

  const { groupCounts, globalAvg, emotionLabels } = data;

  // Build chart rows sorted by total count desc
  const rows = emotionLabels.map((label) => {
    const row = { label };
    let total = 0;
    for (const [i, g] of compareGroups.entries()) {
      const cnt = groupCounts[g.key]?.[label] ?? 0;
      row[g.key] = cnt;
      total += cnt;
    }
    row._total = total;
    row._avg = globalAvg[label] ?? 0;
    return row;
  });

  rows.sort((a, b) => b._total - a._total);
  const displayRows = rows.slice(0, 20);

  const maxCount = Math.max(
    ...displayRows.flatMap((r) =>
      compareGroups.map((g) => r[g.key] ?? 0)
    ),
    1
  );
  const chartHeight = isMultiGroup
    ? Math.max(420, displayRows.length * Math.max(48, compareGroups.length * 24))
    : Math.max(320, displayRows.length * 34);
  const barCategoryGap = isMultiGroup ? "14%" : "25%";
  const barGap = isMultiGroup ? 5 : 2;
  const chartRightMargin = isMultiGroup ? 92 : 60;
  const multiGroupBarSize = compareGroups.length <= 2 ? 20 : compareGroups.length === 3 ? 18 : 16;

  function getGroupBarColor(label, groupIndex) {
    const sentGroup = getEmotionGroup(label);
    const palette = SENTIMENT_PALETTES[sentGroup] || SENTIMENT_PALETTES.neutral;
    return palette[groupIndex % palette.length];
  }

  function renderGroupValueLabel(groupIndex) {
    return ({ x = 0, y = 0, width = 0, height = 0, value, payload, index }) => {
      if (!value) return null;
      const label = payload?.label ?? displayRows[index]?.label;
      if (!label) return null;
      const fill = getGroupBarColor(label, groupIndex);
      return (
        <text
          x={x + width + 6}
          y={y + height / 2}
          dy={4}
          textAnchor="start"
          fontSize={10}
          fontWeight={600}
          fill={fill}
        >
          {value}
        </text>
      );
    };
  }

  // Custom Y-axis tick with click
  function CustomYTick({ x, y, payload }) {
    const label = payload.value;
    const isSelected = chartSelection.selectedEmotions.includes(label);
    return (
      <g transform={`translate(${x},${y})`}>
        <text
          x={-4}
          y={0}
          dy={4}
          textAnchor="end"
          fontSize={11}
          fill={isSelected ? "#1B365D" : "#555"}
          fontWeight={isSelected ? "700" : "400"}
          cursor="pointer"
          onClick={() => handleEmotionClick(label)}
        >
          {isSelected ? "✓ " : ""}{label}
        </text>
      </g>
    );
  }

  // Custom dot for global average
  function AvgDot({ cx, cy, payload }) {
    const avg = payload._avg;
    if (!avg) return null;
    const dotX = cx; // positioned by recharts based on value
    return <circle cx={dotX} cy={cy} r={5} fill={AVG_COLOR} stroke="white" strokeWidth={1.5} />;
  }

  const sentColor = SENT_COLOR[sentimentGroup] || "#1B365D";
  const hasSelection = chartSelection.selectedEmotions.length > 0;

  return (
    <div className="bg-[#faf9f5] rounded-xl border border-gray-200 p-6 mb-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-gray-800">감정별 분포</h2>
          {chartSelection.selectedEmotions.length > 0 && (
            <p className="text-xs text-gray-500 mt-0.5">
              선택: {chartSelection.selectedEmotions.join(", ")}
            </p>
          )}
        </div>
        <button
          onClick={handleOpenTimeseries}
          disabled={!hasSelection}
          className={`text-sm px-4 py-1.5 rounded-lg font-medium transition-colors ${
            hasSelection
              ? "bg-[#1B365D] text-white hover:bg-[#1B365D]/90"
              : "bg-gray-100 text-gray-400 cursor-not-allowed"
          }`}
        >
          시계열 분석 실행 →
        </button>
      </div>

      <p className="text-xs text-gray-400 mb-3">감정 레이블을 클릭하면 시계열 분석에 추가됩니다 (최대 3개)</p>

      <ResponsiveContainer width="100%" height={chartHeight}>
        <BarChart
          data={displayRows}
          layout="vertical"
          margin={{ top: 4, right: chartRightMargin, left: 130, bottom: 4 }}
          barCategoryGap={barCategoryGap}
          barGap={barGap}
        >
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e5e5e5" />
          <XAxis type="number" domain={[0, maxCount + 1]} tick={{ fontSize: 11, fill: "#888" }} />
          <YAxis
            type="category"
            dataKey="label"
            tick={<CustomYTick />}
            width={130}
            interval={0}
          />
          <Tooltip
            cursor={{ fill: 'transparent' }}
            formatter={(val, name) =>
              name === "_avg" || name === "전체평균"
                ? [typeof val === "number" ? val.toFixed(2) : val, "전체평균"]
                : [val, name]
            }
            contentStyle={{ fontSize: 12, borderRadius: 8 }}
          />

          {compareGroups.length === 1 && compareGroups[0].key === "전체" ? (
            <Bar dataKey="전체" fill={sentColor} radius={[0, 3, 3, 0]} maxBarSize={16}>
              {displayRows.map((entry) => {
                const barColor = sentimentGroup === "all"
                  ? (SENT_COLOR[getEmotionGroup(entry.label)] || "#87867f")
                  : sentColor;
                const isSelected = chartSelection.selectedEmotions.includes(entry.label);
                const hasSelection = chartSelection.selectedEmotions.length > 0;
                return (
                  <Cell
                    key={entry.label}
                    fill={barColor}
                    opacity={hasSelection && !isSelected ? 0.3 : 1}
                  />
                );
              })}
              <LabelList
                dataKey="전체"
                position="right"
                style={{ fontSize: 10, fill: "#6b7280" }}
              />
            </Bar>
          ) : (
            compareGroups.map((g, i) => (
              <Bar
                key={g.key}
                dataKey={g.key}
                name={g.label}
                fill={GROUP_COLORS[i % GROUP_COLORS.length]}
                radius={[0, 3, 3, 0]}
                maxBarSize={multiGroupBarSize}
              >
                {displayRows.map((entry) => (
                  <Cell
                    key={entry.label}
                    fill={getGroupBarColor(entry.label, i)}
                  />
                ))}
                <LabelList
                  dataKey={g.key}
                  position="right"
                  content={renderGroupValueLabel(i)}
                />
              </Bar>
            ))
          )}

          {/* avg overlay as reference dots — rendered as a scatter-style bar with tiny width */}
          <Bar
            dataKey="_avg"
            name="전체평균"
            fill={AVG_COLOR}
            maxBarSize={2}
            radius={4}
          />
        </BarChart>
      </ResponsiveContainer>

      {/* Legend */}
      <div className="flex items-center gap-4 mt-3 flex-wrap">
        {compareGroups.length > 1 || compareGroups[0]?.key !== "전체" ? (
          <div className="flex flex-wrap gap-x-4 gap-y-1.5 w-full">
            <div className="flex items-center gap-3 flex-wrap">
              {compareGroups.map((g, i) => (
                <div key={g.key} className="flex items-center gap-1.5 text-xs text-gray-600">
                  <span className="flex gap-0.5">
                    <span className="w-2 h-3 rounded-sm inline-block" style={{ backgroundColor: SENTIMENT_PALETTES.negative[i % 3] }} />
                    <span className="w-2 h-3 rounded-sm inline-block" style={{ backgroundColor: SENTIMENT_PALETTES.positive[i % 3] }} />
                  </span>
                  {g.label}
                </div>
              ))}
            </div>
            <div className="flex items-center gap-3 flex-wrap text-xs text-gray-400 border-l border-gray-200 pl-3">
              <div className="flex items-center gap-1">
                <span className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: SENT_COLOR.positive }} />긍정
              </div>
              <div className="flex items-center gap-1">
                <span className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: SENT_COLOR.neutral }} />중립
              </div>
              <div className="flex items-center gap-1">
                <span className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: SENT_COLOR.negative }} />부정
              </div>
            </div>
          </div>
        ) : sentimentGroup === "all" ? (
          <>
            <div className="flex items-center gap-1.5 text-xs text-gray-600">
              <span className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: SENT_COLOR.positive }} />
              긍정
            </div>
            <div className="flex items-center gap-1.5 text-xs text-gray-600">
              <span className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: SENT_COLOR.neutral }} />
              중립
            </div>
            <div className="flex items-center gap-1.5 text-xs text-gray-600">
              <span className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: SENT_COLOR.negative }} />
              부정
            </div>
          </>
        ) : (
          <div className="flex items-center gap-1.5 text-xs text-gray-600">
            <span className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: sentColor }} />
            전체
          </div>
        )}
        <div className="flex items-center gap-1.5 text-xs text-gray-600">
          <span className="w-3 h-3 rounded-full inline-block" style={{ backgroundColor: AVG_COLOR }} />
          전체 평균
        </div>
      </div>
    </div>
  );
}
