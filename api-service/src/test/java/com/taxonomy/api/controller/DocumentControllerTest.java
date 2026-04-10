package com.taxonomy.api.controller;

import com.taxonomy.api.config.SecurityConfig;
import com.taxonomy.api.dto.response.ChunkResponse;
import com.taxonomy.api.dto.response.DocumentResponse;
import com.taxonomy.api.service.DocumentService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(DocumentController.class)
@Import(SecurityConfig.class)
@TestPropertySource(properties = "app.api-key=test-api-key")
class DocumentControllerTest {

    private static final String API_KEY = "test-api-key";

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private DocumentService documentService;

    @Test
    void upload_returns201AndDocumentPayload() throws Exception {
        UUID collectionId = UUID.randomUUID();
        UUID documentId = UUID.randomUUID();
        var file = new MockMultipartFile(
                "files",
                "report.txt",
                MediaType.TEXT_PLAIN_VALUE,
                "energy systems".getBytes()
        );
        when(documentService.upload(eq(collectionId), any()))
                .thenReturn(List.of(new DocumentResponse(
                        documentId,
                        collectionId,
                        "report.txt",
                        MediaType.TEXT_PLAIN_VALUE,
                        14L,
                        "NEW",
                        Instant.parse("2026-03-19T10:00:00Z"),
                        null
                )));

        mockMvc.perform(multipart("/api/collections/{id}/documents:upload", collectionId)
                        .file(file)
                        .header("X-API-Key", API_KEY)
                        .with(csrf()))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$[0].id").value(documentId.toString()))
                .andExpect(jsonPath("$[0].filename").value("report.txt"))
                .andExpect(jsonPath("$[0].status").value("NEW"));
    }

    @Test
    void listByCollection_returnsDocuments() throws Exception {
        UUID collectionId = UUID.randomUUID();
        when(documentService.findByCollection(collectionId))
                .thenReturn(List.of(new DocumentResponse(
                        UUID.randomUUID(),
                        collectionId,
                        "report.txt",
                        MediaType.TEXT_PLAIN_VALUE,
                        14L,
                        "NEW",
                        Instant.now(),
                        null
                )));

        mockMvc.perform(get("/api/collections/{id}/documents", collectionId)
                        .header("X-API-Key", API_KEY))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].collectionId").value(collectionId.toString()))
                .andExpect(jsonPath("$[0].filename").value("report.txt"));
    }

    @Test
    void get_returnsSingleDocument() throws Exception {
        UUID documentId = UUID.randomUUID();
        UUID collectionId = UUID.randomUUID();
        when(documentService.findById(documentId))
                .thenReturn(new DocumentResponse(
                        documentId,
                        collectionId,
                        "report.txt",
                        MediaType.TEXT_PLAIN_VALUE,
                        14L,
                        "NEW",
                        Instant.now(),
                        null
                ));

        mockMvc.perform(get("/api/documents/{docId}", documentId)
                        .header("X-API-Key", API_KEY))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(documentId.toString()))
                .andExpect(jsonPath("$.collectionId").value(collectionId.toString()));
    }

    @Test
    void getChunks_returnsPaginatedChunkData() throws Exception {
        UUID documentId = UUID.randomUUID();
        UUID chunkId = UUID.randomUUID();
        when(documentService.getChunks(eq(documentId), any()))
                .thenReturn(new PageImpl<>(
                        List.of(new ChunkResponse(
                                chunkId,
                                documentId,
                                0,
                                "energy systems are resilient",
                                "en",
                                0,
                                28
                        )),
                        PageRequest.of(0, 20),
                        1
                ));

        mockMvc.perform(get("/api/documents/{docId}/chunks", documentId)
                        .header("X-API-Key", API_KEY))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content[0].id").value(chunkId.toString()))
                .andExpect(jsonPath("$.content[0].documentId").value(documentId.toString()))
                .andExpect(jsonPath("$.content[0].lang").value("en"));
    }

    @Test
    void noApiKey_returns403() throws Exception {
        mockMvc.perform(get("/api/documents/{docId}", UUID.randomUUID()))
                .andExpect(status().isForbidden());
    }

    @Test
    void upload_withoutFiles_returns400() throws Exception {
        UUID collectionId = UUID.randomUUID();

        mockMvc.perform(multipart("/api/collections/{id}/documents:upload", collectionId)
                        .header("X-API-Key", API_KEY)
                        .with(csrf()))
                .andExpect(status().isBadRequest());
    }
}
