package com.taxonomy.api.repository;

import com.taxonomy.api.entity.ConceptOccurrence;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface ConceptOccurrenceRepository extends JpaRepository<ConceptOccurrence, UUID> {

    List<ConceptOccurrence> findByConceptId(UUID conceptId);
}
