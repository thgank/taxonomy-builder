package com.taxonomy.api.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.CreationTimestamp;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "collections")
@Getter @Setter
@NoArgsConstructor
public class Collection {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(nullable = false, length = 255)
    private String name;

    private String description;

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private Instant createdAt;

    @OneToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "active_job_id")
    private Job activeJob;

    public Collection(String name, String description) {
        this.name = name;
        this.description = description;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof Collection c)) return false;
        return id != null && id.equals(c.getId());
    }

    @Override
    public int hashCode() {
        return getClass().hashCode();
    }
}
