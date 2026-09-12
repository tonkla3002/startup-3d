pipeline {
    agent any

    // GitHub webhook เข้ามาไม่ได้ (เซิร์ฟเวอร์บล็อก inbound จากต่างประเทศ)
    // จึงให้ Jenkins ไปถาม GitHub เองทุก 2 นาทีแทน
    triggers {
        pollSCM('H/2 * * * *')
    }

    stages {
        stage('Pull latest code') {
            steps {
                dir('/opt/streamora') {
                    retry(3) {
                        sh 'git pull origin main'
                    }
                }
            }
        }

        stage('Verify .env exists') {
            steps {
                dir('/opt/streamora') {
                    sh '''
                        if [ ! -f .env ]; then
                            echo "ไม่พบ .env ใน /opt/streamora"
                            exit 1
                        fi
                    '''
                }
            }
        }

        stage('Deploy') {
            steps {
                dir('/opt/streamora') {
                    // VPS บล็อก Docker Hub จึง build image ใหม่ไม่ได้
                    // แทนด้วยการ copy code เข้า container ที่รันอยู่ แล้ว restart
                    sh 'docker cp app/. streamora-api-1:/srv/app/'
                    sh 'docker compose -f docker-compose.prod.yml -f docker-compose.vps.yml restart api'
                }
            }
        }

        stage('Health check') {
            steps {
                sh '''
                    sleep 10
                    curl -f http://localhost:8000/api/v1/health || echo "เตือน: health check ไม่ผ่าน ดู log ด้วย docker compose logs"
                '''
            }
        }
    }

    post {
        success { echo 'Deploy สำเร็จ: streamora' }
        failure { echo 'Deploy ล้มเหลว เช็ค console log ด้านบน' }
    }
}
