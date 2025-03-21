import os
import requests
import subprocess
import json
import base64
import keyring
from git import Repo
from typing import List
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

    def get_spacectl_token(self):
        print("\n🔐 Authenticating with Spacelift...")
        
        # Step 1: Login with correct command
        login_cmd = ['spacectl', 'profile', 'login']
        subprocess.run(login_cmd, check=True)
        
        # Step 2: Export the JWT token with correct command
        token_cmd = ['spacectl', 'profile', 'export-token']
        token_result = subprocess.run(
            token_cmd,
            capture_output=True,
            text=True,
            check=True
        )
    
        
        self.bearer_token = token_result.stdout.strip()
        print("✅ Successfully authenticated with Spacelift")
        return True

    def store_credentials(self, pat: str):
        keyring.set_password(self.service_id, self.username, pat)
        print("✅ Credentials securely stored for future use")

    def get_stored_credentials(self) -> str:
        return keyring.get_password(self.service_id, self.username)

    def save_config(self):
        config = {
            'azure_org': self.azure_org,
            'azure_project': self.azure_project,
            'spacelift_org': self.spacelift_org
        }
        with open(self.config_file, 'w') as f:
            json.dump(config, f)

    def load_config(self):
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                return config
        except:
            return None

    def log_migration(self, message: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.migration_log.append(f"{timestamp}: {message}")
        
    def save_migration_log(self):
        with open('migration_log.txt', 'w') as f:
            f.write('\n'.join(self.migration_log))

    def get_user_input(self):
        print("\n🔷 Configuration Setup")
        saved_config = self.load_config()
        
        if saved_config:
            default_azure_org = saved_config.get('azure_org', '')
            default_azure_project = saved_config.get('azure_project', '')
            default_spacelift_org = saved_config.get('spacelift_org', '')
            
            self.azure_org = input(f"Enter your Azure DevOps organization name [{default_azure_org}]: ").strip() or default_azure_org
            self.azure_project = input(f"Enter your Azure DevOps project name [{default_azure_project}]: ").strip() or default_azure_project
            spacelift_input = input(f"Enter your Spacelift organization name [{default_spacelift_org}]: ").strip() or default_spacelift_org
        else:
            self.azure_org = input("Enter your Azure DevOps organization name: ").strip()
            self.azure_project = input("Enter your Azure DevOps project name: ").strip()
            spacelift_input = input("Enter your Spacelift organization name: ").strip()
        
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

    def validate_credentials(self):
        print("\n🔑 Checking for stored credentials...")
        
        azure_pat = self.get_stored_credentials()
        
        if not azure_pat:
            azure_pat = input("Enter your Azure DevOps PAT token: ")
            store = input("Would you like to store this token securely for future use? (y/n): ")
            if store.lower() == 'y':
                self.store_credentials(azure_pat)
        else:
            print("✅ Found stored credentials!")
        
        # Add validation check
        if not azure_pat or len(azure_pat.strip()) == 0:
            raise ValueError("Azure PAT token is empty or invalid")
            
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
        
        print(f"Connecting to Azure DevOps API...")
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            repos = response.json()["value"]
            print(f"✅ Successfully retrieved {len(repos)} repositories")
            return repos
        else:
            print(f"Status code: {response.status_code}")
            print("Please verify your organization name, project name, and PAT token")
            retry = input("Would you like to enter credentials again? (y/n): ")
            if retry.lower() == 'y':
                os.environ["AZURE_DEVOPS_PAT"] = input("Enter your Azure DevOps PAT token: ")
                return self.get_azure_repos()
            return []
    def clone_repo(self, repo_url: str, local_path: str, repo_name: str):
        print(f"\n📥 Cloning repository: {repo_name}")
        
        # Handle spaces in paths and URLs
        pat = os.getenv("AZURE_DEVOPS_PAT")
        encoded_project = self.azure_project.replace(" ", "%20")
        encoded_repo = repo_name.replace(" ", "%20")
        auth_url = f"https://{pat}@dev.azure.com/{self.azure_org}/{encoded_project}/_git/{encoded_repo}"
        
        # Create safe local path
        safe_local_path = os.path.join(self.temp_dir, repo_name.replace(" ", "_"))
        
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


    def get_repo_versions(self, repo_path: str) -> dict:
        print(f"\n📑 Analyzing repository versions")
        repo = Repo(repo_path)
        
        versions = {
            'tags': [],
            'latest_commit': repo.head.commit.hexsha
        }
        
        # Add index to track tag order
        for idx, tag in enumerate(repo.tags, start=1):
            versions['tags'].append({
                'name': tag.name,
                'commit': tag.commit.hexsha,
                'date': tag.commit.committed_datetime,
                'message': tag.commit.message.strip(),
                'index': idx  # This will increment for each tag
            })
        
        # Sort by date and preserve index
        sorted_tags = sorted(versions['tags'], key=lambda x: x['date'])
        for idx, tag in enumerate(sorted_tags, start=1):
            tag['index'] = idx
        versions['tags'] = sorted_tags
        
        return versions

    import re

    def format_version_tag(self, tag_name: str, index: int) -> str:
        """Convert tag to semantic version format"""
        print(f"\n🏷️  Processing tag: {tag_name}")
        
        # Check if tag already follows semantic versioning
        if re.match(r'^v?\d+\.\d+\.\d+$', tag_name):
            version = tag_name if tag_name.startswith('v') else f'v{tag_name}'
        else:
            # Create incremental semantic version based on index
            version = f'v1.{index}.0'
        
        print(f"✨ Converted to semantic version: {version}")
        return version


    def create_module_version(self, module_name: str, tag_data: dict):
        print("\n🔍 Starting Version Creation Debug")
        api_url = f"https://{self.spacelift_org}.app.spacelift.io/graphql"
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
        
        response = requests.post(
            api_url,
            json={"query": mutation, "variables": variables},
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.bearer_token}"
            }
        )
        
        print(f"Version creation response: {response.json()}")
        return response.status_code == 200

    def validate_spacelift_token(self, token: str) -> bool:
        api_url = f"https://{self.spacelift_org}.app.spacelift.io/graphql"
    
        headers = {
            "Authorization": token,
            "Content-Type": "application/json"
        }
    
        # Query that checks module creation permissions
        query = """
        query ValidateModulePermissions {
            viewer {
                id
                canCreateModules
            }
        }
        """
    
        response = requests.post(
            api_url,
            json={"query": query},
            headers=headers
        )
    
        if response.status_code == 200:
            data = response.json()
            if "errors" not in data and data.get("data", {}).get("viewer", {}).get("canCreateModules"):
                return True
    
        print("⚠️  Token requires module creation permissions. Please check token settings in Spacelift.")
        return False

    def format_module_name(self, name: str) -> str:
        """Format module name to meet Spacelift requirements"""
        # Convert to lowercase first
        formatted = name.lower()
        # Replace any spaces with dashes
        formatted = formatted.replace(' ', '-')
        # Remove any special characters except dashes and underscores
        formatted = ''.join(c for c in formatted if c.isalnum() or c in '-_')
        # Ensure it starts and ends with letters
        formatted = formatted.strip('-_')
        
        print(f"🏷️ Formatted module name: {formatted}")
        return formatted

    def get_default_branch(self, local_path: str) -> str:
        """Detect the default branch name from the repository"""
        repo = Repo(local_path)
        default_branch = repo.active_branch.name
        print(f"📌 Detected default branch: {default_branch}")
        return default_branch

    def create_spacelift_module(self, module_name: str, local_path: str):
        print(f"\n🚀 Creating Spacelift module: {module_name}")
    
        # Space selection at module level
        print("\n📍 Spacelift Space Selection")
        target_space = input(f"Enter target Spacelift space for module '{module_name}' (press Enter for root space): ").strip() or "root"
        print(f"✅ Creating module in space: {target_space}")
    
        api_url = f"https://{self.spacelift_org}.app.spacelift.io/graphql"
        safe_module_name = self.format_module_name(module_name)
    
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.bearer_token}"
        }
    
        mutation = """
        mutation CreateModule($input: ModuleCreateInput!) {
            moduleCreate(input: $input) {
                id
                name
            }
        }
        """
    
        # Get the actual default branch
        default_branch = self.get_default_branch(local_path)
    
        variables = {
            "input": {
                "name": safe_module_name,
                "description": f"Terraform module imported from Azure DevOps: {safe_module_name}",
                "terraformProvider": "default",
                "provider": "AZURE_DEVOPS",
                "repository": safe_module_name,
                "namespace": self.azure_project,
                "space": target_space,
                "branch": default_branch,
                "projectRoot": "",
                "labels": [],
                "administrative": False,
                "workflowTool": "TERRAFORM_FOSS",
                "localPreviewEnabled": True,
                "protectFromDeletion": True,
                "updateInput": {
                    "name": safe_module_name,
                    "description": f"Terraform module imported from Azure DevOps: {safe_module_name}",
                    "terraformProvider": "default",
                    "provider": "AZURE_DEVOPS",
                    "repository": safe_module_name,
                    "namespace": self.azure_project,
                    "space": target_space,
                    "branch": default_branch,
                    "projectRoot": "",
                    "labels": [],
                    "administrative": False,
                    "workflowTool": "TERRAFORM_FOSS",
                    "localPreviewEnabled": True,
                    "protectFromDeletion": False
                }
            }
        }
    
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
                self.log_migration(f"Created module: {module_name}")
                versions = self.get_repo_versions(local_path)
                for tag in versions['tags']:
                    self.create_module_version(module_name, tag)
                return True
            else:
                print(f"Error creating module: {result['errors']}")
                return False
        else:
            print(f"Error: API request failed with status code {response.status_code}")
            return False            
    def analyze_terraform_files(self, local_path: str) -> dict:
        # Your existing analyze_terraform_files implementation        print(f"\n🔍 Analyzing Terraform files...")
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

    def validate_source_integration(self):
        print("\n🔍 Checking Spacelift source code integrations...")
        
        api_url = f"https://{self.spacelift_org}.app.spacelift.io/graphql"
        
        query = """
        query {
            sourceConnections {
                id
                type
                name
                isReady
                azureDevOps {
                    organization
                    project
                    accessToken
                    isValid
                }
            }
        }
        """
        
        response = requests.post(
            api_url,
            json={"query": query},
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.bearer_token}"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            azure_integrations = [
                conn for conn in data.get('data', {}).get('sourceConnections', [])
                if (conn['type'] == 'AZURE_DEVOPS' and 
                    conn['isReady'] and 
                    conn['azureDevOps']['isValid'] and
                    conn['azureDevOps']['organization'] == self.azure_org and
                    conn['azureDevOps']['project'] == self.azure_project)
            ]
            
            if azure_integrations:
                print(f"✅ Found valid Azure DevOps integration for {self.azure_org}/{self.azure_project}")
                return True
                
            print("❌ No valid Azure DevOps integration found")
            print(f"Please ensure your Spacelift integration has access to {self.azure_org}/{self.azure_project}")
            return False

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

    def run(self):
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

        os.makedirs(self.temp_dir, exist_ok=True)

        for repo in selected_repos:
            repo_name = repo["name"]
            repo_url = repo["remoteUrl"]
            local_path = os.path.join(self.temp_dir, repo_name)

            proceed_repo = input(f"\nProcess repository {repo_name}? (y/n/q for quit): ").lower()
            if proceed_repo == 'q':
                print("Migration stopped by user request.")
                self.log_migration("Migration stopped by user")
                break
            elif proceed_repo != 'y':
                print(f"Skipping {repo_name}")
                self.log_migration(f"Skipped repository: {repo_name}")
                continue

            self.clone_repo(repo_url, local_path, repo_name)
            
            tf_analysis = self.analyze_terraform_files(local_path)
            
            if tf_analysis['has_terraform']:
                print(f"\nFound {tf_analysis['file_count']} Terraform files:")
                for tf_file in tf_analysis['files']:
                    print(f"- {tf_file}")
                
                create_module = input(f"\nCreate Spacelift module for {repo_name}? (y/n): ")
                if create_module.lower() == 'y':
                    self.create_spacelift_module(repo_name, local_path)
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

    def purge_credentials(self):
        """Remove all stored credentials from the keyring"""
        keyring.delete_password(self.service_id, self.username)
        keyring.delete_password(self.service_id, "spacelift_key_id")
        keyring.delete_password(self.service_id, "spacelift_key_secret")
        print("✅ All stored credentials have been purged")

if __name__ == "__main__":
    migration = InteractiveMigration()
    migration.run()
