# Core Workflow Checklist

Use this checklist during smoke testing and while collecting screenshots for the
assignment report.

## Preconditions

- services are running through Docker Compose or local dev setup
- `X-API-Key` is configured correctly
- at least one sample document is available for upload

## Collection and document flow

- [ ] Create a collection through API or web UI
- [ ] Verify the collection appears in the collection list
- [ ] Upload one or more supported files (`pdf`, `docx`, `html`, `txt`)
- [ ] Confirm uploaded documents are linked to the selected collection
- [ ] Confirm document status is created without storage failure

## Pipeline execution

- [ ] Create a `FULL_PIPELINE` job for the collection
- [ ] Verify the API returns a valid `jobId`
- [ ] Verify job status changes from `QUEUED` to `RUNNING`
- [ ] Verify job events are recorded during stage execution
- [ ] Verify no second active job can be started for the same collection
- [ ] Verify cancelled jobs stop progressing

## Taxonomy result validation

- [ ] Confirm a taxonomy version is created for the job
- [ ] Retrieve the taxonomy tree successfully
- [ ] Search for at least one concept in the generated taxonomy
- [ ] Open concept detail and verify parent/child/evidence data is present
- [ ] Export taxonomy as JSON or CSV

## Manual editing checks

- [ ] Add a manual edge to the taxonomy
- [ ] Update edge score or approval state
- [ ] Delete an edge
- [ ] Create a label for a candidate edge
- [ ] Verify changes are persisted and reflected by follow-up API calls

## Negative checks

- [ ] Attempt to create a job with invalid parameters and verify validation error
- [ ] Attempt to upload an unsupported file type and verify failure handling
- [ ] Request a missing collection, job, or taxonomy and verify a not-found response
- [ ] Attempt a request without `X-API-Key` and verify access is rejected

## Evidence to capture

- screenshot of running containers or local services
- screenshot of Swagger UI or Postman collection
- screenshot of job progress / events
- screenshot of taxonomy tree or concept detail
- screenshot or log excerpt of at least one negative test case
