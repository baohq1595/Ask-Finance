# Ask Finance — Terraform (GCP)

Single-file IaC for the Ask Finance backend. Everything is hardcoded inside
`main.tf` — environment switching is done with **Terraform workspaces** only.

## Workspace mapping

| Workspace | `project_id` | min / max instances |
| --- | --- | --- |
| `sit` | `ask-finance-sit` | 0 / 3 |
| `prod` | `ask-finance-prod` | 1 / 10 |

Other hardcoded values (edit at the top of `main.tf` if needed):

- `region = "us-central1"`
- `github_repository = "baohq1595/Ask-Finance"`

## What it creates

- Required APIs (`run`, `artifactregistry`, `aiplatform`, `iam`, `iamcredentials`, `sts`, `logging`, `cloudresourcemanager`).
- Artifact Registry Docker repo (`<region>-docker.pkg.dev/<project>/ask-finance`).
- Runtime SA `sa-ask-finance-runtime` with `roles/aiplatform.user` + `roles/logging.logWriter`.
- CI SA `sa-ask-finance-ci` with `roles/run.developer`, AR writer, and `roles/iam.serviceAccountUser` on the runtime SA.
- Workload Identity Pool/Provider trusting `baohq1595/Ask-Finance` (no JSON keys).
- Cloud Run v2 service with env vars, scaling, runtime SA. The container image is owned by CI (`lifecycle.ignore_changes`).
- Public ingress via `roles/run.invoker` to `allUsers`.

## Apply

```bash
cd infra/terraform
terraform init

# SIT
terraform workspace new sit       # first time
terraform workspace select sit    # subsequent runs
terraform apply

# PROD
terraform workspace new prod
terraform workspace select prod
terraform apply
```

The two workspaces use **separate state files**, so SIT and PROD never
overwrite each other.

## Wire up GitHub Actions

After the first apply, grab the bootstrap output:

```bash
terraform output -json github_actions_variables
```

Create these as **repository variables** in GitHub (Settings → Secrets and
variables → Actions → Variables — none are sensitive):

- `GCP_PROJECT_ID`
- `GCP_REGION`
- `WIF_PROVIDER`
- `WIF_SERVICE_ACCOUNT`
- `CLOUD_RUN_SERVICE_ACCOUNT`

Then push to `main` (or run `Deploy backend to Cloud Run` manually).

## Point the UI at the deployed backend

```bash
ASK_FINANCE_API_URL="$(terraform output -raw cloud_run_service_url)" python ../../app.py
```

## Destroy

```bash
terraform workspace select sit
terraform destroy
```
