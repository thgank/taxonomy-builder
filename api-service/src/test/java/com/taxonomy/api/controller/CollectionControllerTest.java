package com.taxonomy.api.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.taxonomy.api.config.SecurityConfig;
import com.taxonomy.api.dto.request.CreateCollectionRequest;
import com.taxonomy.api.dto.response.CollectionResponse;
import com.taxonomy.api.service.CollectionService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(CollectionController.class)
@Import(SecurityConfig.class)
@TestPropertySource(properties = "app.api-key=test-api-key")
class CollectionControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private CollectionService collectionService;

    private static final String API_KEY = "test-api-key";

    @Test
    void createCollection_returns201() throws Exception {
        var resp = new CollectionResponse(
                UUID.randomUUID(), "Finance", "Financial docs",
                Instant.now(), 0);
        when(collectionService.create(any())).thenReturn(resp);

        mockMvc.perform(post("/api/collections")
                        .header("X-API-Key", API_KEY)
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                                new CreateCollectionRequest("Finance", "Financial docs"))))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.name").value("Finance"));
    }

    @Test
    void listCollections_returns200() throws Exception {
        when(collectionService.findAll()).thenReturn(List.of());

        mockMvc.perform(get("/api/collections")
                        .header("X-API-Key", API_KEY))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$").isArray());
    }

    @Test
    void noApiKey_returns403() throws Exception {
        mockMvc.perform(get("/api/collections"))
                .andExpect(status().isForbidden());
    }
}
