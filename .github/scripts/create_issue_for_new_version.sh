#!/bin/bash

SOFTWARE=$1
APBS="apbs"
PDB2PQR="pdb2pqr"
VERSION_FILE="versions.json"

# Check that argument is 'apbs' or 'pdb2pqr'
if [[ "$SOFTWARE" != "$APBS" && "$SOFTWARE" != "$PDB2PQR" ]]
    then echo "ERROR: argument must be '$APBS' or '$PDB2PQR'"
    exit 1
fi

# Get current version and latest release
CURRENT_VERSION=$(cat $VERSION_FILE | jq -r --arg software "$SOFTWARE" '.[$software]')
LATEST_VERSION=$(gh release view -R electrostatics/$SOFTWARE --json tagName --jq .tagName)
echo "Latest release: $LATEST_VERSION"
echo "Current version ($VERSION_FILE): $CURRENT_VERSION"

# Create new issue if version number differs from versions.json
if [[ "$LATEST_VERSION" =~ ^v[0-9]+\.[0-9]+(\.[0-9]+)+$ ]] # matches on semver format, numbers only
then
    # trim 'v' from version string
    trimmed_version=${LATEST_VERSION:1}

    if [[ "$CURRENT_VERSION" != "$trimmed_version" ]]
    then
        echo "Creating issue to update $VERSION_FILE from $CURRENT_VERSION to $trimmed_version"
        echo "Creating new issue in $TARGET_REPOSITORY"
        gh issue create \
            --title "New ${SOFTWARE^^} release $LATEST_VERSION detected. Update $VERSION_FILE" \
            --body "A new version of ${SOFTWARE^^} (\`$LATEST_VERSION\`) has been released. Please update \`$VERSION_FILE\` to \`\"$SOFTWARE\": \"$trimmed_version\"\`." \
            --repo "$TARGET_REPOSITORY" \
            --assignee Eo300,intendo,mmacduff \
            --label "deployment"
    else
        echo "Issue not created. No change detected in ${SOFTWARE^^} version: $CURRENT_VERSION (current) -> $trimmed_version (latest release)"
    fi

else
    echo "Latest release '$LATEST_VERSION' does not match 'vX.Y.Z' format. No update needed."
fi
