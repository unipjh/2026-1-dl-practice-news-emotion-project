import { useEffect, useState, useCallback } from "react";
import { useApp } from "../context/AppContext";
import { getHeadlines, getCrawlerStatus } from "../lib/api";

const PUB_COLORS = {
  "조선일보": "bg-blue-50 text-blue-700",
  "한겨레": "bg-green-50 text-green-700",
  "매일경제": "bg-orange-50 text-orange-700",
  "연합뉴스": "bg-purple-50 text-purple-700",
};

export default function HeadlineList() {
  const { dt, sentimentGroup, compareGroups, setSelectedHeadline } = useApp();
  const [result, setResult] = useState(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [lastCrawled, setLastCrawled] = useState(null);

  useEffect(() => {
    getCrawlerStatus().then((s) => setLastCrawled(s.last_crawled_at));
    const id = setInterval(
      () => getCrawlerStatus().then((s) => setLastCrawled(s.last_crawled_at)),
      60000
    );
    return () => clearInterval(id);
  }, []);

  const load = useCallback(async (pg = 1) => {
    setLoading(true);
    try {
      const res = await getHeadlines({
        dt, sentimentGroup, compareGroups, page: pg, pageSize: 20,
      });
      setResult(res);
    } finally {
      setLoading(false);
    }
  }, [dt, sentimentGroup, compareGroups]);

  useEffect(() => {
    setPage(1);
    load(1);
  }, [load]);

  function handlePage(pg) {
    setPage(pg);
    load(pg);
  }

  const totalPages = result ? Math.ceil(result.total / 20) : 0;

  return (
    <div className="bg-[#faf9f5] rounded-xl border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold text-gray-800">헤드라인</h2>
        {result && (
          <span className="text-xs text-gray-400">
            총 {result.total}개 · 현재 필터 기준
            {lastCrawled && ` · 최신 크롤링: ${formatTime(lastCrawled)}`}
          </span>
        )}
      </div>

      {loading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="animate-pulse">
              <div className="h-4 bg-gray-200 rounded w-24 mb-2" />
              <div className="h-4 bg-gray-200 rounded w-full mb-1" />
              <div className="h-3 bg-gray-100 rounded w-32" />
            </div>
          ))}
        </div>
      ) : result?.items.length === 0 ? (
        <p className="text-sm text-gray-400 py-8 text-center">해당 필터 조건에 맞는 헤드라인이 없습니다.</p>
      ) : (
        <div className="divide-y divide-gray-100">
          {result.items.map((item) => {
            const top2 = item.emotions.slice(0, 2);
            const pubColor = PUB_COLORS[item.publisher] || "bg-gray-100 text-gray-600";
            return (
              <div
                key={item.id}
                className="py-3 cursor-pointer hover:bg-gray-50 -mx-2 px-2 rounded-lg transition-colors"
                onClick={() => setSelectedHeadline(item)}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${pubColor}`}>
                    {item.publisher}
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
                    {item.category}
                  </span>
                  <span className="text-xs text-gray-400 ml-auto">
                    {formatDate(item.published_at)}
                  </span>
                </div>
                <p className="text-sm font-medium text-gray-800 mb-1 leading-snug">{item.headline}</p>
                <div className="flex gap-2">
                  {top2.map((e) => (
                    <span key={e.label} className="text-xs text-gray-500">
                      {e.label} <span className="text-gray-400">{e.prob.toFixed(2)}</span>
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-1 mt-5">
          <button
            disabled={page <= 1}
            onClick={() => handlePage(page - 1)}
            className="px-3 py-1 text-sm rounded-lg border border-gray-200 disabled:opacity-40 hover:bg-gray-50"
          >
            이전
          </button>
          <span className="text-sm text-gray-500 px-2">
            {page} / {totalPages}
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => handlePage(page + 1)}
            className="px-3 py-1 text-sm rounded-lg border border-gray-200 disabled:opacity-40 hover:bg-gray-50"
          >
            다음
          </button>
        </div>
      )}
    </div>
  );
}

function formatDate(iso) {
  const d = new Date(iso);
  const mo = d.getMonth() + 1;
  const day = d.getDate();
  const h = String(d.getHours()).padStart(2, "0");
  const m = String(d.getMinutes()).padStart(2, "0");
  return `${mo}/${day} ${h}:${m}`;
}

function formatTime(iso) {
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
