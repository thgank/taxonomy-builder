package com.taxonomy.api.entity;

import com.taxonomy.api.entity.enums.DocumentStatus;
import com.taxonomy.api.entity.enums.JobStatus;
import com.taxonomy.api.entity.enums.JobType;
import com.taxonomy.api.entity.enums.TaxonomyStatus;
import org.junit.jupiter.api.Test;

import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

class EntityCoverageTest {

    @Test
    void equalityContracts_useIdentifierSemantics() {
        assertEntityEquality(new Collection("Energy", "Docs"), new Collection("Energy", "Docs"));
        assertEntityEquality(new Document(), new Document());
        assertEntityEquality(new Job(), new Job());
        assertEntityEquality(new Concept(), new Concept());
        assertEntityEquality(new ConceptOccurrence(), new ConceptOccurrence());
        assertEntityEquality(new DocumentChunk(), new DocumentChunk());
        assertEntityEquality(new JobEvent(), new JobEvent());
        assertEntityEquality(new TaxonomyEdge(), new TaxonomyEdge());
        assertEntityEquality(new TaxonomyVersion(), new TaxonomyVersion());
    }

    @Test
    void entities_exposeExpectedDefaults() {
        Document document = new Document();
        assertEquals(DocumentStatus.NEW, document.getStatus());

        Job job = new Job();
        assertEquals(JobStatus.QUEUED, job.getStatus());
        assertEquals(0, job.getProgress());
        assertEquals(0, job.getRetryCount());
        job.setType(JobType.EVALUATE);
        assertEquals(JobType.EVALUATE, job.getType());

        Concept concept = new Concept();
        assertTrue(concept.getSurfaceForms().isEmpty());
        assertEquals(0.0, concept.getScore());

        ConceptOccurrence occurrence = new ConceptOccurrence();
        assertEquals(0.0, occurrence.getConfidence());

        TaxonomyVersion version = new TaxonomyVersion();
        assertEquals("hybrid", version.getAlgorithm());
        assertEquals(TaxonomyStatus.NEW, version.getStatus());
        assertTrue(version.getParameters().isEmpty());
        assertTrue(version.getQualityMetrics().isEmpty());

        TaxonomyEdge edge = new TaxonomyEdge();
        assertEquals("is_a", edge.getRelation());
        assertEquals(0.0, edge.getScore());
        assertTrue(edge.getEvidence().isEmpty());

        TaxonomyEdgeCandidate candidate = new TaxonomyEdgeCandidate();
        assertEquals("unknown", candidate.getMethod());
        assertEquals("build", candidate.getStage());
        assertEquals("pending", candidate.getDecision());
        assertEquals(0.0, candidate.getBaseScore());
        assertEquals(0.0, candidate.getFinalScore());
        assertEquals(0.0, candidate.getRiskScore());
        assertTrue(candidate.getFeatureVector().isEmpty());
        assertTrue(candidate.getEvidence().isEmpty());

        TaxonomyEdgeLabel label = new TaxonomyEdgeLabel();
        assertEquals("manual", label.getLabelSource());
        assertTrue(label.getMeta().isEmpty());

        TaxonomyRelease release = new TaxonomyRelease();
        assertEquals("active", release.getChannel());
        assertEquals(100, release.getTrafficPercent());
        assertTrue(release.getIsActive());
        assertTrue(release.getQualitySnapshot().isEmpty());

        TaxonomyThresholdProfile profile = new TaxonomyThresholdProfile();
        assertFalse(profile.getIsActive());
        assertEquals(50, profile.getMinSamples());
        assertTrue(profile.getProfile().isEmpty());
        assertTrue(profile.getMetrics().isEmpty());

        JobEvent event = new JobEvent(job, "WARN", "something happened");
        assertSame(job, event.getJob());
        assertEquals("WARN", event.getLevel());
        assertEquals("something happened", event.getMessage());
        assertTrue(event.getMeta().isEmpty());

        version.setParameters(Map.of("method_taxonomy", "hybrid"));
        assertEquals("hybrid", version.getParameters().get("method_taxonomy"));
    }

    private static void assertEntityEquality(Object left, Object right) {
        UUID id = UUID.randomUUID();
        setId(left, id);
        setId(right, id);

        assertEquals(left, right);
        assertEquals(left.getClass().hashCode(), left.hashCode());

        setId(right, UUID.randomUUID());
        assertNotEquals(left, right);
        setId(left, null);
        assertNotEquals(left, right);
    }

    private static void setId(Object entity, UUID id) {
        switch (entity) {
            case Collection value -> value.setId(id);
            case Document value -> value.setId(id);
            case Job value -> value.setId(id);
            case Concept value -> value.setId(id);
            case ConceptOccurrence value -> value.setId(id);
            case DocumentChunk value -> value.setId(id);
            case JobEvent value -> value.setId(id);
            case TaxonomyEdge value -> value.setId(id);
            case TaxonomyVersion value -> value.setId(id);
            default -> throw new IllegalArgumentException("Unsupported entity: " + entity.getClass());
        }
    }
}
