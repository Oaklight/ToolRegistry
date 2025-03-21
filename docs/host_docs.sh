#!/bin/bash

# Ensure the PATH includes standard directories
export PATH="/bin:/usr/bin:/usr/local/bin:$PATH"

# Dynamically determine the paths to commands
declare -A COMMANDS=(
    ["MKDIR"]="$(which mkdir)"
    ["RSYNC"]="$(which rsync)"
    ["SSH"]="$(which ssh)"
    ["REALPATH"]="$(which realpath)"
    ["SED"]="$(which sed)"
)

# Verify all commands are available
for CMD in "${!COMMANDS[@]}"; do
    if [[ -z "${COMMANDS[$CMD]}" ]]; then
        echo "Error: Command '$CMD' not found. Please install it and ensure it's in your PATH."
        exit 1
    fi
    declare "$CMD=${COMMANDS[$CMD]}"
done

# Variables
DOCS_DIR="${DOCS_DIR:-build/html}"                                  # Default Sphinx docs path, can be overridden
DOCS_DIR=$("$REALPATH" "$DOCS_DIR" | "$SED" -e 's/[[:space:]]*$//') # Convert to absolute path and trim trailing spaces
SERVER_HOST="cloud.pol1"
SERVER_DOCS_DIR="domains/toolregistry.lab.oaklight.cn/public_html"

# print out pwd
echo "Current working directory: $(pwd)"

# print out content of DOCS_DIR
echo "Content of DOCS_DIR: $(ls -l "$DOCS_DIR")"

# Function to sync documentation to the remote server and set ownership
sync_to_remote() {
    echo "Creating target directory on the remote server if it doesn't exist..."
    "$SSH" "$SERVER_HOST" "mkdir -p $SERVER_DOCS_DIR"
    if [[ $? -ne 0 ]]; then
        echo "Error: Failed to create target directory on the remote server."
        exit 1
    fi
    echo "Target directory has been created (if it didn't exist)."

    echo "Syncing documentation to the remote server using rsync..."
    "$RSYNC" --rsh="$SSH" -avz --delete "$DOCS_DIR/" "$SERVER_HOST:$SERVER_DOCS_DIR/"
    if [[ $? -ne 0 ]]; then
        echo "Error: Failed to sync documentation to the remote server."
        exit 1
    fi
    echo "Documentation has been synced to the remote server."
}

# Step 1: Ensure Sphinx docs are generated
if [[ ! -d "$DOCS_DIR" ]]; then
    echo "Error: Sphinx documentation not found in $DOCS_DIR. Please run 'make html' first."
    exit 1
fi

# Step 2: Sync Documentation to Server
sync_to_remote

echo "Documentation has been hosted on your server."
