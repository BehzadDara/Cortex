import type { AudioOverviewSummary } from "../types";

export function isUnfinished(overview: AudioOverviewSummary): boolean {
  return overview.status === "queued" || overview.status === "running";
}

export function errorMessage(caught: unknown): string {
  return caught instanceof Error ? caught.message : String(caught);
}

export function overviewName(overview: AudioOverviewSummary): string {
  if (overview.title) return overview.title;
  return `${overview.collection_name ?? "Collection"} overview`;
}
