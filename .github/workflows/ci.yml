name: ci

on:
  push:
    branches: [main]
    paths-ignore: ["k8s/**", "README.md"]   # the bot's manifest commit must not retrigger CI
  pull_request:
    paths-ignore: ["k8s/**", "README.md"]

permissions:
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: app/requirements.txt
      - name: Install
        run: pip install -r app/requirements.txt pytest flake8
      - name: Lint
        run: flake8 app --max-line-length 100
      - name: Unit tests
        working-directory: app
        run: pytest -q

  build-push-deploy:
    needs: test
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    permissions:
      contents: write          # lets the job commit the new image tag
    env:
      IMAGE: ${{ secrets.DOCKERHUB_USERNAME }}/myapp
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      - name: Build image (local, not pushed yet)
        uses: docker/build-push-action@v6
        with:
          context: app
          load: true
          tags: ${{ env.IMAGE }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Smoke test the container
        run: |
          docker run -d --name smoke -p 8080:8080 ${IMAGE}:${GITHUB_SHA}
          for i in $(seq 1 10); do
            curl -fs http://localhost:8080/health && exit 0
            sleep 2
          done
          docker logs smoke
          exit 1

      - name: Push image
        uses: docker/build-push-action@v6
        with:
          context: app
          push: true
          tags: ${{ env.IMAGE }}:${{ github.sha }}
          cache-from: type=gha

      - name: Update image tag in Git (Argo CD picks this up)
        run: |
          cd k8s/overlays/dev
          sed -i "s|newName:.*|newName: ${IMAGE}|; s|newTag:.*|newTag: \"${GITHUB_SHA}\"|" kustomization.yaml
          git config user.name  "ci-bot"
          git config user.email "ci-bot@users.noreply.github.com"
          git add kustomization.yaml
          git commit -m "deploy ${GITHUB_SHA::7} to dev" || exit 0
          git pull --rebase origin main
          git push origin HEAD:main
