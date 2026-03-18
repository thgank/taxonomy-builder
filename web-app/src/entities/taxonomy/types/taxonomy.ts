export interface TaxonomyVersion {
  id: string;
  collectionId: string;
  algorithm: string;
  parameters: Record<string, unknown> | null;
  qualityMetrics: Record<string, unknown> | null;
  status: "NEW" | "RUNNING" | "READY" | "FAILED";
  createdAt: string;
  finishedAt: string | null;
  edgeCount: number;
  conceptCount: number;
}

export interface TaxonomyTreeNode {
  conceptId: string;
  label: string;
  score: number | null;
  children: TaxonomyTreeNode[];
}

export interface TaxonomyTree {
  taxonomyVersionId: string;
  roots: TaxonomyTreeNode[];
}

export interface TaxonomyEdge {
  id: string;
  parentConceptId: string;
  parentLabel: string;
  childConceptId: string;
  childLabel: string;
  relation: string | null;
  score: number | null;
  evidence: Record<string, unknown>[];
}

export interface CreateTaxonomyEdgeRequest {
  parentConceptId: string;
  childConceptId: string;
  relation?: string;
  score?: number;
}

export interface UpdateTaxonomyEdgeRequest {
  score?: number;
  approved?: boolean;
}

export interface TaxonomyEdgeLabel {
  id: string;
  candidateId: string | null;
  taxonomyVersionId: string;
  collectionId: string;
  parentConceptId: string | null;
  childConceptId: string | null;
  parentLabel: string | null;
  childLabel: string | null;
  label: string | null;
  labelSource: string | null;
  reviewerId: string | null;
  reason: string | null;
  meta: Record<string, unknown> | null;
  createdAt: string;
}

export interface CreateTaxonomyEdgeLabelRequest {
  candidateId?: string;
  parentConceptId?: string;
  childConceptId?: string;
  parentLabel?: string;
  childLabel?: string;
  label?: string;
  labelSource?: string;
  reviewerId?: string;
  reason?: string;
  meta?: Record<string, unknown>;
}

export interface Concept {
  id: string;
  canonical: string;
  surfaceForms: string[];
  lang: string | null;
  score: number | null;
}

export interface RelatedConcept {
  id: string;
  canonical: string;
  edgeScore: number | null;
}

export interface OccurrenceInfo {
  chunkId: string;
  documentId: string;
  snippet: string;
  confidence: number | null;
}

export interface ConceptDetail extends Concept {
  parents: RelatedConcept[];
  children: RelatedConcept[];
  occurrences: OccurrenceInfo[];
}

export interface TaxonomyExport {
  taxonomyVersionId: string;
  collectionId: string;
  algorithm: string;
  parameters: Record<string, unknown> | null;
  qualityMetrics: Record<string, unknown> | null;
  nodes: Array<{ id: string; label: string }>;
  edges: Array<{
    parent: string;
    child: string;
    score: number | null;
    evidence: Record<string, unknown>[];
  }>;
}
