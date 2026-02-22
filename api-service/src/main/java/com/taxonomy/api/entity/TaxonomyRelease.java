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
@Table(name = "taxonomy_releases")
@Getter
@Setter
@NoArgsConstructor
public class TaxonomyRelease {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "collection_id", nullable = false)
    private Collection collection;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "taxonomy_version_id", nullable = false)
    private TaxonomyVersion taxonomyVersion;

    @Column(name = "release_name", nullable = false, length = 128)
    private String releaseName;

    @Column(nullable = false, length = 16)
    private String channel = "active";

    @Column(name = "traffic_percent", nullable = false)
    private Integer trafficPercent = 100;

    @Column(name = "is_active", nullable = false)
    private Boolean isActive = true;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "rollback_of")
    private TaxonomyRelease rollbackOf;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "quality_snapshot", columnDefinition = "jsonb")
    private Map<String, Object> qualitySnapshot = new HashMap<>();

    @Column(columnDefinition = "TEXT")
    private String notes;

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private Instant createdAt;
}
