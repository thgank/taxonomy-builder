package com.taxonomy.api.service;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.mock.web.MockMultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

class StorageServiceTest {

    @Test
    void sanitize_removesPathTraversal() {
        assertEquals("evil.txt", StorageService.sanitize("../../evil.txt"));
    }

    @Test
    void sanitize_rejectsMacroFiles() {
        assertThrows(IllegalArgumentException.class,
                () -> StorageService.sanitize("report.docm"));
    }

    @Test
    void sanitize_handlesCyrillicNames() {
        String result = StorageService.sanitize("документ.pdf");
        assertTrue(result.endsWith(".pdf"));
        assertFalse(result.contains(".."));
    }

    @Test
    void sanitize_handlesBlank() {
        assertEquals("unnamed", StorageService.sanitize(""));
        assertEquals("unnamed", StorageService.sanitize(null));
    }

    @Test
    void sanitize_rewritesHiddenAndUnsafeCharacters() {
        assertEquals("_.secret_report_.pdf", StorageService.sanitize(".secret report?.pdf"));
    }

    @Test
    void store_persistsFileAndResolveReturnsAbsolutePath(@TempDir Path tempDir) throws IOException {
        StorageService storageService = new StorageService(tempDir.toString());
        UUID collectionId = UUID.randomUUID();
        UUID documentId = UUID.randomUUID();
        MockMultipartFile file = new MockMultipartFile(
                "files",
                "report.txt",
                "text/plain",
                "hello taxonomy".getBytes()
        );

        String relativePath = storageService.store(collectionId, documentId, "report.txt", file);
        Path resolved = storageService.resolve(relativePath);

        assertTrue(Files.exists(resolved));
        assertEquals("hello taxonomy", Files.readString(resolved));
        assertTrue(relativePath.contains(collectionId.toString()));
        assertTrue(relativePath.contains(documentId.toString()));
    }
}
