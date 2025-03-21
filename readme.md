# Spacelift Module Migration Tool

A Python-based utility for migrating Terraform modules from Azure DevOps repositories to Spacelift.

## Overview

This tool automates the process of migrating Terraform modules from Azure DevOps repositories to Spacelift. It handles repository cloning, module creation, and version management to streamline the migration workflow.

## Features

- Interactive command-line interface
- Secure credential management using system keyring
- Automatic repository analysis for Terraform files
- Spacelift module creation with version history
- Migration logging for audit purposes
- Support for multiple repositories
- Configurable space targeting in Spacelift

## Prerequisites

- Python 3.6+
- Git
- Spacelift CLI (`spacectl`) installed and configured
- Azure DevOps Personal Access Token (PAT) with repository access
- Spacelift account with module creation permissions

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/Cobra-IT/Devops-Spacelift-Module-Migration.git
   ```

2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Required Python Packages

- requests
- GitPython
- keyring
- typing

## Usage

Run the script with Python:

```bash
python Spacelift_Module_migration_script.py
```

The script will guide you through the following steps:

1. Configuration setup (Azure DevOps organization, project, and Spacelift organization)
2. Authentication with Azure DevOps and Spacelift
3. Repository selection
4. Module migration with version creation
5. Cleanup

## Workflow

1. **Configuration**: Enter your Azure DevOps organization, project, and Spacelift organization details.
2. **Authentication**: Provide your Azure DevOps PAT and authenticate with Spacelift.
3. **Repository Selection**: Choose which repositories to migrate.
4. **Analysis**: The script analyzes repositories for Terraform files.
5. **Migration**: Creates Spacelift modules for repositories containing Terraform files.
6. **Version Creation**: Creates versions in Spacelift based on repository tags.
7. **Cleanup**: Optionally removes temporary files and stored credentials.

## Security

- Azure DevOps PAT is stored securely in your system's keyring
- Credentials can be purged after migration
- No credentials are written to disk

## Troubleshooting

- **Authentication Issues**: Ensure your Azure DevOps PAT has sufficient permissions
- **Spacelift Connection Problems**: Verify your Spacelift CLI is properly configured
- **Repository Access Errors**: Check that your Azure DevOps integration in Spacelift is properly set up

## Logs

The script generates a `migration_log.txt` file with timestamps for all migration activities, which can be used for auditing or troubleshooting.

## Configuration

The script creates a `migration_config.json` file to store your configuration for future runs.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
