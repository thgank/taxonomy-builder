package com.taxonomy.api.repository;

import com.taxonomy.api.entity.TaxonomyRelease;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface TaxonomyReleaseRepository extends JpaRepository<TaxonomyRelease, UUID> {

    List<TaxonomyRelease> findByCollectionIdOrderByCreatedAtDesc(UUID collectionId);

    Optional<TaxonomyRelease> findByCollectionIdAndChannelAndIsActiveTrue(UUID collectionId, String channel);
}
