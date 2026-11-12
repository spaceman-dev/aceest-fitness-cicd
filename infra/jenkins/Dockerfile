# Jenkins controller for the ACEest pipeline.
# The stock LTS image has no docker CLI, kubectl, python or sonar-scanner,
# and the Jenkinsfile shells out to all four, so they are baked in here.
FROM jenkins/jenkins:lts-jdk21

ARG KUBECTL_VERSION=v1.37.0
ARG SONAR_SCANNER_VERSION=8.0.1.6346

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 python3-venv python3-pip gettext-base unzip curl jq \
    && rm -rf /var/lib/apt/lists/*

# Networks that inspect TLS re-sign every download with their own root CA.
# Any *.crt dropped into extra-ca/ (git-ignored) is trusted by curl, pip and
# the JVM, so the downloads below and the plugin install keep working.
COPY extra-ca/ /usr/local/share/ca-certificates/extra/
RUN update-ca-certificates \
    && for crt in /usr/local/share/ca-certificates/extra/*.crt; do \
         [ -f "$crt" ] || continue; \
         keytool -importcert -noprompt -cacerts -storepass changeit \
           -alias "extra-$(basename "$crt" .crt)" -file "$crt"; \
       done

# docker CLI + buildx only; the daemon is the host's, reached through the socket
COPY --from=docker:29-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker:29-cli /usr/local/libexec/docker/cli-plugins/docker-buildx \
     /usr/local/libexec/docker/cli-plugins/docker-buildx

# SonarQube's CSS/HTML analysers run on Node and refuse Debian's older nodejs
COPY --from=node:24-slim /usr/local/bin/node /usr/local/bin/node

RUN arch="$(dpkg --print-architecture)" \
    && curl -fsSL --retry 5 --retry-delay 5 --retry-all-errors -o /usr/local/bin/kubectl \
        "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${arch}/kubectl" \
    && chmod 0755 /usr/local/bin/kubectl

# Same scanner version as the Jenkins lab sheet. The plain zip runs on the
# image's own JDK, so it works on amd64 and arm64 hosts alike.
RUN curl -fsSL --retry 5 --retry-delay 5 --retry-all-errors -o /tmp/scanner.zip \
        "https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-${SONAR_SCANNER_VERSION}.zip" \
    && unzip -q /tmp/scanner.zip -d /opt \
    && mv "/opt/sonar-scanner-${SONAR_SCANNER_VERSION}" /opt/sonar-scanner \
    && rm /tmp/scanner.zip

ENV PATH="/opt/sonar-scanner/bin:${PATH}"

USER jenkins

COPY --chown=jenkins:jenkins plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt

COPY --chown=jenkins:jenkins casc.yaml /usr/share/jenkins/ref/casc.yaml

ENV JAVA_OPTS="-Djenkins.install.runSetupWizard=false" \
    CASC_JENKINS_CONFIG=/usr/share/jenkins/ref/casc.yaml
