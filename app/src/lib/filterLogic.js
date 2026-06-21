export function buildCompareGroups(filter) {
  const { publishers: P, categories: C } = filter;

  if (P.length === 0 && C.length === 0) {
    return [{ key: "전체", label: "전체" }];
  }

  if (P.length === 0 && C.length > 0) {
    return C.map((c) => ({ key: c, label: c, category: c }));
  }

  if (P.length > 0 && C.length === 0) {
    return P.map((p) => ({ key: p, label: p, publisher: p }));
  }

  const groups = [];
  for (const p of P) {
    for (const c of C) {
      groups.push({ key: `${p}_${c}`, label: `${p}_${c}`, publisher: p, category: c });
    }
  }
  return groups;
}

export function canSelect(current) {
  return current.publishers.length + current.categories.length < 4;
}

export function getTimeRange(mode) {
  const end = new Date();
  const start = new Date();
  if (mode === "6h") start.setHours(end.getHours() - 6);
  if (mode === "1d") start.setDate(end.getDate() - 1);
  if (mode === "1w") start.setDate(end.getDate() - 7);
  if (mode === "1m") start.setMonth(end.getMonth() - 1);
  if (mode === "1y") start.setFullYear(end.getFullYear() - 1);
  return { start, end };
}

export function getBucketUnit(mode) {
  if (mode === "6h") return 30;     // minutes
  if (mode === "1d") return 120;    // minutes
  if (mode === "1w") return 1440;   // minutes (1 day)
  if (mode === "1m") return 10080;  // minutes (1 week)
  return 43200;                     // minutes (1 month, ~30days)
}

export function formatBucketLabel(date, mode) {
  if (mode === "1w" || mode === "1m" || mode === "1y") {
    return `${date.getMonth() + 1}/${date.getDate()}`;
  }
  const h = String(date.getHours()).padStart(2, "0");
  const m = String(date.getMinutes()).padStart(2, "0");
  return `${h}:${m}`;
}

export function matchesGroup(record, group) {
  if (group.key === "전체") return true;
  if (group.publisher && group.category) {
    return record.publisher === group.publisher && record.category === group.category;
  }
  if (group.publisher) return record.publisher === group.publisher;
  if (group.category) return record.category === group.category;
  return false;
}

export function toggleEmotionSelect(state, emotion) {
  if (state.selectedEmotions.includes(emotion)) {
    return { ...state, selectedEmotions: state.selectedEmotions.filter((e) => e !== emotion) };
  }
  if (state.selectedEmotions.length >= 3) {
    return { ...state, _toastTrigger: Date.now() };
  }
  return { ...state, selectedEmotions: [...state.selectedEmotions, emotion] };
}

export function getHighlightStyle(weight, maxWeight) {
  const normalized = weight / maxWeight;
  if (normalized < 0.3) return "";
  if (normalized < 0.6) return "bg-blue-100";
  if (normalized < 0.85) return "bg-blue-300";
  return "bg-blue-500 text-white";
}

// ELECTRA/BERT 특수 토큰, 서브워드 접두사, 순수 구두점은 Evidence로 무의미하므로 제외
const _SPECIAL_TOKEN = /^\[.*\]$/;          // [CLS] [SEP] [PAD] [UNK]
const _SUBWORD = /^##/;                      // ##있어요 → 서브워드 조각
const _PUNCT_ONLY = /^[^\p{L}\p{N}]+$/u;   // 문자·숫자가 하나도 없는 순수 기호/구두점

function isMeaningfulToken(token) {
  if (!token || token.trim() === "") return false;
  if (_SPECIAL_TOKEN.test(token)) return false;
  if (_SUBWORD.test(token)) return false;
  if (_PUNCT_ONLY.test(token)) return false;
  return true;
}

export function getEvidenceTokens(tokens, weights) {
  return weights
    .map((w, i) => ({ w, token: tokens[i] }))
    .filter(({ token }) => isMeaningfulToken(token))
    .sort((a, b) => b.w - a.w)
    .slice(0, 3)
    .map((x) => x.token);
}
