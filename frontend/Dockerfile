# 1. Build Stage
FROM node:20-alpine AS builder

WORKDIR /app

# 의존성 설치
COPY package*.json ./
RUN npm install

# 소스 코드 복사 및 빌드 수행
COPY . .
RUN npm run build

# 2. Production Stage (Nginx)
FROM nginx:alpine

# Nginx 기본 설정의 html 서빙 폴더로 빌드된 정적 파일 복사
COPY --from=builder /app/dist /usr/share/nginx/html

# 포트 노출
EXPOSE 80

# Nginx 실행
CMD ["nginx", "-g", "daemon off;"]
