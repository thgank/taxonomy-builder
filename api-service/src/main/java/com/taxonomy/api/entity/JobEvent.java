package com.taxonomy.api.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

@Entity
@Table(name = "job_events")
@Getter @Setter
@NoArgsConstructor
public class JobEvent {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "job_id", nullable = false)
    private Job job;

    @Column(nullable = false)
    private Instant ts = Instant.now();

    @Column(nullable = false, length = 16)
    private String level = "INFO";

    @Column(nullable = false, columnDefinition = "TEXT")
    private String message;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(columnDefinition = "jsonb")
    private Map<String, Object> meta = new HashMap<>();

    public JobEvent(Job job, String level, String message) {
        this.job = job;
        this.level = level;
        this.message = message;
        this.ts = Instant.now();
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof JobEvent je)) return false;
        return id != null && id.equals(je.getId());
    }

    @Override
    public int hashCode() {
        return getClass().hashCode();
    }
}
