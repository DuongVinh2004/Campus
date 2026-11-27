# Simulation of the cloud VM (Ubuntu 24.04) for rollout step 1.13. Built from the repository root:
#   docker build -f infra/cloud/docker/Dockerfile -t campus247-sim .
# Only code goes into the image. Model files, the retrieval index and the web app are mounted read-only at run time and the
# restored state lives in the container, so nothing of the development machine's live runtime is touched.
FROM ubuntu:24.10
ENV DEBIAN_FRONTEND=noninteractive CAMPUS247_ROOT=/opt/campus247 CAMPUS247_SKIP_SERVICES=1 CAMPUS247_SKIP_FETCH=1 CAMPUS247_PROFILE=cloud
WORKDIR /opt/campus247
# The installer only needs the lock file, the profiles and the kit: copying the rest of the code afterwards keeps the
# (slow) install layer cached while the code changes.
COPY pyproject.toml uv.lock ./
COPY infra/profiles ./infra/profiles
COPY infra/cloud ./infra/cloud
COPY scripts/runtime_profile.py ./scripts/runtime_profile.py
RUN bash infra/cloud/install.sh && rm -rf /var/lib/apt/lists/*
COPY scripts ./scripts
COPY services ./services
COPY packages ./packages
COPY contracts ./contracts
COPY evals/load ./evals/load
COPY evals/runners ./evals/runners
COPY evals/datasets/rag-v2 ./evals/datasets/rag-v2
COPY infra/cloud/docker/run-stack.sh /usr/local/bin/run-stack
RUN chmod +x /usr/local/bin/run-stack
ENTRYPOINT ["/usr/local/bin/run-stack"]
