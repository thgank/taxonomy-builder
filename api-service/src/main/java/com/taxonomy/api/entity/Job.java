package com.taxonomy.api.entity;

import com.taxonomy.api.entity.enums.JobStatus;
import com.taxonomy.api.entity.enums.JobType;
import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.CreationTimestamp;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "jobs")
@Getter @Setter
@NoArgsConstructor
public class Job {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "collection_id", nullable = false)
    private Collection collection;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "taxonomy_version_id")
    private TaxonomyVersion taxonomyVersion;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private JobType type;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private JobStatus status = JobStatus.QUEUED;

    @Column(nullable = false)
    private Integer progress = 0;

    @Column(name = "error_message", columnDefinition = "TEXT")
    private String errorMessage;

    @Column(name = "current_stage", length = 32)
    private String currentStage;

    @Column(name = "retry_count", nullable = false)
    private Integer retryCount = 0;

    @Column(name = "correlation_id", length = 64)
    private String correlationId;

    @Column(name = "trace_id", length = 64)
    private String traceId;

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private Instant createdAt;

    @Column(name = "started_at")
    private Instant startedAt;

    @Column(name = "finished_at")
    private Instant finishedAt;

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof Job j)) return false;
        return id != null && id.equals(j.getId());
    }

    @Override
    public int hashCode() {
        return getClass().hashCode();
    }
}
