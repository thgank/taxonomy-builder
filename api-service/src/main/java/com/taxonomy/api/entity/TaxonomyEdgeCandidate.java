package com.taxonomy.api.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

@Entity
@Table(name = "taxonomy_edge_candidates")
@Getter
@Setter
@NoArgsConstructor
public class TaxonomyEdgeCandidate {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "taxonomy_version_id", nullable = false)
    private TaxonomyVersion taxonomyVersion;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "collection_id", nullable = false)
    private Collection collection;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "parent_concept_id")
    private Concept parentConcept;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "child_concept_id")
    private Concept childConcept;

    @Column(name = "parent_label", nullable = false, columnDefinition = "TEXT")
    private String parentLabel;

    @Column(name = "child_label", nullable = false, columnDefinition = "TEXT")
    private String childLabel;

    @Column(length = 10)
    private String lang;

    @Column(nullable = false, length = 64)
    private String method = "unknown";

    @Column(nullable = false, length = 32)
    private String stage = "build";

    @Column(name = "base_score", nullable = false)
    private Double baseScore = 0.0;

    @Column(name = "ranker_score")
    private Double rankerScore;

    @Column(name = "evidence_score")
    private Double evidenceScore;

    @Column(name = "final_score", nullable = false)
    private Double finalScore = 0.0;

    @Column(nullable = false, length = 16)
    private String decision = "pending";

    @Column(name = "risk_score", nullable = false)
    private Double riskScore = 0.0;

    @Column(name = "rejection_reason", columnDefinition = "TEXT")
    private String rejectionReason;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "feature_vector", columnDefinition = "jsonb")
    private Map<String, Object> featureVector = new HashMap<>();

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(columnDefinition = "jsonb")
    private Map<String, Object> evidence = new HashMap<>();

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private Instant createdAt;
}
