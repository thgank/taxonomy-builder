package com.taxonomy.api.repository;

import com.taxonomy.api.entity.TaxonomyThresholdProfile;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

@Repository
public interface TaxonomyThresholdProfileRepository extends JpaRepository<TaxonomyThresholdProfile, UUID> {

    Optional<TaxonomyThresholdProfile> findFirstByCollectionIdAndNameAndIsActiveTrueOrderByCreatedAtDesc(
            UUID collectionId,
            String name
    );
}
