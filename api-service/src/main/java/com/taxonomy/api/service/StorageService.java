package com.taxonomy.api.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.UUID;

@Service
public class StorageService {

    private static final Logger log = LoggerFactory.getLogger(StorageService.class);
    private final Path rootPath;

    public StorageService(@Value("${app.storage.path}") String storagePath) {
        this.rootPath = Path.of(storagePath);
    }

    /**
     * Store uploaded file and return relative path.
     */
    public String store(UUID collectionId, UUID documentId,
                        String sanitizedFilename, MultipartFile file) throws IOException {
        Path dir = rootPath.resolve(collectionId.toString()).resolve(documentId.toString());
        Files.createDirectories(dir);
        Path target = dir.resolve(sanitizedFilename);
        Files.copy(file.getInputStream(), target, StandardCopyOption.REPLACE_EXISTING);
        log.info("Stored file: {}", target);
        return rootPath.relativize(target).toString();
    }

    /**
     * Resolve absolute path from relative storage path.
     */
    public Path resolve(String relativePath) {
        return rootPath.resolve(relativePath);
    }

    /**
     * Sanitize filename to prevent path-traversal.
     */
    public static String sanitize(String original) {
        if (original == null || original.isBlank()) {
            return "unnamed";
        }
        String name = Path.of(original).getFileName().toString();
        // remove potentially dangerous characters
        name = name.replaceAll("[^a-zA-Z0-9._\\-\\p{L}]", "_");
        if (name.startsWith(".")) {
            name = "_" + name;
        }
        // reject macro-enabled office formats
        String lower = name.toLowerCase();
        if (lower.endsWith(".docm") || lower.endsWith(".xlsm") || lower.endsWith(".pptm")) {
            throw new IllegalArgumentException("Macro-enabled files are not allowed: " + name);
        }
        return name;
    }
}
