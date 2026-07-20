# Stage 1: Build the React application
FROM node:22-alpine AS build

WORKDIR /app

# Copy package files
COPY package.json ./
# Install dependencies (using legacy peer deps for React 19 compatibility)
RUN npm install --legacy-peer-deps

# Copy rest of the frontend source code
COPY . .

# Build the project
RUN npm run build

# Stage 2: Serve static files with Nginx
FROM nginx:stable-alpine

# Copy custom nginx configuration (optional, fallback to default)
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
