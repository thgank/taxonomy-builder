package com.taxonomy.api.service;

import com.taxonomy.api.entity.Collection;
import com.taxonomy.api.entity.Document;
import com.taxonomy.api.entity.enums.DocumentStatus;
import com.taxonomy.api.repository.DocumentChunkRepository;
import com.taxonomy.api.repository.DocumentRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mock.web.MockMultipartFile;

import java.io.IOException;
import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.atLeast;
import static org.mockito.Mockito.same;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class DocumentServiceTest {

    @Mock private DocumentRepository documentRepo;
    @Mock private DocumentChunkRepository chunkRepo;
    @Mock private CollectionService collectionService;
    @Mock private StorageService storageService;

    private DocumentService documentService;

    @BeforeEach
    void setUp() {
        documentService = new DocumentService(
                documentRepo,
                chunkRepo,
                collectionService,
                storageService
        );
    }

    @Test
    void upload_sanitizesFilenameAndStoresRelativePath() throws Exception {
        UUID collectionId = UUID.randomUUID();
        var collection = new Collection("Finance", "Docs");
        var file = new MockMultipartFile(
                "files",
                "../../quarterly report.pdf",
                "application/pdf",
                "test".getBytes()
        );

        when(collectionService.getEntity(collectionId)).thenReturn(collection);
        when(documentRepo.save(any(Document.class))).thenAnswer(invocation -> {
            var doc = invocation.getArgument(0, Document.class);
            if (doc.getId() == null) {
                doc.setId(UUID.randomUUID());
            }
            return doc;
        });
        when(storageService.store(eq(collectionId), any(UUID.class), eq("quarterly_report.pdf"), same(file)))
                .thenReturn("uploads/quarterly_report.pdf");

        var result = documentService.upload(collectionId, List.of(file));

        assertEquals(1, result.size());
        assertEquals("quarterly_report.pdf", result.getFirst().filename());
        assertEquals("NEW", result.getFirst().status());

        var captor = ArgumentCaptor.forClass(Document.class);
        verify(documentRepo, atLeast(2)).save(captor.capture());
        Document stored = captor.getAllValues().getLast();
        assertEquals("uploads/quarterly_report.pdf", stored.getStoragePath());
        assertNotNull(stored.getId());
    }

    @Test
    void upload_marksDocumentFailedWhenStorageThrows() throws Exception {
        UUID collectionId = UUID.randomUUID();
        var collection = new Collection("Finance", "Docs");
        var file = new MockMultipartFile(
                "files",
                "report.pdf",
                "application/pdf",
                "test".getBytes()
        );

        when(collectionService.getEntity(collectionId)).thenReturn(collection);
        when(documentRepo.save(any(Document.class))).thenAnswer(invocation -> {
            var doc = invocation.getArgument(0, Document.class);
            if (doc.getId() == null) {
                doc.setId(UUID.randomUUID());
            }
            return doc;
        });
        when(storageService.store(eq(collectionId), any(UUID.class), eq("report.pdf"), same(file)))
                .thenThrow(new IOException("disk full"));

        var result = documentService.upload(collectionId, List.of(file));

        assertEquals(1, result.size());
        assertEquals("FAILED", result.getFirst().status());

        var captor = ArgumentCaptor.forClass(Document.class);
        verify(documentRepo, atLeast(2)).save(captor.capture());
        Document failed = captor.getAllValues().getLast();
        assertEquals(DocumentStatus.FAILED, failed.getStatus());
    }
}
