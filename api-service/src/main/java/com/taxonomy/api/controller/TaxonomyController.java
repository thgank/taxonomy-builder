package com.taxonomy.api.controller;

import com.taxonomy.api.dto.request.CreateEdgeRequest;
import com.taxonomy.api.dto.request.UpdateEdgeRequest;
import com.taxonomy.api.dto.response.*;
import com.taxonomy.api.service.TaxonomyService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@Tag(name = "Taxonomies", description = "Taxonomy versions, edges, concepts, export")
public class TaxonomyController {

    private final TaxonomyService taxonomyService;

    public TaxonomyController(TaxonomyService taxonomyService) {
        this.taxonomyService = taxonomyService;
    }

    /* ── Versions ────────────────────────────────────────── */

    @GetMapping("/api/collections/{id}/taxonomies")
    @Operation(summary = "List taxonomy versions for a collection")
    public List<TaxonomyVersionResponse> listVersions(@PathVariable UUID id) {
        return taxonomyService.findVersionsByCollection(id);
    }

    @GetMapping("/api/taxonomies/{taxId}")
    @Operation(summary = "Get taxonomy version metadata")
    public TaxonomyVersionResponse getVersion(@PathVariable UUID taxId) {
        return taxonomyService.findVersionById(taxId);
    }

    /* ── Tree ────────────────────────────────────────────── */

    @GetMapping("/api/taxonomies/{taxId}/tree")
    @Operation(summary = "Get taxonomy as a tree (root nodes + children)")
    public TaxonomyTreeResponse getTree(@PathVariable UUID taxId) {
        return taxonomyService.getTree(taxId);
    }

    /* ── Edges ───────────────────────────────────────────── */

    @GetMapping("/api/taxonomies/{taxId}/edges")
    @Operation(summary = "List taxonomy edges (paginated)")
    public Page<TaxonomyEdgeResponse> getEdges(@PathVariable UUID taxId, Pageable pageable) {
        return taxonomyService.getEdges(taxId, pageable);
    }

    @PostMapping("/api/taxonomies/{taxId}/edges")
    @ResponseStatus(HttpStatus.CREATED)
    @Operation(summary = "Add an edge manually (semi-automatic)")
    public TaxonomyEdgeResponse addEdge(@PathVariable UUID taxId,
                                        @Valid @RequestBody CreateEdgeRequest req) {
        return taxonomyService.addEdge(taxId, req);
    }

    @DeleteMapping("/api/taxonomies/{taxId}/edges/{edgeId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    @Operation(summary = "Delete an edge")
    public void deleteEdge(@PathVariable UUID taxId, @PathVariable UUID edgeId) {
        taxonomyService.deleteEdge(taxId, edgeId);
    }

    @PatchMapping("/api/taxonomies/{taxId}/edges/{edgeId}")
    @Operation(summary = "Update edge score / approval")
    public TaxonomyEdgeResponse updateEdge(@PathVariable UUID taxId,
                                           @PathVariable UUID edgeId,
                                           @RequestBody UpdateEdgeRequest req) {
        return taxonomyService.updateEdge(taxId, edgeId, req);
    }

    /* ── Concepts ────────────────────────────────────────── */

    @GetMapping("/api/taxonomies/{taxId}/concepts/search")
    @Operation(summary = "Search concepts by canonical name")
    public Page<ConceptResponse> searchConcepts(
            @PathVariable UUID taxId,
            @RequestParam("q") String query,
            Pageable pageable) {
        return taxonomyService.searchConcepts(taxId, query, pageable);
    }

    @GetMapping("/api/taxonomies/{taxId}/concepts/{conceptId}")
    @Operation(summary = "Get concept detail with parents, children, evidence")
    public ConceptDetailResponse getConceptDetail(
            @PathVariable UUID taxId,
            @PathVariable UUID conceptId) {
        return taxonomyService.getConceptDetail(taxId, conceptId);
    }

    /* ── Export ───────────────────────────────────────────── */

    @GetMapping({"/api/taxonomies/{taxId}/export", "/api/taxonomies/{taxId}:export"})
    @Operation(summary = "Export taxonomy as JSON or CSV")
    public ResponseEntity<?> export(
            @PathVariable UUID taxId,
            @RequestParam(value = "format", defaultValue = "json") String format) {

        if ("csv".equalsIgnoreCase(format)) {
            String csv = taxonomyService.exportCsv(taxId);
            return ResponseEntity.ok()
                    .header(HttpHeaders.CONTENT_DISPOSITION,
                            "attachment; filename=taxonomy_" + taxId + ".csv")
                    .contentType(MediaType.parseMediaType("text/csv"))
                    .body(csv);
        }

        return ResponseEntity.ok(taxonomyService.export(taxId));
    }
}
