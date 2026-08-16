FROM python:3.13-slim

RUN apt-get update && apt-get install -y libopus0 ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Ensure yt-dlp is installed from GitHub (requirements already references git URL)
# Also keep pip updated
RUN python -m pip install --upgrade pip

COPY bot.py .
CMD ["python", "-u", "bot.py"]
