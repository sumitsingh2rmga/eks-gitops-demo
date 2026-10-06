# EKS + GitHub Actions + Argo CD: minimum-cost test project

```
git push → GitHub Actions: lint → unit tests → build image → container smoke test
        → push to Docker Hub (tag = commit SHA) → CI commits the new tag to k8s/overlays/dev
        → Argo CD (running in EKS) sees the Git change → syncs to namespace "demo"
```

## 0. What you need and what it costs

**Accounts/tools:** AWS account, GitHub account, Docker Hub account; locally `aws` CLI v2, `eksctl`, `kubectl`, `git`.

**AWS safety first (5 min):**
1. Don't use the root user. Create an IAM user (AdministratorAccess is simplest for a throwaway lab) and run `aws configure`, then `aws sts get-caller-identity`.
2. Create an **AWS Budget** alert (for example $10) so a forgotten cluster can't surprise you.

**Cost model (verify in the AWS pricing calculator):** the EKS control plane is billed per hour while the cluster exists, even when idle. The config uses one `t3.medium`, no NAT gateway and no load balancers, which are the usual hidden costs. Budget roughly **$0.15-0.20 per hour**, so a 4-hour session is about $1. **Create the cluster when you practice and delete it afterwards.** The repo, images and pipeline cost nothing to keep.

## 1. Set up GitHub and Docker Hub (one time)

1. Create a **public** GitHub repo named `eks-gitops-demo` (public avoids giving Argo CD repo credentials).
2. Docker Hub: Account Settings → Security → **New Access Token** (Read & Write).
3. GitHub repo → Settings → Secrets and variables → Actions → add:
   - `DOCKERHUB_USERNAME`  - sumitsinghrmga, docker login -u sumitsinghrmga
   - `DOCKERHUB_TOKEN`  - dckr_pat_-twsYVrqD2cffGhCKbIyZ8tReWM
4. Settings → Actions → General → Workflow permissions: **Read and write** (needed for the CI bot commit).
5. Edit `argocd/application.yaml` and set `repoURL` to your repo, then push this project to `main`.
   The first CI run builds and pushes `DOCKERHUB_USER/myapp` (Docker Hub creates the repo as public on first push).

## 2. Create the EKS cluster (~15-20 min)

```bash
eksctl create cluster -f infra/cluster.yaml
kubectl get nodes          # expect 1 Ready node
```

Capacity note: a `t3.medium` allows about 17 pods. Argo CD (~7 pods) + system pods + the app fit, but don't add much more.

## 3. Install Argo CD (no load balancer, access by port-forward)

```bash
kubectl create namespace argocd
kubectl apply -n argocd --server-side --force-conflicts \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl -n argocd rollout status deploy/argocd-server

# admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d; echo

# UI at https://localhost:8080 (user: admin). Leave this running in its own terminal.
kubectl -n argocd port-forward svc/argocd-server 8080:443
```

## 4. Connect the app to Argo CD

```bash
kubectl apply -f argocd/application.yaml
kubectl -n argocd get applications          # wait for Synced / Healthy
kubectl -n demo get pods
kubectl -n demo port-forward svc/myapp 8081:80
curl localhost:8081/health                   # {"status":"ok"}
```

If the first sync shows `ImagePullBackOff`, CI hasn't pushed the image and tag yet. Check the Actions tab, and Argo CD will heal itself after the bot commit.

## 5. Run the pipeline end to end (practice list)

1. **Happy path:** in `app/app.py` change `VERSION` default to `"v2"` and push. CI goes green, a `deploy <sha>` commit appears, Argo CD syncs, and `curl localhost:8081/` shows v2.
2. **Test gate:** break `test_app.py` and push. Nothing is built or deployed.
3. **Smoke-test gate:** change the Dockerfile `CMD` to a wrong module. The container smoke test fails and nothing is pushed.
4. **Bad release:** make `/health` return 500. The readiness probe stops the rollout, and the old pod keeps serving (`maxUnavailable: 0`).
5. **Rollback:** `git revert <bad-commit> && git push`. Argo CD syncs the previous state.
6. **Drift / self-heal:** `kubectl -n demo scale deploy/myapp --replicas=3` and watch Argo CD revert it to 1.

## 6. Adding stages later (your next step)

- Copy `k8s/overlays/dev` to `overlays/staging` and `overlays/prod` (different replicas, tags, namespace).
- Add one Argo CD `Application` per overlay.
- In CI, keep "update dev tag" automatic. Add a second job that promotes the same SHA to staging/prod by editing that overlay's `newTag`, using a **GitHub Environment** with required reviewers as the approval gate.
- Add real test stages (integration tests against the dev namespace, security scan with Trivy) before the promote jobs.

## 7. Maintaining it

- Keep action versions pinned (`@v4` etc.) and enable Dependabot for `github-actions` and `pip`.
- Rotate the Docker Hub token periodically.
- Keep Kubernetes up to date. EKS bills a higher control-plane rate for versions past standard support, so recreate the cluster from `infra/cluster.yaml` (newest version) instead of keeping it for months.
- If you protect `main` with branch rules, allow the bot to push or switch to the PR-based flow.

## 8. Cleanup (always do this)

```bash
kubectl delete -f argocd/application.yaml        # optional, removes the app first
eksctl delete cluster -f infra/cluster.yaml --wait
```
Then check the AWS console for leftovers: CloudFormation stacks (`eksctl-gitops-demo-*`), EC2 volumes and Elastic IPs. They should all be gone.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| CI fails at "Update image tag": push rejected | Workflow permissions not Read and write, or `main` is protected |
| `ImagePullBackOff` | Wrong Docker Hub username in the overlay, or the repo is private. Make it public or add an imagePullSecret |
| Pods `Pending` | Node is full (about 17 pods) or `Insufficient cpu/memory`. Run `kubectl describe pod` |
| Argo CD `ComparisonError` / repo not found | `repoURL` typo, or the GitHub repo is private |
| `kubectl` can't connect after a restart | `aws eks update-kubeconfig --name gitops-demo --region ap-south-1` |
