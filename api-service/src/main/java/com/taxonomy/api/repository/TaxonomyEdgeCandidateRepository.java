package com.taxonomy.api.repository;

import com.taxonomy.api.entity.TaxonomyEdgeCandidate;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.UUID;

@Repository
public interface TaxonomyEdgeCandidateRepository extends JpaRepository<TaxonomyEdgeCandidate, UUID> {
}
