pipeline {
    agent any
    
    parameters {
        string(name: 'OPENAI_API_KEY', defaultValue: '', description: 'OpenAI API Key (optional)')
    }
    
    environment {
        REPO_URL = 'https://github.com/amitavroy/sapience.git'
        SSH_CREDENTIAL_ID = 'webdev-242'
        DEPLOY_SERVER = 'autodevops@192.168.7.242'
        DEPLOY_BASE_PATH = '/mnt/data/sapience'
    }
    
    stages {
        stage('Checkout') {
            steps {
                sshagent(credentials: ["${SSH_CREDENTIAL_ID}"]) {
                    sh '''
                        ssh -o StrictHostKeyChecking=no ${DEPLOY_SERVER} "
                            cd ${DEPLOY_BASE_PATH} &&
                            git config --global --add safe.directory ${DEPLOY_BASE_PATH} &&
                            if [ ! -d .git ]; then
                                git clone ${REPO_URL} .
                            else
                                git pull origin main || (rm -rf .git && git clone ${REPO_URL} .)
                            fi
                        "
                    '''
                }
            }
        }
        
        stage('Setup Environment & Build') {
            steps {
                withCredentials([file(credentialsId: 'sapiene-env', variable: 'ENV_FILE')]) {
                    sshagent(credentials: ["${SSH_CREDENTIAL_ID}"]) {
                        sh """
                            scp -o StrictHostKeyChecking=no \${ENV_FILE} ${DEPLOY_SERVER}:${DEPLOY_BASE_PATH}/.env
                            ssh -o StrictHostKeyChecking=no ${DEPLOY_SERVER} "cd ${DEPLOY_BASE_PATH} &&
                            sed -i '/^OPENAI_API_KEY=/d' .env &&
                            echo 'OPENAI_API_KEY=${params.OPENAI_API_KEY}' >> .env &&
                            docker compose build
                            "
                        """
                    }
                }
            }
        }
        
        stage('Deploy') {
            steps {
                sshagent(credentials: ["${SSH_CREDENTIAL_ID}"]) {
                    sh '''
                        ssh -o StrictHostKeyChecking=no ${DEPLOY_SERVER} "
                            cd ${DEPLOY_BASE_PATH} &&
                            docker compose down &&
                            docker compose up -d &&
                            sleep 10 &&
                            docker compose exec -T php php artisan key:generate --force &&
                            sleep 30
                            docker compose exec -T php php artisan migrate --force && 
                            sleep 30
                            docker compose exec -T php npm run build && 
                            sleep 60
                            docker compose exec -T php php artisan wayfinder:generate
                        "
                    '''
                }
            }
        }
    }
    
    post {
        success {
            echo 'Deployment completed successfully!'
        }
        failure {
            echo 'Deployment failed!'
        }
        always {
            cleanWs()
        }
    }
}
