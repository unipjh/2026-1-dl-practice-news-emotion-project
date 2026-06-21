import { getTimeRange, matchesGroup, getBucketUnit, formatBucketLabel } from "./filterLogic";
import { filterEmotionsByGroup, filterVisibleEmotions, getEmotionGroup, isCountableEmotion } from "./emotions";

export async function getCrawlerStatus() {
  try {
    const res = await fetch("/crawler/status");
    return res.json();
  } catch {
    return { last_crawled_at: null };
  }
}

// ─── Token cleanup ────────────────────────────────────────────────────────────

const SPECIAL_TOKENS = new Set(["[CLS]", "[SEP]", "[PAD]", "[UNK]", "[MASK]"]);
const HTML_ENTITIES = {
  "&quot;": '"', "&amp;": "&", "&lt;": "<", "&gt;": ">", "&apos;": "'", "&nbsp;": " ",
};

/**
 * Merges WordPiece ## subword tokens, removes special tokens, and decodes HTML entities.
 * Input: [{token, weight}]  Output: {tokens: string[], weights: number[]}
 */
export function mergeWordPieceTokens(attnList) {
  if (!attnList || attnList.length === 0) return { tokens: [], weights: [] };

  // Step 1: filter specials, merge ## continuations
  const merged = [];
  for (const { token, weight } of attnList) {
    if (SPECIAL_TOKENS.has(token)) continue;
    if (token.startsWith("##")) {
      if (merged.length > 0) {
        merged[merged.length - 1].token += token.slice(2);
        merged[merged.length - 1].weight = Math.max(merged[merged.length - 1].weight, weight);
      }
    } else {
      merged.push({ token, weight });
    }
  }

  // Step 2: collapse HTML entity sequences (& + name + ;) → single char
  const result = [];
  let i = 0;
  while (i < merged.length) {
    if (
      merged[i].token === "&" &&
      i + 2 < merged.length &&
      merged[i + 2].token === ";"
    ) {
      const entity = `&${merged[i + 1].token};`;
      const decoded = HTML_ENTITIES[entity];
      if (decoded !== undefined) {
        result.push({
          token: decoded,
          weight: Math.max(merged[i].weight, merged[i + 1].weight, merged[i + 2].weight),
        });
        i += 3;
        continue;
      }
    }
    result.push(merged[i]);
    i++;
  }

  return {
    tokens: result.map((r) => r.token),
    weights: result.map((r) => r.weight),
  };
}

// ─── Backend headline cache ───────────────────────────────────────────────────

let _backendCache = null;
let _backendCacheExp = 0;
const CACHE_TTL_MS = 30_000;

async function loadAllFromBackend() {
  const now = Date.now();
  if (_backendCache && now < _backendCacheExp) return _backendCache;

  const res = await fetch("/headlines?limit=200000");
  if (!res.ok) {
    throw new Error("Failed to load headlines: " + res.status);
  }
  const raw = await res.json();

  _backendCache = raw.map((item) => ({
    ...item,
    emotions: filterVisibleEmotions(
      Object.entries(item.emotions)
        .map(([label, prob]) => ({ label, prob }))
        .sort((a, b) => b.prob - a.prob),
      0,
      item.top_emotion ?? null
    ),
  }));
  _backendCacheExp = now + CACHE_TTL_MS;
  return _backendCache;
}

/** Fetch full detail (with attention_weights) for a single headline. */
export async function getHeadlineDetail(id) {
  const res = await fetch(`/headlines/${id}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  const { tokens, weights } = mergeWordPieceTokens(data.attention_weights || []);
  return {
    ...data,
    emotions: filterVisibleEmotions(
      Object.entries(data.emotions)
        .map(([label, prob]) => ({ label, prob }))
        .sort((a, b) => b.prob - a.prob),
      0,
      data.top_emotion ?? null
    ),
    tokens,
    attention_weights: weights,
  };
}

/** Returns the full cached headline array (for client-side computations). */
export async function getAllHeadlines() {
  return loadAllFromBackend();
}

export async function getHeadlines(query) {
  const all = await loadAllFromBackend();
  const { start, end } = getTimeRange(query.dt);

  let filtered = all.filter((r) => {
    const t = new Date(r.published_at);
    return t >= start && t <= end;
  });

  if (query.compareGroups && query.compareGroups.length > 0) {
    const isGlobal =
      query.compareGroups.length === 1 && query.compareGroups[0].key === "전체";
    if (!isGlobal) {
      filtered = filtered.filter((r) =>
        query.compareGroups.some((g) => matchesGroup(r, g))
      );
    }
  }

  if (query.sentimentGroup && query.sentimentGroup !== "all") {
    filtered = filtered.filter((r) =>
      r.emotions.some(
        (e) => getEmotionGroup(e.label) === query.sentimentGroup && isCountableEmotion(r.emotions, e.label, 0.5, r.top_emotion ?? null)
      )
    );
  }

  filtered.sort((a, b) => new Date(b.published_at) - new Date(a.published_at));

  const page = query.page || 1;
  const pageSize = query.pageSize || 20;
  const total = filtered.length;
  const items = filtered.slice((page - 1) * pageSize, page * pageSize);

  return { items, total, page, pageSize };
}

// ─── Chart aggregations from backend/DB headlines ─────────────────────────────

export async function getDistribution(filter) {
  const all = await loadAllFromBackend();
  const { start, end } = getTimeRange(filter.dt);

  const inRange = all.filter((r) => {
    const t = new Date(r.published_at);
    return t >= start && t <= end;
  });

  const emotionLabels = filterEmotionsByGroup(
    filter.sentimentGroup === "all" ? "all" : filter.sentimentGroup
  );

  const groups = filter.compareGroups;
  const THRESHOLD = 0.3;

  const result = {};
  for (const group of groups) {
    const groupData = inRange.filter((r) => matchesGroup(r, group));
    const counts = {};
    for (const label of emotionLabels) counts[label] = 0;
    for (const r of groupData) {
      for (const e of r.emotions) {
        if (emotionLabels.includes(e.label) && isCountableEmotion(r.emotions, e.label, THRESHOLD, r.top_emotion ?? null)) {
          counts[e.label] = (counts[e.label] || 0) + 1;
        }
      }
    }
    result[group.key] = counts;
  }

  const globalCounts = {};
  for (const label of emotionLabels) globalCounts[label] = 0;
  for (const r of inRange) {
    for (const e of r.emotions) {
      if (emotionLabels.includes(e.label) && isCountableEmotion(r.emotions, e.label, THRESHOLD, r.top_emotion ?? null)) {
        globalCounts[e.label] = (globalCounts[e.label] || 0) + 1;
      }
    }
  }
  const totalDocs = inRange.length || 1;
  const globalAvg = {};
  for (const label of emotionLabels) {
    globalAvg[label] = globalCounts[label] / totalDocs;
  }

  return { groupCounts: result, globalAvg, emotionLabels };
}

export async function getTrends(query) {
  const all = await loadAllFromBackend();
  const { start, end } = getTimeRange(query.dt);
  const bucketMinutes = getBucketUnit(query.dt);

  const inRange = all.filter((r) => {
    const t = new Date(r.published_at);
    return t >= start && t <= end;
  });

  const buckets = [];
  const cur = new Date(start);
  const bucketMs = bucketMinutes * 60 * 1000;
  cur.setTime(Math.ceil(cur.getTime() / bucketMs) * bucketMs);
  while (cur <= end) {
    buckets.push(new Date(cur));
    cur.setTime(cur.getTime() + bucketMs);
  }

  const THRESHOLD = 0.3;
  const result = {};

  for (const emotion of query.selectedEmotions) {
    result[emotion] = {};
    for (const group of query.compareGroups) {
      const series = buckets.map((b) => {
        const bEnd = new Date(b.getTime() + bucketMs);
        const count = inRange.filter((r) => {
          const t = new Date(r.published_at);
          if (t < b || t >= bEnd) return false;
          if (!matchesGroup(r, group)) return false;
          return r.emotions.some((e) => e.label === emotion && isCountableEmotion(r.emotions, e.label, THRESHOLD, r.top_emotion ?? null));
        }).length;
        return { time: formatBucketLabel(b, query.dt), count };
      });
      result[emotion][group.key] = series;
    }
  }

  const bucketLabels = buckets.map((b) => formatBucketLabel(b, query.dt));
  return { trends: result, bucketLabels };
}
