package com.taxonomy.api.repository;

import com.taxonomy.api.entity.Document;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface DocumentRepository extends JpaRepository<Document, UUID> {

    List<Document> findByCollectionId(UUID collectionId);

    Page<Document> findByCollectionId(UUID collectionId, Pageable pageable);

    long countByCollectionId(UUID collectionId);
}
