package com.taxonomy.api.service;

import com.taxonomy.api.dto.request.CreateCollectionRequest;
import com.taxonomy.api.entity.Collection;
import com.taxonomy.api.exception.ResourceNotFoundException;
import com.taxonomy.api.repository.CollectionRepository;
import com.taxonomy.api.repository.DocumentRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class CollectionServiceTest {

    @Mock
    private CollectionRepository collectionRepo;

    @Mock
    private DocumentRepository documentRepo;

    private CollectionService collectionService;

    @BeforeEach
    void setUp() {
        collectionService = new CollectionService(collectionRepo, documentRepo);
    }

    @Test
    void create_persistsCollectionAndReturnsResponse() {
        UUID collectionId = UUID.randomUUID();
        when(collectionRepo.save(any(Collection.class))).thenAnswer(invocation -> {
            Collection collection = invocation.getArgument(0, Collection.class);
            collection.setId(collectionId);
            collection.setCreatedAt(Instant.parse("2026-03-21T10:00:00Z"));
            return collection;
        });

        var response = collectionService.create(new CreateCollectionRequest("Energy", "Energy domain docs"));

        assertEquals(collectionId, response.id());
        assertEquals("Energy", response.name());
        assertEquals(0, response.documentCount());
    }

    @Test
    void findAll_mapsDocumentCountsForEveryCollection() {
        Collection energy = new Collection("Energy", "Docs");
        energy.setId(UUID.randomUUID());
        Collection finance = new Collection("Finance", "Docs");
        finance.setId(UUID.randomUUID());
        when(collectionRepo.findAll()).thenReturn(List.of(energy, finance));
        when(documentRepo.countByCollectionId(energy.getId())).thenReturn(3L);
        when(documentRepo.countByCollectionId(finance.getId())).thenReturn(1L);

        var response = collectionService.findAll();

        assertEquals(2, response.size());
        assertEquals(3, response.getFirst().documentCount());
        assertEquals(1, response.getLast().documentCount());
    }

    @Test
    void findById_returnsMappedResponse() {
        UUID collectionId = UUID.randomUUID();
        Collection collection = new Collection("Energy", "Docs");
        collection.setId(collectionId);
        when(collectionRepo.findById(collectionId)).thenReturn(Optional.of(collection));
        when(documentRepo.countByCollectionId(collectionId)).thenReturn(4L);

        var response = collectionService.findById(collectionId);

        assertEquals(collectionId, response.id());
        assertEquals(4, response.documentCount());
    }

    @Test
    void getEntity_returnsCollectionAndThrowsWhenMissing() {
        UUID collectionId = UUID.randomUUID();
        Collection collection = new Collection("Energy", "Docs");
        collection.setId(collectionId);
        when(collectionRepo.findById(collectionId)).thenReturn(Optional.of(collection));
        when(collectionRepo.findById(UUID.fromString("00000000-0000-0000-0000-000000000001"))).thenReturn(Optional.empty());

        assertSame(collection, collectionService.getEntity(collectionId));
        assertThrows(
                ResourceNotFoundException.class,
                () -> collectionService.getEntity(UUID.fromString("00000000-0000-0000-0000-000000000001"))
        );
    }
}
