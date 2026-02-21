package com.taxonomy.api.repository;

import com.taxonomy.api.entity.TaxonomyEdge;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface TaxonomyEdgeRepository extends JpaRepository<TaxonomyEdge, UUID> {

    Page<TaxonomyEdge> findByTaxonomyVersionId(UUID taxonomyVersionId, Pageable pageable);

    List<TaxonomyEdge> findByTaxonomyVersionId(UUID taxonomyVersionId);

    List<TaxonomyEdge> findByTaxonomyVersionIdAndParentConceptId(UUID taxonomyVersionId, UUID parentConceptId);

    List<TaxonomyEdge> findByTaxonomyVersionIdAndChildConceptId(UUID taxonomyVersionId, UUID childConceptId);

    @Query("""
        SELECT e FROM TaxonomyEdge e
        WHERE e.taxonomyVersion.id = :tvId
          AND e.childConcept.id NOT IN (
              SELECT e2.parentConcept.id FROM TaxonomyEdge e2
              WHERE e2.taxonomyVersion.id = :tvId
          )
        """)
    List<TaxonomyEdge> findLeafEdges(@Param("tvId") UUID taxonomyVersionId);

    @Query("""
        SELECT DISTINCT e.parentConcept.id FROM TaxonomyEdge e
        WHERE e.taxonomyVersion.id = :tvId
          AND e.parentConcept.id NOT IN (
              SELECT e2.childConcept.id FROM TaxonomyEdge e2
              WHERE e2.taxonomyVersion.id = :tvId
          )
        """)
    List<UUID> findRootConceptIds(@Param("tvId") UUID taxonomyVersionId);

    long countByTaxonomyVersionId(UUID taxonomyVersionId);
}
