package com.taxonomy.api.service;

import com.taxonomy.api.dto.request.CreateJobRequest;
import com.taxonomy.api.dto.response.JobEventResponse;
import com.taxonomy.api.dto.response.JobResponse;
import com.taxonomy.api.entity.Collection;
import com.taxonomy.api.entity.Job;
import com.taxonomy.api.entity.TaxonomyVersion;
import com.taxonomy.api.entity.enums.JobStatus;
import com.taxonomy.api.entity.enums.JobType;
import com.taxonomy.api.entity.enums.TaxonomyStatus;
import com.taxonomy.api.exception.ConflictException;
import com.taxonomy.api.exception.ResourceNotFoundException;
import com.taxonomy.api.messaging.JobPublisher;
import com.taxonomy.api.messaging.PipelineMessage;
import com.taxonomy.api.repository.JobEventRepository;
import com.taxonomy.api.repository.JobRepository;
import com.taxonomy.api.repository.TaxonomyVersionRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataIntegrityViolationException;
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
        Collection collection = collectionService.getEntity(collectionId);
        JobType type = parseJobType(req.type());

        // ── Concurrency guard: reject if collection already has an active job ──
        if (collection.getActiveJob() != null) {
            Job active = collection.getActiveJob();
            if (active.getStatus() == JobStatus.QUEUED
                    || active.getStatus() == JobStatus.RUNNING
                    || active.getStatus() == JobStatus.RETRYING) {
                throw new ConflictException(
                        "Collection already has an active job: " + active.getId()
                                + " (status=" + active.getStatus() + ")"
                );
            }
        }

        Map<String, Object> params = validateAndNormalizeParams(
                req.params() != null ? new HashMap<>(req.params()) : new HashMap<>()
        );

        // ── Create taxonomy version for pipeline / taxonomy / evaluate jobs ──
        TaxonomyVersion taxVersion = null;
        if (type == JobType.FULL_PIPELINE || type == JobType.TAXONOMY || type == JobType.EVALUATE) {
            taxVersion = new TaxonomyVersion();
            taxVersion.setCollection(collection);
            taxVersion.setAlgorithm(
                    params.getOrDefault("method_taxonomy", "hybrid").toString()
            );
            taxVersion.setParameters(params);
            taxVersion.setStatus(TaxonomyStatus.NEW);
            taxVersion = taxVersionRepo.save(taxVersion);
        }

        // ── Create job with stage info ──
        String firstStage = PipelineStages.firstStage(type);
        String correlationId = UUID.randomUUID().toString();
        String traceId = correlationId;

        Job job = new Job();
        job.setCollection(collection);
        job.setType(type);
        job.setStatus(JobStatus.QUEUED);
        job.setTaxonomyVersion(taxVersion);
        job.setCurrentStage(firstStage);
        job.setCorrelationId(correlationId);
        job.setTraceId(correlationId);
        try {
            job = jobRepo.saveAndFlush(job);
        } catch (DataIntegrityViolationException ex) {
            throw new ConflictException(
                    "Collection already has an active job. Please wait for it to finish."
            );
        }

        // ── Set active job on collection ──
        collection.setActiveJob(job);

        // ── Publish to first stage ──
        PipelineMessage msg = PipelineMessage.of(
                job.getId(), collectionId,
                taxVersion != null ? taxVersion.getId() : null,
                type.name(),
                params,
                correlationId,
                traceId
        );
        publisher.publish(firstStage, msg);

        log.info("Created job {} type={} stage={} for collection {}",
                job.getId(), type, firstStage, collectionId);
        return toResponse(job);
    }

    public JobResponse findById(UUID jobId) {
        return toResponse(getEntity(jobId));
    }

    @Transactional
    public JobResponse cancel(UUID jobId) {
        Job job = getEntity(jobId);
        if (job.getStatus() == JobStatus.QUEUED
                || job.getStatus() == JobStatus.RUNNING
                || job.getStatus() == JobStatus.RETRYING) {
            job.setStatus(JobStatus.CANCELLED);
            job.setFinishedAt(Instant.now());
            jobRepo.save(job);

            // Release concurrency lock
            Collection collection = job.getCollection();
            if (collection.getActiveJob() != null
                    && collection.getActiveJob().getId().equals(job.getId())) {
                collection.setActiveJob(null);
            }
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

    // ── Helpers ──────────────────────────────────────────

    private JobType parseJobType(String raw) {
        try {
            return JobType.valueOf(raw.toUpperCase());
        } catch (IllegalArgumentException e) {
            throw new IllegalArgumentException(
                    "Invalid job type: '" + raw + "'. Valid values: "
                            + java.util.Arrays.toString(JobType.values())
            );
        }
    }

    /**
     * Validate and normalize pipeline parameters with safe bounds.
     */
    private Map<String, Object> validateAndNormalizeParams(Map<String, Object> params) {
        // method_term_extraction
        String termMethod = params.getOrDefault("method_term_extraction", "both").toString();
        if (!List.of("tfidf", "textrank", "both").contains(termMethod)) {
            throw new IllegalArgumentException(
                    "Invalid method_term_extraction: '" + termMethod + "'. Allowed: tfidf, textrank, both");
        }
        params.put("method_term_extraction", termMethod);

        // method_taxonomy
        String taxMethod = params.getOrDefault("method_taxonomy", "hybrid").toString();
        if (!List.of("hearst", "embedding", "hybrid").contains(taxMethod)) {
            throw new IllegalArgumentException(
                    "Invalid method_taxonomy: '" + taxMethod + "'. Allowed: hearst, embedding, hybrid");
        }
        params.put("method_taxonomy", taxMethod);

        // max_terms: 10..5000
        int maxTerms = intParam(params, "max_terms", 500);
        if (maxTerms < 10 || maxTerms > 5000) {
            throw new IllegalArgumentException("max_terms must be between 10 and 5000");
        }
        params.put("max_terms", maxTerms);

        // min_freq: 1..100
        int minFreq = intParam(params, "min_freq", 2);
        if (minFreq < 1 || minFreq > 100) {
            throw new IllegalArgumentException("min_freq must be between 1 and 100");
        }
        params.put("min_freq", minFreq);

        // similarity_threshold: 0.1..1.0
        double simThreshold = doubleParam(params, "similarity_threshold", 0.55);
        if (simThreshold < 0.1 || simThreshold > 1.0) {
            throw new IllegalArgumentException("similarity_threshold must be between 0.1 and 1.0");
        }
        params.put("similarity_threshold", simThreshold);

        // fuzz_threshold: 50..100
        int fuzzThreshold = intParam(params, "fuzz_threshold", 85);
        if (fuzzThreshold < 50 || fuzzThreshold > 100) {
            throw new IllegalArgumentException("fuzz_threshold must be between 50 and 100");
        }
        params.put("fuzz_threshold", fuzzThreshold);

        // chunk_size: 200..5000
        int chunkSize = intParam(params, "chunk_size", 1000);
        if (chunkSize < 200 || chunkSize > 5000) {
            throw new IllegalArgumentException("chunk_size must be between 200 and 5000");
        }
        params.put("chunk_size", chunkSize);

        // max_depth: 1..20
        int maxDepth = intParam(params, "max_depth", 6);
        if (maxDepth < 1 || maxDepth > 20) {
            throw new IllegalArgumentException("max_depth must be between 1 and 20");
        }
        params.put("max_depth", maxDepth);

        return params;
    }

    private int intParam(Map<String, Object> params, String key, int defaultVal) {
        Object val = params.get(key);
        if (val == null) return defaultVal;
        if (val instanceof Number n) return n.intValue();
        try {
            return Integer.parseInt(val.toString());
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException(key + " must be a valid integer");
        }
    }

    private double doubleParam(Map<String, Object> params, String key, double defaultVal) {
        Object val = params.get(key);
        if (val == null) return defaultVal;
        if (val instanceof Number n) return n.doubleValue();
        try {
            return Double.parseDouble(val.toString());
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException(key + " must be a valid number");
        }
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
