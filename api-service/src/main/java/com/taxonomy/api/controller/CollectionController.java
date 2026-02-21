package com.taxonomy.api.controller;

import com.taxonomy.api.dto.request.CreateCollectionRequest;
import com.taxonomy.api.dto.response.CollectionResponse;
import com.taxonomy.api.service.CollectionService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/collections")
@Tag(name = "Collections", description = "Manage document collections")
public class CollectionController {

    private final CollectionService collectionService;

    public CollectionController(CollectionService collectionService) {
        this.collectionService = collectionService;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @Operation(summary = "Create a new collection")
    public CollectionResponse create(@Valid @RequestBody CreateCollectionRequest req) {
        return collectionService.create(req);
    }

    @GetMapping
    @Operation(summary = "List all collections")
    public List<CollectionResponse> list() {
        return collectionService.findAll();
    }

    @GetMapping("/{id}")
    @Operation(summary = "Get collection details")
    public CollectionResponse get(@PathVariable UUID id) {
        return collectionService.findById(id);
    }
}
