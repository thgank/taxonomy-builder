package com.taxonomy.api.repository;

import com.taxonomy.api.entity.TaxonomyEdgeLabel;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.UUID;

@Repository
public interface TaxonomyEdgeLabelRepository extends JpaRepository<TaxonomyEdgeLabel, UUID> {

    Page<TaxonomyEdgeLabel> findByTaxonomyVersionId(UUID taxonomyVersionId, Pageable pageable);
}
