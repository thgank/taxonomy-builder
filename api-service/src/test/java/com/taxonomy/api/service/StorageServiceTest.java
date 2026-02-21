package com.taxonomy.api.service;

import org.junit.jupiter.api.Test;

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
}
