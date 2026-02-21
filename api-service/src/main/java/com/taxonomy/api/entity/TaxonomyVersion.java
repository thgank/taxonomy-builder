package com.taxonomy.api.entity;

import com.taxonomy.api.entity.enums.TaxonomyStatus;
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
@Table(name = "taxonomy_versions")
@Getter @Setter
@NoArgsConstructor
public class TaxonomyVersion {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "collection_id", nullable = false)
    private Collection collection;

    @Column(nullable = false, length = 64)
    private String algorithm = "hybrid";

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(columnDefinition = "jsonb")
    private Map<String, Object> parameters = new HashMap<>();

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private TaxonomyStatus status = TaxonomyStatus.NEW;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "quality_metrics", columnDefinition = "jsonb")
    private Map<String, Object> qualityMetrics = new HashMap<>();

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private Instant createdAt;

    @Column(name = "finished_at")
    private Instant finishedAt;

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof TaxonomyVersion tv)) return false;
        return id != null && id.equals(tv.getId());
    }

    @Override
    public int hashCode() {
        return getClass().hashCode();
    }
}
