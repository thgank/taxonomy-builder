package com.taxonomy.api.service;

import com.taxonomy.api.dto.request.CreateJobRequest;
import com.taxonomy.api.dto.response.JobEventResponse;
import com.taxonomy.api.dto.response.JobResponse;
import com.taxonomy.api.entity.Job;
import com.taxonomy.api.entity.TaxonomyVersion;
import com.taxonomy.api.entity.enums.JobStatus;
import com.taxonomy.api.entity.enums.JobType;
import com.taxonomy.api.entity.enums.TaxonomyStatus;
import com.taxonomy.api.exception.ResourceNotFoundException;
import com.taxonomy.api.messaging.JobPublisher;
import com.taxonomy.api.messaging.PipelineMessage;
import com.taxonomy.api.repository.JobEventRepository;
import com.taxonomy.api.repository.JobRepository;
import com.taxonomy.api.repository.TaxonomyVersionRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
@Transactional(readOnly = true)
public class JobService {

    private static final Logger log = LoggerFactory.getLogger(JobService.class);

    private final JobRepository jobRepo;
    private final JobEventRepository jobEventRepo;
    private final TaxonomyVersionRepository taxVersionRepo;
    private final CollectionService collectionService;
    private final JobPublisher publisher;

    public JobService(JobRepository jobRepo,
                      JobEventRepository jobEventRepo,
                      TaxonomyVersionRepository taxVersionRepo,
                      CollectionService collectionService,
                      JobPublisher publisher) {
        this.jobRepo = jobRepo;
        this.jobEventRepo = jobEventRepo;
        this.taxVersionRepo = taxVersionRepo;
        this.collectionService = collectionService;
        this.publisher = publisher;
    }

    @Transactional
    public JobResponse create(UUID collectionId, CreateJobRequest req) {
        var collection = collectionService.getEntity(collectionId);
        JobType type = JobType.valueOf(req.type().toUpperCase());

        Map<String, Object> params = req.params() != null ? req.params() : new HashMap<>();

        // Create taxonomy version for pipeline/taxonomy jobs
        TaxonomyVersion taxVersion = null;
        if (type == JobType.FULL_PIPELINE || type == JobType.TAXONOMY) {
            taxVersion = new TaxonomyVersion();
            taxVersion.setCollection(collection);
            taxVersion.setAlgorithm(
                    params.getOrDefault("method_taxonomy", "hybrid").toString()
            );
            taxVersion.setParameters(params);
            taxVersion.setStatus(TaxonomyStatus.NEW);
            taxVersion = taxVersionRepo.save(taxVersion);
        }

        var job = new Job();
        job.setCollection(collection);
        job.setType(type);
        job.setStatus(JobStatus.QUEUED);
        job.setTaxonomyVersion(taxVersion);
        job = jobRepo.save(job);

        // Publish message
        PipelineMessage msg = PipelineMessage.of(
                job.getId(), collectionId,
                taxVersion != null ? taxVersion.getId() : null,
                params
        );

        switch (type) {
            case FULL_PIPELINE, IMPORT -> publisher.publishImport(msg);
            case NLP -> publisher.publishNlp(msg);
            case TERMS -> publisher.publishTerms(msg);
            case TAXONOMY -> publisher.publishBuild(msg);
        }

        log.info("Created job {} type={} for collection {}", job.getId(), type, collectionId);
        return toResponse(job);
    }

    public JobResponse findById(UUID jobId) {
        return toResponse(getEntity(jobId));
    }

    @Transactional
    public JobResponse cancel(UUID jobId) {
        var job = getEntity(jobId);
        if (job.getStatus() == JobStatus.QUEUED || job.getStatus() == JobStatus.RUNNING) {
            job.setStatus(JobStatus.CANCELLED);
            job.setFinishedAt(Instant.now());
            jobRepo.save(job);
        }
        return toResponse(job);
    }

    public List<JobEventResponse> getEvents(UUID jobId) {
        return jobEventRepo.findByJobIdOrderByTsAsc(jobId).stream()
                .map(e -> new JobEventResponse(
                        e.getId(), e.getTs(), e.getLevel(),
                        e.getMessage(), e.getMeta()))
                .toList();
    }

    private Job getEntity(UUID jobId) {
        return jobRepo.findById(jobId)
                .orElseThrow(() -> new ResourceNotFoundException("Job", jobId));
    }

    private JobResponse toResponse(Job j) {
        return new JobResponse(
                j.getId(),
                j.getCollection().getId(),
                j.getTaxonomyVersion() != null ? j.getTaxonomyVersion().getId() : null,
                j.getType().name(),
                j.getStatus().name(),
                j.getProgress(),
                j.getErrorMessage(),
                j.getCreatedAt(),
                j.getStartedAt(),
                j.getFinishedAt()
        );
    }
}
