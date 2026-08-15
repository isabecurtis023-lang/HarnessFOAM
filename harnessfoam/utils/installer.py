# 2026-08-15 (gemini-2.5-pro)
import platform
import shutil
import subprocess
import os

def is_openfoam_installed() -> bool:
    """Check if blockMesh (a standard OpenFOAM utility) is available in PATH."""
    return shutil.which("blockMesh") is not None

def get_install_command() -> str:
    """Return the recommended installation command based on the OS."""
    system = platform.system().lower()
    if system == "linux":
        return "sudo sh -c 'wget -O - https://dl.openfoam.org/source/7 | bash' # Or use apt-get install openfoam-default"
    elif system in ["windows", "darwin"]:
        # Windows/Mac usually use Docker
        return "docker pull openfoam/openfoam10-paraview510 && docker run -it openfoam/openfoam10-paraview510"
    return "Check https://openfoam.org/download/ for installation instructions."

def prompt_and_install_openfoam() -> bool:
    """
    In a CLI context, prompt the user for permission and attempt installation.
    Returns True if successfully installed or already installed.
    """
    if is_openfoam_installed():
        return True
        
    print("\n[WARNING] OpenFOAM is not detected on your system PATH.")
    cmd = get_install_command()
    print(f"Recommended installation method for your OS ({platform.system()}):\n> {cmd}\n")
    
    response = input("Would you like to attempt automatic installation? (y/N): ")
    if response.lower() == 'y':
        system = platform.system().lower()
        try:
            if system == "linux":
                # Very basic apt attempt (might require sudo password)
                subprocess.run(["sudo", "apt-get", "update"], check=True)
                subprocess.run(["sudo", "apt-get", "install", "-y", "openfoam"], check=True)
            else:
                # Docker attempt
                subprocess.run(["docker", "pull", "openfoam/openfoam10-paraview510"], check=True)
            print("Installation routine completed. Please verify OpenFOAM is working.")
            return True
        except Exception as e:
            print(f"Installation failed: {e}")
            print("Please install OpenFOAM manually.")
            return False
    return False

if __name__ == "__main__":
    if not is_openfoam_installed():
        prompt_and_install_openfoam()
    else:
        print("OpenFOAM is correctly installed.")
