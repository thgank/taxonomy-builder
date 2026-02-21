package com.taxonomy.api.repository;

import com.taxonomy.api.entity.TaxonomyVersion;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface TaxonomyVersionRepository extends JpaRepository<TaxonomyVersion, UUID> {

    List<TaxonomyVersion> findByCollectionIdOrderByCreatedAtDesc(UUID collectionId);
}
