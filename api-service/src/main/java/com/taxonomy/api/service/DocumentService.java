package com.taxonomy.api.service;

import com.taxonomy.api.dto.response.ChunkResponse;
import com.taxonomy.api.dto.response.DocumentResponse;
import com.taxonomy.api.entity.Document;
import com.taxonomy.api.entity.enums.DocumentStatus;
import com.taxonomy.api.exception.ResourceNotFoundException;
import com.taxonomy.api.repository.DocumentChunkRepository;
import com.taxonomy.api.repository.DocumentRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

@Service
@Transactional(readOnly = true)
public class DocumentService {

    private static final Logger log = LoggerFactory.getLogger(DocumentService.class);

    private final DocumentRepository documentRepo;
    private final DocumentChunkRepository chunkRepo;
    private final CollectionService collectionService;
    private final StorageService storageService;

    public DocumentService(DocumentRepository documentRepo,
                           DocumentChunkRepository chunkRepo,
                           CollectionService collectionService,
                           StorageService storageService) {
        this.documentRepo = documentRepo;
        this.chunkRepo = chunkRepo;
        this.collectionService = collectionService;
        this.storageService = storageService;
    }

    @Transactional
    public List<DocumentResponse> upload(UUID collectionId, List<MultipartFile> files) {
        var collection = collectionService.getEntity(collectionId);
        List<DocumentResponse> results = new ArrayList<>();

        for (MultipartFile file : files) {
            String sanitized = StorageService.sanitize(file.getOriginalFilename());
            var doc = new Document();
            doc.setCollection(collection);
            doc.setFilename(sanitized);
            doc.setMimeType(file.getContentType() != null ? file.getContentType() : "application/octet-stream");
            doc.setSizeBytes(file.getSize());
            doc.setStatus(DocumentStatus.NEW);
            doc = documentRepo.save(doc);

            try {
                String path = storageService.store(collectionId, doc.getId(), sanitized, file);
                doc.setStoragePath(path);
                documentRepo.save(doc);
            } catch (IOException e) {
                log.error("Failed to store file: {}", sanitized, e);
                doc.setStatus(DocumentStatus.FAILED);
                documentRepo.save(doc);
            }

            results.add(toResponse(doc));
        }
        return results;
    }

    public List<DocumentResponse> findByCollection(UUID collectionId) {
        return documentRepo.findByCollectionId(collectionId).stream()
                .map(this::toResponse)
                .toList();
    }

    public DocumentResponse findById(UUID docId) {
        return toResponse(getEntity(docId));
    }

    public Document getEntity(UUID docId) {
        return documentRepo.findById(docId)
                .orElseThrow(() -> new ResourceNotFoundException("Document", docId));
    }

    public Page<ChunkResponse> getChunks(UUID docId, Pageable pageable) {
        return chunkRepo.findByDocumentId(docId, pageable)
                .map(c -> new ChunkResponse(
                        c.getId(), c.getDocument().getId(),
                        c.getChunkIndex(), c.getText(), c.getLang(),
                        c.getCharStart(), c.getCharEnd()));
    }

    private DocumentResponse toResponse(Document d) {
        return new DocumentResponse(
                d.getId(),
                d.getCollection().getId(),
                d.getFilename(),
                d.getMimeType(),
                d.getSizeBytes(),
                d.getStatus().name(),
                d.getCreatedAt(),
                d.getParsedAt()
        );
    }
}
