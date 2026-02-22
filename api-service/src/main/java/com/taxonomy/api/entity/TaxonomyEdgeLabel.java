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
@Table(name = "taxonomy_edge_labels")
@Getter
@Setter
@NoArgsConstructor
public class TaxonomyEdgeLabel {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "candidate_id")
    private TaxonomyEdgeCandidate candidate;

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

    @Column(nullable = false, length = 16)
    private String label;

    @Column(name = "label_source", nullable = false, length = 32)
    private String labelSource = "manual";

    @Column(name = "reviewer_id", length = 64)
    private String reviewerId;

    @Column(columnDefinition = "TEXT")
    private String reason;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(columnDefinition = "jsonb")
    private Map<String, Object> meta = new HashMap<>();

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private Instant createdAt;
}
