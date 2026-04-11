output "cloud_run_url" {
  value = google_cloud_run_service.tams_api.status[0].url
}

output "build_command" {
  value = "gcloud builds submit --tag ${var.region}-docker.pkg.dev/${var.project_id}/${var.repository_name}/tams-api:latest ."
  description = "Run this command from the root of the repository to build and push the real image."
}

output "curl_test_command" {
  value = "curl -H \"Authorization: Bearer $(gcloud auth print-identity-token)\" ${google_cloud_run_service.tams_api.status[0].url}/service"
  description = "Run this command to test the API after deploying the real image."
}
