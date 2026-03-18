package com.taxonomy.api.service;

import com.taxonomy.api.dto.request.CreateEdgeLabelRequest;
import com.taxonomy.api.dto.request.CreateEdgeRequest;
import com.taxonomy.api.entity.Collection;
import com.taxonomy.api.entity.Concept;
import com.taxonomy.api.entity.TaxonomyEdge;
import com.taxonomy.api.entity.TaxonomyEdgeCandidate;
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
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
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
    void addEdge_rejectsSelfLoop() {
        var collection = new Collection("Finance", "Docs");
        collection.setId(UUID.randomUUID());

        var version = new TaxonomyVersion();
        version.setId(UUID.randomUUID());
        version.setCollection(collection);
        version.setStatus(TaxonomyStatus.READY);

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
        var targetCollection = new Collection("Finance", "Docs");
        targetCollection.setId(UUID.randomUUID());
        var otherCollection = new Collection("Legal", "Docs");
        otherCollection.setId(UUID.randomUUID());

        var version = new TaxonomyVersion();
        version.setId(UUID.randomUUID());
        version.setCollection(targetCollection);

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
    void createEdgeLabel_normalizesApprovedToAcceptedAndUpdatesCandidate() {
        var collection = new Collection("Finance", "Docs");
        collection.setId(UUID.randomUUID());

        var version = new TaxonomyVersion();
        version.setId(UUID.randomUUID());
        version.setCollection(collection);

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
        verify(edgeCandidateRepo).save(candidate);
    }

    @Test
    void getTree_returnsStandaloneRootsWhenNoEdgesExist() {
        var collection = new Collection("Finance", "Docs");
        collection.setId(UUID.randomUUID());

        var version = new TaxonomyVersion();
        version.setId(UUID.randomUUID());
        version.setCollection(collection);

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

    private static Concept concept(UUID id, Collection collection, String canonical) {
        var concept = new Concept();
        concept.setId(id);
        concept.setCollection(collection);
        concept.setCanonical(canonical);
        concept.setLang("en");
        concept.setScore(1.0);
        return concept;
    }
}
