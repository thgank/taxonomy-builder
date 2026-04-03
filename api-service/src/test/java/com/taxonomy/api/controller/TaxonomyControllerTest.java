package com.taxonomy.api.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.taxonomy.api.config.SecurityConfig;
import com.taxonomy.api.dto.request.CreateEdgeLabelRequest;
import com.taxonomy.api.dto.request.CreateEdgeRequest;
import com.taxonomy.api.dto.request.CreateReleaseRequest;
import com.taxonomy.api.dto.request.UpdateEdgeRequest;
import com.taxonomy.api.dto.response.ConceptDetailResponse;
import com.taxonomy.api.dto.response.ConceptResponse;
import com.taxonomy.api.dto.response.TaxonomyEdgeLabelResponse;
import com.taxonomy.api.dto.response.TaxonomyEdgeResponse;
import com.taxonomy.api.dto.response.TaxonomyExportResponse;
import com.taxonomy.api.dto.response.TaxonomyReleaseResponse;
import com.taxonomy.api.dto.response.TaxonomyTreeResponse;
import com.taxonomy.api.dto.response.TaxonomyVersionResponse;
import com.taxonomy.api.service.TaxonomyService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doNothing;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(TaxonomyController.class)
@Import(SecurityConfig.class)
@TestPropertySource(properties = "app.api-key=test-api-key")
class TaxonomyControllerTest {

    private static final String API_KEY = "test-api-key";

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private TaxonomyService taxonomyService;

    @Test
    void listVersions_returns200() throws Exception {
        UUID collectionId = UUID.randomUUID();
        UUID taxonomyId = UUID.randomUUID();
        when(taxonomyService.findVersionsByCollection(collectionId)).thenReturn(List.of(
                new TaxonomyVersionResponse(
                        taxonomyId,
                        collectionId,
                        "hybrid",
                        Map.of("max_terms", 120),
                        Map.of("quality_score_10", 7.8),
                        "READY",
                        Instant.parse("2026-03-20T10:00:00Z"),
                        Instant.parse("2026-03-20T10:05:00Z"),
                        8,
                        12
                )
        ));

        mockMvc.perform(get("/api/collections/{id}/taxonomies", collectionId)
                        .header("X-API-Key", API_KEY))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].id").value(taxonomyId.toString()))
                .andExpect(jsonPath("$[0].status").value("READY"))
                .andExpect(jsonPath("$[0].algorithm").value("hybrid"));
    }

    @Test
    void getVersionAndTree_return200() throws Exception {
        UUID taxonomyId = UUID.randomUUID();
        UUID conceptId = UUID.randomUUID();
        when(taxonomyService.findVersionById(taxonomyId)).thenReturn(
                new TaxonomyVersionResponse(
                        taxonomyId,
                        UUID.randomUUID(),
                        "hybrid",
                        Map.of(),
                        Map.of("coverage", 0.9),
                        "READY",
                        Instant.now(),
                        Instant.now(),
                        4,
                        6
                )
        );
        when(taxonomyService.getTree(taxonomyId)).thenReturn(
                new TaxonomyTreeResponse(
                        taxonomyId,
                        List.of(new TaxonomyTreeResponse.TreeNode(
                                conceptId,
                                "energy",
                                0.92,
                                List.of()
                        ))
                )
        );

        mockMvc.perform(get("/api/taxonomies/{taxId}", taxonomyId)
                        .header("X-API-Key", API_KEY))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(taxonomyId.toString()))
                .andExpect(jsonPath("$.edgeCount").value(4));

        mockMvc.perform(get("/api/taxonomies/{taxId}/tree", taxonomyId)
                        .header("X-API-Key", API_KEY))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.taxonomyVersionId").value(taxonomyId.toString()))
                .andExpect(jsonPath("$.roots[0].label").value("energy"));
    }

    @Test
    void edgeEndpoints_coverReadWriteDelete() throws Exception {
        UUID taxonomyId = UUID.randomUUID();
        UUID edgeId = UUID.randomUUID();
        UUID parentId = UUID.randomUUID();
        UUID childId = UUID.randomUUID();
        var edgeResponse = new TaxonomyEdgeResponse(
                edgeId,
                parentId,
                "energy",
                childId,
                "battery storage",
                "is-a",
                0.88,
                List.of(Map.of("method", "manual"))
        );
        when(taxonomyService.getEdges(eq(taxonomyId), any())).thenReturn(
                new PageImpl<>(List.of(edgeResponse), PageRequest.of(0, 20), 1)
        );
        when(taxonomyService.addEdge(eq(taxonomyId), any(CreateEdgeRequest.class))).thenReturn(edgeResponse);
        when(taxonomyService.updateEdge(eq(taxonomyId), eq(edgeId), any(UpdateEdgeRequest.class))).thenReturn(edgeResponse);
        doNothing().when(taxonomyService).deleteEdge(taxonomyId, edgeId);

        mockMvc.perform(get("/api/taxonomies/{taxId}/edges", taxonomyId)
                        .header("X-API-Key", API_KEY))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content[0].id").value(edgeId.toString()))
                .andExpect(jsonPath("$.content[0].parentLabel").value("energy"));

        mockMvc.perform(post("/api/taxonomies/{taxId}/edges", taxonomyId)
                        .header("X-API-Key", API_KEY)
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                                new CreateEdgeRequest(parentId, childId, "is-a", 0.88)
                        )))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").value(edgeId.toString()));

        mockMvc.perform(patch("/api/taxonomies/{taxId}/edges/{edgeId}", taxonomyId, edgeId)
                        .header("X-API-Key", API_KEY)
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                                new UpdateEdgeRequest(0.91, Boolean.TRUE)
                        )))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.score").value(0.88));

        mockMvc.perform(delete("/api/taxonomies/{taxId}/edges/{edgeId}", taxonomyId, edgeId)
                        .header("X-API-Key", API_KEY)
                        .with(csrf()))
                .andExpect(status().isNoContent());
    }

    @Test
    void labelConceptAndExportEndpoints_returnExpectedPayloads() throws Exception {
        UUID taxonomyId = UUID.randomUUID();
        UUID labelId = UUID.randomUUID();
        UUID conceptId = UUID.randomUUID();
        UUID collectionId = UUID.randomUUID();
        var labelResponse = new TaxonomyEdgeLabelResponse(
                labelId,
                UUID.randomUUID(),
                taxonomyId,
                collectionId,
                UUID.randomUUID(),
                UUID.randomUUID(),
                "energy",
                "battery storage",
                "accepted",
                "manual",
                "qa-user",
                "confirmed",
                Map.of("source", "review"),
                Instant.parse("2026-03-20T10:10:00Z")
        );
        when(taxonomyService.createEdgeLabel(eq(taxonomyId), any(CreateEdgeLabelRequest.class))).thenReturn(labelResponse);
        when(taxonomyService.getEdgeLabels(eq(taxonomyId), any())).thenReturn(
                new PageImpl<>(List.of(labelResponse), PageRequest.of(0, 20), 1)
        );
        when(taxonomyService.searchConcepts(eq(taxonomyId), eq("energy"), any())).thenReturn(
                new PageImpl<>(List.of(new ConceptResponse(
                        conceptId,
                        "energy storage",
                        List.of("energy storage"),
                        "en",
                        0.81
                )), PageRequest.of(0, 20), 1)
        );
        when(taxonomyService.getConceptDetail(taxonomyId, conceptId)).thenReturn(
                new ConceptDetailResponse(
                        conceptId,
                        "energy storage",
                        List.of("energy storage"),
                        "en",
                        0.81,
                        List.of(new ConceptDetailResponse.RelatedConcept(UUID.randomUUID(), "energy", 0.9)),
                        List.of(),
                        List.of(new ConceptDetailResponse.OccurrenceInfo(
                                UUID.randomUUID(),
                                UUID.randomUUID(),
                                "energy storage systems are critical",
                                0.77
                        ))
                )
        );
        when(taxonomyService.export(taxonomyId, true)).thenReturn(
                new TaxonomyExportResponse(
                        taxonomyId,
                        collectionId,
                        "hybrid",
                        Map.of(),
                        Map.of("quality_score_10", 7.8),
                        List.of(new TaxonomyExportResponse.ExportNode(conceptId, "energy storage")),
                        List.of()
                )
        );
        when(taxonomyService.exportCsv(taxonomyId)).thenReturn("parent,child,score\nenergy,battery storage,0.88\n");

        mockMvc.perform(post("/api/taxonomies/{taxId}/labels", taxonomyId)
                        .header("X-API-Key", API_KEY)
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                                new CreateEdgeLabelRequest(
                                        UUID.randomUUID(),
                                        null,
                                        null,
                                        null,
                                        null,
                                        "accepted",
                                        "manual",
                                        "qa-user",
                                        "confirmed",
                                        Map.of("source", "review")
                                )
                        )))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").value(labelId.toString()))
                .andExpect(jsonPath("$.label").value("accepted"));

        mockMvc.perform(get("/api/taxonomies/{taxId}/labels", taxonomyId)
                        .header("X-API-Key", API_KEY))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content[0].reviewerId").value("qa-user"));

        mockMvc.perform(get("/api/taxonomies/{taxId}/concepts/search", taxonomyId)
                        .header("X-API-Key", API_KEY)
                        .param("q", "energy"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content[0].canonical").value("energy storage"));

        mockMvc.perform(get("/api/taxonomies/{taxId}/concepts/{conceptId}", taxonomyId, conceptId)
                        .header("X-API-Key", API_KEY))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.canonical").value("energy storage"))
                .andExpect(jsonPath("$.parents[0].canonical").value("energy"));

        mockMvc.perform(get("/api/taxonomies/{taxId}/export", taxonomyId)
                        .header("X-API-Key", API_KEY)
                        .param("include_orphans", "true"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.taxonomyVersionId").value(taxonomyId.toString()))
                .andExpect(jsonPath("$.nodes[0].label").value("energy storage"));

        mockMvc.perform(get("/api/taxonomies/{taxId}/export", taxonomyId)
                        .header("X-API-Key", API_KEY)
                        .param("format", "csv"))
                .andExpect(status().isOk())
                .andExpect(header().string("Content-Disposition", "attachment; filename=taxonomy_" + taxonomyId + ".csv"))
                .andExpect(content().contentType("text/csv"))
                .andExpect(content().string("parent,child,score\nenergy,battery storage,0.88\n"));
    }

    @Test
    void releaseEndpoints_returnExpectedPayloads() throws Exception {
        UUID collectionId = UUID.randomUUID();
        UUID releaseId = UUID.randomUUID();
        UUID taxonomyId = UUID.randomUUID();
        var releaseResponse = new TaxonomyReleaseResponse(
                releaseId,
                collectionId,
                taxonomyId,
                "baseline-v1",
                "active",
                100,
                true,
                null,
                Map.of("quality_score_10", 8.1),
                "stable release",
                Instant.parse("2026-03-20T11:00:00Z")
        );
        when(taxonomyService.listReleases(collectionId)).thenReturn(List.of(releaseResponse));
        when(taxonomyService.createRelease(eq(collectionId), any(CreateReleaseRequest.class))).thenReturn(releaseResponse);
        when(taxonomyService.promoteRelease(eq(collectionId), eq(releaseId), any())).thenReturn(releaseResponse);
        when(taxonomyService.rollbackRelease(eq(collectionId), eq(releaseId), any())).thenReturn(releaseResponse);

        mockMvc.perform(get("/api/collections/{id}/releases", collectionId)
                        .header("X-API-Key", API_KEY))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].releaseName").value("baseline-v1"));

        mockMvc.perform(post("/api/collections/{id}/releases", collectionId)
                        .header("X-API-Key", API_KEY)
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                                new CreateReleaseRequest(taxonomyId, "baseline-v1", "active", 100, "stable release")
                        )))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").value(releaseId.toString()));

        mockMvc.perform(post("/api/collections/{id}/releases/{releaseId}/promote", collectionId, releaseId)
                        .header("X-API-Key", API_KEY)
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"channel\":\"canary\",\"trafficPercent\":25}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.channel").value("active"));

        mockMvc.perform(post("/api/collections/{id}/releases/{releaseId}/rollback", collectionId, releaseId)
                        .header("X-API-Key", API_KEY)
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"channel\":\"active\",\"reason\":\"rollback requested\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(releaseId.toString()));
    }

    @Test
    void noApiKey_returns403() throws Exception {
        mockMvc.perform(get("/api/taxonomies/{taxId}/tree", UUID.randomUUID()))
                .andExpect(status().isForbidden());
    }
}
