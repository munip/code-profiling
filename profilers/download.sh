#!/bin/bash
# Download profilers locally for Docker build
# Run this script on your local machine before building Docker image

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILERS_DIR="$(dirname "$SCRIPT_DIR")/profilers"

echo "Downloading profilers to: $PROFILERS_DIR"

mkdir -p "$PROFILERS_DIR/async-profiler"

# Detect architecture
ARCH=$(uname -m)
echo "Detected architecture: $ARCH"

# Download async-profiler (architecture-aware)
if [ "$ARCH" = "aarch64" ]; then
    FILENAME="async-profiler-3.0-linux-arm64.tar.gz"
else
    FILENAME="async-profiler-3.0-linux-x64.tar.gz"
fi

echo "Downloading async-profiler: $FILENAME"
curl -L "https://github.com/async-profiler/async-profiler/releases/download/v3.0/$FILENAME" -o /tmp/profiler.tar.gz

echo "Extracting async-profiler..."
tar -xzf /tmp/profiler.tar.gz -C "$PROFILERS_DIR/async-profiler"
mv "$PROFILERS_DIR/async-profiler/async-profiler-"*/* "$PROFILERS_DIR/async-profiler/" 2>/dev/null || true
rm -rf "$PROFILERS_DIR/async-profiler/async-profiler-"*
rm /tmp/profiler.tar.gz

echo "async-profiler installed"

# Download austin
echo "Downloading austin..."
curl -L "https://github.com/nickparajon/austin/releases/download/2.1.2/austin-2.1.2-x64.gz" -o /tmp/austin.gz
gunzip -f /tmp/austin.gz
chmod +x /tmp/austin
mv /tmp/austin "$PROFILERS_DIR/austin"

echo "austin installed"

echo ""
echo "Profilers downloaded successfully!"
echo "  - async-profiler: $PROFILERS_DIR/async-profiler/"
echo "  - austin: $PROFILERS_DIR/austin"
