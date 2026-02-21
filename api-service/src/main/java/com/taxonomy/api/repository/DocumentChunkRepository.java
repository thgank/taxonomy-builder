package com.taxonomy.api.repository;

import com.taxonomy.api.entity.DocumentChunk;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.UUID;

@Repository
public interface DocumentChunkRepository extends JpaRepository<DocumentChunk, UUID> {

    Page<DocumentChunk> findByDocumentId(UUID documentId, Pageable pageable);

    long countByDocumentId(UUID documentId);
}
