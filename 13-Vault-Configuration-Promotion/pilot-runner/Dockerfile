FROM ubuntu:24.04
# Build dependencies for the disposable validation/OIDC runner, not a Vault server.
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates curl git python3 unzip tar gzip sudo \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/actions-runner
# Verify the pinned runner archive before extraction; review checksum on upgrades.
RUN curl --fail --silent --show-error --location \
    https://github.com/actions/runner/releases/download/v2.337.0/actions-runner-linux-x64-2.337.0.tar.gz \
    -o runner.tar.gz \
    && echo '70920811a4f8ad4328818682bca5c6469c1c942fab52448868071d0063816613  runner.tar.gz' | sha256sum -c - \
    && tar -xzf runner.tar.gz && rm runner.tar.gz \
    && ./bin/installdependencies.sh \
    && useradd --create-home runner && chown -R runner:runner /opt/actions-runner
COPY entrypoint.sh /opt/entrypoint.sh
RUN chmod 755 /opt/entrypoint.sh
USER runner
# start.py supplies registration environment; entrypoint accepts one ephemeral job.
ENTRYPOINT ["/opt/entrypoint.sh"]
