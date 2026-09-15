/*
 * Jenkinsfile — Employee Leave Management System
 * ================================================
 * Declarative Jenkins pipeline with four stages:
 *   Setup → Unit Tests → Integration Tests → System Tests
 *
 * Author  : Eyob Kassaye (ATE/4534/16) — Person 3, Test Automation Engineer & CI/CD
 * Course  : Software Testing & Validation
 *
 * Prerequisites (Jenkins Docker setup):
 *   See docs/jenkins_docker_setup.md for full instructions.
 *
 * Quick start:
 *   docker run -d -p 8080:8080 -p 50000:50000 \
 *     -v jenkins_home:/var/jenkins_home \
 *     -v /var/run/docker.sock:/var/run/docker.sock \
 *     jenkins/jenkins:lts
 */

pipeline {
    agent any

    environment {
        PYTHON      = 'python3'
        VENV_DIR    = '.venv'
        // Selenium target — set to the test server spun up in the System Tests stage
        FLASK_PORT  = '5001'
        SELENIUM_BASE_URL = "http://localhost:${FLASK_PORT}"
        SELENIUM_DRIVER   = 'chrome'
    }

    options {
        // Keep the last 10 builds to save disk space
        buildDiscarder(logRotator(numToKeepStr: '10'))
        // Fail the build if no activity for 30 minutes
        timeout(time: 30, unit: 'MINUTES')
        timestamps()
    }

    stages {

        // ─────────────────────────────────────────────
        // Stage 1: Setup
        // ─────────────────────────────────────────────
        stage('Setup') {
            steps {
                echo '=== Setup: Creating virtual environment and installing dependencies ==='
                sh """
                    ${PYTHON} -m venv ${VENV_DIR}
                    . ${VENV_DIR}/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements.txt
                """
            }
        }

        // ─────────────────────────────────────────────
        // Stage 2: Unit Tests
        // ─────────────────────────────────────────────
        stage('Unit Tests') {
            steps {
                echo '=== Unit Tests: business_logic, routes, decision table, state transitions ==='
                sh """
                    . ${VENV_DIR}/bin/activate
                    python -m pytest \\
                        tests/test_business_logic.py \\
                        tests/test_routes.py \\
                        tests/test_decision_table.py \\
                        tests/test_state_transitions.py \\
                        -m "not defect and not system" \\
                        --cov=app \\
                        --cov-branch \\
                        --cov-report=xml:coverage_unit.xml \\
                        --cov-report=html:htmlcov_unit \\
                        --cov-report=term-missing \\
                        --tb=short \\
                        -v
                """
            }
            post {
                always {
                    // Publish JUnit-compatible XML if junit plugin is installed
                    // junit '**/pytest_unit_results.xml'
                    publishHTML([
                        allowMissing: false,
                        alwaysLinkToLastBuild: true,
                        keepAll: true,
                        reportDir: 'htmlcov_unit',
                        reportFiles: 'index.html',
                        reportName: 'Unit Test Coverage Report'
                    ])
                }
            }
        }

        // ─────────────────────────────────────────────
        // Stage 3: Integration Tests
        // ─────────────────────────────────────────────
        stage('Integration Tests') {
            steps {
                echo '=== Integration Tests: route → business_logic → model → SQLite ==='
                sh """
                    . ${VENV_DIR}/bin/activate
                    python -m pytest \\
                        tests/test_integration.py \\
                        -m "integration and not defect" \\
                        --cov=app \\
                        --cov-branch \\
                        --cov-report=xml:coverage_integration.xml \\
                        --cov-report=html:htmlcov_integration \\
                        --cov-report=term-missing \\
                        --tb=short \\
                        -v
                """
            }
            post {
                always {
                    publishHTML([
                        allowMissing: false,
                        alwaysLinkToLastBuild: true,
                        keepAll: true,
                        reportDir: 'htmlcov_integration',
                        reportFiles: 'index.html',
                        reportName: 'Integration Test Coverage Report'
                    ])
                }
            }
        }

        // ─────────────────────────────────────────────
        // Stage 4: System Tests (Selenium)
        // ─────────────────────────────────────────────
        stage('System Tests') {
            steps {
                echo '=== System Tests: Selenium end-to-end in headless Chrome ==='
                sh """
                    . ${VENV_DIR}/bin/activate

                    # Start Flask app on an unused port (5001) in the background
                    FLASK_RUN_PORT=${FLASK_PORT} python run.py &
                    FLASK_PID=\$!
                    echo "Flask PID: \$FLASK_PID"

                    # Wait up to 20 s for the server to accept connections
                    for i in \$(seq 1 20); do
                        curl -s http://localhost:${FLASK_PORT} > /dev/null && \\
                            echo "Server ready after \${i}s" && break
                        sleep 1
                    done

                    # Run Selenium tests
                    python -m pytest \\
                        tests/selenium/test_leave_workflow.py \\
                        -m "system and not defect" \\
                        --tb=short \\
                        -v || SYSTEM_TEST_EXIT=\$?

                    # Always kill the Flask server
                    kill \$FLASK_PID 2>/dev/null || true

                    # Propagate the exit code from pytest
                    exit \${SYSTEM_TEST_EXIT:-0}
                """
            }
        }

        // ─────────────────────────────────────────────
        // Stage 5: Defect Probes (informational)
        // ─────────────────────────────────────────────
        stage('Defect Probes') {
            steps {
                echo '=== Defect Probes: Expected to fail — shows open defects ==='
                // catchError keeps the pipeline from failing hard on known defects
                catchError(buildResult: 'UNSTABLE', stageResult: 'UNSTABLE') {
                    sh """
                        . ${VENV_DIR}/bin/activate
                        python -m pytest \\
                            -m defect \\
                            --tb=short \\
                            -v
                    """
                }
            }
        }
    }

    post {
        always {
            echo '=== Pipeline complete — archiving artefacts ==='
            archiveArtifacts artifacts: 'htmlcov_*/**', allowEmptyArchive: true
            archiveArtifacts artifacts: 'coverage_*.xml', allowEmptyArchive: true
        }
        success {
            echo '✅ All required stages passed.'
        }
        unstable {
            echo '⚠️  Build is UNSTABLE — defect probes failed (open defects remain).'
        }
        failure {
            echo '❌ Build FAILED — a required stage did not pass.'
        }
    }
}
