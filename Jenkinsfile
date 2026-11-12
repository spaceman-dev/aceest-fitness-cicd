// ACEest Fitness & Gym - Jenkins pipeline
//
//   every branch  : lint, unit tests, image build, tests inside the image
//   main          : + SonarQube analysis / quality gate, publish build image,
//                   then release to Kubernetes through all five strategies
//   tag vX.Y.Z    : + publish the release image X.Y.Z
//
// Each build archives versioned artifacts (wheel, source tarball, release.json).
// Every strategy script verifies its rollout and reverts on its own if the new
// version fails (see scripts/deploy-*.sh); Jenkinsfile.rollback is the manual way back.

pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '30', artifactNumToKeepStr: '30'))
        timeout(time: 30, unit: 'MINUTES')
    }

    triggers {
        // Jenkins runs on a laptop that GitHub cannot reach, so it polls instead of using a webhook
        pollSCM('H/2 * * * *')
    }

    parameters {
        string(name: 'STRATEGIES', defaultValue: 'rolling,blue-green,canary,ab-testing,shadow',
               description: 'Release strategies to run for a main build (comma separated)')
        choice(name: 'FAULT_INJECTION', choices: ['none', 'unhealthy', 'errors'],
               description: 'Rollback drill: start the new pods with a fault and let the pipeline revert them')
    }

    environment {
        IMAGE_REPO = "${env.ACEEST_IMAGE_REPO ?: '192.168.89.10:5000/aceest-fitness'}"
        VENV = '.venv-ci'
        PIP_DISABLE_PIP_VERSION_CHECK = '1'
        PYTHONDONTWRITEBYTECODE = '1'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                script {
                    env.APP_VERSION = sh(returnStdout: true,
                        script: '''awk -F'"' '/^__version__/ {print $2}' aceest/__init__.py''').trim()
                    env.GIT_SHORT = sh(returnStdout: true, script: 'git rev-parse --short=7 HEAD').trim()
                    env.IMAGE_TAG = "${env.APP_VERSION}-${env.GIT_SHORT}"
                    currentBuild.displayName = "#${env.BUILD_NUMBER} v${env.APP_VERSION}"
                    if (env.TAG_NAME && env.TAG_NAME != "v${env.APP_VERSION}") {
                        error("Tag ${env.TAG_NAME} does not match the application version ${env.APP_VERSION}")
                    }
                }
                sh 'git --no-pager log -1 --pretty="Building %h: %s (%an)"'
            }
        }

        stage('Install') {
            steps {
                sh '''
                    python3 -m venv "$VENV"
                    "$VENV/bin/pip" install -q -r requirements-dev.txt
                '''
            }
        }

        stage('Lint') {
            steps {
                sh '"$VENV/bin/flake8" .'
            }
        }

        stage('Unit Tests') {
            steps {
                sh '"$VENV/bin/pytest" --junitxml=reports/junit.xml --cov-report=xml:reports/coverage.xml'
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'reports/junit.xml'
                    recordCoverage(tools: [[parser: 'COBERTURA', pattern: 'reports/coverage.xml']],
                                   sourceCodeRetention: 'NEVER')
                }
            }
        }

        stage('SonarQube Analysis') {
            when { branch 'main' }
            steps {
                withSonarQubeEnv('sonarqube') {
                    sh 'sonar-scanner -Dsonar.projectVersion="$APP_VERSION"'
                }
            }
        }

        stage('Quality Gate') {
            when { branch 'main' }
            steps {
                timeout(time: 5, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
            }
        }

        stage('Build Image') {
            steps {
                sh '''
                    docker build --target test -t "aceest-fitness-test:$IMAGE_TAG" .
                    docker build --target runtime \
                        --build-arg APP_VERSION="$APP_VERSION" \
                        --build-arg GIT_COMMIT="$GIT_COMMIT" \
                        -t "$IMAGE_REPO:$IMAGE_TAG" .
                '''
            }
        }

        stage('Test in Container') {
            steps {
                // the full Pytest suite, inside the image built from this commit
                sh 'docker run --rm "aceest-fitness-test:$IMAGE_TAG"'
                // and the runtime image: becomes healthy, runs as non-root, reports its version
                sh '''
                    cid=$(docker run -d -e ACEEST_TRACK=ci "$IMAGE_REPO:$IMAGE_TAG")
                    trap 'docker rm -f "$cid" >/dev/null 2>&1 || true' EXIT
                    state=starting
                    for i in $(seq 1 30); do
                        state=$(docker inspect -f '{{.State.Health.Status}}' "$cid")
                        [ "$state" = healthy ] && break
                        sleep 2
                    done
                    if [ "$state" != healthy ]; then docker logs "$cid"; exit 1; fi
                    if [ "$(docker exec "$cid" id -u)" = 0 ]; then echo "image runs as root"; exit 1; fi
                    docker exec -e EXPECTED="$APP_VERSION" "$cid" python -c "
import json, os, urllib.request
body = json.load(urllib.request.urlopen('http://127.0.0.1:5000/api/health', timeout=5))
assert body['version'] == os.environ['EXPECTED'], body
print('runtime image OK:', body)
"
                '''
            }
        }

        stage('Package') {
            steps {
                sh '''
                    rm -rf dist && mkdir -p dist
                    "$VENV/bin/pip" wheel -q --no-deps -w dist .
                    git archive --format=tar.gz --prefix="aceest-fitness-$APP_VERSION/" \
                        -o "dist/aceest-fitness-$APP_VERSION-src.tar.gz" HEAD
                    printf '{"version": "%s", "commit": "%s", "image": "%s", "build": "%s"}\n' \
                        "$APP_VERSION" "$GIT_COMMIT" "$IMAGE_REPO:$IMAGE_TAG" "$BUILD_TAG" > dist/release.json
                '''
                archiveArtifacts artifacts: 'dist/*', fingerprint: true
            }
        }

        stage('Publish Image') {
            when { anyOf { branch 'main'; buildingTag() } }
            steps {
                script {
                    if (env.ACEEST_REGISTRY_CREDENTIALS) {
                        registryLogin(env.ACEEST_REGISTRY_CREDENTIALS)
                    }
                    if (env.TAG_NAME) {
                        sh '''
                            docker tag "$IMAGE_REPO:$IMAGE_TAG" "$IMAGE_REPO:$APP_VERSION"
                            docker push "$IMAGE_REPO:$APP_VERSION"
                        '''
                    } else {
                        sh '''
                            docker push "$IMAGE_REPO:$IMAGE_TAG"
                            docker tag "$IMAGE_REPO:$IMAGE_TAG" "$IMAGE_REPO:latest"
                            docker push "$IMAGE_REPO:latest"
                        '''
                    }
                }
            }
        }

        stage('Deploy to Kubernetes') {
            when { branch 'main' }
            environment {
                IMAGE = "${env.IMAGE_REPO}:${env.IMAGE_TAG}"
                TEST_IMAGE = "aceest-fitness-test:${env.IMAGE_TAG}"
                INGRESS = "${env.ACEEST_INGRESS ?: 'http://192.168.89.2'}"
                DOCKER_NETWORK = "${env.ACEEST_DOCKER_NETWORK ?: 'aceest-net'}"
            }
            parallel {
                stage('Rolling Update') {
                    when { expression { wanted('rolling') } }
                    steps { release('rolling') }
                }
                stage('Blue-Green') {
                    when { expression { wanted('blue-green') } }
                    steps { release('blue-green') }
                }
                stage('Canary') {
                    when { expression { wanted('canary') } }
                    steps { release('canary') }
                }
                stage('A/B Testing') {
                    when { expression { wanted('ab-testing') } }
                    steps { release('ab-testing') }
                }
                stage('Shadow') {
                    when { expression { wanted('shadow') } }
                    steps { release('shadow') }
                }
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'reports/*', allowEmptyArchive: true
        }
        success {
            echo "v${env.APP_VERSION} (${env.GIT_SHORT}) passed every stage"
        }
        failure {
            echo "v${env.APP_VERSION} (${env.GIT_SHORT}) failed - nothing was published"
        }
        cleanup {
            sh 'docker rmi "aceest-fitness-test:$IMAGE_TAG" >/dev/null 2>&1 || true'
            cleanWs()
        }
    }
}

boolean wanted(String strategy) {
    def selected = (params.STRATEGIES ?: 'rolling,blue-green,canary,ab-testing,shadow').split(',').collect { it.trim() }
    return selected.contains(strategy)
}

void release(String strategy) {
    def fault = params.FAULT_INJECTION ?: 'none'
    withCredentials([file(credentialsId: 'kubeconfig-aceest', variable: 'KUBECONFIG')]) {
        withEnv(["FAULT=${fault == 'none' ? '' : fault}", "BUILD_LABEL=jenkins #${env.BUILD_NUMBER}"]) {
            sh "scripts/deploy-${strategy}.sh"
        }
    }
}

// Only needed for registries that require auth (e.g. Docker Hub); the local
// registry used during development accepts anonymous pushes.
void registryLogin(String credentialsId) {
    withCredentials([usernamePassword(credentialsId: credentialsId,
                                      usernameVariable: 'REG_USER',
                                      passwordVariable: 'REG_PASS')]) {
        sh 'echo "$REG_PASS" | docker login -u "$REG_USER" --password-stdin "${IMAGE_REPO%%/*}"'
    }
}
