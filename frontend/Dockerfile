# Build stage
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# Serve stage
FROM nginx:stable-alpine

# Fix: run as root so nginx can write pid file
RUN sed -i 's|user  nginx;|user root;|g' /etc/nginx/nginx.conf

# Fix: use /tmp for pid file (writable even with restricted containers)
RUN sed -i 's|pid\s\+/run/nginx.pid;|pid /tmp/nginx.pid;|g' /etc/nginx/nginx.conf

# Update nginx.conf to listen on 15731
COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN sed -i 's/listen 80;/listen 15731;/g' /etc/nginx/conf.d/default.conf

COPY --from=build /app/dist /usr/share/nginx/html

# Override entrypoint: bypass privilege drop so nginx runs as root
ENTRYPOINT []
EXPOSE 15731
CMD ["nginx", "-g", "daemon off;"]