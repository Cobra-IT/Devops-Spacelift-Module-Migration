import os
import requests
import subprocess
import json
import base64
import keyring
from git import Repo
from typing import List, Dict, Any, Optional
import time
import shutil
import sys
from datetime import datetime
import re

class InteractiveMigration:
    def __init__(self):
        self.azure_org = None
        self.azure_project = None
        self.spacelift_org = None
        self.temp_dir = "temp_modules"
        self.migration_log = []
        self.config_file = 'migration_config.json'
        self.service_id = "azure_devops_migration"
        self.username = "default"
        self.bearer_token = None  # Initialize token as None
        
        # Global module options with defaults
        self.global_options = {
            "workflowTool": "OPEN_TOFU",  # Default to OpenTofu
            "administrative": False,
            "localPreviewEnabled": False,
            "protectFromDeletion": True,
            "terraformProvider": "default",
            "projectRoot": "",
            "labels": []
        }

    # Helper function to post GraphQL queries
    def graphql_post(self, query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
        api_url = f"https://{self.spacelift_org}.app.spacelift.io/graphql"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.bearer_token}"
        }
        response = requests.post(api_url, json={"query": query, "variables": variables}, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"GraphQL request failed with status {response.status_code}")

    def get_spacectl_token(self) -> bool:
        print("\n🔐 Authenticating with Spacelift...")
        try:
            subprocess.run(['spacectl', 'profile', 'login'], check=True)
            token_result = subprocess.run(
                ['spacectl', 'profile', 'export-token'],
                capture_output=True,
                text=True,
                check=True
            )
            self.bearer_token = token_result.stdout.strip()
            print("✅ Successfully authenticated with Spacelift")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Error during Spacelift authentication: {e}")
            return False

    def store_credentials(self, pat: str):
        keyring.set_password(self.service_id, self.username, pat)  # Changed from self.service_id to self.service_id
        print("✅ Credentials securely stored for future use")

    def get_stored_credentials(self) -> str:
        return keyring.get_password(self.service_id, self.username)  # Changed from self.service_id to self.service_id

    def save_config(self):
        config = {
            'azure_org': self.azure_org,
            'azure_project': self.azure_project,
            'spacelift_org': self.spacelift_org
        }
        with open(self.config_file, 'w') as f:  # Changed from self.config_file to self.config_file
            json.dump(config, f)

    def load_config(self) -> Optional[Dict[str, Any]]:
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                return config
        except:
            return None

    def log_migration(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.migration_log.append(f"{timestamp}: {message}")

    def save_migration_log(self) -> None:
        with open('migration_log.txt', 'w') as f:
            f.write('\n'.join(self.migration_log))

    def get_user_input(self) -> bool:
        print("\n🔷 Configuration Setup")
        saved_config = self.load_config()
        default_azure_org = saved_config.get('azure_org', '') if saved_config else ''
        default_azure_project = saved_config.get('azure_project', '') if saved_config else ''
        default_spacelift_org = saved_config.get('spacelift_org', '') if saved_config else ''
        
        self.azure_org = input(f"Enter your Azure DevOps organization name [{default_azure_org}]: ").strip() or default_azure_org
        self.azure_project = input(f"Enter your Azure DevOps project name [{default_azure_project}]: ").strip() or default_azure_project
        spacelift_input = input(f"Enter your Spacelift organization name [{default_spacelift_org}]: ").strip() or default_spacelift_org
        self.spacelift_org = spacelift_input.replace('https://', '').replace('.app.spacelift.io', '')
        
        print("\n📋 Confirming configuration:")
        print(f"Azure Organization: {self.azure_org}")
        print(f"Azure Project: {self.azure_project}")
        print(f"Spacelift Organization: {self.spacelift_org}")
        
        confirm = input("\nIs this configuration correct? (y/n): ")
        if confirm.lower() == 'y':
            self.save_config()
            return True
        return False

    def validate_credentials(self) -> bool:
        print("\n🔑 Checking for stored credentials...")
        
        try:
            azure_pat = self.get_stored_credentials()
            print(f"Debug - Retrieved PAT: {'*****' + azure_pat[-4:] if azure_pat else 'None'}")
        except Exception as e:
            print(f"Error retrieving credentials from keyring: {str(e)}")
            azure_pat = None
        
        if not azure_pat:
            azure_pat = input("Enter your Azure DevOps PAT token: ")
            store = input("Would you like to store this token securely for future use? (y/n): ")
            if store.lower() == 'y':
                try:
                    self.store_credentials(azure_pat)
                    # Verify storage worked
                    verification = self.get_stored_credentials()
                    if verification:
                        print("✅ Verified credentials were stored successfully")
                    else:
                        print("⚠️ Failed to verify stored credentials")
                except Exception as e:
                    print(f"Error storing credentials in keyring: {str(e)}")
                    print("⚠️ Will continue without storing credentials")
        else:
            print("✅ Found stored credentials!")
        
        # Add validation check
        if not azure_pat or len(azure_pat.strip()) == 0:
            raise ValueError("Azure PAT token is empty or invalid")
        
        # Changed from "AZURE_DEVOPS_PAT" to "AZURE_DEVOPS_PAT"
        os.environ["AZURE_DEVOPS_PAT"] = azure_pat
        return True

    def get_azure_repos(self) -> List[dict]:
        print("\n🔍 Fetching repositories from Azure DevOps...")
        pat = os.getenv("AZURE_DEVOPS_PAT")
        encoded_pat = base64.b64encode(f":{pat}".encode()).decode()
        url = f"https://dev.azure.com/{self.azure_org}/{self.azure_project}/_apis/git/repositories?api-version=7.1"
        headers = {
            "Authorization": f"Basic {encoded_pat}",
            "Accept": "application/json"
        }
        print("Connecting to Azure DevOps API...")
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            repos = response.json().get("value", [])
            print(f"✅ Successfully retrieved {len(repos)} repositories")
            return repos
        else:
            print(f"Error: Status code {response.status_code}. Please verify your details.")
            retry = input("Would you like to enter credentials again? (y/n): ").strip()
            if retry.lower() == 'y':
                os.environ["AZURE_DEVOPS_PAT"] = input("Enter your Azure DevOps PAT token: ").strip()
                return self.get_azure_repos()
            return []

    def clone_repo(self, repo_url: str, local_path: str, repo_name: str):
        print(f"\n📥 Cloning repository: {repo_name}")
        
        # Handle spaces in paths and URLs
        pat = os.getenv("AZURE_DEVOPS_PAT")  # Changed from AZURE_PAT_ENV
        encoded_project = self.azure_project.replace(" ", "%20")
        encoded_repo = repo_name.replace(" ", "%20")
        auth_url = f"https://{pat}@dev.azure.com/{self.azure_org}/{encoded_project}/_git/{encoded_repo}"
        
        # Create safe local path
        safe_local_path = os.path.join(self.temp_dir, repo_name.replace(" ", "_"))  # Changed from self.TEMP_DIR
        
        # Check if directory exists using safe_local_path
        if os.path.exists(safe_local_path):
            overwrite = input(f"Repository folder {repo_name} already exists. Overwrite? (y/n): ")
            if overwrite.lower() == 'y':
                print(f"Removing existing folder: {repo_name}")
                shutil.rmtree(safe_local_path)
            else:
                print(f"Skipping {repo_name}")
                self.log_migration(f"Skipped existing repository: {repo_name}")
                return
        
        Repo.clone_from(
            auth_url,
            safe_local_path,
            env={"GIT_TERMINAL_PROMPT": "0"}
        )
        print(f"✅ Successfully cloned {repo_name}")
        self.log_migration(f"Cloned repository: {repo_name}")

    def get_repo_versions(self, repo_path: str) -> Dict[str, Any]:
        print("\n📑 Analyzing repository versions")
        repo = Repo(repo_path)
        versions = {
            'tags': [],
            'latest_commit': repo.head.commit.hexsha
        }
        processed_commits = set()
        for idx, tag in enumerate(repo.tags, start=1):
            commit_sha = tag.commit.hexsha
            tag_name = tag.name
            if commit_sha in processed_commits:
                print(f"Skipping duplicate tag {tag_name} for commit {commit_sha[:8]}")
                continue
            if not re.match(r'^v?\d+\.\d+\.\d+$', tag_name) and not re.search(r'(\d+)\.(\d+)\.(\d+)', tag_name):
                print(f"⚠️ Skipping non-semantic version tag: {tag_name}")
                continue
            processed_commits.add(commit_sha)
            versions['tags'].append({
                'name': tag_name,
                'commit': commit_sha,
                'date': tag.commit.committed_datetime,
                'message': tag.commit.message.strip(),
                'index': idx
            })
        sorted_tags = sorted(versions['tags'], key=lambda x: x['date'])
        for idx, tag in enumerate(sorted_tags, start=1):
            tag['index'] = idx
        versions['tags'] = sorted_tags
        if not versions['tags']:
            print("⚠️ No semantic version tags found in the repository")
        else:
            print(f"✅ Found {len(versions['tags'])} semantic version tags")
        return versions

    def format_version_tag(self, tag_name: str, index: int) -> str:
        print(f"\n🏷️ Processing tag: {tag_name}")
        if re.match(r'^v?\d+\.\d+\.\d+$', tag_name):
            version = tag_name if tag_name.startswith('v') else f'v{tag_name}'
            print(f"✨ Using existing semantic version: {version}")
            return version
        version_match = re.search(r'(\d+)\.(\d+)\.(\d+)', tag_name)
        if version_match:
            major, minor, patch = version_match.groups()
            version = f'v{major}.{minor}.{patch}'
            print(f"✨ Extracted semantic version: {version}")
            return version
        print(f"⚠️ Warning: Non-semantic tag reached format_version_tag: {tag_name}")
        return f'v1.{index}.0'

    def create_module_version(self, module_name: str, tag_data: dict) -> bool:
        print("\n🔍 Creating module version")
        safe_module_name = self.format_module_name(module_name)
        version = self.format_version_tag(tag_data['name'], tag_data.get('index', 1))
        mutation = """
        mutation CreateVersion($module: ID!, $version: String!, $commitSha: String) {
            versionCreate(
                module: $module,
                version: $version,
                commitSha: $commitSha
            ) {
                id
                number
                state
            }
        }
        """
        variables = {
            "module": f"terraform-default-{safe_module_name}",
            "version": version,
            "commitSha": tag_data['commit']
        }
        try:
            response = requests.post(
                f"https://{self.spacelift_org}.app.spacelift.io/graphql",
                json={"query": mutation, "variables": variables},
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.bearer_token}"
                }
            )
            result = response.json()
            print(f"Version creation response: {result}")
            return response.status_code == 200
        except Exception as e:
            print(f"Error creating module version: {e}")
            return False

    def validate_spacelift_token(self, token: str) -> bool:
        api_url = f"https://{self.spacelift_org}.app.spacelift.io/graphql"
        headers = {
            "Authorization": token,
            "Content-Type": "application/json"
        }
        query = """
        query ValidateModulePermissions {
            viewer {
                id
                canCreateModules
            }
        }
        """
        response = requests.post(api_url, json={"query": query}, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if "errors" not in data and data.get("data", {}).get("viewer", {}).get("canCreateModules"):
                return True
        print("⚠️  Token requires module creation permissions. Please check token settings in Spacelift.")
        return False

    def format_module_name(self, name: str) -> str:
        formatted = name.lower().replace(' ', '-')
        formatted = ''.join(c for c in formatted if c.isalnum() or c in '-_').strip('-_')
        print(f"🏷️ Formatted module name: {formatted}")
        return formatted

    def get_default_branch(self, local_path: str) -> str:
        repo = Repo(local_path)
        try:
            default_branch = repo.active_branch.name
        except TypeError:
            default_branch = "main"
        print(f"📌 Detected default branch: {default_branch}")
        return default_branch

    def configure_global_options(self):
        """Allow user to configure global options for all modules"""
        print("\n🔧 Configure Global Module Options")
        print("These settings will apply to all modules unless overridden per module.")
        
        # Workflow tool selection
        print("\nSelect workflow tool:")
        print("1. OpenTofu (default)")
        print("2. Terraform")
        workflow_choice = input("Enter choice [1]: ").strip() or "1"
        self.global_options["workflowTool"] = "TERRAFORM" if workflow_choice == "2" else "OPEN_TOFU"
        
        # Administrative flag
        admin_choice = input("\nMake modules administrative? (y/n) [n]: ").strip().lower() or "n"
        self.global_options["administrative"] = admin_choice == "y"
        
        # Local preview
        preview_choice = input("\nEnable local preview? (y/n) [n]: ").strip().lower() or "n"
        self.global_options["localPreviewEnabled"] = preview_choice == "y"
        
        # Protection from deletion
        protect_choice = input("\nProtect modules from deletion? (y/n) [y]: ").strip().lower() or "y"
        self.global_options["protectFromDeletion"] = protect_choice == "y"
        
        # Project root
        project_root = input("\nDefault project root (subfolder containing Terraform files) []: ").strip()
        self.global_options["projectRoot"] = project_root
        
        # Labels
        labels_input = input("\nDefault labels (comma-separated) []: ").strip()
        self.global_options["labels"] = [label.strip() for label in labels_input.split(",")] if labels_input else []
        
        print("\n✅ Global options configured:")
        for key, value in self.global_options.items():
            print(f"  - {key}: {value}")
        
        return True

    def get_module_options(self, module_name: str) -> Dict[str, Any]:
        """Get module-specific options, with option to use global defaults"""
        print(f"\n🔧 Configure Options for Module: {module_name}")
        print("Press Enter to use global defaults or provide custom values.")
        
        # Start with a copy of global options
        module_options = self.global_options.copy()
        
        # Ask if user wants to customize this module
        customize = input("\nCustomize options for this module? (y/n) [n]: ").strip().lower() or "n"
        if customize != "y":
            print("Using global defaults for this module.")
            return module_options
        
        # Workflow tool selection
        print("\nSelect workflow tool:")
        print(f"1. OpenTofu (global: {'Yes' if module_options['workflowTool'] == 'OPEN_TOFU' else 'No'})")
        print(f"2. Terraform (global: {'Yes' if module_options['workflowTool'] == 'TERRAFORM' else 'No'})")
        workflow_choice = input("Enter choice [global default]: ").strip()
        if workflow_choice == "1":
            module_options["workflowTool"] = "OPEN_TOFU"
        elif workflow_choice == "2":
            module_options["workflowTool"] = "TERRAFORM"
        
        # Administrative flag
        admin_default = "y" if module_options["administrative"] else "n"
        admin_choice = input(f"\nMake module administrative? (y/n) [global: {admin_default}]: ").strip().lower()
        if admin_choice in ["y", "n"]:
            module_options["administrative"] = admin_choice == "y"
        
        # Local preview
        preview_default = "y" if module_options["localPreviewEnabled"] else "n"
        preview_choice = input(f"\nEnable local preview? (y/n) [global: {preview_default}]: ").strip().lower()
        if preview_choice in ["y", "n"]:
            module_options["localPreviewEnabled"] = preview_choice == "y"
        
        # Protection from deletion
        protect_default = "y" if module_options["protectFromDeletion"] else "n"
        protect_choice = input(f"\nProtect module from deletion? (y/n) [global: {protect_default}]: ").strip().lower()
        if protect_choice in ["y", "n"]:
            module_options["protectFromDeletion"] = protect_choice == "y"
        
        # Project root
        current_root = module_options["projectRoot"] or "root directory"
        project_root = input(f"\nProject root (subfolder containing Terraform files) [global: {current_root}]: ").strip()
        if project_root:
            module_options["projectRoot"] = project_root
        
        # Labels
        current_labels = ", ".join(module_options["labels"]) if module_options["labels"] else "none"
        labels_input = input(f"\nLabels (comma-separated) [global: {current_labels}]: ").strip()
        if labels_input:
            module_options["labels"] = [label.strip() for label in labels_input.split(",")]
        
        print("\n✅ Module options configured:")
        for key, value in module_options.items():
            print(f"  - {key}: {value}")
        
        return module_options

    def create_spacelift_module(self, module_name: str, local_path: str, space_id: str, integration_id: str):
        print(f"\n🚀 Creating Spacelift module: {module_name}")
        print(f"✅ Using space: {space_id}")
        print(f"✅ Using integration: {integration_id}")

        # Get module-specific options
        module_options = self.get_module_options(module_name)

        api_url = f"https://{self.spacelift_org}.app.spacelift.io/graphql"
        safe_module_name = self.format_module_name(module_name)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.bearer_token}"
        }
        
        # Get the actual default branch
        default_branch = self.get_default_branch(local_path)
        
        # Use the exact mutation from the HAR file
        mutation = """
        mutation CreateModule($input: ModuleCreateInput!) {
            moduleCreate(input: $input) {
                id
                __typename
            }
        }
        """
        
        # Use the exact input structure from the HAR file with module options
        variables = {
            "input": {
                "name": safe_module_name,
                "labels": module_options["labels"],
                "description": f"Module imported from Azure DevOps: {module_name}",
                "terraformProvider": module_options["terraformProvider"],
                "branch": default_branch,
                "namespace": self.azure_project,
                "projectRoot": module_options["projectRoot"],
                "provider": "AZURE_DEVOPS",
                "repository": safe_module_name,
                "space": space_id,
                "vcsIntegrationId": integration_id,
                "updateInput": {
                    "workerPool": None,
                    "workflowTool": module_options["workflowTool"],
                    "administrative": module_options["administrative"],
                    "localPreviewEnabled": module_options["localPreviewEnabled"],
                    "branch": default_branch,
                    "description": f"Module imported from Azure DevOps: {module_name}",
                    "labels": module_options["labels"],
                    "name": safe_module_name,
                    "namespace": self.azure_project,
                    "projectRoot": module_options["projectRoot"],
                    "protectFromDeletion": module_options["protectFromDeletion"],
                    "provider": "AZURE_DEVOPS",
                    "repository": safe_module_name,
                    "runnerImage": None,
                    "space": space_id,
                    "terraformProvider": module_options["terraformProvider"],
                    "vcsIntegrationId": integration_id,
                    "workerPool": None,
                    "workflowTool": module_options["workflowTool"]
                }
            }
        }

        print(f"Creating module with input: {json.dumps(variables, indent=2)}")
        
        response = requests.post(
            api_url,
            json={"query": mutation, "variables": variables},
            headers=headers
        )

        print(f"🔍 API Response: {response.json()}")

        if response.status_code == 200:
            result = response.json()
            if "errors" not in result:
                print(f"✅ Module {module_name} successfully created")
                self.log_migration(f"Created module: {module_name} in space: {space_id} with integration: {integration_id}")
                
                # Get versions but ensure only one per commit and only semantic versions
                versions = self.get_repo_versions(local_path)
                
                if not versions['tags']:
                    print("\n⚠️ No semantic version tags found in the repository.")
                    print("Only tags following semantic versioning (e.g., v1.0.0, 1.2.3) will be migrated.")
                    print("Other tags will be ignored.")
                else:
                    print(f"\n📦 Creating {len(versions['tags'])} versions from semantic version tags...")
                    
                    # Track which commits we've already created versions for
                    processed_commits = set()
                    
                    for tag in versions['tags']:
                        commit_sha = tag['commit']
                        
                        # Skip if we've already processed this commit
                        if commit_sha in processed_commits:
                            print(f"Skipping version creation for duplicate commit {commit_sha[:8]}")
                            continue
                        
                        processed_commits.add(commit_sha)
                        self.create_module_version(module_name, tag)
                
                return True
            else:
                error_message = result.get('errors', [{}])[0].get('message', 'Unknown error')
                print(f"Error creating module: {result['errors']}")
                return False
        else:
            print(f"Error: API request failed with status code {response.status_code}")
            return False

    def analyze_terraform_files(self, local_path: str) -> Dict[str, Any]:
        print("\n🔍 Analyzing Terraform files...")
        terraform_files = []
        for root, _, files in os.walk(local_path):
            for file in files:
                if file.endswith('.tf'):
                    terraform_files.append(os.path.join(root, file))
        return {
            'has_terraform': len(terraform_files) > 0,
            'file_count': len(terraform_files),
            'files': terraform_files
        }

    def validate_source_integration(self) -> bool:
        return True

    def select_repositories(self, repos: List[dict]) -> List[dict]:
        print("\n📋 Available repositories:")
        for idx, repo in enumerate(repos, 1):
            print(f"{idx}. {repo['name']}")
        selection = input("\nPress Enter to migrate all repositories, or enter a number to select specific repo: ").strip()
        if not selection:
            print("✨ Migrating all repositories")
            return repos
        try:
            idx = int(selection) - 1
            if 0 <= idx < len(repos):
                selected_repo = repos[idx]
                print(f"\n✨ Selected repository for migration: {selected_repo['name']}")
                return [selected_repo]
            else:
                print("Invalid selection, migrating all repositories")
                return repos
        except ValueError:
            print("Invalid input, migrating all repositories")
            return repos

    def get_available_spaces(self) -> List[dict]:
        print("\n🔍 Fetching available Spacelift spaces...")
        query = """
        query GetSpaces {
            spaces {
                id
                name
                description
            }
        }
        """
        try:
            result = self.graphql_post(query)
            spaces = result.get("data", {}).get("spaces", [])
            print(f"✅ Found {len(spaces)} spaces")
            return spaces
        except Exception as e:
            print(f"❌ Error fetching spaces: {e}")
            return []

    def get_space_integrations(self, space_id: str) -> List[dict]:
        print(f"\n🔍 Fetching VCS integrations for space: {space_id}...")
        query = """
        query {
            vcsIntegrations {
                id
                name
                provider
                space {
                    id
                    name
                }
            }
        }
        """
        try:
            result = self.graphql_post(query)
            all_integrations = result.get("data", {}).get("vcsIntegrations", [])
            space_integrations = [integration for integration in all_integrations if integration.get("space", {}).get("id") == space_id]
            print(f"✅ Found {len(space_integrations)} VCS integrations in space {space_id}")
            return space_integrations
        except Exception as e:
            print(f"❌ Error fetching integrations: {e}")
            return []

    def select_space_and_integration(self) -> (Optional[str], Optional[str]):
        spaces = self.get_available_spaces()
        if not spaces:
            print("❌ No spaces found. Using root space as fallback.")
            return "root", "automationdevops"
        print("\n📋 Available spaces:")
        for idx, space in enumerate(spaces, 1):
            print(f"{idx}. {space['name']} (ID: {space['id']})")
        selected_space = None
        while not selected_space:
            try:
                selection = input("\nSelect a space (number): ").strip()
                idx = int(selection) - 1
                if 0 <= idx < len(spaces):
                    selected_space = spaces[idx]
                    print(f"✅ Selected space: {selected_space['name']}")
                else:
                    print("❌ Invalid selection. Please try again.")
            except ValueError:
                print("❌ Please enter a valid number.")
        space_id = selected_space['id']
        integrations = self.get_space_integrations(space_id)
        azure_devops_integrations = [integration for integration in integrations if integration.get('provider') == 'AZURE_DEVOPS']
        if not azure_devops_integrations:
            print("⚠️ No Azure DevOps integrations found in this space.")
            show_all = input("Would you like to see all available Azure DevOps integrations across all spaces? (y/n): ").strip()
            if show_all.lower() == 'y':
                self.show_available_integrations()
                integration_id = input("\nEnter the ID of the integration you want to use: ").strip()
                return space_id, integration_id
            use_default = input("Would you like to try using the default 'automationdevops' integration? (y/n): ").strip()
            if use_default.lower() == 'y':
                return space_id, "automationdevops"
            print("❌ Cannot proceed without a valid Azure DevOps integration.")
            return None, None
        print("\n📋 Available Azure DevOps integrations:")
        for idx, integration in enumerate(azure_devops_integrations, 1):
            print(f"{idx}. {integration['name']} (ID: {integration['id']})")
        selected_integration = None
        while not selected_integration:
            try:
                selection = input("\nSelect an integration (number): ").strip()
                idx = int(selection) - 1
                if 0 <= idx < len(azure_devops_integrations):
                    selected_integration = azure_devops_integrations[idx]
                    print(f"✅ Selected integration: {selected_integration['name']}")
                else:
                    print("❌ Invalid selection. Please try again.")
            except ValueError:
                print("❌ Please enter a valid number.")
        return space_id, selected_integration['id']

    def show_available_integrations(self) -> None:
        print("\nFetching available Azure DevOps integrations...")
        query = """
        query {
            vcsIntegrations {
                id
                name
                provider
                space {
                    id
                    name
                }
            }
        }
        """
        try:
            result = self.graphql_post(query)
            vcs_integrations = result.get('data', {}).get('vcsIntegrations', [])
            azure_devops_integrations = [integration for integration in vcs_integrations if integration.get('provider') == 'AZURE_DEVOPS']
            if azure_devops_integrations:
                print("\nAvailable Azure DevOps integrations:")
                for integration in azure_devops_integrations:
                    space_name = integration.get('space', {}).get('name', 'Unknown')
                    print(f"- {integration.get('id')} (Name: {integration.get('name')}, Space: {space_name})")
            else:
                print("\nNo Azure DevOps integrations found.")
        except Exception as e:
            print(f"❌ Error fetching integrations: {e}")

    def purge_credentials(self) -> None:
        keyring.delete_password(self.service_id, self.username)
        try:
            keyring.delete_password(self.service_id, "spacelift_key_id")
            keyring.delete_password(self.service_id, "spacelift_key_secret")
        except Exception:
            pass
        print("✅ All stored credentials have been purged")

    def run(self) -> None:
        print("Welcome to the Azure DevOps to Spacelift Migration Tool!")
        self.log_migration("Starting migration process")
        
        if not self.get_user_input():
            print("Configuration cancelled. Exiting...")
            return

        if not self.validate_credentials():
            print("Credential validation failed. Exiting...")
            return

        repos = self.get_azure_repos()
        selected_repos = self.select_repositories(repos)

        proceed = input("\nWould you like to proceed with the migration? (y/n): ")
        if proceed.lower() != 'y':
            print("Migration cancelled. Exiting...")
            return

        # Spacelift authentication now happens after user confirms they want to proceed
        if not self.get_spacectl_token():
            print("Spacelift authentication failed. Exiting...")
            return
        
        # Configure global options for all modules
        self.configure_global_options()
        
        # Select space and integration once before processing repositories
        print("\n🔷 Spacelift Space and Integration Selection")
        print("Select the space and integration to use for all modules:")
        space_id, integration_id = self.select_space_and_integration()
        
        if not space_id or not integration_id:
            print("Space or integration selection failed. Exiting...")
            return
        
        # Ask if user wants to use the same space and integration for all modules
        use_same = input("\nDo you want to use this space and integration for all modules? (y/n): ")
        use_same_for_all = use_same.lower() == 'y'
        
        os.makedirs(self.temp_dir, exist_ok=True)

        # Flag to track if we're in automatic mode
        auto_process = False
        # Store default choices for automatic mode
        auto_create_module = True

        for idx, repo in enumerate(selected_repos):
            repo_name = repo["name"]
            repo_url = repo["remoteUrl"]
            local_path = os.path.join(self.temp_dir, repo_name)

            if not auto_process:
                # Add 'a' option for automatic processing of all remaining repos
                proceed_repo = input(f"\nProcess repository {repo_name}? (y/n/q for quit/a for auto-process all remaining): ").lower()
                
                if proceed_repo == 'q':
                    print("Migration stopped by user request.")
                    self.log_migration("Migration stopped by user")
                    break
                elif proceed_repo == 'a':
                    print(f"\n🚀 Switching to automatic mode for all remaining repositories ({len(selected_repos) - idx} left)")
                    auto_process = True
                    # Continue with this repository in automatic mode
                elif proceed_repo != 'y':
                    print(f"Skipping {repo_name}")
                    self.log_migration(f"Skipped repository: {repo_name}")
                    continue
            else:
                print(f"\n🔄 Auto-processing repository: {repo_name} ({idx + 1}/{len(selected_repos)})")

            self.clone_repo(repo_url, local_path, repo_name)
            
            tf_analysis = self.analyze_terraform_files(local_path)
            
            if tf_analysis['has_terraform']:
                print(f"\nFound {tf_analysis['file_count']} Terraform files:")
                for tf_file in tf_analysis['files'][:5]:  # Show only first 5 files to avoid cluttering the output
                    print(f"- {tf_file}")
                if len(tf_analysis['files']) > 5:
                    print(f"  ... and {len(tf_analysis['files']) - 5} more files")
                
                if not auto_process:
                    create_module = input(f"\nCreate Spacelift module for {repo_name}? (y/n): ")
                    auto_create_module = create_module.lower() == 'y'
                else:
                    print(f"\n{'✅' if auto_create_module else '❌'} {'Creating' if auto_create_module else 'Skipping'} Spacelift module for {repo_name}")
                
                if auto_create_module:
                    # If not using the same space/integration for all, select for this module
                    current_space_id = space_id
                    current_integration_id = integration_id
                    
                    if not use_same_for_all and not auto_process:
                        print(f"\n🔷 Spacelift Space and Integration Selection for {repo_name}")
                        current_space_id, current_integration_id = self.select_space_and_integration()
                        
                        if not current_space_id or not current_integration_id:
                            print(f"⚠️ Skipping module creation for {repo_name} due to missing space or integration")
                            self.log_migration(f"Skipped module creation for {repo_name} due to missing space or integration")
                            continue
                    
                    self.create_spacelift_module(repo_name, local_path, current_space_id, current_integration_id)
                    time.sleep(2)
            else:
                print(f"⚠️ No Terraform files found in {repo_name}, skipping...")
                self.log_migration(f"No Terraform files found in {repo_name}")

        cleanup = input("\nWould you like to clean up temporary files? (y/n): ")
        if cleanup.lower() == 'y':
            print("\n🧹 Cleaning up temporary files...")
            subprocess.run(["rm", "-rf", self.temp_dir])
            print("✅ Cleanup complete")
            self.log_migration("Cleaned up temporary files")

        self.save_migration_log()
        print("\n✨ Migration process completed!")
        print("📝 Migration log saved to migration_log.txt")

        purge = input("\nWould you like to purge stored credentials? (y/n): ")
        if purge.lower() == 'y':
            self.purge_credentials()

if __name__ == "__main__":
    migration = InteractiveMigration()
    migration.run()