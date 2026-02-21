package com.taxonomy.api.repository;

import com.taxonomy.api.entity.Job;
import com.taxonomy.api.entity.enums.JobStatus;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface JobRepository extends JpaRepository<Job, UUID> {

    List<Job> findByCollectionIdOrderByCreatedAtDesc(UUID collectionId);

    List<Job> findByStatus(JobStatus status);
}
