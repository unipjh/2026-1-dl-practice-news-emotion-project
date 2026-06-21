export const POSITIVE_EMOTIONS = [
  "환영/호의", "감동/감탄", "고마움", "존경", "기대감", "뿌듯함",
  "편안/쾌적", "신기함/관심", "아껴주는", "즐거움/신남",
  "흐뭇함(귀여움/예쁨)", "불쌍함/연민", "행복", "기쁨", "안심/신뢰",
];

export const NEUTRAL_LABEL = "없음";

export const NEUTRAL_EMOTIONS = [
  NEUTRAL_LABEL, "우쭐댐/무시함", "놀람", "깨달음", "비장함",
];

export const NEGATIVE_EMOTIONS = [
  "불평/불만", "지긋지긋", "슬픔", "화남/분노",
  "안타까움/실망", "의심/불신", "부끄러움", "공포/무서움",
  "절망", "한심함", "역겨움/징그러움", "짜증", "어이없음",
  "패배/자기혐오", "귀찮음", "힘듦/지침", "죄책감", "증오/혐오",
  "당황/난처", "경악", "부담/안_내킴", "서러움", "재미없음",
  "불안/걱정",
];

export const ALL_EMOTIONS = [...POSITIVE_EMOTIONS, ...NEUTRAL_EMOTIONS, ...NEGATIVE_EMOTIONS];

export function isNeutralTopEmotion(emotions, topEmotionLabel = null) {
  if (topEmotionLabel !== null) return topEmotionLabel === NEUTRAL_LABEL;
  const none = emotions.find((e) => e.label === NEUTRAL_LABEL);
  if (!none) return false;
  const maxProb = Math.max(...emotions.map((e) => e.prob));
  return none.prob >= maxProb;
}

export function isCountableEmotion(emotions, label, threshold = 0, topEmotionLabel = null) {
  const emotion = emotions.find((e) => e.label === label);
  if (!emotion || emotion.prob < threshold) return false;
  if (label !== NEUTRAL_LABEL) return true;
  return isNeutralTopEmotion(emotions, topEmotionLabel);
}

export function filterVisibleEmotions(emotions, threshold = 0, topEmotionLabel = null) {
  return emotions.filter((e) => isCountableEmotion(emotions, e.label, threshold, topEmotionLabel));
}

export function getEmotionGroup(label) {
  if (POSITIVE_EMOTIONS.includes(label)) return "positive";
  if (NEUTRAL_EMOTIONS.includes(label)) return "neutral";
  return "negative";
}

export function filterEmotionsByGroup(group) {
  if (group === "positive") return POSITIVE_EMOTIONS;
  if (group === "neutral") return NEUTRAL_EMOTIONS;
  if (group === "negative") return NEGATIVE_EMOTIONS;
  return ALL_EMOTIONS;
}
