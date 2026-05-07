#!/usr/bin/env bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd "$SCRIPT_DIR" || exit

if [ -n "${ARKIVE_SECRET_KEY_FILE}" ]; then
    KEY_FILE="${ARKIVE_SECRET_KEY_FILE}"
else
    KEY_FILE=".arkive_secret_key"
fi

PORT="${PORT:-8080}"
HOST="${HOST:-0.0.0.0}"
if test "$ARKIVE_SECRET_KEY $ARKIVE_JWT_SECRET_KEY" = " "; then
  echo "Loading ARKIVE_SECRET_KEY from file, not provided as an environment variable."

  if ! [ -e "$KEY_FILE" ]; then
    echo "Generating ARKIVE_SECRET_KEY"
    # Generate a random value to use as a ARKIVE_SECRET_KEY in case the user didn't provide one.
    echo $(head -c 12 /dev/random | base64) > "$KEY_FILE"
  fi

  echo "Loading ARKIVE_SECRET_KEY from $KEY_FILE"
  ARKIVE_SECRET_KEY=$(cat "$KEY_FILE")
fi


# Check if SPACE_ID is set, if so, configure for space
if [ -n "$SPACE_ID" ]; then
  echo "Configuring for HuggingFace Space deployment"
  if [ -n "$ADMIN_USER_EMAIL" ] && [ -n "$ADMIN_USER_PASSWORD" ]; then
    echo "Admin user configured, creating"
    ARKIVE_SECRET_KEY="$ARKIVE_SECRET_KEY" uvicorn arkive.main:app --host "$HOST" --port "$PORT" --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}" &
    arkive_pid=$!
    echo "Waiting for arkive to start..."
    while ! curl -s "http://localhost:${PORT}/health" > /dev/null; do
      sleep 1
    done
    echo "Creating admin user..."
    curl \
      -X POST "http://localhost:${PORT}/api/v1/auths/signup" \
      -H "accept: application/json" \
      -H "Content-Type: application/json" \
      -d "{ \"email\": \"${ADMIN_USER_EMAIL}\", \"password\": \"${ADMIN_USER_PASSWORD}\", \"name\": \"Admin\" }"
    echo "Shutting down arkive..."
    kill $arkive_pid
  fi

  export ARKIVE_URL=${SPACE_HOST}
fi

PYTHON_CMD=$(command -v python3 || command -v python)
UVICORN_WORKERS="${UVICORN_WORKERS:-1}"

# If script is called with arguments, use them; otherwise use default workers
if [ "$#" -gt 0 ]; then
    ARGS=("$@")
else
    ARGS=(--workers "$UVICORN_WORKERS")
fi

# Run uvicorn
ARKIVE_SECRET_KEY="$ARKIVE_SECRET_KEY" exec "$PYTHON_CMD" -m uvicorn arkive.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}" \
    "${ARGS[@]}"
