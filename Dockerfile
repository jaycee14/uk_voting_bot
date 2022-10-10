# https://cloud.google.com/run/docs/quickstarts/build-and-deploy/deploy-python-service
# Use the official lightweight Python image.
# https://hub.docker.com/_/python

# build locally
# docker build -t uk_voting_bot:latest .

#run locally
# docker run -p 8080:8080 uk_voting_bot:latest

FROM python:3.8-slim AS uk_voting_bot

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED True

# Copy local code to the container image.
ENV APP_HOME /app
WORKDIR $APP_HOME
COPY requirements.txt ./
# Install production dependencies.
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

# Bucket Name
ENV MP_BUCKET_NAME=uk-voting-bot-cloud-bucket-110922
# for debug
# ENV GOOGLE_APPLICATION_CREDENTIALS=uk-voting-bot-2c521de46d41.json
# ENV PORT=8080

# CMD python main.py
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app