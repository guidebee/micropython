pipeline {
    agent any

    stages {
        stage('build-mpy-cross') {
                steps {
                    sh "cd mpy-cross; make "
                }
            }
        stage('build-stem32') {
                        steps {
                            sh "cd ports/stm32; make BOARD=PYBV11"
                        }
                    }

    }

    post {
            success {
                archiveArtifacts artifacts: 'build-PYBV11/firmware.dfu', fingerprint: true

            }
        }
}
