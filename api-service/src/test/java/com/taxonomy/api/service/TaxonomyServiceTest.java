package com.taxonomy.api.service;

import com.taxonomy.api.dto.request.CreateEdgeLabelRequest;
import com.taxonomy.api.dto.request.CreateEdgeRequest;
import com.taxonomy.api.dto.request.CreateReleaseRequest;
import com.taxonomy.api.dto.request.PromoteReleaseRequest;
import com.taxonomy.api.dto.request.RollbackReleaseRequest;
import com.taxonomy.api.dto.request.UpdateEdgeRequest;
import com.taxonomy.api.entity.Collection;
import com.taxonomy.api.entity.Concept;
import com.taxonomy.api.entity.ConceptOccurrence;
import com.taxonomy.api.entity.Document;
import com.taxonomy.api.entity.DocumentChunk;
import com.taxonomy.api.entity.TaxonomyEdge;
import com.taxonomy.api.entity.TaxonomyEdgeCandidate;
import com.taxonomy.api.entity.TaxonomyRelease;
import com.taxonomy.api.entity.TaxonomyVersion;
import com.taxonomy.api.entity.enums.TaxonomyStatus;
import com.taxonomy.api.repository.ConceptOccurrenceRepository;
import com.taxonomy.api.repository.ConceptRepository;
import com.taxonomy.api.repository.TaxonomyEdgeCandidateRepository;
import com.taxonomy.api.repository.TaxonomyEdgeLabelRepository;
import com.taxonomy.api.repository.TaxonomyEdgeRepository;
import com.taxonomy.api.repository.TaxonomyReleaseRepository;
import com.taxonomy.api.repository.TaxonomyVersionRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.atLeastOnce;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class TaxonomyServiceTest {

    @Mock private TaxonomyVersionRepository taxVersionRepo;
    @Mock private TaxonomyEdgeRepository edgeRepo;
    @Mock private TaxonomyEdgeCandidateRepository edgeCandidateRepo;
    @Mock private TaxonomyEdgeLabelRepository edgeLabelRepo;
    @Mock private TaxonomyReleaseRepository releaseRepo;
    @Mock private ConceptRepository conceptRepo;
    @Mock private ConceptOccurrenceRepository occurrenceRepo;

    private TaxonomyService taxonomyService;

    @BeforeEach
    void setUp() {
        taxonomyService = new TaxonomyService(
                taxVersionRepo,
                edgeRepo,
                edgeCandidateRepo,
                edgeLabelRepo,
                releaseRepo,
                conceptRepo,
                occurrenceRepo
        );
    }

    @Test
    void findVersionsByCollection_mapsCountsAndMetadata() {
        var collection = collection("Finance");
        var version = version(collection);
        version.setAlgorithm("hybrid");
        version.setParameters(Map.of("maxDepth", 4));
        version.setQualityMetrics(Map.of("coverage", 0.91));
        version.setStatus(TaxonomyStatus.READY);
        version.setCreatedAt(Instant.parse("2026-03-30T10:00:00Z"));

        when(taxVersionRepo.findByCollectionIdOrderByCreatedAtDesc(collection.getId())).thenReturn(List.of(version));
        when(edgeRepo.countByTaxonomyVersionId(version.getId())).thenReturn(5L);
        when(conceptRepo.countByCollectionId(collection.getId())).thenReturn(8L);

        var response = taxonomyService.findVersionsByCollection(collection.getId());

        assertEquals(1, response.size());
        assertEquals(version.getId(), response.getFirst().id());
        assertEquals("READY", response.getFirst().status());
        assertEquals(5L, response.getFirst().edgeCount());
        assertEquals(8L, response.getFirst().conceptCount());
    }

    @Test
    void getTree_returnsStandaloneRootsWhenNoEdgesExist() {
        var collection = collection("Finance");
        var version = version(collection);
        var bank = concept(UUID.randomUUID(), collection, "bank");
        bank.setScore(0.9);
        var insurance = concept(UUID.randomUUID(), collection, "insurance");
        insurance.setScore(0.8);

        when(taxVersionRepo.findById(version.getId())).thenReturn(Optional.of(version));
        when(edgeRepo.findRootConceptIds(version.getId())).thenReturn(List.of());
        when(conceptRepo.findByCollectionId(collection.getId())).thenReturn(List.of(bank, insurance));

        var tree = taxonomyService.getTree(version.getId());

        assertEquals(version.getId(), tree.taxonomyVersionId());
        assertEquals(2, tree.roots().size());
        assertEquals(List.of(), tree.roots().getFirst().children());
    }

    @Test
    void getTree_buildsNestedChildrenAndStopsOnCycles() {
        var collection = collection("Energy");
        var version = version(collection);
        var root = concept(UUID.randomUUID(), collection, "energy");
        var child = concept(UUID.randomUUID(), collection, "battery storage");

        when(taxVersionRepo.findById(version.getId())).thenReturn(Optional.of(version));
        when(edgeRepo.findRootConceptIds(version.getId())).thenReturn(List.of(root.getId()));
        when(edgeRepo.findByTaxonomyVersionId(version.getId())).thenReturn(List.of(
                edge(version, root, child, 0.9, "is_a"),
                edge(version, child, root, 0.4, "is_a")
        ));
        when(conceptRepo.findById(root.getId())).thenReturn(Optional.of(root));
        when(conceptRepo.findById(child.getId())).thenReturn(Optional.of(child));

        var tree = taxonomyService.getTree(version.getId());

        assertEquals(1, tree.roots().size());
        assertEquals("energy", tree.roots().getFirst().label());
        assertEquals(1, tree.roots().getFirst().children().size());
        assertEquals("battery storage", tree.roots().getFirst().children().getFirst().label());
    }

    @Test
    void addEdge_createsManualApprovedEdgeWithDefaults() {
        var collection = collection("Finance");
        var version = version(collection);
        var parent = concept(UUID.randomUUID(), collection, "bank");
        var child = concept(UUID.randomUUID(), collection, "commercial bank");

        when(taxVersionRepo.findById(version.getId())).thenReturn(Optional.of(version));
        when(conceptRepo.findById(parent.getId())).thenReturn(Optional.of(parent));
        when(conceptRepo.findById(child.getId())).thenReturn(Optional.of(child));
        when(edgeRepo.save(any(TaxonomyEdge.class))).thenAnswer(invocation -> {
            var saved = invocation.getArgument(0, TaxonomyEdge.class);
            saved.setId(UUID.randomUUID());
            return saved;
        });

        var response = taxonomyService.addEdge(
                version.getId(),
                new CreateEdgeRequest(parent.getId(), child.getId(), null, null)
        );

        assertEquals(parent.getId(), response.parentConceptId());
        assertEquals(child.getId(), response.childConceptId());
        assertEquals("is_a", response.relation());
        assertEquals(1.0, response.score());
        assertEquals("manual", response.evidence().getFirst().get("source"));
    }

    @Test
    void addEdge_rejectsSelfLoop() {
        var collection = collection("Finance");
        var version = version(collection);
        var concept = concept(UUID.randomUUID(), collection, "bank");

        when(taxVersionRepo.findById(version.getId())).thenReturn(Optional.of(version));
        when(conceptRepo.findById(concept.getId())).thenReturn(Optional.of(concept));

        assertThrows(IllegalArgumentException.class, () -> taxonomyService.addEdge(
                version.getId(),
                new CreateEdgeRequest(concept.getId(), concept.getId(), null, null)
        ));
    }

    @Test
    void addEdge_rejectsCrossCollectionParent() {
        var targetCollection = collection("Finance");
        var otherCollection = collection("Legal");
        var version = version(targetCollection);
        var parent = concept(UUID.randomUUID(), otherCollection, "bank");
        var child = concept(UUID.randomUUID(), targetCollection, "commercial bank");

        when(taxVersionRepo.findById(version.getId())).thenReturn(Optional.of(version));
        when(conceptRepo.findById(parent.getId())).thenReturn(Optional.of(parent));
        when(conceptRepo.findById(child.getId())).thenReturn(Optional.of(child));

        assertThrows(IllegalArgumentException.class, () -> taxonomyService.addEdge(
                version.getId(),
                new CreateEdgeRequest(parent.getId(), child.getId(), null, null)
        ));
    }

    @Test
    void updateAndDeleteEdge_validateOwnershipAndAppendApprovalEvidence() {
        var collection = collection("Finance");
        var version = version(collection);
        var otherVersion = version(collection);
        var parent = concept(UUID.randomUUID(), collection, "bank");
        var child = concept(UUID.randomUUID(), collection, "credit union");
        var edge = edge(version, parent, child, 0.7, "is_a");
        edge.setId(UUID.randomUUID());
        edge.setEvidence(List.of(Map.of("source", "bootstrap")));
        edge.setApproved(false);

        when(edgeRepo.findById(edge.getId())).thenReturn(Optional.of(edge));
        when(edgeRepo.save(any(TaxonomyEdge.class))).thenAnswer(invocation -> invocation.getArgument(0, TaxonomyEdge.class));

        var updated = taxonomyService.updateEdge(version.getId(), edge.getId(), new UpdateEdgeRequest(0.93, true));

        assertEquals(0.93, updated.score());
        assertEquals(2, updated.evidence().size());
        assertEquals(true, updated.evidence().getLast().get("approved"));

        assertThrows(
                IllegalArgumentException.class,
                () -> taxonomyService.deleteEdge(otherVersion.getId(), edge.getId())
        );

        taxonomyService.deleteEdge(version.getId(), edge.getId());
        verify(edgeRepo).delete(edge);
    }

    @Test
    void createEdgeLabel_normalizesApprovedToAcceptedAndUpdatesCandidate() {
        var collection = collection("Finance");
        var version = version(collection);
        var parent = concept(UUID.randomUUID(), collection, "bank");
        var child = concept(UUID.randomUUID(), collection, "commercial bank");

        var candidate = new TaxonomyEdgeCandidate();
        candidate.setId(UUID.randomUUID());
        candidate.setTaxonomyVersion(version);
        candidate.setCollection(collection);
        candidate.setParentConcept(parent);
        candidate.setChildConcept(child);
        candidate.setParentLabel("bank");
        candidate.setChildLabel("commercial bank");

        when(taxVersionRepo.findById(version.getId())).thenReturn(Optional.of(version));
        when(edgeCandidateRepo.findById(candidate.getId())).thenReturn(Optional.of(candidate));
        when(edgeLabelRepo.save(any())).thenAnswer(invocation -> {
            var row = invocation.getArgument(0, com.taxonomy.api.entity.TaxonomyEdgeLabel.class);
            row.setId(UUID.randomUUID());
            return row;
        });

        var response = taxonomyService.createEdgeLabel(
                version.getId(),
                new CreateEdgeLabelRequest(
                        candidate.getId(),
                        null,
                        null,
                        null,
                        null,
                        "approved",
                        null,
                        "qa-user",
                        "confirmed manually",
                        null
                )
        );

        assertEquals("accepted", response.label());
        assertEquals("manual", response.labelSource());
        assertEquals("accepted", candidate.getDecision());
        assertNull(candidate.getRejectionReason());
        verify(edgeCandidateRepo).save(candidate);
    }

    @Test
    void getEdgeLabelsAndSearchConcepts_mapPagedResponses() {
        var collection = collection("Finance");
        var version = version(collection);
        var concept = concept(UUID.randomUUID(), collection, "commercial bank");
        concept.setSurfaceForms(List.of("commercial bank", "bank"));
        var labelRow = new com.taxonomy.api.entity.TaxonomyEdgeLabel();
        labelRow.setId(UUID.randomUUID());
        labelRow.setTaxonomyVersion(version);
        labelRow.setCollection(collection);
        labelRow.setParentConcept(concept);
        labelRow.setChildConcept(concept);
        labelRow.setParentLabel("bank");
        labelRow.setChildLabel("bank");
        labelRow.setLabel("accepted");
        labelRow.setMeta(Map.of("source", "qa"));

        when(taxVersionRepo.findById(version.getId())).thenReturn(Optional.of(version));
        when(edgeLabelRepo.findByTaxonomyVersionId(version.getId(), PageRequest.of(0, 10))).thenReturn(
                new PageImpl<>(List.of(labelRow), PageRequest.of(0, 10), 1)
        );
        when(conceptRepo.searchByCanonical(collection.getId(), "bank", PageRequest.of(0, 10))).thenReturn(
                new PageImpl<>(List.of(concept), PageRequest.of(0, 10), 1)
        );

        var labels = taxonomyService.getEdgeLabels(version.getId(), PageRequest.of(0, 10));
        var concepts = taxonomyService.searchConcepts(version.getId(), "bank", PageRequest.of(0, 10));

        assertEquals(1, labels.getTotalElements());
        assertEquals("accepted", labels.getContent().getFirst().label());
        assertEquals(1, concepts.getTotalElements());
        assertEquals("commercial bank", concepts.getContent().getFirst().canonical());
    }

    @Test
    void createAndPromoteRelease_deactivateExistingChannelRelease() {
        var collection = collection("Finance");
        var version = version(collection);
        version.setQualityMetrics(Map.of("f1", 0.88));
        var activeExisting = release(collection, version, "release-current", "active", 100);
        activeExisting.setId(UUID.randomUUID());
        activeExisting.setIsActive(true);

        when(taxVersionRepo.findById(version.getId())).thenReturn(Optional.of(version));
        when(releaseRepo.findByCollectionIdAndChannelAndIsActiveTrue(collection.getId(), "active"))
                .thenReturn(Optional.of(activeExisting));
        when(releaseRepo.save(any(TaxonomyRelease.class))).thenAnswer(invocation -> {
            var saved = invocation.getArgument(0, TaxonomyRelease.class);
            if (saved.getId() == null) {
                saved.setId(UUID.randomUUID());
            }
            return saved;
        });

        var created = taxonomyService.createRelease(
                collection.getId(),
                new CreateReleaseRequest(version.getId(), "release-v2", null, null, "baseline ready")
        );

        assertEquals("active", created.channel());
        assertEquals(100, created.trafficPercent());
        assertEquals(Map.of("f1", 0.88), created.qualitySnapshot());
        assertEquals(false, activeExisting.getIsActive());

        var promoteTarget = release(collection, version, "release-canary", "canary", 10);
        promoteTarget.setId(UUID.randomUUID());
        promoteTarget.setNotes("old");
        when(releaseRepo.findById(promoteTarget.getId())).thenReturn(Optional.of(promoteTarget));
        when(releaseRepo.findByCollectionIdAndChannelAndIsActiveTrue(collection.getId(), "canary"))
                .thenReturn(Optional.empty());

        var promoted = taxonomyService.promoteRelease(
                collection.getId(),
                promoteTarget.getId(),
                new PromoteReleaseRequest("canary", 25, "widen traffic")
        );

        assertEquals("canary", promoted.channel());
        assertEquals(25, promoted.trafficPercent());
        assertEquals("widen traffic", promoted.notes());
    }

    @Test
    void rollbackRelease_createsRollbackReleaseFromTargetVersion() {
        var collection = collection("Energy");
        var sourceVersion = version(collection);
        var targetVersion = version(collection);
        targetVersion.setQualityMetrics(Map.of("quality", 0.93));

        var source = release(collection, sourceVersion, "release-2026-03", "active", 100);
        source.setId(UUID.randomUUID());
        var target = release(collection, targetVersion, "release-2026-02", "active", 100);
        target.setId(UUID.randomUUID());
        target.setQualitySnapshot(Map.of("quality", 0.93));
        var currentlyActive = release(collection, sourceVersion, "release-live", "active", 100);
        currentlyActive.setId(UUID.randomUUID());
        currentlyActive.setIsActive(true);

        when(releaseRepo.findById(source.getId())).thenReturn(Optional.of(source));
        when(releaseRepo.findById(target.getId())).thenReturn(Optional.of(target));
        when(releaseRepo.findByCollectionIdAndChannelAndIsActiveTrue(collection.getId(), "active"))
                .thenReturn(Optional.of(currentlyActive));
        when(releaseRepo.save(any(TaxonomyRelease.class))).thenAnswer(invocation -> {
            var saved = invocation.getArgument(0, TaxonomyRelease.class);
            if (saved.getId() == null) {
                saved.setId(UUID.randomUUID());
            }
            return saved;
        });

        var rollback = taxonomyService.rollbackRelease(
                collection.getId(),
                source.getId(),
                new RollbackReleaseRequest(target.getId(), null, "restore stable graph")
        );

        assertEquals("rollback-to-release-2026-02", rollback.releaseName());
        assertEquals(targetVersion.getId(), rollback.taxonomyVersionId());
        assertEquals(source.getId(), rollback.rollbackOf());
        assertEquals("restore stable graph", rollback.notes());
        assertEquals(false, currentlyActive.getIsActive());
    }

    @Test
    void getConceptDetail_mapsParentsChildrenAndOccurrences() {
        var collection = collection("Energy");
        var version = version(collection);
        var parent = concept(UUID.randomUUID(), collection, "energy system");
        var concept = concept(UUID.randomUUID(), collection, "battery storage");
        concept.setSurfaceForms(List.of("battery storage", "storage battery"));
        var child = concept(UUID.randomUUID(), collection, "grid battery storage");

        var chunk = new DocumentChunk();
        chunk.setId(UUID.randomUUID());
        var document = new Document();
        document.setId(UUID.randomUUID());
        chunk.setDocument(document);
        var occurrence = new ConceptOccurrence();
        occurrence.setConcept(concept);
        occurrence.setChunk(chunk);
        occurrence.setSnippet("battery storage improves resilience");
        occurrence.setConfidence(0.87);

        when(taxVersionRepo.findById(version.getId())).thenReturn(Optional.of(version));
        when(conceptRepo.findById(concept.getId())).thenReturn(Optional.of(concept));
        when(edgeRepo.findByTaxonomyVersionIdAndChildConceptId(version.getId(), concept.getId()))
                .thenReturn(List.of(edge(version, parent, concept, 0.91, "is_a")));
        when(edgeRepo.findByTaxonomyVersionIdAndParentConceptId(version.getId(), concept.getId()))
                .thenReturn(List.of(edge(version, concept, child, 0.75, "is_a")));
        when(occurrenceRepo.findByConceptId(concept.getId())).thenReturn(List.of(occurrence));

        var detail = taxonomyService.getConceptDetail(version.getId(), concept.getId());

        assertEquals("battery storage", detail.canonical());
        assertEquals(1, detail.parents().size());
        assertEquals("energy system", detail.parents().getFirst().canonical());
        assertEquals(1, detail.children().size());
        assertEquals("grid battery storage", detail.children().getFirst().canonical());
        assertEquals(1, detail.occurrences().size());
        assertEquals(document.getId(), detail.occurrences().getFirst().documentId());
    }

    @Test
    void exportAndExportCsv_includeOrphansAndEscapedLabels() {
        var collection = collection("Finance");
        var version = version(collection);
        version.setAlgorithm("hybrid");
        version.setParameters(Map.of("minScore", 0.62));
        version.setQualityMetrics(Map.of("lcr", 0.95));
        var parent = concept(UUID.randomUUID(), collection, "bank");
        var child = concept(UUID.randomUUID(), collection, "credit, union");
        var orphan = concept(UUID.randomUUID(), collection, "insurance");
        var edge = edge(version, parent, child, 0.88, "is_a");

        when(taxVersionRepo.findById(version.getId())).thenReturn(Optional.of(version));
        when(edgeRepo.findByTaxonomyVersionId(version.getId())).thenReturn(List.of(edge));
        when(conceptRepo.findByCollectionId(collection.getId())).thenReturn(List.of(parent, child, orphan));
        when(conceptRepo.findById(parent.getId())).thenReturn(Optional.of(parent));
        when(conceptRepo.findById(child.getId())).thenReturn(Optional.of(child));
        when(conceptRepo.findById(orphan.getId())).thenReturn(Optional.of(orphan));

        var export = taxonomyService.export(version.getId(), true);
        var csv = taxonomyService.exportCsv(version.getId());

        assertEquals(3, export.nodes().size());
        assertEquals(1, export.edges().size());
        assertEquals(version.getId(), export.taxonomyVersionId());
        assertEquals(collection.getId(), export.collectionId());
        assertNotNull(csv);
        assertEquals(true, csv.contains("\"credit, union\""));
        assertEquals(true, csv.startsWith("parent_id,parent_label,child_id,child_label,relation,score\n"));
    }

    @Test
    void createRelease_rejectsInvalidTrafficRange() {
        var collection = collection("Finance");
        var version = version(collection);

        when(taxVersionRepo.findById(version.getId())).thenReturn(Optional.of(version));

        assertThrows(
                IllegalArgumentException.class,
                () -> taxonomyService.createRelease(
                        collection.getId(),
                        new CreateReleaseRequest(version.getId(), "release-v2", "canary", 101, null)
                )
        );
    }

    private static Collection collection(String name) {
        var collection = new Collection(name, "Docs");
        collection.setId(UUID.randomUUID());
        return collection;
    }

    private static TaxonomyVersion version(Collection collection) {
        var version = new TaxonomyVersion();
        version.setId(UUID.randomUUID());
        version.setCollection(collection);
        version.setStatus(TaxonomyStatus.READY);
        version.setParameters(Map.of());
        version.setQualityMetrics(Map.of());
        return version;
    }

    private static Concept concept(UUID id, Collection collection, String canonical) {
        var concept = new Concept();
        concept.setId(id);
        concept.setCollection(collection);
        concept.setCanonical(canonical);
        concept.setLang("en");
        concept.setScore(1.0);
        return concept;
    }

    private static TaxonomyEdge edge(TaxonomyVersion version, Concept parent, Concept child, double score, String relation) {
        var edge = new TaxonomyEdge();
        edge.setId(UUID.randomUUID());
        edge.setTaxonomyVersion(version);
        edge.setParentConcept(parent);
        edge.setChildConcept(child);
        edge.setScore(score);
        edge.setRelation(relation);
        edge.setEvidence(List.of(Map.of("method", "manual")));
        return edge;
    }

    private static TaxonomyRelease release(Collection collection, TaxonomyVersion version, String name, String channel, int traffic) {
        var release = new TaxonomyRelease();
        release.setCollection(collection);
        release.setTaxonomyVersion(version);
        release.setReleaseName(name);
        release.setChannel(channel);
        release.setTrafficPercent(traffic);
        release.setIsActive(true);
        release.setQualitySnapshot(Map.of());
        return release;
    }
}
