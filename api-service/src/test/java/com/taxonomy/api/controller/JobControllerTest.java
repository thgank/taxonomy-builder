package com.taxonomy.api.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.taxonomy.api.config.SecurityConfig;
import com.taxonomy.api.dto.request.CreateJobRequest;
import com.taxonomy.api.dto.response.JobEventResponse;
import com.taxonomy.api.dto.response.JobResponse;
import com.taxonomy.api.service.JobService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(JobController.class)
@Import(SecurityConfig.class)
@TestPropertySource(properties = "app.api-key=test-api-key")
class JobControllerTest {

    private static final String API_KEY = "test-api-key";

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private JobService jobService;

    @Test
    void createJob_returns201() throws Exception {
        UUID collectionId = UUID.randomUUID();
        UUID jobId = UUID.randomUUID();
        when(jobService.create(eq(collectionId), any(CreateJobRequest.class)))
                .thenReturn(new JobResponse(
                        jobId,
                        collectionId,
                        UUID.randomUUID(),
                        "FULL_PIPELINE",
                        "QUEUED",
                        0,
                        null,
                        Instant.now(),
                        null,
                        null
                ));

        mockMvc.perform(post("/api/collections/{id}/jobs", collectionId)
                        .header("X-API-Key", API_KEY)
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                                new CreateJobRequest("FULL_PIPELINE", Map.of("max_terms", 100)))))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").value(jobId.toString()))
                .andExpect(jsonPath("$.type").value("FULL_PIPELINE"))
                .andExpect(jsonPath("$.status").value("QUEUED"));
    }

    @Test
    void createJob_withoutType_returns400() throws Exception {
        UUID collectionId = UUID.randomUUID();

        mockMvc.perform(post("/api/collections/{id}/jobs", collectionId)
                        .header("X-API-Key", API_KEY)
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                .content("{\"params\":{}}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void createJob_invalidChunkSize_returns400() throws Exception {
        UUID collectionId = UUID.randomUUID();
        when(jobService.create(eq(collectionId), any(CreateJobRequest.class)))
                .thenThrow(new IllegalArgumentException("chunk_size must be a valid integer"));

        mockMvc.perform(post("/api/collections/{id}/jobs", collectionId)
                        .header("X-API-Key", API_KEY)
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                                new CreateJobRequest("FULL_PIPELINE", Map.of("chunk_size", "huge")))))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("chunk_size must be a valid integer"));
    }

    @Test
    void getEvents_returns200() throws Exception {
        UUID jobId = UUID.randomUUID();
        when(jobService.getEvents(jobId)).thenReturn(List.of(
                new JobEventResponse(
                        UUID.randomUUID(),
                        Instant.now(),
                        "INFO",
                        "Import started",
                        Map.of("stage", "import")
                )
        ));

        mockMvc.perform(get("/api/jobs/{jobId}/events", jobId)
                        .header("X-API-Key", API_KEY))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].level").value("INFO"))
                .andExpect(jsonPath("$[0].message").value("Import started"));
    }

    @Test
    void cancel_returns200() throws Exception {
        UUID jobId = UUID.randomUUID();
        when(jobService.cancel(jobId)).thenReturn(new JobResponse(
                jobId,
                UUID.randomUUID(),
                null,
                "IMPORT",
                "CANCELLED",
                100,
                null,
                Instant.now(),
                Instant.now(),
                Instant.now()
        ));

        mockMvc.perform(post("/api/jobs/{jobId}:cancel", jobId)
                        .header("X-API-Key", API_KEY)
                        .with(csrf()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("CANCELLED"));
    }
}
