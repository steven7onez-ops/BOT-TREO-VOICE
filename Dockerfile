FROM node:24-slim

# Cài ffmpeg
RUN apt-get update && apt-get install -y ffmpeg python3 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY package*.json ./
RUN npm install --omit=dev

COPY . .

# Tạo thư mục cần thiết
RUN mkdir -p database audio_cache

CMD ["node", "index.js"]
