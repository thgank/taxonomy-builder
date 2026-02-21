package com.taxonomy.api.service;

import com.taxonomy.api.dto.request.CreateJobRequest;
import com.taxonomy.api.entity.Collection;
import com.taxonomy.api.entity.enums.JobStatus;
import com.taxonomy.api.exception.ConflictException;
import com.taxonomy.api.messaging.JobPublisher;
import com.taxonomy.api.repository.JobEventRepository;
import com.taxonomy.api.repository.JobRepository;
import com.taxonomy.api.repository.TaxonomyVersionRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class JobServiceTest {

    @Mock private JobRepository jobRepo;
    @Mock private JobEventRepository jobEventRepo;
    @Mock private TaxonomyVersionRepository taxVersionRepo;
    @Mock private CollectionService collectionService;
    @Mock private JobPublisher publisher;

    private JobService jobService;

    @BeforeEach
    void setUp() {
        jobService = new JobService(
                jobRepo, jobEventRepo, taxVersionRepo,
                collectionService, publisher
        );
    }

    @Test
    void create_rejectsInvalidJobType() {
        UUID collectionId = UUID.randomUUID();
        var collection = new Collection("Test", "desc");
        collection.setActiveJob(null);
        when(collectionService.getEntity(collectionId)).thenReturn(collection);

        var req = new CreateJobRequest("INVALID_TYPE", null);

        assertThrows(IllegalArgumentException.class,
                () -> jobService.create(collectionId, req));
    }

    @Test
    void create_rejectsConcurrentJob() {
        UUID collectionId = UUID.randomUUID();
        var collection = new Collection("Test", "desc");

        // Simulate active running job
        var activeJob = new com.taxonomy.api.entity.Job();
        activeJob.setStatus(JobStatus.RUNNING);
        collection.setActiveJob(activeJob);

        when(collectionService.getEntity(collectionId)).thenReturn(collection);

        var req = new CreateJobRequest("FULL_PIPELINE", null);

        assertThrows(ConflictException.class,
                () -> jobService.create(collectionId, req));
    }

    @Test
    void create_rejectsInvalidMaxTerms() {
        UUID collectionId = UUID.randomUUID();
        var collection = new Collection("Test", "desc");
        collection.setActiveJob(null);
        when(collectionService.getEntity(collectionId)).thenReturn(collection);

        var req = new CreateJobRequest("IMPORT", Map.of("max_terms", 99999));

        assertThrows(IllegalArgumentException.class,
                () -> jobService.create(collectionId, req));
    }

    @Test
    void create_rejectsInvalidTaxonomyMethod() {
        UUID collectionId = UUID.randomUUID();
        var collection = new Collection("Test", "desc");
        collection.setActiveJob(null);
        when(collectionService.getEntity(collectionId)).thenReturn(collection);

        var req = new CreateJobRequest("IMPORT", Map.of("method_taxonomy", "invalid"));

        assertThrows(IllegalArgumentException.class,
                () -> jobService.create(collectionId, req));
    }

    @Test
    void create_acceptsValidParams() {
        UUID collectionId = UUID.randomUUID();
        var collection = new Collection("Test", "desc");
        collection.setActiveJob(null);
        when(collectionService.getEntity(collectionId)).thenReturn(collection);
        when(jobRepo.saveAndFlush(any())).thenAnswer(inv -> {
            var job = inv.getArgument(0, com.taxonomy.api.entity.Job.class);
            // Simulate JPA generating an ID
            job.setId(UUID.randomUUID());
            return job;
        });

        var req = new CreateJobRequest("IMPORT",
                Map.of("max_terms", 200, "method_taxonomy", "hybrid"));

        var response = jobService.create(collectionId, req);
        assertNotNull(response);
        assertEquals("IMPORT", response.type());
        assertEquals("QUEUED", response.status());
        verify(publisher).publish(eq("import"), any());
    }
}
