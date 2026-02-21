package com.taxonomy.api.controller;

import com.taxonomy.api.dto.request.CreateJobRequest;
import com.taxonomy.api.dto.response.JobEventResponse;
import com.taxonomy.api.dto.response.JobResponse;
import com.taxonomy.api.service.JobService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@Tag(name = "Jobs", description = "Manage processing jobs")
public class JobController {

    private final JobService jobService;

    public JobController(JobService jobService) {
        this.jobService = jobService;
    }

    @PostMapping("/api/collections/{id}/jobs")
    @ResponseStatus(HttpStatus.CREATED)
    @Operation(summary = "Create and start a new pipeline job")
    public JobResponse create(@PathVariable UUID id,
                              @Valid @RequestBody CreateJobRequest req) {
        return jobService.create(id, req);
    }

    @GetMapping("/api/jobs/{jobId}")
    @Operation(summary = "Get job status and progress")
    public JobResponse get(@PathVariable UUID jobId) {
        return jobService.findById(jobId);
    }

    @GetMapping("/api/jobs/{jobId}/events")
    @Operation(summary = "Get job audit events")
    public List<JobEventResponse> events(@PathVariable UUID jobId) {
        return jobService.getEvents(jobId);
    }

    @PostMapping("/api/jobs/{jobId}:cancel")
    @Operation(summary = "Cancel a running job (best-effort)")
    public JobResponse cancel(@PathVariable UUID jobId) {
        return jobService.cancel(jobId);
    }
}
