import { ScoredStock, WeightConfig } from '../types';

export const DEFAULT_WEIGHTS: WeightConfig = {
  model: 0.35,
  technical: 0.25,
  volume_price: 0.20,
  candle: 0.10,
  sentiment: 0.10,
};

export function normalizeWeights(weights: WeightConfig): WeightConfig {
  const sum = 
    Math.max(0, weights.model) +
    Math.max(0, weights.technical) +
    Math.max(0, weights.volume_price) +
    Math.max(0, weights.candle) +
    Math.max(0, weights.sentiment);

  if (sum === 0) {
    return { ...DEFAULT_WEIGHTS };
  }

  return {
    model: Math.round((Math.max(0, weights.model) / sum) * 100) / 100,
    technical: Math.round((Math.max(0, weights.technical) / sum) * 100) / 100,
    volume_price: Math.round((Math.max(0, weights.volume_price) / sum) * 100) / 100,
    candle: Math.round((Math.max(0, weights.candle) / sum) * 100) / 100,
    sentiment: Math.round((Math.max(0, weights.sentiment) / sum) * 100) / 100,
  };
}

export function calculateCompositeScores(
  stocks: ScoredStock[],
  weights: WeightConfig
): ScoredStock[] {
  const normWeights = normalizeWeights(weights);

  const recomputed = stocks.map((s) => {
    const composite_score = Number(
      (
        s.model_score * normWeights.model +
        s.technical_score * normWeights.technical +
        s.volume_price_score * normWeights.volume_price +
        s.candle_score * normWeights.candle +
        s.sentiment_score * normWeights.sentiment
      ).toFixed(1)
    );

    return {
      ...s,
      composite_score,
    };
  });

  // Sort descending by composite_score
  recomputed.sort((a, b) => b.composite_score - a.composite_score);

  // Assign ranks
  return recomputed.map((s, idx) => ({
    ...s,
    rank: idx + 1,
  }));
}
