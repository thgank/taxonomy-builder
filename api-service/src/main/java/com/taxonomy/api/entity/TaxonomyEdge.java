package com.taxonomy.api.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Entity
@Table(name = "taxonomy_edges")
@Getter @Setter
@NoArgsConstructor
public class TaxonomyEdge {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "taxonomy_version_id", nullable = false)
    private TaxonomyVersion taxonomyVersion;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "parent_concept_id", nullable = false)
    private Concept parentConcept;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "child_concept_id", nullable = false)
    private Concept childConcept;

    @Column(nullable = false, length = 32)
    private String relation = "is_a";

    @Column(nullable = false)
    private Double score = 0.0;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(columnDefinition = "jsonb")
    private List<Map<String, Object>> evidence = new ArrayList<>();

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private Instant createdAt;

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof TaxonomyEdge te)) return false;
        return id != null && id.equals(te.getId());
    }

    @Override
    public int hashCode() {
        return getClass().hashCode();
    }
}
