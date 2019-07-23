pipeline {
    agent any



    stages {
        stage('build-mpy-cross') {
                steps {
                    sh "cd mpy-cross; make "
                }
            }

    }
}
