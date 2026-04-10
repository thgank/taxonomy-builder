package com.taxonomy.api.service;

import com.taxonomy.api.dto.request.CreateJobRequest;
import com.taxonomy.api.entity.Collection;
import com.taxonomy.api.entity.JobEvent;
import com.taxonomy.api.entity.TaxonomyVersion;
import com.taxonomy.api.entity.enums.JobStatus;
import com.taxonomy.api.entity.enums.JobType;
import com.taxonomy.api.exception.ConflictException;
import com.taxonomy.api.exception.ResourceNotFoundException;
import com.taxonomy.api.messaging.JobPublisher;
import com.taxonomy.api.repository.JobEventRepository;
import com.taxonomy.api.repository.JobRepository;
import com.taxonomy.api.repository.TaxonomyVersionRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.DataIntegrityViolationException;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;
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
    void create_rejectsRetryingConcurrentJob() {
        UUID collectionId = UUID.randomUUID();
        var collection = new Collection("Test", "desc");

        var activeJob = new com.taxonomy.api.entity.Job();
        activeJob.setStatus(JobStatus.RETRYING);
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

    @Test
    void create_fullPipelineCreatesTaxonomyVersionAndNormalizesDefaults() {
        UUID collectionId = UUID.randomUUID();
        var collection = new Collection("Test", "desc");
        collection.setId(collectionId);
        when(collectionService.getEntity(collectionId)).thenReturn(collection);
        when(taxVersionRepo.save(any())).thenAnswer(invocation -> {
            TaxonomyVersion version = invocation.getArgument(0, TaxonomyVersion.class);
            version.setId(UUID.randomUUID());
            return version;
        });
        when(jobRepo.saveAndFlush(any())).thenAnswer(invocation -> {
            var job = invocation.getArgument(0, com.taxonomy.api.entity.Job.class);
            job.setId(UUID.randomUUID());
            return job;
        });

        var response = jobService.create(collectionId, new CreateJobRequest("FULL_PIPELINE", Map.of()));

        ArgumentCaptor<TaxonomyVersion> versionCaptor = ArgumentCaptor.forClass(TaxonomyVersion.class);
        verify(taxVersionRepo).save(versionCaptor.capture());
        TaxonomyVersion savedVersion = versionCaptor.getValue();
        assertEquals("hybrid", savedVersion.getAlgorithm());
        assertEquals("both", savedVersion.getParameters().get("method_term_extraction"));
        assertEquals("hybrid", savedVersion.getParameters().get("method_taxonomy"));
        assertEquals(1000, savedVersion.getParameters().get("chunk_size"));
        assertEquals(6, savedVersion.getParameters().get("max_depth"));
        assertNotNull(collection.getActiveJob());
        assertNotNull(response.taxonomyVersionId());
        verify(publisher).publish(eq("import"), any());
    }

    @Test
    void create_wrapsDataIntegrityViolationAsConflict() {
        UUID collectionId = UUID.randomUUID();
        var collection = new Collection("Test", "desc");
        when(collectionService.getEntity(collectionId)).thenReturn(collection);
        when(jobRepo.saveAndFlush(any())).thenThrow(new DataIntegrityViolationException("duplicate active job"));

        var req = new CreateJobRequest("IMPORT", Map.of());

        assertThrows(ConflictException.class, () -> jobService.create(collectionId, req));
        verify(publisher, never()).publish(any(), any());
    }

    @Test
    void create_rejectsInvalidNumericParameterFormat() {
        UUID collectionId = UUID.randomUUID();
        var collection = new Collection("Test", "desc");
        when(collectionService.getEntity(collectionId)).thenReturn(collection);

        var req = new CreateJobRequest("IMPORT", Map.of("chunk_size", "large"));

        IllegalArgumentException error = assertThrows(IllegalArgumentException.class, () -> jobService.create(collectionId, req));
        assertTrue(error.getMessage().contains("chunk_size"));
    }

    @Test
    void cancel_releasesActiveJobLock() {
        UUID jobId = UUID.randomUUID();
        var collection = new Collection("Test", "desc");
        var job = new com.taxonomy.api.entity.Job();
        job.setId(jobId);
        job.setCollection(collection);
        job.setType(JobType.FULL_PIPELINE);
        job.setStatus(JobStatus.RUNNING);
        collection.setActiveJob(job);

        when(jobRepo.findById(jobId)).thenReturn(Optional.of(job));

        var response = jobService.cancel(jobId);

        assertEquals("CANCELLED", response.status());
        assertNull(collection.getActiveJob());
        verify(jobRepo).save(job);
    }

    @Test
    void cancel_doesNotSaveTerminalJob() {
        UUID jobId = UUID.randomUUID();
        var collection = new Collection("Test", "desc");
        var job = new com.taxonomy.api.entity.Job();
        job.setId(jobId);
        job.setCollection(collection);
        job.setType(JobType.EVALUATE);
        job.setStatus(JobStatus.SUCCESS);
        collection.setActiveJob(job);
        when(jobRepo.findById(jobId)).thenReturn(Optional.of(job));

        var response = jobService.cancel(jobId);

        assertEquals("SUCCESS", response.status());
        assertSame(job, collection.getActiveJob());
        verify(jobRepo, never()).save(any());
    }

    @Test
    void findById_missingJobThrowsNotFound() {
        UUID jobId = UUID.randomUUID();
        when(jobRepo.findById(jobId)).thenReturn(Optional.empty());

        assertThrows(ResourceNotFoundException.class, () -> jobService.findById(jobId));
    }

    @Test
    void getEvents_mapsRepositoryEntitiesToResponse() {
        UUID jobId = UUID.randomUUID();
        var job = new com.taxonomy.api.entity.Job();
        job.setId(jobId);
        JobEvent event = new JobEvent(job, "INFO", "started");
        event.setId(UUID.randomUUID());
        event.setTs(Instant.parse("2026-04-10T10:15:30Z"));
        event.setMeta(Map.of("stage", "import"));
        when(jobEventRepo.findByJobIdOrderByTsAsc(jobId)).thenReturn(List.of(event));

        var events = jobService.getEvents(jobId);

        assertEquals(1, events.size());
        assertEquals("INFO", events.getFirst().level());
        assertEquals("started", events.getFirst().message());
        assertEquals("import", events.getFirst().meta().get("stage"));
    }
}
