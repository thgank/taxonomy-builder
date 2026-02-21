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
import java.util.UUID;

@Entity
@Table(name = "concepts")
@Getter @Setter
@NoArgsConstructor
public class Concept {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "collection_id", nullable = false)
    private Collection collection;

    @Column(nullable = false, columnDefinition = "TEXT")
    private String canonical;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "surface_forms", columnDefinition = "jsonb")
    private List<String> surfaceForms = new ArrayList<>();

    @Column(length = 10)
    private String lang;

    @Column(nullable = false)
    private Double score = 0.0;

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private Instant createdAt;

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof Concept c)) return false;
        return id != null && id.equals(c.getId());
    }

    @Override
    public int hashCode() {
        return getClass().hashCode();
    }
}
