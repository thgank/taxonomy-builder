package com.taxonomy.api.controller;

import com.taxonomy.api.dto.request.CreateEdgeRequest;
import com.taxonomy.api.dto.request.CreateEdgeLabelRequest;
import com.taxonomy.api.dto.request.CreateReleaseRequest;
import com.taxonomy.api.dto.request.PromoteReleaseRequest;
import com.taxonomy.api.dto.request.RollbackReleaseRequest;
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

    @GetMapping("/api/taxonomies/{taxId:[0-9a-fA-F\\-]{36}}")
    @Operation(summary = "Get taxonomy version metadata")
    public TaxonomyVersionResponse getVersion(@PathVariable UUID taxId) {
        return taxonomyService.findVersionById(taxId);
    }

    /* ── Tree ────────────────────────────────────────────── */

    @GetMapping("/api/taxonomies/{taxId:[0-9a-fA-F\\-]{36}}/tree")
    @Operation(summary = "Get taxonomy as a tree (root nodes + children)")
    public TaxonomyTreeResponse getTree(@PathVariable UUID taxId) {
        return taxonomyService.getTree(taxId);
    }

    /* ── Edges ───────────────────────────────────────────── */

    @GetMapping("/api/taxonomies/{taxId:[0-9a-fA-F\\-]{36}}/edges")
    @Operation(summary = "List taxonomy edges (paginated)")
    public Page<TaxonomyEdgeResponse> getEdges(@PathVariable UUID taxId, Pageable pageable) {
        return taxonomyService.getEdges(taxId, pageable);
    }

    @PostMapping("/api/taxonomies/{taxId:[0-9a-fA-F\\-]{36}}/edges")
    @ResponseStatus(HttpStatus.CREATED)
    @Operation(summary = "Add an edge manually (semi-automatic)")
    public TaxonomyEdgeResponse addEdge(@PathVariable UUID taxId,
                                        @Valid @RequestBody CreateEdgeRequest req) {
        return taxonomyService.addEdge(taxId, req);
    }

    @DeleteMapping("/api/taxonomies/{taxId:[0-9a-fA-F\\-]{36}}/edges/{edgeId:[0-9a-fA-F\\-]{36}}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    @Operation(summary = "Delete an edge")
    public void deleteEdge(@PathVariable UUID taxId, @PathVariable UUID edgeId) {
        taxonomyService.deleteEdge(taxId, edgeId);
    }

    @PatchMapping("/api/taxonomies/{taxId:[0-9a-fA-F\\-]{36}}/edges/{edgeId:[0-9a-fA-F\\-]{36}}")
    @Operation(summary = "Update edge score / approval")
    public TaxonomyEdgeResponse updateEdge(@PathVariable UUID taxId,
                                           @PathVariable UUID edgeId,
                                           @RequestBody UpdateEdgeRequest req) {
        return taxonomyService.updateEdge(taxId, edgeId, req);
    }

    @PostMapping("/api/taxonomies/{taxId:[0-9a-fA-F\\-]{36}}/labels")
    @ResponseStatus(HttpStatus.CREATED)
    @Operation(summary = "Create manual label for candidate edge")
    public TaxonomyEdgeLabelResponse createEdgeLabel(@PathVariable UUID taxId,
                                                     @RequestBody CreateEdgeLabelRequest req) {
        return taxonomyService.createEdgeLabel(taxId, req);
    }

    @GetMapping("/api/taxonomies/{taxId:[0-9a-fA-F\\-]{36}}/labels")
    @Operation(summary = "List edge labels for taxonomy version")
    public Page<TaxonomyEdgeLabelResponse> getEdgeLabels(@PathVariable UUID taxId, Pageable pageable) {
        return taxonomyService.getEdgeLabels(taxId, pageable);
    }

    /* ── Concepts ────────────────────────────────────────── */

    @GetMapping("/api/taxonomies/{taxId:[0-9a-fA-F\\-]{36}}/concepts/search")
    @Operation(summary = "Search concepts by canonical name")
    public Page<ConceptResponse> searchConcepts(
            @PathVariable UUID taxId,
            @RequestParam("q") String query,
            Pageable pageable) {
        return taxonomyService.searchConcepts(taxId, query, pageable);
    }

    @GetMapping("/api/taxonomies/{taxId:[0-9a-fA-F\\-]{36}}/concepts/{conceptId:[0-9a-fA-F\\-]{36}}")
    @Operation(summary = "Get concept detail with parents, children, evidence")
    public ConceptDetailResponse getConceptDetail(
            @PathVariable UUID taxId,
            @PathVariable UUID conceptId) {
        return taxonomyService.getConceptDetail(taxId, conceptId);
    }

    /* ── Export ───────────────────────────────────────────── */

    @GetMapping("/api/taxonomies/{taxId:[0-9a-fA-F\\-]{36}}/export")
    @Operation(summary = "Export taxonomy as JSON or CSV")
    public ResponseEntity<?> export(
            @PathVariable UUID taxId,
            @RequestParam(value = "format", defaultValue = "json") String format,
            @RequestParam(value = "include_orphans", defaultValue = "false") boolean includeOrphans) {

        if ("csv".equalsIgnoreCase(format)) {
            String csv = taxonomyService.exportCsv(taxId);
            return ResponseEntity.ok()
                    .header(HttpHeaders.CONTENT_DISPOSITION,
                            "attachment; filename=taxonomy_" + taxId + ".csv")
                    .contentType(MediaType.parseMediaType("text/csv"))
                    .body(csv);
        }

        return ResponseEntity.ok(taxonomyService.export(taxId, includeOrphans));
    }

    /* ── Releases / Canary / Rollback ──────────────────── */

    @GetMapping("/api/collections/{id}/releases")
    @Operation(summary = "List taxonomy releases for collection")
    public List<TaxonomyReleaseResponse> listReleases(@PathVariable UUID id) {
        return taxonomyService.listReleases(id);
    }

    @PostMapping("/api/collections/{id}/releases")
    @ResponseStatus(HttpStatus.CREATED)
    @Operation(summary = "Create release from taxonomy version")
    public TaxonomyReleaseResponse createRelease(@PathVariable UUID id,
                                                 @RequestBody CreateReleaseRequest req) {
        return taxonomyService.createRelease(id, req);
    }

    @PostMapping("/api/collections/{id}/releases/{releaseId:[0-9a-fA-F\\-]{36}}/promote")
    @Operation(summary = "Promote release to active/canary channel")
    public TaxonomyReleaseResponse promoteRelease(@PathVariable UUID id,
                                                  @PathVariable UUID releaseId,
                                                  @RequestBody(required = false) PromoteReleaseRequest req) {
        PromoteReleaseRequest payload = req != null ? req : new PromoteReleaseRequest("active", 100, null);
        return taxonomyService.promoteRelease(id, releaseId, payload);
    }

    @PostMapping("/api/collections/{id}/releases/{releaseId:[0-9a-fA-F\\-]{36}}/rollback")
    @Operation(summary = "Rollback channel to previously known release")
    public TaxonomyReleaseResponse rollbackRelease(@PathVariable UUID id,
                                                   @PathVariable UUID releaseId,
                                                   @RequestBody RollbackReleaseRequest req) {
        return taxonomyService.rollbackRelease(id, releaseId, req);
    }
}
