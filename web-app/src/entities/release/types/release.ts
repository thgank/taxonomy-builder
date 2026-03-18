export interface TaxonomyRelease {
  id: string;
  collectionId: string;
  taxonomyVersionId: string;
  releaseName: string;
  channel: string;
  trafficPercent: number | null;
  isActive: boolean | null;
  rollbackOf: string | null;
  qualitySnapshot: Record<string, unknown> | null;
  notes: string | null;
  createdAt: string;
}

export interface CreateReleaseRequest {
  taxonomyVersionId?: string;
  releaseName?: string;
  channel?: string;
  trafficPercent?: number;
  notes?: string;
}

export interface PromoteReleaseRequest {
  channel?: string;
  trafficPercent?: number;
  notes?: string;
}

export interface RollbackReleaseRequest {
  rollbackToReleaseId?: string;
  channel?: string;
  notes?: string;
}
