#!/bin/bash

START_CMD="uvicorn app.main:app --reload"
HEALTH_URL="http://localhost:8000/api/v1/health/restart"
CHECK_INTERVAL=5
WAIT_TIME=15

start_service() {
    echo "$(date) - starting service..."
    $START_CMD &
    SERVICE_PID=$!
    echo "$(date) - service started, PID: $SERVICE_PID"
}

stop_service() {
    if [ ! -z "$SERVICE_PID" ]; then
        echo "$(date) - stopping service, PID: $SERVICE_PID..."
        kill $SERVICE_PID
        wait $SERVICE_PID 2>/dev/null
        echo "$(date) - service stopped"
    fi
}

trap 'stop_service; exit' SIGINT SIGTERM

start_service

while true; do
    sleep $CHECK_INTERVAL

    if ! ps -p $SERVICE_PID > /dev/null; then
        echo "$(date) - service unexpectedly terminated, restarting..."
        start_service
        continue
    fi

    RESPONSE=$(curl -s $HEALTH_URL)
    if [[ -n "$RESPONSE" ]]; then
        restart_flag=$(echo "$RESPONSE" | jq -r '.restart' 2>/dev/null)
        if [[ "$restart_flag" == "true" || "$restart_flag" == "True" ]]; then
            echo "$(date) - detected restart signal: $RESPONSE"
            sleep $WAIT_TIME
            echo "$(date) - restarting service..."
            stop_service
            start_service
        fi
    fi
done

# curl -X POST http://localhost:8000/api/v1/health/restart
