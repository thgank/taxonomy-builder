package com.taxonomy.api.service;

import com.taxonomy.api.dto.request.CreateCollectionRequest;
import com.taxonomy.api.dto.response.CollectionResponse;
import com.taxonomy.api.entity.Collection;
import com.taxonomy.api.exception.ResourceNotFoundException;
import com.taxonomy.api.repository.CollectionRepository;
import com.taxonomy.api.repository.DocumentRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Service
@Transactional(readOnly = true)
public class CollectionService {

    private final CollectionRepository collectionRepo;
    private final DocumentRepository documentRepo;

    public CollectionService(CollectionRepository collectionRepo,
                             DocumentRepository documentRepo) {
        this.collectionRepo = collectionRepo;
        this.documentRepo = documentRepo;
    }

    @Transactional
    public CollectionResponse create(CreateCollectionRequest req) {
        var entity = new Collection(req.name(), req.description());
        entity = collectionRepo.save(entity);
        return toResponse(entity, 0);
    }

    public List<CollectionResponse> findAll() {
        return collectionRepo.findAll().stream()
                .map(c -> toResponse(c, documentRepo.countByCollectionId(c.getId())))
                .toList();
    }

    public CollectionResponse findById(UUID id) {
        var entity = collectionRepo.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Collection", id));
        long docCount = documentRepo.countByCollectionId(id);
        return toResponse(entity, docCount);
    }

    public Collection getEntity(UUID id) {
        return collectionRepo.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Collection", id));
    }

    private CollectionResponse toResponse(Collection c, long docCount) {
        return new CollectionResponse(
                c.getId(), c.getName(), c.getDescription(),
                c.getCreatedAt(), docCount
        );
    }
}
