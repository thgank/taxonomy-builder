package com.taxonomy.api.service;

import com.taxonomy.api.dto.request.CreateEdgeRequest;
import com.taxonomy.api.dto.request.UpdateEdgeRequest;
import com.taxonomy.api.dto.response.*;
import com.taxonomy.api.entity.Concept;
import com.taxonomy.api.entity.TaxonomyEdge;
import com.taxonomy.api.entity.TaxonomyVersion;
import com.taxonomy.api.exception.ResourceNotFoundException;
import com.taxonomy.api.repository.*;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;
import java.util.stream.Collectors;

@Service
@Transactional(readOnly = true)
public class TaxonomyService {

    private final TaxonomyVersionRepository taxVersionRepo;
    private final TaxonomyEdgeRepository edgeRepo;
    private final ConceptRepository conceptRepo;
    private final ConceptOccurrenceRepository occurrenceRepo;

    public TaxonomyService(TaxonomyVersionRepository taxVersionRepo,
                           TaxonomyEdgeRepository edgeRepo,
                           ConceptRepository conceptRepo,
                           ConceptOccurrenceRepository occurrenceRepo) {
        this.taxVersionRepo = taxVersionRepo;
        this.edgeRepo = edgeRepo;
        this.conceptRepo = conceptRepo;
        this.occurrenceRepo = occurrenceRepo;
    }

    /* ── Versions ────────────────────────────────────────── */

    public List<TaxonomyVersionResponse> findVersionsByCollection(UUID collectionId) {
        return taxVersionRepo.findByCollectionIdOrderByCreatedAtDesc(collectionId).stream()
                .map(this::toVersionResponse)
                .toList();
    }

    public TaxonomyVersionResponse findVersionById(UUID taxId) {
        return toVersionResponse(getVersionEntity(taxId));
    }

    /* ── Tree ────────────────────────────────────────────── */

    public TaxonomyTreeResponse getTree(UUID taxId) {
        var version = getVersionEntity(taxId);
        List<UUID> rootIds = edgeRepo.findRootConceptIds(taxId);

        // If no edges, collect all concepts as standalone roots
        if (rootIds.isEmpty()) {
            List<Concept> concepts = conceptRepo.findByCollectionId(version.getCollection().getId());
            List<TaxonomyTreeResponse.TreeNode> roots = concepts.stream()
                    .map(c -> new TaxonomyTreeResponse.TreeNode(
                            c.getId(), c.getCanonical(), c.getScore(), List.of()))
                    .toList();
            return new TaxonomyTreeResponse(taxId, roots);
        }

        List<TaxonomyEdge> allEdges = edgeRepo.findByTaxonomyVersionId(taxId);
        Map<UUID, List<TaxonomyEdge>> childrenMap = allEdges.stream()
                .collect(Collectors.groupingBy(e -> e.getParentConcept().getId()));

        List<TaxonomyTreeResponse.TreeNode> roots = rootIds.stream()
                .map(rootId -> buildTreeNode(rootId, childrenMap, new HashSet<>()))
                .filter(Objects::nonNull)
                .toList();

        return new TaxonomyTreeResponse(taxId, roots);
    }

    private TaxonomyTreeResponse.TreeNode buildTreeNode(
            UUID conceptId,
            Map<UUID, List<TaxonomyEdge>> childrenMap,
            Set<UUID> visited) {

        if (visited.contains(conceptId)) return null; // cycle guard

        Concept concept = conceptRepo.findById(conceptId).orElse(null);
        if (concept == null) return null;

        Set<UUID> nextVisited = new HashSet<>(visited);
        nextVisited.add(conceptId);
        List<TaxonomyEdge> childEdges = childrenMap.getOrDefault(conceptId, List.of());
        List<TaxonomyTreeResponse.TreeNode> children = childEdges.stream()
                .map(e -> buildTreeNode(e.getChildConcept().getId(), childrenMap, nextVisited))
                .filter(Objects::nonNull)
                .toList();

        return new TaxonomyTreeResponse.TreeNode(
                concept.getId(), concept.getCanonical(),
                concept.getScore(), children
        );
    }

    /* ── Edges ───────────────────────────────────────────── */

    public Page<TaxonomyEdgeResponse> getEdges(UUID taxId, Pageable pageable) {
        return edgeRepo.findByTaxonomyVersionId(taxId, pageable)
                .map(this::toEdgeResponse);
    }

    @Transactional
    public TaxonomyEdgeResponse addEdge(UUID taxId, CreateEdgeRequest req) {
        var version = getVersionEntity(taxId);
        UUID collectionId = version.getCollection().getId();

        var parent = conceptRepo.findById(req.parentConceptId())
                .orElseThrow(() -> new ResourceNotFoundException("Concept", req.parentConceptId()));
        var child = conceptRepo.findById(req.childConceptId())
                .orElseThrow(() -> new ResourceNotFoundException("Concept", req.childConceptId()));

        // ── Cross-collection guard ──
        if (!parent.getCollection().getId().equals(collectionId)) {
            throw new IllegalArgumentException(
                    "Parent concept " + parent.getId() + " belongs to a different collection");
        }
        if (!child.getCollection().getId().equals(collectionId)) {
            throw new IllegalArgumentException(
                    "Child concept " + child.getId() + " belongs to a different collection");
        }

        // ── Self-loop guard ──
        if (req.parentConceptId().equals(req.childConceptId())) {
            throw new IllegalArgumentException("Cannot create a self-referencing edge");
        }

        var edge = new TaxonomyEdge();
        edge.setTaxonomyVersion(version);
        edge.setParentConcept(parent);
        edge.setChildConcept(child);
        edge.setRelation(req.relation() != null ? req.relation() : "is_a");
        edge.setScore(req.score() != null ? req.score() : 1.0);
        edge.setEvidence(List.of(Map.of("source", "manual")));
        edge.setApproved(true);
        edge = edgeRepo.save(edge);
        return toEdgeResponse(edge);
    }

    @Transactional
    public void deleteEdge(UUID taxId, UUID edgeId) {
        var edge = edgeRepo.findById(edgeId)
                .orElseThrow(() -> new ResourceNotFoundException("TaxonomyEdge", edgeId));
        if (!edge.getTaxonomyVersion().getId().equals(taxId)) {
            throw new IllegalArgumentException("Edge does not belong to this taxonomy version");
        }
        edgeRepo.delete(edge);
    }

    @Transactional
    public TaxonomyEdgeResponse updateEdge(UUID taxId, UUID edgeId, UpdateEdgeRequest req) {
        var edge = edgeRepo.findById(edgeId)
                .orElseThrow(() -> new ResourceNotFoundException("TaxonomyEdge", edgeId));
        if (!edge.getTaxonomyVersion().getId().equals(taxId)) {
            throw new IllegalArgumentException("Edge does not belong to this taxonomy version");
        }
        if (req.score() != null) {
            edge.setScore(req.score());
        }
        if (req.approved() != null) {
            edge.setApproved(req.approved());
            List<Map<String, Object>> ev = new ArrayList<>(edge.getEvidence());
            ev.add(Map.of("approved", req.approved(), "ts", System.currentTimeMillis()));
            edge.setEvidence(ev);
        }
        edge = edgeRepo.save(edge);
        return toEdgeResponse(edge);
    }

    /* ── Concepts search & detail ────────────────────────── */

    public Page<ConceptResponse> searchConcepts(UUID taxId, String query, Pageable pageable) {
        var version = getVersionEntity(taxId);
        return conceptRepo.searchByCanonical(version.getCollection().getId(), query, pageable)
                .map(this::toConceptResponse);
    }

    public ConceptDetailResponse getConceptDetail(UUID taxId, UUID conceptId) {
        var version = getVersionEntity(taxId);
        var concept = conceptRepo.findById(conceptId)
                .orElseThrow(() -> new ResourceNotFoundException("Concept", conceptId));
        if (!concept.getCollection().getId().equals(version.getCollection().getId())) {
            throw new IllegalArgumentException("Concept does not belong to this taxonomy collection");
        }

        // Parents: edges where this concept is the child
        var parentEdges = edgeRepo.findByTaxonomyVersionIdAndChildConceptId(taxId, conceptId);
        var parents = parentEdges.stream()
                .map(e -> new ConceptDetailResponse.RelatedConcept(
                        e.getParentConcept().getId(),
                        e.getParentConcept().getCanonical(),
                        e.getScore()))
                .toList();

        // Children: edges where this concept is the parent
        var childEdges = edgeRepo.findByTaxonomyVersionIdAndParentConceptId(taxId, conceptId);
        var children = childEdges.stream()
                .map(e -> new ConceptDetailResponse.RelatedConcept(
                        e.getChildConcept().getId(),
                        e.getChildConcept().getCanonical(),
                        e.getScore()))
                .toList();

        // Occurrences (evidence)
        var occurrences = occurrenceRepo.findByConceptId(conceptId).stream()
                .map(o -> new ConceptDetailResponse.OccurrenceInfo(
                        o.getChunk().getId(),
                        o.getChunk().getDocument().getId(),
                        o.getSnippet(),
                        o.getConfidence()))
                .toList();

        return new ConceptDetailResponse(
                concept.getId(), concept.getCanonical(),
                concept.getSurfaceForms(), concept.getLang(),
                concept.getScore(), parents, children, occurrences
        );
    }

    /* ── Export ───────────────────────────────────────────── */

    public TaxonomyExportResponse export(UUID taxId) {
        return export(taxId, false);
    }

    public TaxonomyExportResponse export(UUID taxId, boolean includeOrphans) {
        var version = getVersionEntity(taxId);
        var edges = edgeRepo.findByTaxonomyVersionId(taxId);

        // Collect all concept IDs
        Set<UUID> conceptIds = new HashSet<>();
        for (var e : edges) {
            conceptIds.add(e.getParentConcept().getId());
            conceptIds.add(e.getChildConcept().getId());
        }
        if (includeOrphans) {
            conceptRepo.findByCollectionId(version.getCollection().getId())
                    .forEach(c -> conceptIds.add(c.getId()));
        }

        List<TaxonomyExportResponse.ExportNode> nodes = conceptIds.stream()
                .map(id -> conceptRepo.findById(id).orElse(null))
                .filter(Objects::nonNull)
                .map(c -> new TaxonomyExportResponse.ExportNode(c.getId(), c.getCanonical()))
                .toList();

        List<TaxonomyExportResponse.ExportEdge> edgeDtos = edges.stream()
                .map(e -> new TaxonomyExportResponse.ExportEdge(
                        e.getParentConcept().getId(),
                        e.getChildConcept().getId(),
                        e.getScore(),
                        e.getEvidence()))
                .toList();

        return new TaxonomyExportResponse(
                taxId, version.getCollection().getId(),
                version.getAlgorithm(), version.getParameters(),
                version.getQualityMetrics(),
                nodes, edgeDtos
        );
    }

    /* ── CSV export ──────────────────────────────────────── */

    public String exportCsv(UUID taxId) {
        var edges = edgeRepo.findByTaxonomyVersionId(taxId);
        var sb = new StringBuilder();
        sb.append("parent_id,parent_label,child_id,child_label,relation,score\n");
        for (var e : edges) {
            sb.append(csvEscape(e.getParentConcept().getId().toString())).append(',');
            sb.append(csvEscape(e.getParentConcept().getCanonical())).append(',');
            sb.append(csvEscape(e.getChildConcept().getId().toString())).append(',');
            sb.append(csvEscape(e.getChildConcept().getCanonical())).append(',');
            sb.append(csvEscape(e.getRelation())).append(',');
            sb.append(e.getScore()).append('\n');
        }
        return sb.toString();
    }

    /* ── Helpers ──────────────────────────────────────────── */

    private TaxonomyVersion getVersionEntity(UUID taxId) {
        return taxVersionRepo.findById(taxId)
                .orElseThrow(() -> new ResourceNotFoundException("TaxonomyVersion", taxId));
    }

    private TaxonomyVersionResponse toVersionResponse(TaxonomyVersion v) {
        long edgeCount = edgeRepo.countByTaxonomyVersionId(v.getId());
        long conceptCount = conceptRepo.countByCollectionId(v.getCollection().getId());
        return new TaxonomyVersionResponse(
                v.getId(), v.getCollection().getId(),
                v.getAlgorithm(), v.getParameters(),
                v.getQualityMetrics(),
                v.getStatus().name(),
                v.getCreatedAt(), v.getFinishedAt(),
                edgeCount, conceptCount
        );
    }

    private TaxonomyEdgeResponse toEdgeResponse(TaxonomyEdge e) {
        return new TaxonomyEdgeResponse(
                e.getId(),
                e.getParentConcept().getId(),
                e.getParentConcept().getCanonical(),
                e.getChildConcept().getId(),
                e.getChildConcept().getCanonical(),
                e.getRelation(), e.getScore(), e.getEvidence()
        );
    }

    private ConceptResponse toConceptResponse(Concept c) {
        return new ConceptResponse(
                c.getId(), c.getCanonical(),
                c.getSurfaceForms(), c.getLang(), c.getScore()
        );
    }

    private String csvEscape(String value) {
        if (value == null) return "";
        if (value.contains(",") || value.contains("\"") || value.contains("\n")) {
            return "\"" + value.replace("\"", "\"\"") + "\"";
        }
        return value;
    }
}
