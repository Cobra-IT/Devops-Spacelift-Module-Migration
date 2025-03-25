# Azure DevOps to Spacelift Module Migration Tool

This tool automates the migration of Terraform modules from Azure DevOps repositories to Spacelift. It handles repository cloning, module creation, version management, and provides both interactive and automated workflows.

## Features

- Securely authenticate with Azure DevOps and Spacelift
- Scan and analyze Azure DevOps repositories for Terraform modules
- Create corresponding modules in Spacelift with proper configuration
- Migrate semantic version tags from repositories
- Configure module settings globally or per-module
- Support for batch processing with automatic mode
- Secure credential management

## Prerequisites

- Python 3.7+
- Git installed and available in PATH
- Spacelift CLI (`spacectl`) installed and configured
- Azure DevOps Personal Access Token (PAT) with read access to repositories
- Spacelift account with module creation permissions

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/azure-devops-to-spacelift-migration.git
   cd azure-devops-to-spacelift-migration
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the migration script:

```bash
python Spacelift_Module_migration_script_v1.3.py
```

The script will guide you through the migration process with interactive prompts.

## Configuration Options

### Azure DevOps Configuration

- **Organization Name**: Your Azure DevOps organization
- **Project Name**: The Azure DevOps project containing your Terraform modules
- **Personal Access Token**: A PAT with read access to repositories

### Spacelift Configuration

- **Organization Name**: Your Spacelift organization name
- **Space**: The Spacelift space where modules will be created
- **VCS Integration**: The Azure DevOps integration to use for modules

### Global Module Options

These options can be configured once and applied to all modules:

| Option | Description | Default |
|--------|-------------|---------|
| Workflow Tool | OpenTofu or Terraform | OpenTofu |
| Administrative | Whether modules have administrative privileges | False |
| Local Preview | Enable local preview functionality | False |
| Protection | Protect modules from deletion | True |
| Project Root | Subfolder containing Terraform files | "" (root) |
| Labels | Tags to apply to modules | [] |

### Per-Module Options

Each module can override global settings with custom configurations:

- Custom workflow tool
- Administrative status
- Local preview setting
- Deletion protection
- Project root directory
- Custom labels

## Processing Modes

### Interactive Mode

By default, the script prompts for confirmation before processing each repository.

### Automatic Mode

During repository processing, you can switch to automatic mode by selecting the 'a' option. This will:

1. Process all remaining repositories without further prompts
2. Apply the same settings to all remaining modules
3. Continue with the last selected options for module creation

## Version Management

The script handles module versioning with the following rules:

- Only semantic version tags (e.g., v1.0.0, 1.2.3) are migrated
- Each commit is processed only once, even if multiple tags point to it
- Tags are sorted chronologically by commit date
- Non-semantic tags can be converted to semantic format

## Security

- Azure DevOps PAT tokens can be securely stored in the system keyring
- Credentials can be purged after migration is complete
- No credentials are stored in plain text

## Troubleshooting

### Common Issues

1. **Authentication Failures**:
   - Ensure your Azure DevOps PAT has sufficient permissions
   - Verify Spacelift CLI is properly authenticated with `spacectl profile login`

2. **Module Creation Errors**:
   - Check that your Spacelift account has module creation permissions
   - Verify the Azure DevOps integration in Spacelift is properly configured
   - Ensure repository names follow Spacelift naming conventions

3. **Version Creation Errors**:
   - Verify that tags in your repositories follow semantic versioning
   - Check that the commits referenced by tags exist in the repository

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Spacelift for their GraphQL API
- Azure DevOps for their REST API
- The Python community for excellent libraries