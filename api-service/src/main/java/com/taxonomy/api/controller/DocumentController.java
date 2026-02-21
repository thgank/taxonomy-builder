package com.taxonomy.api.controller;

import com.taxonomy.api.dto.response.ChunkResponse;
import com.taxonomy.api.dto.response.DocumentResponse;
import com.taxonomy.api.service.DocumentService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;
import java.util.UUID;

@RestController
@Tag(name = "Documents", description = "Upload and manage documents")
public class DocumentController {

    private final DocumentService documentService;

    public DocumentController(DocumentService documentService) {
        this.documentService = documentService;
    }

    @PostMapping(value = "/api/collections/{id}/documents:upload",
                 consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    @ResponseStatus(HttpStatus.CREATED)
    @Operation(summary = "Upload one or more documents to a collection")
    public List<DocumentResponse> upload(
            @PathVariable UUID id,
            @RequestParam("files") List<MultipartFile> files) {
        return documentService.upload(id, files);
    }

    @GetMapping("/api/collections/{id}/documents")
    @Operation(summary = "List documents in a collection")
    public List<DocumentResponse> listByCollection(@PathVariable UUID id) {
        return documentService.findByCollection(id);
    }

    @GetMapping("/api/documents/{docId}")
    @Operation(summary = "Get document details")
    public DocumentResponse get(@PathVariable UUID docId) {
        return documentService.findById(docId);
    }

    @GetMapping("/api/documents/{docId}/chunks")
    @Operation(summary = "Get document chunks (paginated)")
    public Page<ChunkResponse> getChunks(@PathVariable UUID docId, Pageable pageable) {
        return documentService.getChunks(docId, pageable);
    }
}
