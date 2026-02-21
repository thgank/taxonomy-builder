package com.taxonomy.api.repository;

import com.taxonomy.api.entity.Concept;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface ConceptRepository extends JpaRepository<Concept, UUID> {

    List<Concept> findByCollectionId(UUID collectionId);

    Optional<Concept> findByCollectionIdAndCanonical(UUID collectionId, String canonical);

    @Query("""
        SELECT c FROM Concept c
        WHERE c.collection.id = :collectionId
          AND LOWER(c.canonical) LIKE LOWER(CONCAT('%', :query, '%'))
        ORDER BY c.score DESC
        """)
    Page<Concept> searchByCanonical(@Param("collectionId") UUID collectionId,
                                    @Param("query") String query,
                                    Pageable pageable);

    long countByCollectionId(UUID collectionId);
}
