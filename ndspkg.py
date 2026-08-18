import json
import os
import socket
import urllib.request
from ftplib import FTP
from ipaddress import ip_address
from pathlib import Path

import ftpbackend as ftpserver

SAVE_FILE = Path(__file__).with_name("ndsip.txt")
REPO_CONFIG_FILE = Path(__file__).with_name("repos.json")


def ensure_repo_config():
    """Create a repo config file if it doesn't already exist."""
    if REPO_CONFIG_FILE.exists():
        return

    default_repos = {
        "selected": "main",
        "repositories": [
            {
                "name": "main",
                "url": "https://raw.githubusercontent.com/p1xelpp/ndspkg/refs/heads/main/index.json"
            }
        ]
    }

    REPO_CONFIG_FILE.write_text(json.dumps(default_repos, indent=2), encoding="utf-8")


def load_repo_config():
    """Load the list of package repositories from JSON."""
    ensure_repo_config()
    try:
        with REPO_CONFIG_FILE.open("r", encoding="utf-8") as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError):
        config = {"selected": "main", "repositories": []}

    repos = config.get("repositories", [])
    if not repos:
        return {"selected": "main", "repositories": [{"name": "main", "url": "https://raw.githubusercontent.com/p1xelpp/ndspkg/refs/heads/main/index.json"}]}

    selected = config.get("selected")
    if selected not in {repo.get("name") for repo in repos if repo.get("name")}:
        selected = repos[0].get("name", "main")

    return {"selected": selected, "repositories": repos}


def save_repo_config(config):
    """Write the repo config back to disk."""
    REPO_CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")


def get_selected_repo_url():
    """Return the current selected repo index URL."""
    config = load_repo_config()
    selected_name = config.get("selected")
    for repo in config.get("repositories", []):
        if repo.get("name") == selected_name:
            return repo.get("url")
    return config.get("repositories", [{}])[0].get("url", "")


def list_repo_options():
    """Print the available repo names and the currently selected one."""
    config = load_repo_config()
    repos = config.get("repositories", [])
    current = config.get("selected")

    if not repos:
        print("No repositories configured.")
        return

    print("\nRepositories:")
    for repo in repos:
        name = repo.get("name", "unknown")
        marker = "*" if name == current else " "
        print(f"{marker} {name} -> {repo.get('url', '')}")


def select_repo(name):
    """Select a repo by name from the config file."""
    config = load_repo_config()
    repos = config.get("repositories", [])
    for repo in repos:
        if repo.get("name") == name:
            config["selected"] = name
            save_repo_config(config)
            print(f"Selected repo: {name}")
            return True
    print(f"Repo '{name}' was not found.")
    return False


def add_repo(name, url):
    """Add a new package repository entry to the config file."""
    repo_name = str(name).strip()
    repo_url = str(url).strip()

    if not repo_name:
        print("Usage: addrepo <name> <url>")
        return False

    if not repo_url:
        print("Usage: addrepo <name> <url>")
        return False

    config = load_repo_config()
    repos = config.get("repositories", [])
    for repo in repos:
        if repo.get("name", "").lower() == repo_name.lower():
            print(f"Repo '{repo_name}' already exists.")
            return False

    repos.append({"name": repo_name, "url": repo_url})
    config["repositories"] = repos
    config["selected"] = repo_name
    save_repo_config(config)
    print(f"Added repo '{repo_name}' -> {repo_url}")
    return True


def remove_repo(name):
    """Remove a repository entry from the config file."""
    repo_name = str(name).strip()
    if not repo_name:
        print("Usage: removerepo <name>")
        return False

    config = load_repo_config()
    repos = config.get("repositories", [])
    filtered = [repo for repo in repos if repo.get("name", "").lower() != repo_name.lower()]

    if len(filtered) == len(repos):
        print(f"Repo '{repo_name}' was not found.")
        return False

    config["repositories"] = filtered
    if config.get("selected", "") == repo_name:
        config["selected"] = filtered[0].get("name", "main") if filtered else "main"

    save_repo_config(config)
    print(f"Removed repo '{repo_name}'")
    return True


def load_saved_ndsip():
    """Load a previously saved DSi host and port if it exists."""
    try:
        if SAVE_FILE.exists():
            saved_value = SAVE_FILE.read_text(encoding="utf-8").strip()
            if not saved_value:
                return "", 5000

            if "|" in saved_value:
                host_part, port_part = saved_value.split("|", 1)
                try:
                    return host_part.strip(), int(port_part.strip())
                except ValueError:
                    return host_part.strip(), 5000

            return saved_value, 5000
    except OSError:
        pass
    return "", 5000


def save_ndsip(ndsip, port=5000):
    """Persist the DSi host and port so they don't need to be entered every time."""
    saved_ndsip = str(ndsip).strip()
    saved_port = int(port)
    try:
        SAVE_FILE.write_text(f"{saved_ndsip}|{saved_port}", encoding="utf-8")
        return saved_ndsip, saved_port
    except OSError as exc:
        print(f"Warning: could not save ndsip: {exc}")
        return saved_ndsip, saved_port


def normalize_host(value):
    """Strip junk from a hostname or IP address."""
    cleaned = str(value).strip().strip("'\" ")
    if not cleaned:
        return ""
    cleaned = cleaned.rstrip("\r\n")
    if cleaned.startswith("http://"):
        cleaned = cleaned.split("//", 1)[1]
    if "/" in cleaned:
        cleaned = cleaned.split("/", 1)[0]
    return cleaned


def validate_host(host):
    """Validate host formatting before trying to connect."""
    host = normalize_host(host)
    if not host:
        raise ValueError("No IP address was entered.")

    try:
        ip_address(host)
        return host
    except ValueError:
        pass

    if "." in host or "-" in host or host.replace("_", "").isalnum():
        return host

    raise ValueError(f"Invalid host/IP entered: '{host}'. Use something like 192.168.1.50 or your DSi hostname.")


def connect_dsi(saved_host="", saved_port=5000):
    """Prompt for and connect to the DSi FTP server."""
    if saved_host:
        raw_host = input(f"enter the ip that ftpd gave u [{saved_host}]: ").strip()
        ndsip = normalize_host(raw_host) if raw_host else saved_host
    else:
        ndsip = normalize_host(input("enter the ip that ftpd gave u: "))

    try:
        port_input = input(f"enter the ftp port [{saved_port}]: ").strip()
        ftp_port = int(port_input) if port_input else saved_port
    except ValueError:
        ftp_port = saved_port

    ndsip = validate_host(ndsip)
    save_ndsip(ndsip, ftp_port)

    ftp = FTP()
    try:
        ftp.connect(host=ndsip, port=ftp_port)
        ftp.login(user="", passwd="")
        print("--- Successfully Connected! ---")
        return ftp
    except (socket.gaierror, OSError, ConnectionRefusedError) as exc:
        print(f"\nCould not connect to '{ndsip}:{ftp_port}'.")
        print("Check that the DSi FTP server is running, the IP is correct, and you're on the same network.")
        print(f"Connection error: {exc}")
        return None


def fetch_online_packages():
    """Download and parse the selected repo's package index."""
    repo_url = get_selected_repo_url()
    if not repo_url:
        print("No repo URL configured.")
        return []

    try:
        with urllib.request.urlopen(repo_url, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        print(f"Failed to fetch online packages from {repo_url}: {exc}")
        return []

    packages = data.get("packages", [])
    if isinstance(packages, dict):
        packages = [packages]
    return packages


def list_online_packages():
    """Print the packages available from the currently selected repo."""
    packages = fetch_online_packages()
    if not packages:
        print("No packages found in the selected online repo.")
        return

    print(f"\nAvailable packages from {get_selected_repo_url()}:")
    for pkg in packages:
        name = pkg.get("name", "unknown")
        version = pkg.get("version", "unknown")
        description = pkg.get("description", "")
        print(f"- {name} v{version}: {description}")


def install_package(package_name, ftp):
    """Download a package from the selected repo and upload it to the DSi SD card."""
    packages = fetch_online_packages()
    if not packages:
        return False

    for pkg in packages:
        if pkg.get("name", "").lower() == package_name.lower():
            url = pkg.get("url")
            if not url:
                print(f"Package '{package_name}' does not have a valid download URL.")
                return False

            filename = os.path.basename(url)
            print(f"Downloading '{filename}' from repo...")
            try:
                with urllib.request.urlopen(url, timeout=30) as response:
                    data = response.read()
            except Exception as exc:
                print(f"Download failed: {exc}")
                return False

            with open(filename, "wb") as local_file:
                local_file.write(data)

            print(f"Installing '{filename}' to the DSi...")
            ftpserver.handle_command(f"put {filename}", ftp)

            try:
                os.remove(filename)
            except OSError:
                pass

            print(f"Installed '{package_name}' successfully.")
            return True

    print(f"Package '{package_name}' was not found in the selected repo.")
    return False


def get_file_from_dsi(filename, ftp):
    """Download a file from the DSi SD card and save it locally."""
    if not filename:
        print("Usage: get <filename>")
        return False

    target_name = os.path.basename(filename)
    local_path = Path(target_name)
    try:
        with local_path.open("wb") as local_file:
            ftp.retrbinary(f"RETR {filename}", local_file.write)
        print(f"Downloaded '{filename}' to '{local_path}'")
        return True
    except Exception as exc:
        print(f"Download failed: {exc}")
        return False


def shell_loop():
    """Run the interactive frontend shell."""
    saved_host, saved_port = load_saved_ndsip()
    ftp = connect_dsi(saved_host, saved_port)
    if ftp is None:
        print("Connection failed. Exiting.")
        return

    print("\nCommands: repo | repo add <name> <url> | repo remove <name> | addrepo <name> <url> | removerepo <name> | lsp | lsds | get <file> | install <package> | help | exit")

    while True:
        try:
            cmd = input("ndspkg> ").strip()
        except KeyboardInterrupt:
            print("\nExiting shell...")
            break

        if not cmd:
            continue

        if cmd == "help":
            print("Available commands:")
            print("  repo                     - list repo choices or select a repo")
            print("  repo add <name> <url>    - add a new repo to the config")
            print("  repo remove <name>       - remove a repo from the config")
            print("  addrepo <name> <url>     - add a new repo to the config")
            print("  removerepo <name>        - remove a repo from the config")
            print("  lsp                      - list packages from the selected repo")
            print("  lsds                     - list files on the DSi SD card")
            print("  get <file>               - download a file from the DSi SD card")
            print("  install <package>        - download and install a package from the selected repo")
            print("  exit                     - leave the shell")

        elif cmd.startswith("repo"):
            args = cmd.split(maxsplit=3)
            if len(args) == 1:
                list_repo_options()
            elif len(args) >= 3 and args[1].lower() == "add":
                if len(args) >= 4:
                    add_repo(args[2], args[3])
                else:
                    print("Usage: repo add <name> <url>")
            elif len(args) >= 3 and args[1].lower() == "remove":
                remove_repo(args[2])
            else:
                select_repo(args[1].strip())

        elif cmd.startswith("addrepo "):
            parts = cmd.split(maxsplit=3)
            if len(parts) >= 4:
                add_repo(parts[1], parts[2] + " " + parts[3] if len(parts) == 4 and " " in parts[2] else parts[2])
            else:
                print("Usage: addrepo <name> <url>")

        elif cmd.startswith("removerepo "):
            parts = cmd.split(maxsplit=2)
            if len(parts) >= 2:
                remove_repo(parts[1])
            else:
                print("Usage: removerepo <name>")

        elif cmd == "lsp":
            list_online_packages()

        elif cmd == "lsds":
            ftpserver.handle_command("ls", ftp)

        elif cmd.startswith("get "):
            filename = cmd.split(" ", 1)[1].strip()
            get_file_from_dsi(filename, ftp)

        elif cmd.startswith("install "):
            package_name = cmd.split(" ", 1)[1].strip()
            if package_name:
                install_package(package_name, ftp)
            else:
                print("Usage: install <package>")

        elif cmd in {"exit", "quit"}:
            print("Goodbye.")
            break

        else:
            print(f"Unknown command: '{cmd}'")

    try:
        ftp.quit()
    except Exception:
        pass


def main():
    try:
        shell_loop()
    except KeyboardInterrupt:
        print("\nCancelled. Exiting gracefully.")


if __name__ == "__main__":
    main()
