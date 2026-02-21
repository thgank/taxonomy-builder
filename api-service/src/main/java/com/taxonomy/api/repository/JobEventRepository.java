package com.taxonomy.api.repository;

import com.taxonomy.api.entity.JobEvent;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface JobEventRepository extends JpaRepository<JobEvent, UUID> {

    List<JobEvent> findByJobIdOrderByTsAsc(UUID jobId);
}
