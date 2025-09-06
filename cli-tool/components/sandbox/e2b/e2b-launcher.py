#!/usr/bin/env python3.11
"""
E2B Claude Code Sandbox Launcher
Executes Claude Code prompts in isolated E2B cloud sandbox
"""

import os
import sys
import json
import datetime
import re

# Debug: Print Python path information
print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")
print(f"Python path: {sys.path[:3]}...")  # Show first 3 paths

try:
    from e2b import Sandbox
    print("✓ E2B imported successfully")
except ImportError as e:
    print(f"✗ E2B import failed: {e}")
    print("Trying to install E2B...")
    import subprocess
    # Try different installation methods for different Python environments
    install_commands = [
        [sys.executable, '-m', 'pip', 'install', '--user', 'e2b'],  # User install first
        [sys.executable, '-m', 'pip', 'install', '--break-system-packages', 'e2b'],  # System packages
        [sys.executable, '-m', 'pip', 'install', 'e2b']  # Default fallback
    ]
    
    result = None
    for cmd in install_commands:
        print(f"Trying: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ Installation successful")
            break
        else:
            print(f"✗ Failed: {result.stderr.strip()[:100]}...")
    
    if result is None:
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', 'e2b'], 
                              capture_output=True, text=True)
    print(f"Install result: {result.returncode}")
    if result.stdout:
        print(f"Install stdout: {result.stdout}")
    if result.stderr:
        print(f"Install stderr: {result.stderr}")
    
    # Try importing again
    try:
        from e2b import Sandbox
        print("✓ E2B imported successfully after install")
    except ImportError as e2:
        print(f"✗ E2B still failed after install: {e2}")
        sys.exit(1)

# Try to import and use dotenv if available, but don't fail if it's not
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv is optional since we can get keys from command line arguments
    pass

def main():
    
    # Parse command line arguments
    if len(sys.argv) < 2:
        print("Usage: python e2b-launcher.py <prompt> [components_to_install] [e2b_api_key] [anthropic_api_key]")
        sys.exit(1)
    
    prompt = sys.argv[1]
    components_to_install = sys.argv[2] if len(sys.argv) > 2 else ""
    
    # Get API keys from command line arguments or environment variables
    e2b_api_key = sys.argv[3] if len(sys.argv) > 3 else os.getenv('E2B_API_KEY')
    anthropic_api_key = sys.argv[4] if len(sys.argv) > 4 else os.getenv('ANTHROPIC_API_KEY')
    
    if not e2b_api_key:
        print("Error: E2B API key is required")
        print("Provide via command line argument or E2B_API_KEY environment variable")
        sys.exit(1)
    
    if not anthropic_api_key:
        print("Error: Anthropic API key is required")
        print("Provide via command line argument or ANTHROPIC_API_KEY environment variable")
        sys.exit(1)
    
    try:
        # Create E2B sandbox with Claude Code template with retry logic
        print("🚀 Creating E2B sandbox with Claude Code...")
        
        # Try creating sandbox with retries for WebSocket issues
        max_retries = 3
        retry_count = 0
        sbx = None
        
        while retry_count < max_retries and sbx is None:
            try:
                if retry_count > 0:
                    print(f"🔄 Retry {retry_count}/{max_retries - 1} - WebSocket connection...")
                
                sbx = Sandbox.create(
                    template="anthropic-claude-code",
                    api_key=e2b_api_key,
                    envs={
                        'ANTHROPIC_API_KEY': anthropic_api_key,
                    },
                    timeout=600,  # 10 minutes timeout for longer operations
                )
                
                # Keep sandbox alive during operations
                print(f"🔄 Extending sandbox timeout to prevent early termination...")
                sbx.set_timeout(900)  # 15 minutes total
                print(f"✅ Sandbox created: {sbx.sandbox_id}")
                break
                
            except Exception as e:
                error_msg = str(e).lower()
                if "websocket" in error_msg or "connection" in error_msg or "timeout" in error_msg:
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"⚠️  WebSocket connection failed (attempt {retry_count}), retrying in 3 seconds...")
                        import time
                        time.sleep(3)
                        continue
                    else:
                        print(f"❌ WebSocket connection failed after {max_retries} attempts")
                        print("💡 This might be due to:")
                        print("   • Network/firewall restrictions blocking WebSocket connections")
                        print("   • Temporary E2B service issues")
                        print("   • Corporate proxy blocking WebSocket traffic")
                        print("💡 Try:")
                        print("   • Running from a different network")
                        print("   • Checking your firewall/proxy settings")
                        print("   • Waiting a few minutes and trying again")
                        raise e
                else:
                    # Non-WebSocket error, don't retry
                    raise e
        
        if sbx is None:
            raise Exception("Failed to create sandbox after all retry attempts")
        
        # Install components if specified
        if components_to_install:
            print("📦 Installing specified components...")
            install_result = sbx.commands.run(
                f"npx claude-code-templates@latest {components_to_install}",
                timeout=120,  # 2 minutes for component installation
            )
            
            if install_result.exit_code != 0:
                print(f"⚠️  Component installation warnings:")
                print(install_result.stderr)
            else:
                print("✅ Components installed successfully")
        
        # Execute Claude Code with the prompt
        print(f"🤖 Executing Claude Code with prompt: '{prompt[:50]}{'...' if len(prompt) > 50 else ''}'")
        
        # First, check if Claude Code is installed and available
        print("🔍 Checking Claude Code installation...")
        check_result = sbx.commands.run("which claude", timeout=10)
        if check_result.exit_code == 0:
            print(f"✅ Claude found at: {check_result.stdout.strip()}")
        else:
            print("❌ Claude not found, checking PATH...")
            path_result = sbx.commands.run("echo $PATH", timeout=5)
            print(f"PATH: {path_result.stdout}")
            ls_result = sbx.commands.run("ls -la /usr/local/bin/ | grep claude", timeout=5)
            print(f"Claude binaries: {ls_result.stdout}")
        
        # Check current directory and permissions
        print("🔍 Checking sandbox environment...")
        pwd_result = sbx.commands.run("pwd", timeout=5)
        print(f"Current directory: {pwd_result.stdout.strip()}")
        
        whoami_result = sbx.commands.run("whoami", timeout=5)
        print(f"Current user: {whoami_result.stdout.strip()}")
        
        # Check if we can write to current directory
        test_write = sbx.commands.run("touch test_write.tmp && rm test_write.tmp", timeout=5)
        if test_write.exit_code == 0:
            print("✅ Write permissions OK")
        else:
            print("❌ Write permission issue")
        
        # Build Claude Code command with better error handling
        claude_command = f"echo '{prompt}' | claude -p --dangerously-skip-permissions"
        print(f"🚀 Running command: {claude_command}")
        
        # Execute with extended timeout for complex operations
        result = sbx.commands.run(
            claude_command,
            timeout=600,  # 10 minutes timeout for complex operations
        )
        
        print(f"🔍 Command exit code: {result.exit_code}")
        if result.stdout:
            print(f"📤 Command stdout length: {len(result.stdout)} characters")
        if result.stderr:
            print(f"📤 Command stderr length: {len(result.stderr)} characters")
        
        print("=" * 60)
        print("🎯 CLAUDE CODE OUTPUT:")
        print("=" * 60)
        print(result.stdout)
        
        if result.stderr:
            print("=" * 60)
            print("⚠️  STDERR:")
            print("=" * 60)
            print(result.stderr)
        
        # List generated files
        print("=" * 60)
        print("📁 GENERATED FILES:")
        print("=" * 60)
        
        files_result = sbx.commands.run("find . -type f \\( -name '*.html' -o -name '*.js' -o -name '*.css' -o -name '*.py' -o -name '*.json' -o -name '*.md' -o -name '*.tsx' -o -name '*.ts' \\) ! -path '*/.claude/*' ! -path '*/node_modules/*' | head -20")
        if files_result.stdout.strip():
            print(files_result.stdout)
            
            # Download important files to local machine
            print("\n" + "=" * 60)
            print("💾 DOWNLOADING FILES TO LOCAL MACHINE:")
            print("=" * 60)
            
            # Create unique folder for this execution in project root
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            clean_prompt = re.sub(r'[^\w\s-]', '', prompt).strip()
            clean_prompt = re.sub(r'[-\s]+', '-', clean_prompt)[:30]
            folder_name = f"{timestamp}_{clean_prompt}"
            
            # Create output directory in project root (not inside .claude)
            local_output_dir = f"./e2b-outputs/{folder_name}"
            os.makedirs(local_output_dir, exist_ok=True)
            
            print(f"📂 Output folder: {local_output_dir}")
            
            files_to_download = files_result.stdout.strip().split('\n')
            for file_path in files_to_download:
                file_path = file_path.strip()
                if file_path:  # Already filtered out .claude and node_modules in find command
                    try:
                        # Read file content from sandbox
                        file_content = sbx.commands.run(f"cat '{file_path}'", timeout=30)
                        if file_content.exit_code == 0:
                            # Create local path
                            local_file = os.path.join(local_output_dir, os.path.basename(file_path))
                            
                            # Write file locally
                            with open(local_file, 'w', encoding='utf-8') as f:
                                f.write(file_content.stdout)
                            
                            print(f"✅ Downloaded: {file_path} → {local_file}")
                        else:
                            print(f"❌ Failed to read: {file_path}")
                    except Exception as e:
                        print(f"❌ Error downloading {file_path}: {e}")
            
            print(f"\n📁 All files downloaded to: {os.path.abspath(local_output_dir)}")
            
        else:
            print("No common files generated")
        
        print("=" * 60)
        print(f"✅ Execution completed successfully")
        print(f"🗂️  Sandbox ID: {sbx.sandbox_id}")
        print("💡 Note: Sandbox will be automatically destroyed")
        
    except Exception as e:
        print(f"❌ Error executing Claude Code in sandbox: {str(e)}")
        sys.exit(1)
    
    finally:
        # Cleanup sandbox
        try:
            if 'sbx' in locals():
                sbx.kill()
                print("🧹 Sandbox cleaned up")
        except Exception as cleanup_error:
            print(f"⚠️  Cleanup warning: {cleanup_error}")

if __name__ == "__main__":
    main()