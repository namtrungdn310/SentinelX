import type { MetricSample } from "./types";
import { validMetric } from "./presentation";

/** Normalize REST/push batches before choosing the latest value or charting. */
export function mergeSamples(existing: MetricSample[], incoming: MetricSample[]): MetricSample[] {
  const unique = new Map<string, MetricSample>();
  for (const sample of [...existing, ...incoming]) {
    if (!Number.isFinite(Date.parse(sample.observed_at)) ||
        !validMetric(sample.cpu_percent) || !validMetric(sample.memory_percent)) continue;
    unique.set(new Date(sample.observed_at).toISOString(), sample);
  }
  return [...unique.values()]
    .sort((a, b) => Date.parse(a.observed_at) - Date.parse(b.observed_at))
    .slice(-120);
}

/** Fixed-width clock labels need 76px plus an 8px gap. End labels are anchored inward. */
export function timeTicks(start: number, end: number, plotWidth: number): number[] {
  if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return [];
  if (end - start < 1000 || plotWidth < 160) return [start];
  const count = Math.min(5, Math.max(2, Math.floor((end - start) / 1000) + 1), Math.max(2, Math.floor(plotWidth / 168) + 1));
  return Array.from({ length: count }, (_, index) => start + (end - start) * index / (count - 1));
}
